from flask import Blueprint, request, redirect, url_for
from database import conectar_db
from estilo import renderizar_pagina

mercado_bp = Blueprint('mercado', __name__, url_prefix='/mercado')

# --- NOSSA BASE DE DADOS COM UNIDADES DE MEDIDA ---
ITENS_PLANILHA = {
    "Alho": "kg", "Cebola": "kg", "Café": "kg", "Farofa": "g", "Pipoca": "g",
    "Margarina": "kg", "Arroz": "kg", "Feijão": "kg", "Macarrão": "kg", "Açúcar": "kg",
    "Mistura da Dona": "un", "Oléo": "L", "Vinagre": "ml", "Sal": "kg",
    "Amaciante": "L", "Água sanitária": "L", "Limpador multiuso": "L",
    "Sabão em Pó": "kg", "Desinfetante": "L", "Bombril": "g", "Esponja": "un",
    "Detergente": "L", "Papel Higiênico": "rolos", "Papel toalha": "rolos",
    "Saco de lixo 100L": "pcts", "Sabão em pedra": "un", "Filtro de papel": "un",
    "Páprica defumada": "pct", "Lemon Pepper": "pct", "Pimenta do Reino": "pct",
    "Curry": "pct", "Cominho": "pct", "Chimichurri": "pct", "Orégano": "pct",
    "Alho e Cebola": "pct", "Folha de Loro": "pct", "Ana Maria": "pct", "Tempera Tudo": "pct"
}

@mercado_bp.route("/")
def index():
    conn = conectar_db()
    # Puxa o estoque atual do banco de dados (ignorando os itens zerados)
    itens = conn.execute('SELECT * FROM mercado WHERE quantidade > 0').fetchall()
    conn.close()
    
    # 1. Monta o HTML da lista de Estoque Atual
    html_itens = ""
    for row in itens:
        html_itens += f"""
        <li style="margin-bottom: 15px; list-style-type: none; background-color: #1A1A1A; padding: 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #ff6600;">
            <span style="font-size: 18px;"><strong>{row['item']}</strong> (Qtd: {row['quantidade']})</span>
            <form action="/mercado/diminuir/{row['id']}" method="POST" style="margin: 0;">
                <button type="submit" class="btn-vermelho" style="padding: 10px 15px; margin: 0; font-weight: bold; border-radius: 5px; background-color: #b71c1c; color: white; border: none; cursor: pointer;">📉 Usar 1</button>
            </form>
        </li>
        """
        
    if not html_itens:
        html_itens = "<p style='text-align: center; color: #888; font-size: 18px;'>O estoque está vazio! Faça as compras.</p>"

    # 2. Monta as opções do Menu Dropdown
    opcoes_dropdown = ""
    for item, unidade in sorted(ITENS_PLANILHA.items()):
        opcoes_dropdown += f'<option value="{item} ({unidade})">{item} - {unidade}</option>'

    # 3. Junta tudo em um Painel de Controle unificado e elegante
    conteudo = f"""
    <h2>🛒 Controle do Mercado</h2>
    
    <!-- CAIXA 1: DAR ENTRADA (O formulário gigante) -->
    <div style="background-color: #111; padding: 25px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #333; box-shadow: 0px 4px 10px rgba(0,0,0,0.5);">
        <h3 style="color: #ff6600; text-align: center; margin-top: 0; margin-bottom: 20px;">➕ Dar Entrada</h3>
        
        <form action="/mercado/adicionar" method="POST" style="display: flex; gap: 15px; align-items: center; justify-content: center; flex-wrap: wrap;">
            <select name="item" required style="flex: 2; min-width: 220px; padding: 15px; border-radius: 8px; background-color: #222; color: white; border: 1px solid #444; font-size: 18px;">
                <option value="" disabled selected>Selecione um item da planilha...</option>
                {opcoes_dropdown}
            </select>
            
            <input type="number" name="quantidade" placeholder="Qtd" value="1" min="1" required style="flex: 0.5; min-width: 90px; padding: 15px; border-radius: 8px; background-color: #222; color: white; border: 2px solid #ff6600; text-align: center; font-size: 22px; font-weight: bold;">
            
            <button type="submit" class="btn-laranja" style="flex: 1; min-width: 140px; padding: 15px; font-size: 18px; margin-top: 0; font-weight: bold;">Adicionar</button>
        </form>
    </div>

    <!-- CAIXA 2: O ESTOQUE ATUAL -->
    <div style="background-color: #111; padding: 25px; border-radius: 12px; border: 1px solid #333; box-shadow: 0px 4px 10px rgba(0,0,0,0.5);">
        <h3 style="color: #ff6600; text-align: center; margin-top: 0; margin-bottom: 20px;">📦 Estoque da República</h3>
        <ul style="padding: 0; text-align: left; margin: 0;">
            {html_itens}
        </ul>
    </div>
    
    <br><br>
    <a href='/' class="botao-menu" style="display: block; width: 50%; margin: 0 auto; text-align: center;">🏠 Voltar para o Menu Principal</a>
    """
    
    return renderizar_pagina("Mercado - Arapuca", conteudo)

@mercado_bp.route("/adicionar", methods=["POST"])
def adicionar():
    nome_item = request.form['item']
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
    
    # Redireciona de volta para a tela principal (que agora tem tudo junto)
    return redirect(url_for('mercado.index'))

@mercado_bp.route("/diminuir/<int:id>", methods=["POST"])
def diminuir_mercado(id):
    conn = conectar_db()
    item = conn.execute('SELECT quantidade FROM mercado WHERE id = ?', (id,)).fetchone()
    if item and item['quantidade'] > 0:
        nova_qtd = item['quantidade'] - 1
        conn.execute('UPDATE mercado SET quantidade = ? WHERE id = ?', (nova_qtd, id))
        conn.commit()
    conn.close()
    
    # Redireciona de volta para a tela principal
    return redirect(url_for('mercado.index'))