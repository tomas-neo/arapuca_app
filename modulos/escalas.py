import sqlite3
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos.auth import exigir_cargo, pode
from modulos import planilha
from modulos.funcas import listar_funcas

escalas_bp = Blueprint('escalas', __name__, url_prefix='/escalas')

# 0 = domingo, igual à planilha da casa
DIAS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
DIAS_CURTOS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]


def dia_da_semana(data):
    return (data.weekday() + 1) % 7  # weekday(): segunda = 0


def dia_de_hoje():
    return dia_da_semana(date.today())


def turnos_do_dia(conn, dia, morador_id=None):
    """Lista o que cada um faz no dia: escala, linha e apelido."""
    sql = '''SELECT e.icone, e.nome AS escala, e.prazo_dias, l.nome AS linha,
                    m.apelido, m.id AS morador_id, m.foto_versao
             FROM escala_turnos t
             JOIN escala_linhas l ON l.id = t.linha_id
             JOIN escalas e ON e.id = l.escala_id
             JOIN moradores m ON m.id = t.morador_id
             WHERE t.dia = ? AND m.ativo = 1'''
    args = [dia]
    if morador_id is not None:
        sql += ' AND m.id = ?'
        args.append(morador_id)
    return conn.execute(sql + ' ORDER BY e.id, l.id, m.apelido', args).fetchall()


def minhas_funcoes(morador_id, hoje=None):
    """O que o morador tem que fazer hoje, contando o prazo extra da limpeza (dia + 1)."""
    hoje = hoje or date.today()
    conn = conectar_db()
    funcoes = []
    for atraso in (0, 1):  # escalado hoje ou ontem
        dia = hoje - timedelta(days=atraso)
        for t in turnos_do_dia(conn, dia_da_semana(dia), morador_id):
            if atraso > t['prazo_dias']:
                continue
            if t['prazo_dias'] == 0:
                prazo, urgente = "Hoje", True
            elif atraso == 0:
                prazo, urgente = "Hoje ou amanhã", False
            else:
                prazo, urgente = f"Último dia (era de {DIAS[dia_da_semana(dia)].lower()})", True
            funcoes.append({'escala': t['escala'], 'linha': t['linha'], 'prazo': prazo, 'urgente': urgente})
    conn.close()
    funcoes.sort(key=lambda f: not f['urgente'])
    return funcoes


def proximos_dias(conn, hoje, quantos=7):
    """Os próximos dias com quem faz o quê, agrupado por escala e linha (linhas vazias também,
    para quem edita poder escalar alguém nelas)."""
    escalas = conn.execute('SELECT id, nome FROM escalas ORDER BY id').fetchall()
    linhas = conn.execute('SELECT id, escala_id, nome FROM escala_linhas ORDER BY id').fetchall()
    dias = []
    for i in range(quantos):
        data = hoje + timedelta(days=i)
        dia = dia_da_semana(data)
        turnos = conn.execute(
            '''SELECT t.linha_id, m.id AS morador_id, m.apelido, m.foto_versao
               FROM escala_turnos t JOIN moradores m ON m.id = t.morador_id
               WHERE t.dia = ? AND m.ativo = 1 ORDER BY m.apelido''', (dia,)).fetchall()
        grupos = []
        for e in escalas:
            grupo_linhas = [{'id': l['id'], 'nome': l['nome'],
                             'turnos': [t for t in turnos if t['linha_id'] == l['id']]}
                            for l in linhas if l['escala_id'] == e['id']]
            grupos.append({'id': e['id'], 'escala': e['nome'], 'linhas': grupo_linhas})
        rotulo = "Hoje" if i == 0 else "Amanhã" if i == 1 else DIAS_CURTOS[dia]
        dias.append({'rotulo': rotulo, 'curto': DIAS_CURTOS[dia], 'dia': dia,
                     'data': data.strftime("%d/%m"), 'nome': DIAS[dia], 'grupos': grupos})
    return dias


def montar_escala(conn, escala):
    """Monta {linha: {dia: [moradores]}} para mostrar a semana da escala."""
    linhas = conn.execute('SELECT id, nome FROM escala_linhas WHERE escala_id = ? ORDER BY id',
                          (escala['id'],)).fetchall()
    turnos = conn.execute(
        '''SELECT t.linha_id, t.dia, m.id AS morador_id, m.apelido
           FROM escala_turnos t
           JOIN escala_linhas l ON l.id = t.linha_id
           JOIN moradores m ON m.id = t.morador_id
           WHERE l.escala_id = ? AND m.ativo = 1 ORDER BY l.id, m.apelido''', (escala['id'],)
    ).fetchall()
    por_dia = {d: [] for d in range(7)}
    for t in turnos:
        nome_linha = next(l['nome'] for l in linhas if l['id'] == t['linha_id'])
        por_dia[t['dia']].append({'linha_id': t['linha_id'], 'linha': nome_linha,
                                  'morador_id': t['morador_id'], 'apelido': t['apelido']})
    return {'id': escala['id'], 'nome': escala['nome'], 'icone': escala['icone'],
            'linhas': linhas, 'por_dia': por_dia}


@escalas_bp.route("/")
def index():
    planilha.sincronizar_se_preciso(current_app.config.get('SINCRONIZAR_PLANILHA', True))
    conn = conectar_db()
    dias = proximos_dias(conn, date.today())
    sync = planilha.status(conn)
    funcas = listar_funcas(conn)
    moradores = conn.execute('SELECT id, apelido FROM moradores WHERE ativo = 1 ORDER BY apelido').fetchall()
    conn.close()
    aba = request.args.get('aba', '0')
    editar = pode('estrutura') and request.args.get('editar') == '1'
    return render_template("escalas.html", dias=dias, funcoes=minhas_funcoes(g.morador['id']),
                           sync=sync, funcas=funcas, moradores=moradores, editar=editar,
                           aba=int(aba) if aba.isdigit() and int(aba) < len(dias) else 0,
                           erro=request.args.get('erro', ''), ok=request.args.get('ok', ''))


def voltar_editando(ancora=""):
    """Volta pra tela de escalas no mesmo dia e com a edição aberta."""
    aba = request.form.get('aba', '0')
    return redirect(url_for('escalas.index', editar=1, aba=aba if aba.isdigit() else 0) + ancora)


@escalas_bp.route("/sincronizar", methods=["POST"])
@exigir_cargo('estrutura')
def sincronizar():
    resultado = planilha.sincronizar()
    if resultado['erros']:
        return redirect(url_for('escalas.index', erro="Não consegui ler: " + "; ".join(resultado['erros'])))
    return redirect(url_for('escalas.index', ok="Escalas atualizadas da planilha"))


def ler_int(nome, minimo=None, maximo=None):
    try:
        valor = int(request.form.get(nome, ''))
    except ValueError:
        abort(400)
    if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
        abort(400)
    return valor


@escalas_bp.route("/turno", methods=["POST"])
@exigir_cargo('estrutura')
def adicionar_turno():
    linha_id = ler_int('linha_id')
    dia = ler_int('dia', 0, 6)
    morador_id = ler_int('morador_id')
    conn = conectar_db()
    try:
        conn.execute('INSERT OR IGNORE INTO escala_turnos (linha_id, dia, morador_id) VALUES (?, ?, ?)',
                     (linha_id, dia, morador_id))
        conn.commit()
    except sqlite3.IntegrityError:
        abort(400)  # linha ou morador que não existe
    finally:
        conn.close()
    return voltar_editando()


@escalas_bp.route("/turno/remover", methods=["POST"])
@exigir_cargo('estrutura')
def remover_turno():
    linha_id = ler_int('linha_id')
    dia = ler_int('dia', 0, 6)
    morador_id = ler_int('morador_id')
    conn = conectar_db()
    conn.execute('DELETE FROM escala_turnos WHERE linha_id = ? AND dia = ? AND morador_id = ?',
                 (linha_id, dia, morador_id))
    conn.commit()
    conn.close()
    return voltar_editando()


@escalas_bp.route("/<int:escala_id>/linha", methods=["POST"])
@exigir_cargo('estrutura')
def adicionar_linha(escala_id):
    nome = request.form.get('nome', '').strip()
    if not nome or len(nome) > 30:
        return redirect(url_for('escalas.index', editar=1, erro="Nome da linha inválido (até 30 letras)"))
    conn = conectar_db()
    try:
        conn.execute('INSERT INTO escala_linhas (escala_id, nome) VALUES (?, ?)', (escala_id, nome))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('escalas.index', editar=1, erro=f"Essa escala já tem \"{nome}\""))
    finally:
        conn.close()
    return voltar_editando()


@escalas_bp.route("/linha/<int:linha_id>/apagar", methods=["POST"])
@exigir_cargo('estrutura')
def apagar_linha(linha_id):
    conn = conectar_db()
    conn.execute('DELETE FROM escala_linhas WHERE id = ?', (linha_id,))  # turnos saem junto (cascade)
    conn.commit()
    conn.close()
    return voltar_editando()


@escalas_bp.route("/nova", methods=["POST"])
@exigir_cargo('estrutura')
def nova_escala():
    nome = request.form.get('nome', '').strip()
    icone = ''  # o ícone sai do nome da escala (modulos/icones.py)
    if not nome or len(nome) > 40:
        return redirect(url_for('escalas.index', erro="Nome da escala inválido (até 40 letras)"))
    conn = conectar_db()
    try:
        conn.execute('INSERT INTO escalas (nome, icone) VALUES (?, ?)', (nome, icone))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('escalas.index', erro=f"Já existe a escala \"{nome}\""))
    finally:
        conn.close()
    return redirect(url_for('escalas.index'))
