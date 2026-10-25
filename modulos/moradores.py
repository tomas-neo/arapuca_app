import sqlite3

from flask import Blueprint, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from database import conectar_db
from modulos.auth import somente_admin

moradores_bp = Blueprint('moradores', __name__, url_prefix='/moradores')


@moradores_bp.route("/")
@somente_admin
def index():
    erro = request.args.get('erro', '')
    conn = conectar_db()
    moradores = conn.execute('SELECT id, apelido, admin, ativo, peso FROM moradores ORDER BY ativo DESC, apelido').fetchall()
    conn.close()

    return render_template("moradores.html", moradores=moradores, erro=erro)


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


@moradores_bp.route("/<int:morador_id>/peso", methods=["POST"])
@somente_admin
def mudar_peso(morador_id):
    try:
        peso = float(request.form.get('peso', '').replace(',', '.'))
    except ValueError:
        peso = -1
    if not 0 < peso <= 10:
        return redirect(url_for('moradores.index', erro="Peso precisa ser um número entre 0 e 10 (ex: 1 ou 1,5)"))
    conn = conectar_db()
    conn.execute('UPDATE moradores SET peso = ? WHERE id = ?', (peso, morador_id))
    conn.commit()
    conn.close()
    return redirect(url_for('moradores.index'))
