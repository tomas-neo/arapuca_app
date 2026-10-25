import getpass
import os
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path

import click
from flask import Flask, g, render_template, send_from_directory
from werkzeug.security import generate_password_hash

from database import conectar_db, inicializar_db
from modulos.auth import auth_bp
from modulos.azaralho import azaralho_bp, meus_pontos_do_mes
from modulos.boiler import boiler_bp
from modulos.contas import contas_bp
from modulos.icones import ICONE_MOTIVO, icone, icone_escala
from modulos.escalas import escalas_bp, minhas_tarefas_hoje
from modulos.mercado import mercado_bp
from modulos.moradores import moradores_bp

PASTA = Path(__file__).resolve().parent


def carregar_chave_secreta():
    """Usa ARAPUCA_SECRET_KEY se existir; senão cria (uma vez) o arquivo .secret_key."""
    chave = os.environ.get("ARAPUCA_SECRET_KEY")
    if chave:
        return chave
    arquivo = PASTA / ".secret_key"
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32))
        arquivo.chmod(0o600)
    return arquivo.read_text().strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=carregar_chave_secreta(),
    PERMANENT_SESSION_LIFETIME=timedelta(days=90),
    SESSION_COOKIE_SAMESITE="Lax",
)

inicializar_db()
app.jinja_env.globals.update(icone=icone, icone_escala=icone_escala, icone_motivo=ICONE_MOTIVO)

app.register_blueprint(auth_bp)
app.register_blueprint(moradores_bp)
app.register_blueprint(contas_bp)
app.register_blueprint(escalas_bp)
app.register_blueprint(mercado_bp)
app.register_blueprint(boiler_bp)
app.register_blueprint(azaralho_bp)


@app.route("/sw.js")
def service_worker():
    # O service worker precisa ser servido na raiz para valer para o app inteiro
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/")
def home():
    return render_template("home.html", tarefas=minhas_tarefas_hoje(g.morador["id"]),
                           meus_pontos=meus_pontos_do_mes(g.morador["id"]))


@app.cli.command("criar-admin")
@click.argument("apelido")
def criar_admin(apelido):
    """Cria um morador admin. Uso: flask --app app criar-admin Oca"""
    senha = getpass.getpass("Senha: ")
    if len(senha) < 6:
        raise click.ClickException("A senha precisa de 6 caracteres ou mais")
    if senha != getpass.getpass("Repita a senha: "):
        raise click.ClickException("As senhas não batem")

    conn = conectar_db()
    try:
        conn.execute(
            "INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, 1)",
            (apelido.strip(), generate_password_hash(senha)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise click.ClickException(f"Já existe um morador chamado {apelido}")
    finally:
        conn.close()
    click.echo(f"Admin {apelido} criado. Agora é só entrar pelo app.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
