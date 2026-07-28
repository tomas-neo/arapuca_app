from flask import Blueprint, request, redirect, url_for
from database import conectar_db
from estilo import renderizar_pagina # <--- Importamos a pintura aqui!

mercado_bp = Blueprint('mercado', __name__, url_prefix='/mercado')

@mercado_bp.route("/")
def index():
    conn = conectar_db()
    itens = conn.execute('SELECT * FROM mercado').fetchall()
    conn.close()
    
    html_itens = ""
    for row in itens:
        html_itens += f"""
        <li style="margin-bottom: 15px; list-style-type: none; background-color: #1A1A1A; padding: 10px; border-radius: 8px;">
            <strong>{row['item']}</strong> (Qtd: {row['quantidade']}) 
            <form action="/mercado/diminuir/{row['id']}" method="POST" style="display:inline; float: right;">
                <button type="submit" class="btn-vermelho" style="width: auto; padding: 5px 10px; margin-top: 0;">📉 Usar</button>
            </form>
        </li>
        """
        
    conteudo = f"""
    <h2>🛒 Mercado da Arapuca</h2>
    <ul style="padding: 0; text-align: left; width: 90%; margin: 0 auto;">{html_itens}</ul>
    <hr>
    <h3>Adicionar item comprado:</h3>
    <form action="/mercado/adicionar" method="POST">
        <input type="text" name="item" placeholder="Nome do item" required>
        <input type="number" name="quantidade" placeholder="Qtd" value="1" required style="margin-top: 10px;">
        <button type="submit" class="btn-laranja">➕ Adicionar ao Estoque</button>
    </form>
    <br>
    <a href='/' class="botao-menu">Voltar para o início</a>
    """
    
    # Passamos o conteúdo para o envelope mágico
    return renderizar_pagina("Mercado - Arapuca", conteudo)

@mercado_bp.route("/diminuir/<int:id>", methods=["POST"])
def diminuir_mercado(id):
    conn = conectar_db()
    item = conn.execute('SELECT quantidade FROM mercado WHERE id = ?', (id,)).fetchone()
    if item and item['quantidade'] > 0:
        nova_qtd = item['quantidade'] - 1
        conn.execute('UPDATE mercado SET quantidade = ? WHERE id = ?', (nova_qtd, id))
        conn.commit()
    conn.close()
    return redirect(url_for('mercado.index'))

@mercado_bp.route("/adicionar", methods=["POST"])
def adicionar():
    nome_item = request.form['item'].strip().title()
    qtd_item = int(request.form['quantidade'])
    
    conn = conectar_db()
    item_existente = conn.execute('SELECT id, quantidade FROM mercado WHERE item = ?', (nome_item,)).fetchone()
    
    if item_existente:
        nova_qtd = item_existente['quantidade'] + qtd_item
        conn.execute('UPDATE mercado SET quantidade = ? WHERE id = ?', (nova_qtd, item_existente['id']))
    else:
        conn.execute('INSERT INTO mercado (item, quantidade) VALUES (?, ?)', (nome_item, qtd_item))
        
    conn.commit()
    conn.close()
    return redirect(url_for('mercado.index'))
