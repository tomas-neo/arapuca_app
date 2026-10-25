import sqlite3

from flask import Blueprint, g, redirect, request, url_for
from markupsafe import escape
from werkzeug.security import generate_password_hash

from database import conectar_db
from estilo import renderizar_pagina
from modulos.auth import somente_admin

moradores_bp = Blueprint('moradores', __name__, url_prefix='/moradores')


@moradores_bp.route("/")
@somente_admin
def index():
    erro = request.args.get('erro', '')
    conn = conectar_db()
    moradores = conn.execute('SELECT id, apelido, admin, ativo FROM moradores ORDER BY ativo DESC, apelido').fetchall()
    conn.close()

    linhas = ""
    for m in moradores:
        selo = " 👑" if m['admin'] else ""
        estado = "" if m['ativo'] else " <em style='color:var(--text-muted)'>(saiu)</em>"
        if m['id'] == g.morador['id']:
            acao = "<span style='color:var(--text-muted);font-size:13px;'>você</span>"
        else:
            texto = "Desativar" if m['ativo'] else "Reativar"
            classe = "btn-vermelho" if m['ativo'] else "btn-verde"
            acao = f"""<form action="/moradores/{m['id']}/ativo" method="POST">
                <button type="submit" class="{classe}">{texto}</button></form>"""
        linhas += f"""
        <li class="item-row">
            <span><strong>{escape(m['apelido'])}</strong>{selo}{estado}</span>
            {acao}
        </li>"""

    aviso = f"<div class='alerta alerta-critico'><h3 style='color:#fff;margin:0;'>{escape(erro)}</h3></div>" if erro else ""

    conteudo = f"""
    <h2>👥 Moradores</h2>
    <div class="card">
        <h3>➕ Novo morador</h3>
        {aviso}
        <form action="/moradores/novo" method="POST">
            <input type="text" name="apelido" placeholder="Apelido" required maxlength="40" style="margin-bottom: 10px;">
            <input type="text" name="senha" placeholder="Senha inicial (mín. 6)" minlength="6" required style="margin-bottom: 10px;">
            <label style="display:flex;gap:8px;align-items:center;margin-bottom:10px;color:var(--text-muted);">
                <input type="checkbox" name="admin" value="1" style="width:auto;"> Admin
            </label>
            <button type="submit" class="btn-laranja">Criar</button>
        </form>
        <p style="font-size:13px;">Passe a senha inicial para o morador e peça para ele trocar em "Trocar senha".</p>
    </div>
    <div class="card">
        <h3>🏠 Na casa</h3>
        <ul style="padding: 0; margin: 0;">{linhas}</ul>
    </div>
    <a href='/' class="botao-menu">🏠 Voltar para o início</a>
    """
    return renderizar_pagina("Moradores", conteudo)


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
