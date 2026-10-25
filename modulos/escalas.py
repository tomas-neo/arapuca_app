import sqlite3
from datetime import date

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos.auth import somente_admin

escalas_bp = Blueprint('escalas', __name__, url_prefix='/escalas')

# 0 = domingo, igual à planilha da casa
DIAS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]


def dia_de_hoje():
    return (date.today().weekday() + 1) % 7  # weekday(): segunda = 0


def turnos_do_dia(conn, dia, morador_id=None):
    """Lista o que cada um faz no dia: escala, linha e apelido."""
    sql = '''SELECT e.icone, e.nome AS escala, l.nome AS linha, m.apelido, m.id AS morador_id
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


def minhas_tarefas_hoje(morador_id):
    conn = conectar_db()
    tarefas = turnos_do_dia(conn, dia_de_hoje(), morador_id)
    conn.close()
    return tarefas


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
    conn = conectar_db()
    hoje = dia_de_hoje()
    escalas = [montar_escala(conn, e) for e in conn.execute('SELECT * FROM escalas ORDER BY id')]
    moradores = conn.execute('SELECT id, apelido FROM moradores WHERE ativo = 1 ORDER BY apelido').fetchall()
    hoje_na_casa = turnos_do_dia(conn, hoje)
    conn.close()
    return render_template("escalas.html", escalas=escalas, dias=DIAS, hoje=hoje,
                           hoje_na_casa=hoje_na_casa, moradores=moradores,
                           erro=request.args.get('erro', ''))


def ler_int(nome, minimo=None, maximo=None):
    try:
        valor = int(request.form.get(nome, ''))
    except ValueError:
        abort(400)
    if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
        abort(400)
    return valor


@escalas_bp.route("/turno", methods=["POST"])
@somente_admin
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
    return redirect(url_for('escalas.index') + f"#escala-{request.form.get('escala_id', '')}")


@escalas_bp.route("/turno/remover", methods=["POST"])
@somente_admin
def remover_turno():
    linha_id = ler_int('linha_id')
    dia = ler_int('dia', 0, 6)
    morador_id = ler_int('morador_id')
    conn = conectar_db()
    conn.execute('DELETE FROM escala_turnos WHERE linha_id = ? AND dia = ? AND morador_id = ?',
                 (linha_id, dia, morador_id))
    conn.commit()
    conn.close()
    return redirect(url_for('escalas.index') + f"#escala-{request.form.get('escala_id', '')}")


@escalas_bp.route("/<int:escala_id>/linha", methods=["POST"])
@somente_admin
def adicionar_linha(escala_id):
    nome = request.form.get('nome', '').strip()
    if not nome or len(nome) > 30:
        return redirect(url_for('escalas.index', erro="Nome da linha inválido (até 30 letras)"))
    conn = conectar_db()
    try:
        conn.execute('INSERT INTO escala_linhas (escala_id, nome) VALUES (?, ?)', (escala_id, nome))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('escalas.index', erro=f"Essa escala já tem \"{nome}\""))
    finally:
        conn.close()
    return redirect(url_for('escalas.index') + f"#escala-{escala_id}")


@escalas_bp.route("/linha/<int:linha_id>/apagar", methods=["POST"])
@somente_admin
def apagar_linha(linha_id):
    conn = conectar_db()
    conn.execute('DELETE FROM escala_linhas WHERE id = ?', (linha_id,))  # turnos saem junto (cascade)
    conn.commit()
    conn.close()
    return redirect(url_for('escalas.index'))


@escalas_bp.route("/nova", methods=["POST"])
@somente_admin
def nova_escala():
    nome = request.form.get('nome', '').strip()
    icone = request.form.get('icone', '').strip()[:2] or '📋'
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
