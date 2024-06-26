from flask import Flask, request, render_template, flash, redirect, url_for, jsonify, send_file
import psycopg2
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="projeto_govbr",
            user="postgres",
            password="123456",
            host="192.168.100.10",
            #host="45.5.142.73",
            port="5432"
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

### CADASTRO
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        telefone = request.form['telefone']
        endereco = request.form['endereco']
        idade = request.form['idade']

        conn = get_db_connection()
        if conn is None:
            flash("Erro ao conectar ao banco de dados.")
            return redirect(url_for('cadastro'))

        try:
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM beneficiarios WHERE email = %s", (email,))
            email_existe = cur.fetchone()[0]
            
            if email_existe:
                flash("Erro: Já existe um registro com este email.")
            else:
                cur.execute("INSERT INTO beneficiarios (nome, email, telefone, endereco, idade) VALUES (%s, %s, %s, %s, %s)",
                            (nome, email, telefone, endereco, idade))
                conn.commit()
                flash("Registro inserido com sucesso.")
            
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            print(f"Error performing database operation: {e}")
            flash("Erro ao realizar operação no banco de dados.")
            if conn:
                conn.close()
        
        return redirect(url_for('cadastro'))
    
    return render_template('cadastro.html')

### CONSULTA
@app.route('/consulta')
def consultar_beneficiarios():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Error connecting to the database.'}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM beneficiarios")
        beneficiarios = cur.fetchall()
        cur.close()
        conn.close()

        beneficiarios_json = [{'id':beneficiario [0],'nome': beneficiario[1], 'email': beneficiario[2], 'telefone': beneficiario[3], 'endereco': beneficiario[4], 'idade': beneficiario[5]} for beneficiario in beneficiarios]

        return jsonify(beneficiarios_json)
    except psycopg2.Error as e:
        print(f"Error querying the database: {e}")
        return jsonify({'message': 'Error querying the database.'}), 500
    

### EXCLUIR
@app.route('/excluir', methods=['POST'])
def excluir_beneficiarios():
    ids_to_delete = request.json.get('ids', [])

    if not ids_to_delete:
        return jsonify({'message': 'Nenhum beneficiário selecionado para exclusão.'}), 400
    
    print(f"IDs para deletar: {ids_to_delete}")  # Log 

    try:
        ids_to_delete = [int(id) for id in ids_to_delete]
    except ValueError:
        return jsonify({'message': 'IDs inválidos fornecidos.'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Erro ao conectar ao banco de dados.'}), 500

    try:
        with conn:
            with conn.cursor() as cur:
                # Criação dos placeholders
                placeholders = ', '.join(['%s'] * len(ids_to_delete))
                query = f"DELETE FROM beneficiarios WHERE id IN ({placeholders})"
                
                print(f"Query: {query}")  # Log 
                
                cur.execute(query, ids_to_delete)
        
    except psycopg2.Error as e:
        print(f"Error performing delete operation: {e}")
        return jsonify({'message': 'Erro ao realizar operação de exclusão no banco de dados.'}), 500
    finally:
        conn.close()

    return jsonify({'message': 'Beneficiário(s) excluído(s) com sucesso.'})
  
### GERAR PDF
@app.route('/gerar_pdf', methods=['POST'])
def gerar_pdf():
    ids_to_print = request.json.get('ids', [])

    if not ids_to_print:
        return jsonify({'message': 'Nenhum beneficiário selecionado para impressão.'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Error connecting to the database.'}), 500

    try:
        with conn.cursor() as cur:
            placeholders = ', '.join(['%s'] * len(ids_to_print))
            query = f"SELECT * FROM beneficiarios WHERE id IN ({placeholders})"
            cur.execute(query, ids_to_print)
            beneficiarios = cur.fetchall()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Adiciona a logo
        logo_path = "templates/logo_caixa.png"  # Caminho para a logo
        im = Image(logo_path, 4*inch, 1*inch)  # Tamanho
        elements.append(im)

        # Adiciona o título
        styles = getSampleStyleSheet()
        title = Paragraph("Lista de Beneficiários", styles['Title'])
        elements.append(title)

        elements.append(Spacer(1, 12))  # Espaço após o título

        # Adiciona a tabela
        data = [['Nome', 'Email', 'Telefone', 'Endereço', 'Idade']]
        for beneficiario in beneficiarios:
            data.append([beneficiario[1], beneficiario[2], beneficiario[3], beneficiario[4], beneficiario[5]])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="beneficiarios.pdf", mimetype='application/pdf')

    except psycopg2.Error as e:
        print(f"Error querying the database: {e}")
        return jsonify({'message': 'Error querying the database.'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=62605)