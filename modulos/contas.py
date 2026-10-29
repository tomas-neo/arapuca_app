from decimal import Decimal, ROUND_HALF_UP
import re
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos import financeiro
from modulos.auth import exigir_cargo

contas_bp = Blueprint('contas', __name__, url_prefix='/contas')

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
TIPOS_AJUSTE = {"outros": "Outros", "pendencia": "Pendência", "desconto": "Desconto"}


# ---------- regras de dinheiro (sem Flask, fáceis de testar) ----------

def arredondar(centavos):
    """Arredonda centavos fracionados como a planilha (meio centavo sobe)."""
    return int(Decimal(str(round(centavos, 6))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calcular_mes(aluguel, despesas, quartos, caixinha, fracao_comum=0.5, ajustes=None):
    """Divide o mês igual à planilha Financeiro Arapuca.

    - aluguel × fracao_comum: área comum, igual para todas as vagas
    - aluguel × (1 − fracao_comum): quartos, pela ponderação, dividido pelas vagas do quarto
    - despesas: igual para todas as vagas
    - caixinha: valor fixo por vaga
    - ajustes: {morador_id: centavos} (outros + pendências − desconto)

    quartos: [{'nome', 'ponderacao', 'vagas', 'moradores': [{'id', 'apelido'}]}]
    Devolve (linhas, avisos). Cada linha é uma vaga; vaga sem morador tem morador_id None.
    """
    ajustes = ajustes or {}
    avisos = []
    vagas = []
    for q in quartos:
        n = max(q['vagas'], len(q['moradores']))
        if len(q['moradores']) > q['vagas']:
            avisos.append(f"{q['nome']} tem {len(q['moradores'])} moradores para {q['vagas']} vagas")
        for i in range(n):
            vagas.append((q, q['moradores'][i] if i < len(q['moradores']) else None, n))
    if not vagas:
        return [], ["Cadastre os quartos para dividir as contas"]

    total_vagas = len(vagas)
    soma_pond = sum(q['ponderacao'] for q in quartos)
    if abs(soma_pond - 1) > 0.0005:
        avisos.append(f"As ponderações dos quartos somam {soma_pond:.3f} em vez de 1. O app ajusta na proporção.")

    comum = aluguel * fracao_comum / total_vagas
    por_vaga_desp = despesas / total_vagas
    casa_exata, total_exato = [], []
    for q, _, n in vagas:
        if soma_pond > 0:
            parte_quarto = aluguel * (1 - fracao_comum) * (q['ponderacao'] / soma_pond) / n
        else:
            parte_quarto = aluguel * (1 - fracao_comum) / total_vagas
        casa_exata.append(comum + parte_quarto)
        total_exato.append(comum + parte_quarto + por_vaga_desp)

    # cada vaga arredondada sozinha, igual à planilha (a soma pode variar 1 ou 2 centavos)
    casa = [arredondar(v) for v in casa_exata]
    casa_mais_desp = [arredondar(v) for v in total_exato]

    linhas = []
    for i, (q, morador, _) in enumerate(vagas):
        ajuste = ajustes.get(morador['id'], 0) if morador else 0
        linhas.append({
            'vaga': i + 1,
            'quarto': q['nome'],
            'morador_id': morador['id'] if morador else None,
            'apelido': morador['apelido'] if morador else None,
            'casa_centavos': casa[i],
            'despesas_centavos': casa_mais_desp[i] - casa[i],
            'caixinha_centavos': caixinha,
            'ajustes_centavos': ajuste,
            'total_centavos': casa_mais_desp[i] + caixinha + ajuste,
            'pago_centavos': 0,
        })
    sem_quarto = [m for m in ajustes if not any(l['morador_id'] == m for l in linhas)]
    if sem_quarto:
        avisos.append("Há ajustes de moradores sem quarto; eles não entram na divisão")
    return linhas, avisos


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


def ler_config(conn):
    cfg = {r['chave']: r['valor'] for r in conn.execute('SELECT chave, valor FROM config')}
    return int(cfg.get('caixinha_centavos', 5000)), float(cfg.get('fracao_area_comum', 0.5))


def carregar_quartos(conn):
    quartos = [dict(q) for q in conn.execute('SELECT id, nome, ponderacao, vagas FROM quartos ORDER BY id')]
    for q in quartos:
        q['moradores'] = [dict(m) for m in conn.execute(
            'SELECT id, apelido FROM moradores WHERE ativo = 1 AND quarto_id = ? ORDER BY apelido', (q['id'],))]
    return quartos


def ajustes_do_mes(conn, mes):
    lista = conn.execute(
        '''SELECT a.id, a.morador_id, m.apelido, a.tipo, a.descricao, a.valor_centavos
           FROM ajustes a JOIN moradores m ON m.id = a.morador_id
           WHERE a.mes = ? ORDER BY m.apelido, a.id''', (mes,)).fetchall()
    soma = {}
    for a in lista:
        sinal = -1 if a['tipo'] == 'desconto' else 1
        soma[a['morador_id']] = soma.get(a['morador_id'], 0) + sinal * a['valor_centavos']
    return lista, soma


def mes_esta_fechado(conn, mes):
    return conn.execute('SELECT 1 FROM fechamentos WHERE mes = ? LIMIT 1', (mes,)).fetchone() is not None


def divisao_do_mes(conn, mes):
    """Divisão congelada se o mês foi fechado; senão, prévia com os dados de hoje."""
    fechado = conn.execute(
        '''SELECT f.*, m.apelido FROM fechamentos f LEFT JOIN moradores m ON m.id = f.morador_id
           WHERE f.mes = ? ORDER BY f.vaga''', (mes,)).fetchall()
    if fechado:
        return [dict(l) for l in fechado], [], True

    contas = conn.execute('SELECT tipo, valor_centavos FROM contas WHERE mes = ?', (mes,)).fetchall()
    aluguel = sum(c['valor_centavos'] for c in contas if c['tipo'] == 'aluguel')
    despesas = sum(c['valor_centavos'] for c in contas if c['tipo'] != 'aluguel')
    caixinha, fracao = ler_config(conn)
    _, ajustes = ajustes_do_mes(conn, mes)
    linhas, avisos = calcular_mes(aluguel, despesas, carregar_quartos(conn), caixinha, fracao, ajustes)
    sem_quarto = conn.execute('SELECT apelido FROM moradores WHERE ativo = 1 AND quarto_id IS NULL').fetchall()
    if sem_quarto:
        avisos.append("Sem quarto (fora da divisão): " + ", ".join(m['apelido'] for m in sem_quarto))
    return linhas, avisos, False


def saldo_acumulado(conn, morador_id):
    return conn.execute(
        'SELECT COALESCE(SUM(pago_centavos - total_centavos), 0) FROM fechamentos WHERE morador_id = ?',
        (morador_id,)).fetchone()[0]


def pagina_planilha(conn):
    """Contas vindas da planilha do financeiro: o app só mostra o que está lá."""
    financeiro.sincronizar_se_preciso()
    dados = financeiro.carregar(conn)
    meses = sorted(dados.get("meses", {}))
    mes = request.values.get("mes") or date.today().strftime("%Y-%m")
    if not mes_valido(mes):
        abort(400)
    if meses and mes not in meses and not request.values.get("mes"):
        mes = max([m for m in meses if m <= mes] or meses)  # mês atual ainda sem aba: o último que tem
    info = financeiro.montar_mes(conn, dados, mes, g.morador['id'])
    sync = financeiro.status(conn)
    conn.close()
    anterior = max([m for m in meses if m < mes], default=None)
    proximo = min([m for m in meses if m > mes], default=None)
    return render_template("contas_planilha.html", mes=mes, nome_mes=nome_mes(mes), info=info, sync=sync,
                           anterior=anterior, proximo=proximo, erro=request.args.get("erro", ""),
                           ok=request.args.get("ok", ""))


@contas_bp.route("/")
def index():
    conn = conectar_db()
    if financeiro.arquivo_configurado(conn):
        return pagina_planilha(conn)
    mes = mes_da_url()
    contas = conn.execute(
        'SELECT id, descricao, tipo, valor_centavos FROM contas WHERE mes = ? ORDER BY tipo, id', (mes,)
    ).fetchall()
    linhas, avisos, fechado = divisao_do_mes(conn, mes)
    lista_ajustes, _ = ajustes_do_mes(conn, mes)
    moradores = conn.execute('SELECT id, apelido FROM moradores WHERE ativo = 1 ORDER BY apelido').fetchall()
    meu_saldo = saldo_acumulado(conn, g.morador['id'])
    fotos = {m['id']: m['foto_versao'] for m in conn.execute('SELECT id, foto_versao FROM moradores')}
    saldo_anterior = conn.execute('SELECT COALESCE(saldo_anterior_centavos, 0) FROM moradores WHERE id = ?',
                                  (g.morador['id'],)).fetchone()[0]
    sync = financeiro.status(conn)
    conn.close()

    minha_parte = next((l for l in linhas if l['morador_id'] == g.morador['id']), None)
    return render_template(
        "contas.html",
        mes=mes, nome_mes=nome_mes(mes),
        anterior=deslocar_mes(mes, -1), proximo=deslocar_mes(mes, 1),
        contas=contas,
        total_aluguel=sum(c['valor_centavos'] for c in contas if c['tipo'] == 'aluguel'),
        total_despesas=sum(c['valor_centavos'] for c in contas if c['tipo'] != 'aluguel'),
        linhas=linhas, avisos=avisos, fechado=fechado,
        minha_parte=minha_parte, meu_saldo=meu_saldo, saldo_anterior=saldo_anterior, fotos=fotos,
        ajustes=lista_ajustes, tipos_ajuste=TIPOS_AJUSTE, moradores=moradores,
        erro=request.args.get("erro", ""), sync=sync,
    )


def voltar(mes, erro=None, ancora=""):
    url = url_for("contas.index", mes=mes, erro=erro) if erro else url_for("contas.index", mes=mes)
    return redirect(url + ancora)


def bloquear_se_fechado(conn, mes):
    if mes_esta_fechado(conn, mes):
        conn.close()
        return voltar(mes, "Esse mês já foi fechado. Reabra para mudar.")
    return None


@contas_bp.route("/nova", methods=["POST"])
@exigir_cargo('financeiro')
def nova():
    mes = mes_da_url()
    descricao = request.form.get("descricao", "").strip()
    valor = ler_valor(request.form.get("valor", ""))
    tipo = request.form.get("tipo", "despesa")
    if tipo not in ("aluguel", "despesa"):
        abort(400)
    if not descricao or len(descricao) > 60:
        return voltar(mes, "Coloque uma descrição (até 60 letras)")
    if not valor:
        return voltar(mes, "Valor inválido. Use por exemplo 1.234,56")

    conn = conectar_db()
    if (bloqueio := bloquear_se_fechado(conn, mes)):
        return bloqueio
    conn.execute('INSERT INTO contas (mes, descricao, tipo, valor_centavos, criado_por) VALUES (?, ?, ?, ?, ?)',
                 (mes, descricao, tipo, valor, g.morador['id']))
    conn.commit()
    conn.close()
    return voltar(mes)


@contas_bp.route("/<int:conta_id>/apagar", methods=["POST"])
@exigir_cargo('financeiro')
def apagar(conta_id):
    mes = mes_da_url()
    conn = conectar_db()
    if (bloqueio := bloquear_se_fechado(conn, mes)):
        return bloqueio
    conn.execute('DELETE FROM contas WHERE id = ? AND mes = ?', (conta_id, mes))
    conn.commit()
    conn.close()
    return voltar(mes)


@contas_bp.route("/ajuste", methods=["POST"])
@exigir_cargo('financeiro')
def novo_ajuste():
    mes = mes_da_url()
    tipo = request.form.get("tipo", "")
    descricao = request.form.get("descricao", "").strip() or TIPOS_AJUSTE.get(tipo, "")
    valor = ler_valor(request.form.get("valor", ""))
    try:
        morador_id = int(request.form.get("morador_id", ""))
    except ValueError:
        abort(400)
    if tipo not in TIPOS_AJUSTE:
        abort(400)
    if not valor:
        return voltar(mes, "Valor do ajuste inválido", "#ajustes")

    conn = conectar_db()
    if (bloqueio := bloquear_se_fechado(conn, mes)):
        return bloqueio
    conn.execute('INSERT INTO ajustes (mes, morador_id, tipo, descricao, valor_centavos) VALUES (?, ?, ?, ?, ?)',
                 (mes, morador_id, tipo, descricao[:60], valor))
    conn.commit()
    conn.close()
    return voltar(mes, ancora="#ajustes")


@contas_bp.route("/ajuste/<int:ajuste_id>/apagar", methods=["POST"])
@exigir_cargo('financeiro')
def apagar_ajuste(ajuste_id):
    mes = mes_da_url()
    conn = conectar_db()
    if (bloqueio := bloquear_se_fechado(conn, mes)):
        return bloqueio
    conn.execute('DELETE FROM ajustes WHERE id = ? AND mes = ?', (ajuste_id, mes))
    conn.commit()
    conn.close()
    return voltar(mes, ancora="#ajustes")


@contas_bp.route("/fechar", methods=["POST"])
@exigir_cargo('financeiro')
def fechar():
    """Congela a divisão do mês com os quartos, moradores e valores de agora."""
    mes = mes_da_url()
    conn = conectar_db()
    linhas, _, fechado = divisao_do_mes(conn, mes)
    if not fechado:
        if not linhas or not any(l['casa_centavos'] or l['despesas_centavos'] for l in linhas):
            conn.close()
            return voltar(mes, "Lance as contas e cadastre os quartos antes de fechar o mês")
        conn.executemany(
            '''INSERT INTO fechamentos (mes, vaga, quarto, morador_id, casa_centavos, despesas_centavos,
                                         caixinha_centavos, ajustes_centavos, total_centavos)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            [(mes, l['vaga'], l['quarto'], l['morador_id'], l['casa_centavos'], l['despesas_centavos'],
              l['caixinha_centavos'], l['ajustes_centavos'], l['total_centavos']) for l in linhas])
        conn.commit()
    conn.close()
    return voltar(mes)


@contas_bp.route("/reabrir", methods=["POST"])
@exigir_cargo('financeiro')
def reabrir():
    mes = mes_da_url()
    conn = conectar_db()
    conn.execute('DELETE FROM fechamentos WHERE mes = ?', (mes,))
    conn.commit()
    conn.close()
    return voltar(mes)


@contas_bp.route("/pagamento/<int:vaga>", methods=["POST"])
@exigir_cargo('financeiro')
def registrar_pagamento(vaga):
    """Guarda quanto o morador daquela vaga pagou no mês (vazio ou 'tudo' = valor cheio)."""
    mes = mes_da_url()
    conn = conectar_db()
    linha = conn.execute('SELECT total_centavos FROM fechamentos WHERE mes = ? AND vaga = ?', (mes, vaga)).fetchone()
    if linha is None:
        conn.close()
        abort(404)
    texto = request.form.get("valor", "").strip()
    if texto.lower() in ("", "tudo"):
        pago = linha['total_centavos']
    elif texto == "0":
        pago = 0
    else:
        pago = ler_valor(texto)
        if pago is None:
            conn.close()
            return voltar(mes, "Valor pago inválido", "#divisao")
    conn.execute('UPDATE fechamentos SET pago_centavos = ? WHERE mes = ? AND vaga = ?', (pago, mes, vaga))
    conn.commit()
    conn.close()
    return voltar(mes, ancora="#divisao")


# ---------- planilha do financeiro ----------

@contas_bp.route("/planilha", methods=["POST"])
@exigir_cargo('financeiro')
def configurar_planilha():
    """Liga a leitura da planilha: link do arquivo no Drive e o ano dele."""
    arquivo_id = financeiro.id_do_link(request.form.get("link", ""))
    ano = request.form.get("ano", "").strip()
    if not arquivo_id:
        return redirect(url_for("contas.index", erro="Não reconheci esse link. Cole o link da planilha no Drive."))
    if ano and not (ano.isdigit() and 2020 <= int(ano) <= 2100):
        return redirect(url_for("contas.index", erro="Ano inválido"))
    conn = conectar_db()
    financeiro.salvar_config(conn, financeiro_arquivo_id=arquivo_id, financeiro_ano=ano)
    conn.commit()
    conn.close()
    erro = financeiro.sincronizar()
    if erro:
        return redirect(url_for("contas.index", erro=f"Salvei o link, mas não consegui ler a planilha: {erro}"))
    return redirect(url_for("contas.index", ok="Planilha ligada. As contas agora vêm dela."))


@contas_bp.route("/planilha/atualizar", methods=["POST"])
@exigir_cargo('financeiro')
def atualizar_planilha():
    erro = financeiro.sincronizar()
    mes = request.form.get("mes", "")
    destino = {"mes": mes} if mes_valido(mes) else {}
    if erro:
        return redirect(url_for("contas.index", erro=f"Não consegui ler a planilha: {erro}", **destino))
    return redirect(url_for("contas.index", ok="Atualizado com a planilha", **destino))


@contas_bp.route("/planilha/desligar", methods=["POST"])
@exigir_cargo('financeiro')
def desligar_planilha():
    """Volta para as contas lançadas no próprio app."""
    conn = conectar_db()
    conn.execute("DELETE FROM config WHERE chave IN ('financeiro_arquivo_id', 'financeiro_ano')")
    conn.commit()
    conn.close()
    return redirect(url_for("contas.index"))
