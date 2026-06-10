from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'chave_secreta_estacionamento_2024'

# ============== BANCO DE DADOS ==============
def get_db():
    conn = sqlite3.connect('estacionamento.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabela de Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT UNIQUE NOT NULL,
            telefone TEXT,
            email TEXT,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de Veículos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT UNIQUE NOT NULL,
            modelo TEXT NOT NULL,
            marca TEXT,
            cor TEXT,
            ano INTEGER,
            tipo TEXT DEFAULT 'carro',
            cliente_id INTEGER,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')
    
    # Tabela de Vagas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vagas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER UNIQUE NOT NULL,
            tipo TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'livre'
        )
    ''')
    
    # Tabela de Preços
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT UNIQUE,
            valor REAL NOT NULL
        )
    ''')
    
    # Tabela de Registro de Estacionamento
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            veiculo_id INTEGER NOT NULL,
            vaga_id INTEGER NOT NULL,
            data_entrada TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_saida TIMESTAMP,
            valor REAL,
            status TEXT DEFAULT 'ativo',
            FOREIGN KEY (veiculo_id) REFERENCES veiculos(id),
            FOREIGN KEY (vaga_id) REFERENCES vagas(id)
        )
    ''')
    
    # Inserir dados iniciais se necessário
    cursor.execute("SELECT COUNT(*) FROM vagas")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 11):
            tipo = 'preferencial' if i <= 3 else 'normal'
            cursor.execute("INSERT INTO vagas (numero, tipo) VALUES (?, ?)", (i, tipo))
    
    cursor.execute("SELECT COUNT(*) FROM precos")
    if cursor.fetchone()[0] == 0:
        precos = [('hora', 5.00), ('diaria', 30.00), ('mensal', 300.00)]
        cursor.executemany("INSERT INTO precos (tipo, valor) VALUES (?, ?)", precos)
    
    conn.commit()
    conn.close()

# ============== FUNÇÕES AUXILIARES ==============
def validar_placa(placa):
    """Valida formato de placa brasileira (antiga e Mercosul)"""
    placa = placa.upper().replace('-', '')
    padrao = re.compile(r'^[A-Z]{3}\d{4}$|^[A-Z]{3}\d[A-Z]\d{2}$')
    return bool(padrao.match(placa))

def formatar_placa(placa):
    """Formata a placa para o padrão AAA-1234 ou AAA1B23"""
    placa = placa.upper().replace('-', '')
    if len(placa) == 7 and placa[3].isdigit() and placa[4].isalpha():
        return f"{placa[:3]}-{placa[3:]}"
    elif len(placa) == 7:
        return f"{placa[:3]}-{placa[3:]}"
    return placa

def calcular_valor(entrada, saida):
    """Calcula o valor baseado no tempo estacionado"""
    conn = get_db()
    precos = {row['tipo']: row['valor'] for row in conn.execute("SELECT * FROM precos").fetchall()}
    conn.close()
    
    entrada = datetime.strptime(entrada, '%Y-%m-%d %H:%M:%S')
    saida = datetime.strptime(saida, '%Y-%m-%d %H:%M:%S')
    horas = (saida - entrada).total_seconds() / 3600
    
    if horas <= 1:
        return precos.get('hora', 5.00)
    elif horas <= 12:
        return min(horas * precos.get('hora', 5.00), precos.get('diaria', 30.00))
    else:
        return precos.get('diaria', 30.00)

# ============== ROTAS ==============
@app.route('/')
def index():
    conn = get_db()
    
    # Estatísticas
    stats = {
        'vagas_total': conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0],
        'vagas_livres': conn.execute("SELECT COUNT(*) FROM vagas WHERE status='livre'").fetchone()[0],
        'vagas_ocupadas': conn.execute("SELECT COUNT(*) FROM vagas WHERE status='ocupada'").fetchone()[0],
        'veiculos_ativos': conn.execute("SELECT COUNT(*) FROM registros WHERE status='ativo'").fetchone()[0],
        'receita_hoje': conn.execute("""
            SELECT COALESCE(SUM(valor), 0) FROM registros 
            WHERE status='finalizado' AND date(data_saida) = date('now')
        """).fetchone()[0]
    }
    
    # Veículos estacionados no momento
    estacionados = conn.execute("""
        SELECT r.*, v.placa, v.modelo, v.cor, va.numero as vaga_numero,
               (strftime('%s','now') - strftime('%s', r.data_entrada)) / 3600.0 as horas
        FROM registros r
        JOIN veiculos v ON r.veiculo_id = v.id
        JOIN vagas va ON r.vaga_id = va.id
        WHERE r.status = 'ativo'
        ORDER BY r.data_entrada DESC
    """).fetchall()
    
    conn.close()
    return render_template('index.html', stats=stats, estacionados=estacionados)

# ============== CLIENTES ==============
@app.route('/clientes')
def listar_clientes():
    conn = get_db()
    clientes = conn.execute("SELECT * FROM clientes ORDER BY nome").fetchall()
    conn.close()
    return render_template('clientes.html', clientes=clientes)

@app.route('/clientes/novo', methods=['POST'])
def cadastrar_cliente():
    nome = request.form.get('nome', '').strip()
    cpf = request.form.get('cpf', '').strip()
    telefone = request.form.get('telefone', '').strip()
    email = request.form.get('email', '').strip()
    
    if not nome or not cpf:
        flash('Nome e CPF são obrigatórios!', 'error')
        return redirect(url_for('listar_clientes'))
    
    # Remove caracteres não numéricos do CPF
    cpf = re.sub(r'\D', '', cpf)
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO clientes (nome, cpf, telefone, email) VALUES (?, ?, ?, ?)",
            (nome, cpf, telefone, email)
        )
        conn.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('CPF já cadastrado!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('listar_clientes'))

@app.route('/clientes/excluir/<int:id>')
def excluir_cliente(id):
    conn = get_db()
    conn.execute("DELETE FROM clientes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Cliente excluído!', 'success')
    return redirect(url_for('listar_clientes'))

# ============== VEÍCULOS ==============
@app.route('/veiculos')
def listar_veiculos():
    conn = get_db()
    veiculos = conn.execute("""
        SELECT v.*, c.nome as cliente_nome 
        FROM veiculos v 
        LEFT JOIN clientes c ON v.cliente_id = c.id 
        ORDER BY v.placa
    """).fetchall()
    clientes = conn.execute("SELECT id, nome FROM clientes ORDER BY nome").fetchall()
    conn.close()
    return render_template('veiculos.html', veiculos=veiculos, clientes=clientes)

@app.route('/veiculos/novo', methods=['POST'])
def cadastrar_veiculo():
    placa = formatar_placa(request.form.get('placa', ''))
    modelo = request.form.get('modelo', '').strip()
    marca = request.form.get('marca', '').strip()
    cor = request.form.get('cor', '').strip()
    ano = request.form.get('ano', '').strip()
    tipo = request.form.get('tipo', 'carro').strip()
    cliente_id = request.form.get('cliente_id', '').strip()
    
    if not placa or not modelo:
        flash('Placa e modelo são obrigatórios!', 'error')
        return redirect(url_for('listar_veiculos'))
    
    if not validar_placa(placa):
        flash('Placa inválida!', 'error')
        return redirect(url_for('listar_veiculos'))
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO veiculos (placa, modelo, marca, cor, ano, tipo, cliente_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (placa, modelo, marca, cor, int(ano) if ano else None, tipo, int(cliente_id) if cliente_id else None)
        )
        conn.commit()
        flash('Veículo cadastrado com sucesso!', 'success')
    except sqlite3.IntegrityError:
        flash('Placa já cadastrada!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('listar_veiculos'))

@app.route('/veiculos/excluir/<int:id>')
def excluir_veiculo(id):
    conn = get_db()
    conn.execute("DELETE FROM veiculos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Veículo excluído!', 'success')
    return redirect(url_for('listar_veiculos'))

# ============== ENTRADA E SAÍDA ==============
@app.route('/entrada', methods=['POST'])
def registrar_entrada():
    placa = formatar_placa(request.form.get('placa', ''))
    
    if not placa:
        flash('Placa é obrigatória!', 'error')
        return redirect(url_for('index'))
    
    conn = get_db()
    
    # Buscar veículo
    veiculo = conn.execute("SELECT * FROM veiculos WHERE placa = ?", (placa,)).fetchone()
    
    if not veiculo:
        conn.close()
        flash('Veículo não cadastrado! Cadastre primeiro.', 'error')
        return redirect(url_for('listar_veiculos'))
    
    # Verificar se já está estacionado
    ativo = conn.execute(
        "SELECT id FROM registros WHERE veiculo_id = ? AND status = 'ativo'", 
        (veiculo['id'],)
    ).fetchone()
    
    if ativo:
        conn.close()
        flash('Este veículo já está estacionado!', 'error')
        return redirect(url_for('index'))
    
    # Buscar vaga livre
    vaga = conn.execute("SELECT * FROM vagas WHERE status = 'livre' LIMIT 1").fetchone()
    
    if not vaga:
        conn.close()
        flash('Não há vagas disponíveis!', 'error')
        return redirect(url_for('index'))
    
    # Registrar entrada
    conn.execute(
        "INSERT INTO registros (veiculo_id, vaga_id) VALUES (?, ?)",
        (veiculo['id'], vaga['id'])
    )
    conn.execute("UPDATE vagas SET status = 'ocupada' WHERE id = ?", (vaga['id'],))
    conn.commit()
    conn.close()
    
    flash(f'Entrada registrada! Vaga {vaga["numero"]} - {vaga["tipo"]}', 'success')
    return redirect(url_for('index'))

@app.route('/saida/<int:registro_id>')
def registrar_saida(registro_id):
    conn = get_db()
    
    registro = conn.execute("SELECT * FROM registros WHERE id = ? AND status = 'ativo'", (registro_id,)).fetchone()
    
    if not registro:
        conn.close()
        flash('Registro não encontrado!', 'error')
        return redirect(url_for('index'))
    
    # Calcular valor
    data_saida = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    valor = calcular_valor(registro['data_entrada'], data_saida)
    
    # Finalizar registro
    conn.execute("""
        UPDATE registros 
        SET data_saida = ?, valor = ?, status = 'finalizado' 
        WHERE id = ?
    """, (data_saida, valor, registro_id))
    
    # Liberar vaga
    conn.execute("UPDATE vagas SET status = 'livre' WHERE id = ?", (registro['vaga_id'],))
    conn.commit()
    conn.close()
    
    flash(f'Saída registrada! Valor: R$ {valor:.2f}', 'success')
    return redirect(url_for('index'))

# ============== VAGAS ==============
@app.route('/vagas')
def gerenciar_vagas():
    conn = get_db()
    vagas = conn.execute("SELECT * FROM vagas ORDER BY numero").fetchall()
    conn.close()
    return render_template('vagas.html', vagas=vagas)

@app.route('/vagas/adicionar', methods=['POST'])
def adicionar_vaga():
    numero = request.form.get('numero', '').strip()
    tipo = request.form.get('tipo', 'normal').strip()
    
    if not numero:
        flash('Número da vaga é obrigatório!', 'error')
        return redirect(url_for('gerenciar_vagas'))
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO vagas (numero, tipo) VALUES (?, ?)",
            (int(numero), tipo)
        )
        conn.commit()
        flash('Vaga adicionada!', 'success')
    except sqlite3.IntegrityError:
        flash('Número de vaga já existe!', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('gerenciar_vagas'))

@app.route('/vagas/status/<int:id>/<string:status>')
def alterar_status_vaga(id, status):
    conn = get_db()
    conn.execute("UPDATE vagas SET status = ? WHERE id = ?", (status, id))
    conn.commit()
    conn.close()
    flash(f'Status da vaga alterado!', 'success')
    return redirect(url_for('gerenciar_vagas'))

# ============== RELATÓRIOS ==============
@app.route('/relatorios')
def relatorios():
    conn = get_db()
    
    # Receita total
    receita = conn.execute("""
        SELECT COALESCE(SUM(valor), 0) as total FROM registros WHERE status = 'finalizado'
    """).fetchone()[0]
    
    # Total de registros
    total_registros = conn.execute("SELECT COUNT(*) as total FROM registros").fetchone()[0]
    
    # Veículos mais frequentes
    frequentes = conn.execute("""
        SELECT v.placa, v.modelo, COUNT(*) as total
        FROM registros r
        JOIN veiculos v ON r.veiculo_id = v.id
        GROUP BY v.id
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()
    
    # Registros de hoje
    hoje = conn.execute("""
        SELECT r.*, v.placa, v.modelo
        FROM registros r
        JOIN veiculos v ON r.veiculo_id = v.id
        WHERE date(r.data_entrada) = date('now') OR date(r.data_saida) = date('now')
        ORDER BY r.data_entrada DESC
    """).fetchall()
    
    conn.close()
    
    return render_template('relatorios.html', 
                         receita=receita, 
                         total_registros=total_registros,
                         frequentes=frequentes,
                         hoje=hoje)

# ============== INICIALIZAÇÃO ==============
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)