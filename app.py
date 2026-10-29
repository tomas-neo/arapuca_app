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
from modulos.auth import CARGOS, auth_bp, pode
from modulos.azaralho import azaralho_bp, meus_pontos_do_mes
from modulos.boiler import boiler_bp
from modulos.contas import contas_bp
from modulos.icones import ICONE_MOTIVO, avatar, icone, icone_escala
from modulos.escalas import escalas_bp, minhas_funcoes
from modulos.funcas import funcas_bp, funcas_do_morador
from modulos.mercado import formatar_qtd, mercado_bp
from modulos import casa, planilha
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
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),  # celular fica logado; renova a cada acesso
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,  # foto de perfil
    # escalas: quem manda é o app (o cargo de estrutura edita lá); a planilha só entra pelo botão
    SINCRONIZAR_PLANILHA=os.environ.get("ARAPUCA_SINCRONIZAR", "0") == "1",
    AZARALHO_ATIVO=os.environ.get("ARAPUCA_AZARALHO", "0") == "1",  # em quarentena por enquanto
    BOILER_ATIVO=os.environ.get("ARAPUCA_BOILER", "0") == "1",  # em breve
    SESSION_COOKIE_SAMESITE="Lax",
)

inicializar_db()
_conn = conectar_db()
casa.importar(_conn)  # ano, saldo da planilha e fotos de dados_iniciais/ (fora do git)
_conn.close()
app.jinja_env.filters['qtd'] = formatar_qtd
app.jinja_env.filters['ano'] = casa.formatar_ano
app.jinja_env.globals.update(pode=pode, cargos_nomes=CARGOS, avatar=avatar, icone=icone, icone_escala=icone_escala, icone_motivo=ICONE_MOTIVO)

app.register_blueprint(auth_bp)
app.register_blueprint(moradores_bp)
app.register_blueprint(contas_bp)
app.register_blueprint(escalas_bp)
app.register_blueprint(funcas_bp)
app.register_blueprint(mercado_bp)
app.register_blueprint(boiler_bp)
app.register_blueprint(azaralho_bp)


@app.route("/sw.js")
def service_worker():
    # O service worker precisa ser servido na raiz para valer para o app inteiro
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/")
def home():
    planilha.sincronizar_se_preciso(app.config["SINCRONIZAR_PLANILHA"])
    conn = conectar_db()
    minhas_funcas = funcas_do_morador(conn, g.morador["id"])
    conn.close()
    return render_template("home.html", tarefas=minhas_funcoes(g.morador["id"]), minhas_funcas=minhas_funcas,
                           meus_pontos=meus_pontos_do_mes(g.morador["id"]) if app.config["AZARALHO_ATIVO"] else 0)


@app.cli.command("criar-admin")
@click.argument("apelido")
def criar_admin(apelido):
    """Cria um morador root (acesso total). Uso: flask --app app criar-admin Oca"""
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
    click.echo(f"Root {apelido} criado. Agora é só entrar pelo app.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
