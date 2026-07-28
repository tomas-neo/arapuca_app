from flask import Blueprint, request, redirect, url_for
from database import conectar_db

# Aqui criamos a planta baixa do módulo. 
# Tudo o que for rota de mercado vai começar com '/mercado' automaticamente.
mercado_bp = Blueprint('mercado', __name__, url_prefix='/mercado')

@mercado_bp.route("/")
def index():
    conn = conectar_db()
    itens = conn.execute('SELECT * FROM mercado').fetchall()
    conn.close()
    
    html_itens = ""
    for row in itens:
        html_itens += f"""
        <li>
            <strong>{row['item']}</strong> - Quantidade: {row['quantidade']} 
            <form action="/mercado/diminuir/{row['id']}" method="POST" style="display:inline;">
                <button type="submit">📉 Usar (1)</button>
            </form>
        </li><br>
        """
        
    return f"""
    <h2>🛒 Mercado da Arapuca (Dispensa)</h2>
    <ul>{html_itens}</ul>
    <hr>
    <h3>Adicionar item comprado:</h3>
    <form action="/mercado/adicionar" method="POST">
        <input type="text" name="item" placeholder="Nome do item" required>
        <input type="number" name="quantidade" placeholder="Qtd" value="1" required>
        <button type="submit">➕ Adicionar ao Estoque</button>
    </form>
    <br><a href='/'>Voltar para o início</a>
    """

@mercado_bp.route("/diminuir/<int:id>", methods=["POST"])
def diminuir_mercado(id):
    conn = conectar_db()
    item = conn.execute('SELECT quantidade FROM mercado WHERE id = ?', (id,)).fetchone()
    if item and item['quantidade'] > 0:
        nova_qtd = item['quantidade'] - 1
        conn.execute('UPDATE mercado SET quantidade = ? WHERE id = ?', (nova_qtd, id))
        conn.commit()
    conn.close()
    
    # O url_for agora chama a função 'index' de dentro do Blueprint 'mercado'
    return redirect(url_for('mercado.index'))

@mercado_bp.route("/adicionar", methods=["POST"])
def adicionar():
    nome_item = request.form['item']
    qtd_item = int(request.form['quantidade'])
    
    conn = conectar_db()
    conn.execute('INSERT INTO mercado (item, quantidade) VALUES (?, ?)', (nome_item, qtd_item))
    conn.commit()
    conn.close()
    return redirect(url_for('mercado.index'))
