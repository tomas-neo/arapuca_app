import sqlite3

from flask import Blueprint, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from database import conectar_db
from modulos.auth import somente_admin
from modulos.contas import formatar, ler_valor

moradores_bp = Blueprint('moradores', __name__, url_prefix='/moradores')


@moradores_bp.route("/")
@somente_admin
def index():
    erro = request.args.get('erro', '')
    conn = conectar_db()
    moradores = conn.execute('SELECT id, apelido, admin, ativo, quarto_id FROM moradores ORDER BY ativo DESC, apelido').fetchall()
    quartos = conn.execute(
        '''SELECT q.id, q.nome, q.ponderacao, q.vagas,
                  (SELECT COUNT(*) FROM moradores m WHERE m.quarto_id = q.id AND m.ativo = 1) AS ocupantes
           FROM quartos q ORDER BY q.id''').fetchall()
    cfg = {r['chave']: r['valor'] for r in conn.execute('SELECT chave, valor FROM config')}
    conn.close()

    soma = sum(q['ponderacao'] for q in quartos)
    return render_template("moradores.html", moradores=moradores, quartos=quartos, erro=erro,
                           soma_ponderacao=soma, total_vagas=sum(max(q['vagas'], q['ocupantes']) for q in quartos),
                           caixinha=formatar(int(cfg.get('caixinha_centavos', 5000))),
                           fracao_comum=round(float(cfg.get('fracao_area_comum', 0.5)) * 100))


@moradores_bp.route("/novo", methods=["POST"])
@somente_admin
def novo():
    apelido = request.form.get('apelido', '').strip()
    senha = request.form.get('senha', '')
    admin = 1 if request.form.get('admin') else 0

    if not apelido or len(apelido) > 40:
        return redirect(url_for('moradores.index', erro="Apelido inválido"))
    if len(senha) < 6:
        return redirect(url_for('moradores.index', erro="A senha precisa de 6 caracteres ou mais"))

    conn = conectar_db()
    try:
        conn.execute('INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)',
                     (apelido, generate_password_hash(senha), admin))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('moradores.index', erro=f"Já existe um morador chamado {apelido}"))
    finally:
        conn.close()
    return redirect(url_for('moradores.index'))


@moradores_bp.route("/<int:morador_id>/ativo", methods=["POST"])
@somente_admin
def alternar_ativo(morador_id):
    if morador_id != g.morador['id']:  # admin não se desativa sozinho
        conn = conectar_db()
        conn.execute('UPDATE moradores SET ativo = 1 - ativo WHERE id = ?', (morador_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('moradores.index'))


def ler_numero(nome):
    try:
        return float(request.form.get(nome, '').replace(',', '.'))
    except ValueError:
        return None


def voltar_quartos(erro=None):
    return redirect(url_for('moradores.index', erro=erro) if erro else url_for('moradores.index') + '#quartos')


@moradores_bp.route("/<int:morador_id>/quarto", methods=["POST"])
@somente_admin
def mudar_quarto(morador_id):
    texto = request.form.get('quarto_id', '')
    quarto_id = int(texto) if texto.isdigit() else None
    conn = conectar_db()
    try:
        conn.execute('UPDATE moradores SET quarto_id = ? WHERE id = ?', (quarto_id, morador_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('moradores.index', erro="Esse quarto não existe"))
    finally:
        conn.close()
    return redirect(url_for('moradores.index'))


def ler_quarto():
    nome = request.form.get('nome', '').strip()
    ponderacao = ler_numero('ponderacao')
    try:
        vagas = int(request.form.get('vagas', ''))
    except ValueError:
        vagas = 0
    if not nome or len(nome) > 30:
        return None, "Nome do quarto inválido (até 30 letras)"
    if ponderacao is None or not 0 <= ponderacao <= 1:
        return None, "Ponderação precisa ser entre 0 e 1 (ex: 0,18)"
    if not 1 <= vagas <= 10:
        return None, "Vagas precisa ser entre 1 e 10"
    return (nome, ponderacao, vagas), None


@moradores_bp.route("/quartos/novo", methods=["POST"])
@somente_admin
def novo_quarto():
    dados, erro = ler_quarto()
    if erro:
        return voltar_quartos(erro)
    conn = conectar_db()
    try:
        conn.execute('INSERT INTO quartos (nome, ponderacao, vagas) VALUES (?, ?, ?)', dados)
        conn.commit()
    except sqlite3.IntegrityError:
        return voltar_quartos(f"Já existe o quarto {dados[0]}")
    finally:
        conn.close()
    return voltar_quartos()


@moradores_bp.route("/quartos/<int:quarto_id>", methods=["POST"])
@somente_admin
def editar_quarto(quarto_id):
    dados, erro = ler_quarto()
    if erro:
        return voltar_quartos(erro)
    conn = conectar_db()
    try:
        conn.execute('UPDATE quartos SET nome = ?, ponderacao = ?, vagas = ? WHERE id = ?', (*dados, quarto_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return voltar_quartos(f"Já existe o quarto {dados[0]}")
    finally:
        conn.close()
    return voltar_quartos()


@moradores_bp.route("/quartos/<int:quarto_id>/apagar", methods=["POST"])
@somente_admin
def apagar_quarto(quarto_id):
    conn = conectar_db()
    conn.execute('DELETE FROM quartos WHERE id = ?', (quarto_id,))  # moradores ficam sem quarto
    conn.commit()
    conn.close()
    return voltar_quartos()


@moradores_bp.route("/config", methods=["POST"])
@somente_admin
def salvar_config():
    caixinha = ler_valor(request.form.get('caixinha', ''))
    if request.form.get('caixinha', '').strip() == '0':
        caixinha = 0
    fracao = ler_numero('fracao_comum')
    if caixinha is None:
        return voltar_quartos("Valor da caixinha inválido")
    if fracao is None or not 0 <= fracao <= 100:
        return voltar_quartos("A parte da área comum precisa ser de 0 a 100%")
    conn = conectar_db()
    conn.executemany('INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)',
                     [('caixinha_centavos', str(caixinha)), ('fracao_area_comum', str(fracao / 100))])
    conn.commit()
    conn.close()
    return voltar_quartos()
