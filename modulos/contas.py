import re
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos.auth import somente_admin

contas_bp = Blueprint('contas', __name__, url_prefix='/contas')

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


# ---------- regras de dinheiro (sem Flask, fáceis de testar) ----------

def dividir(total_centavos, pesos):
    """Divide o total proporcional aos pesos, em centavos, sem perder nenhum centavo.

    pesos: {morador_id: peso}. Os centavos que sobram do arredondamento vão
    para quem teve a maior fração cortada (método do maior resto).
    """
    soma = sum(pesos.values())
    if total_centavos <= 0 or soma <= 0:
        return {m: 0 for m in pesos}

    exatos = {m: total_centavos * p / soma for m, p in pesos.items()}
    partes = {m: int(v) for m, v in exatos.items()}
    sobra = total_centavos - sum(partes.values())
    for m in sorted(exatos, key=lambda m: exatos[m] - partes[m], reverse=True)[:sobra]:
        partes[m] += 1
    return partes


def ler_valor(texto):
    """Converte '1.234,56', '1234,56', '1234.56' ou 'R$ 80' em centavos. Devolve None se não der."""
    t = texto.strip().replace("R$", "").replace(" ", "")
    if re.fullmatch(r"\d+\.\d{1,2}", t):
        reais, cent = t.split(".")                      # 1234.56 (ponto decimal)
    elif re.fullmatch(r"(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?", t):
        reais, _, cent = t.replace(".", "").partition(",")  # 1.234,56 / 1234,5 / 1.234 / 80
    else:
        return None
    return int(reais) * 100 + int(cent.ljust(2, "0"))


def formatar(centavos):
    reais, cent = divmod(abs(centavos), 100)
    texto = f"{reais:,}".replace(",", ".") + f",{cent:02d}"
    return ("-R$ " if centavos < 0 else "R$ ") + texto


def mes_valido(mes):
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes or ""))


def deslocar_mes(mes, passo):
    ano, m = map(int, mes.split("-"))
    total = ano * 12 + (m - 1) + passo
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def nome_mes(mes):
    ano, m = mes.split("-")
    return f"{MESES[int(m) - 1].capitalize()} {ano}"


@contas_bp.app_template_filter("reais")
def filtro_reais(centavos):
    return formatar(centavos)


# ---------- páginas ----------

def mes_da_url():
    mes = request.values.get("mes") or date.today().strftime("%Y-%m")
    if not mes_valido(mes):
        abort(400)
    return mes


@contas_bp.route("/")
def index():
    mes = mes_da_url()
    conn = conectar_db()
    contas = conn.execute(
        'SELECT id, descricao, valor_centavos FROM contas WHERE mes = ? ORDER BY id', (mes,)
    ).fetchall()
    total = sum(c['valor_centavos'] for c in contas)

    fechado = conn.execute(
        '''SELECT r.morador_id, m.apelido, r.peso, r.valor_centavos, r.pago
           FROM rateio r JOIN moradores m ON m.id = r.morador_id
           WHERE r.mes = ? ORDER BY m.apelido''', (mes,)
    ).fetchall()

    if fechado:
        divisao = [dict(r) for r in fechado]
    else:
        # Prévia: divide entre quem está ativo hoje, com o peso atual
        ativos = conn.execute(
            'SELECT id, apelido, peso FROM moradores WHERE ativo = 1 ORDER BY apelido'
        ).fetchall()
        partes = dividir(total, {m['id']: m['peso'] for m in ativos})
        divisao = [{'morador_id': m['id'], 'apelido': m['apelido'], 'peso': m['peso'],
                    'valor_centavos': partes[m['id']], 'pago': 0} for m in ativos]
    conn.close()

    minha_parte = next((d for d in divisao if d['morador_id'] == g.morador['id']), None)

    return render_template(
        "contas.html",
        mes=mes,
        nome_mes=nome_mes(mes),
        anterior=deslocar_mes(mes, -1),
        proximo=deslocar_mes(mes, 1),
        contas=contas,
        total=total,
        divisao=divisao,
        fechado=bool(fechado),
        minha_parte=minha_parte,
        erro=request.args.get("erro", ""),
    )


def mes_esta_fechado(conn, mes):
    return conn.execute('SELECT 1 FROM rateio WHERE mes = ? LIMIT 1', (mes,)).fetchone() is not None


@contas_bp.route("/nova", methods=["POST"])
@somente_admin
def nova():
    mes = mes_da_url()
    descricao = request.form.get("descricao", "").strip()
    valor = ler_valor(request.form.get("valor", ""))

    if not descricao or len(descricao) > 60:
        return redirect(url_for("contas.index", mes=mes, erro="Coloque uma descrição (até 60 letras)"))
    if not valor:
        return redirect(url_for("contas.index", mes=mes, erro="Valor inválido. Use por exemplo 1.234,56"))

    conn = conectar_db()
    if mes_esta_fechado(conn, mes):
        conn.close()
        return redirect(url_for("contas.index", mes=mes, erro="Esse mês já foi fechado. Reabra para mudar."))
    conn.execute('INSERT INTO contas (mes, descricao, valor_centavos, criado_por) VALUES (?, ?, ?, ?)',
                 (mes, descricao, valor, g.morador['id']))
    conn.commit()
    conn.close()
    return redirect(url_for("contas.index", mes=mes))


@contas_bp.route("/<int:conta_id>/apagar", methods=["POST"])
@somente_admin
def apagar(conta_id):
    mes = mes_da_url()
    conn = conectar_db()
    if mes_esta_fechado(conn, mes):
        conn.close()
        return redirect(url_for("contas.index", mes=mes, erro="Esse mês já foi fechado. Reabra para mudar."))
    conn.execute('DELETE FROM contas WHERE id = ? AND mes = ?', (conta_id, mes))
    conn.commit()
    conn.close()
    return redirect(url_for("contas.index", mes=mes))


@contas_bp.route("/fechar", methods=["POST"])
@somente_admin
def fechar():
    """Congela a divisão do mês com os moradores ativos e pesos de agora."""
    mes = mes_da_url()
    conn = conectar_db()
    if not mes_esta_fechado(conn, mes):
        total = conn.execute('SELECT COALESCE(SUM(valor_centavos), 0) FROM contas WHERE mes = ?', (mes,)).fetchone()[0]
        ativos = conn.execute('SELECT id, peso FROM moradores WHERE ativo = 1').fetchall()
        if total == 0 or not ativos:
            conn.close()
            return redirect(url_for("contas.index", mes=mes, erro="Lance as contas antes de fechar o mês"))
        pesos = {m['id']: m['peso'] for m in ativos}
        partes = dividir(total, pesos)
        conn.executemany('INSERT INTO rateio (mes, morador_id, peso, valor_centavos) VALUES (?, ?, ?, ?)',
                         [(mes, m, pesos[m], partes[m]) for m in pesos])
        conn.commit()
    conn.close()
    return redirect(url_for("contas.index", mes=mes))


@contas_bp.route("/reabrir", methods=["POST"])
@somente_admin
def reabrir():
    mes = mes_da_url()
    conn = conectar_db()
    conn.execute('DELETE FROM rateio WHERE mes = ?', (mes,))
    conn.commit()
    conn.close()
    return redirect(url_for("contas.index", mes=mes))


@contas_bp.route("/pago/<int:morador_id>", methods=["POST"])
@somente_admin
def marcar_pago(morador_id):
    mes = mes_da_url()
    conn = conectar_db()
    conn.execute('UPDATE rateio SET pago = 1 - pago WHERE mes = ? AND morador_id = ?', (mes, morador_id))
    conn.commit()
    conn.close()
    return redirect(url_for("contas.index", mes=mes))
