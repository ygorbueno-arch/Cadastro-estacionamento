from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Configuração inicial do Banco de Dados
def init_db():
    conn = sqlite3.connect('estacionamento.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            modelo TEXT NOT NULL,
            cor TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect('estacionamento.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM veiculos")
    carros = cursor.fetchall()
    conn.close()
    return render_template('index.html', carros=carros)

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    placa = request.form.get('placa')
    modelo = request.form.get('modelo')
    cor = request.form.get('cor')

    if placa and modelo:
        conn = sqlite3.connect('estacionamento.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO veiculos (placa, modelo, cor) VALUES (?, ?, ?)", 
                       (placa, modelo, cor))
        conn.commit()
        conn.close()
    
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)