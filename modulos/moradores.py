import sqlite3

from flask import Blueprint, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from database import conectar_db
from modulos import casa
from modulos.auth import somente_admin
from modulos.contas import formatar, ler_valor

moradores_bp = Blueprint('moradores', __name__, url_prefix='/moradores')


@moradores_bp.route("/")
@somente_admin
def index():
    erro = request.args.get('erro', '')
    conn = conectar_db()
    moradores = conn.execute('SELECT id, apelido, admin, ativo, quarto_id, foto_versao, ano, saldo_anterior_centavos FROM moradores ORDER BY ativo DESC, apelido').fetchall()
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
    ano = ler_ano(request.form.get('ano', ''))

    if not apelido or len(apelido) > 40:
        return redirect(url_for('moradores.index', erro="Apelido inválido"))
    if len(senha) < 6:
        return redirect(url_for('moradores.index', erro="A senha precisa de 6 caracteres ou mais"))

    conn = conectar_db()
    try:
        conn.execute('INSERT INTO moradores (apelido, senha_hash, admin, ano) VALUES (?, ?, ?, ?)',
                     (apelido, generate_password_hash(senha), admin, ano))
        conn.commit()
        casa.importar(conn)  # se tiver foto/ano/saldo dele em dados_iniciais/, já entra
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


def ler_ano(texto):
    """Aceita "2022", "022" ou "22". Devolve o ano completo ou None."""
    t = texto.strip()
    if not t.isdigit():
        return None
    n = int(t)
    if n < 100:
        n += 2000
    return n if 1990 <= n <= 2100 else None


@moradores_bp.route("/<int:morador_id>/dados", methods=["POST"])
@somente_admin
def mudar_dados(morador_id):
    """Ano de entrada e saldo que veio da planilha antiga (antes do app)."""
    ano = ler_ano(request.form.get('ano', ''))
    texto = request.form.get('saldo', '').strip()
    if texto:
        valor = ler_valor(texto.lstrip('-−'))
        if valor is None:
            return redirect(url_for('moradores.index', erro="Valor do saldo inválido"))
        saldo = -valor if request.form.get('sentido', 'deve') == 'deve' else valor
    else:
        saldo = 0
    conn = conectar_db()
    conn.execute('UPDATE moradores SET ano = ?, saldo_anterior_centavos = ? WHERE id = ?', (ano, saldo, morador_id))
    conn.commit()
    conn.close()
    return redirect(url_for('moradores.index'))
