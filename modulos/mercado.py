"""Estoque da casa: compra mensal, reposições e o que cada um usa."""
from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos.auth import somente_admin
from modulos.mercado_itens import CATEGORIAS, LOCAIS, UNIDADES

mercado_bp = Blueprint('mercado', __name__, url_prefix='/mercado')

ABAS = {"estoque": "Estoque", "compra": "Compra mensal", "reposicao": "Reposição"}
TIPOS = {"compra": "Compra mensal", "reposicao": "Reposição", "uso": "Usou"}


def ler_qtd(texto):
    """'2,5' -> 2.5. Devolve None se não for um número positivo razoável."""
    try:
        valor = round(float(str(texto).strip().replace(",", ".")), 3)
    except ValueError:
        return None
    return valor if 0 < valor <= 10000 else None


def formatar_qtd(valor):
    if valor is None:
        return ""
    texto = f"{valor:.3f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def situacao(item):
    """acabou / acabando / ok, comparando o estoque com a quantidade do mês."""
    if item['estoque'] <= 0:
        return "acabou"
    if item['qtd_mensal'] and item['estoque'] < item['qtd_mensal'] * 0.25:
        return "acabando"
    return "ok"


def carregar_itens(conn):
    itens = []
    for linha in conn.execute('SELECT * FROM mercado_itens WHERE ativo = 1 ORDER BY id'):
        item = dict(linha)
        item['situacao'] = situacao(item)
        item['nivel'] = min(100, round(100 * item['estoque'] / item['qtd_mensal'])) if item['qtd_mensal'] else None
        itens.append(item)
    return itens


def por_local(itens):
    grupos = {local: [] for local in LOCAIS}
    for item in itens:
        grupos.setdefault(item['local'], []).append(item)
    return {local: lista for local, lista in grupos.items() if lista}


def entrar(conn, item_id, quantidade, tipo):
    if conn.execute('SELECT 1 FROM mercado_itens WHERE id = ? AND ativo = 1', (item_id,)).fetchone() is None:
        return False
    conn.execute('UPDATE mercado_itens SET estoque = estoque + ? WHERE id = ?', (quantidade, item_id))
    conn.execute('INSERT INTO mercado_movimentos (item_id, tipo, quantidade, morador_id) VALUES (?, ?, ?, ?)',
                 (item_id, tipo, quantidade, g.morador['id']))
    return True


@mercado_bp.route("/")
def index():
    aba = request.args.get("aba", "estoque")
    if aba not in ABAS:
        abort(404)
    conn = conectar_db()
    itens = carregar_itens(conn)
    historico = conn.execute(
        '''SELECT mv.id, mv.tipo, mv.quantidade, mv.criado_em, mv.morador_id,
                  i.nome, i.unidade, m.apelido
           FROM mercado_movimentos mv JOIN mercado_itens i ON i.id = mv.item_id
           LEFT JOIN moradores m ON m.id = mv.morador_id
           WHERE (? = 'estoque') OR (mv.tipo = ?)
           ORDER BY mv.id DESC LIMIT 12''', (aba, aba)).fetchall()
    conn.close()
    faltando = [i for i in itens if i['situacao'] != "ok" and i['categoria'] != "quando_precisar"]
    return render_template("mercado.html", aba=aba, abas=ABAS, itens=itens, grupos=por_local(itens),
                           faltando=faltando, historico=historico, tipos=TIPOS, categorias=CATEGORIAS,
                           locais=LOCAIS, unidades=UNIDADES, erro=request.args.get("erro", ""),
                           ok=request.args.get("ok", ""))


def voltar(aba, erro=None, ok=None):
    args = {"aba": aba}
    if erro:
        args["erro"] = erro
    if ok:
        args["ok"] = ok
    return redirect(url_for("mercado.index", **args))


@mercado_bp.route("/compra", methods=["POST"])
def compra_mensal():
    """Formulário com todos os itens; entra no estoque o que tiver quantidade."""
    conn = conectar_db()
    entradas = 0
    for chave, texto in request.form.items():
        if not chave.startswith("qtd_") or not texto.strip():
            continue
        quantidade = ler_qtd(texto)
        if quantidade is None:
            conn.close()
            return voltar("compra", erro=f"Quantidade inválida: {texto}")
        if entrar(conn, int(chave[4:]) if chave[4:].isdigit() else 0, quantidade, "compra"):
            entradas += 1
    if not entradas:
        conn.close()
        return voltar("compra", erro="Coloque a quantidade de pelo menos um item")
    conn.commit()
    conn.close()
    return voltar("estoque", ok=f"Compra mensal registrada: {entradas} {'item' if entradas == 1 else 'itens'}")


@mercado_bp.route("/reposicao", methods=["POST"])
def reposicao():
    """Um ou poucos itens: listas item_id[] e qtd[] na mesma ordem."""
    pares = [(i, q) for i, q in zip(request.form.getlist("item_id"), request.form.getlist("qtd")) if i and q.strip()]
    if not pares:
        return voltar("reposicao", erro="Escolha o item e a quantidade")
    conn = conectar_db()
    for item_id, texto in pares:
        quantidade = ler_qtd(texto)
        if quantidade is None or not item_id.isdigit():
            conn.close()
            return voltar("reposicao", erro=f"Quantidade inválida: {texto}")
        entrar(conn, int(item_id), quantidade, "reposicao")
    conn.commit()
    conn.close()
    return voltar("estoque", ok="Reposição registrada")


@mercado_bp.route("/usar", methods=["POST"])
def usar_escolhido():
    item_id = request.form.get("item_id", "")
    if not item_id.isdigit():
        return voltar("estoque", erro="Escolha o item")
    return usar(int(item_id))


@mercado_bp.route("/usar/<int:item_id>", methods=["POST"])
def usar(item_id):
    """Tira do estoque (padrão 1). Nunca deixa negativo."""
    quantidade = ler_qtd(request.form.get("qtd", "1") or "1")
    if quantidade is None:
        return voltar("estoque", erro="Quantidade inválida")
    conn = conectar_db()
    item = conn.execute('SELECT estoque FROM mercado_itens WHERE id = ? AND ativo = 1', (item_id,)).fetchone()
    if item is None:
        conn.close()
        abort(404)
    quantidade = min(quantidade, item['estoque'])
    if quantidade > 0:
        conn.execute('UPDATE mercado_itens SET estoque = estoque - ? WHERE id = ?', (quantidade, item_id))
        conn.execute('INSERT INTO mercado_movimentos (item_id, tipo, quantidade, morador_id) VALUES (?, ?, ?, ?)',
                     (item_id, "uso", quantidade, g.morador['id']))
        conn.commit()
    conn.close()
    return redirect(url_for("mercado.index", aba="estoque") + f"#item-{item_id}")


@mercado_bp.route("/movimento/<int:mov_id>/desfazer", methods=["POST"])
def desfazer(mov_id):
    """Quem lançou (ou um admin) desfaz e o estoque volta."""
    conn = conectar_db()
    mov = conn.execute('SELECT * FROM mercado_movimentos WHERE id = ?', (mov_id,)).fetchone()
    if mov is None:
        conn.close()
        abort(404)
    if not g.morador['admin'] and mov['morador_id'] != g.morador['id']:
        conn.close()
        abort(403)
    sinal = 1 if mov['tipo'] == "uso" else -1
    conn.execute('UPDATE mercado_itens SET estoque = MAX(0, estoque + ?) WHERE id = ?',
                 (sinal * mov['quantidade'], mov['item_id']))
    conn.execute('DELETE FROM mercado_movimentos WHERE id = ?', (mov_id,))
    conn.commit()
    conn.close()
    return voltar(request.form.get("aba", "estoque") if request.form.get("aba") in ABAS else "estoque")


@mercado_bp.route("/itens/novo", methods=["POST"])
@somente_admin
def novo_item():
    nome = request.form.get("nome", "").strip()
    local = request.form.get("local", "Mercado")
    categoria = request.form.get("categoria", "essencial")
    unidade = request.form.get("unidade", "un")
    texto_mensal = request.form.get("qtd_mensal", "").strip()
    mensal = ler_qtd(texto_mensal) if texto_mensal else None
    if not nome or len(nome) > 40:
        return voltar("compra", erro="Nome do item inválido")
    if local not in LOCAIS or categoria not in CATEGORIAS or unidade not in UNIDADES:
        abort(400)
    if texto_mensal and mensal is None:
        return voltar("compra", erro="Quantidade do mês inválida")
    conn = conectar_db()
    existente = conn.execute('SELECT id FROM mercado_itens WHERE nome = ?', (nome,)).fetchone()
    if existente:
        conn.execute('''UPDATE mercado_itens SET local = ?, categoria = ?, unidade = ?, qtd_mensal = ?, ativo = 1
                        WHERE id = ?''', (local, categoria, unidade, mensal, existente['id']))
    else:
        conn.execute('INSERT INTO mercado_itens (nome, local, categoria, unidade, qtd_mensal) VALUES (?, ?, ?, ?, ?)',
                     (nome, local, categoria, unidade, mensal))
    conn.commit()
    conn.close()
    return voltar("compra", ok=f"{nome} está na lista")


@mercado_bp.route("/itens/<int:item_id>/remover", methods=["POST"])
@somente_admin
def remover_item(item_id):
    conn = conectar_db()
    conn.execute('UPDATE mercado_itens SET ativo = 0 WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return voltar("compra")
