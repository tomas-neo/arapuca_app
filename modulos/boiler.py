from datetime import datetime

from flask import Blueprint, current_app, g, redirect, render_template, url_for

from database import conectar_db

boiler_bp = Blueprint('boiler', __name__, url_prefix='/boiler')


@boiler_bp.before_request
def em_breve():
    if not current_app.config.get('BOILER_ATIVO'):
        return render_template("em_breve.html", nome="Boiler", texto="O controle do boiler está chegando.")


@boiler_bp.route("/")
def index():
    conn = conectar_db()
    boiler_info = conn.execute('SELECT status, responsavel, hora_ligado FROM boiler WHERE id = 1').fetchone()
    conn.close()

    minutos = 0
    if boiler_info['status'] == "LIGADO":
        hora_ligado = datetime.strptime(boiler_info['hora_ligado'], "%Y-%m-%d %H:%M:%S")
        minutos = int((datetime.now() - hora_ligado).total_seconds() / 60)

    return render_template(
        "boiler.html",
        status=boiler_info['status'],
        responsavel=boiler_info['responsavel'],
        minutos=minutos,
    )


@boiler_bp.route("/ligar", methods=["POST"])
def ligar():
    nome = g.morador['apelido']
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = conectar_db()
    conn.execute('UPDATE boiler SET status = "LIGADO", responsavel = ?, hora_ligado = ? WHERE id = 1', (nome, agora))
    conn.commit()
    conn.close()
    return redirect(url_for('boiler.index'))

@boiler_bp.route("/desligar", methods=["POST"])
def desligar():
    conn = conectar_db()
    boiler_info = conn.execute('SELECT responsavel FROM boiler WHERE id = 1').fetchone()
    ultimo = boiler_info['responsavel']
    
    conn.execute('UPDATE boiler SET status = "DESLIGADO", responsavel = ?, hora_ligado = NULL WHERE id = 1', (ultimo,))
    conn.commit()
    conn.close()
    return redirect(url_for('boiler.index'))
