from flask import Blueprint, g, redirect, url_for
from markupsafe import escape
from database import conectar_db
from datetime import datetime
from estilo import renderizar_pagina # <--- A pintura aqui também!

boiler_bp = Blueprint('boiler', __name__, url_prefix='/boiler')

@boiler_bp.route("/")
def index():
    conn = conectar_db()
    boiler_info = conn.execute('SELECT status, responsavel, hora_ligado FROM boiler WHERE id = 1').fetchone()
    conn.close()
    
    status = boiler_info['status']
    responsavel = escape(boiler_info['responsavel'])
    hora_ligado_str = boiler_info['hora_ligado']
    
    alerta_tempo = ""
    
    if status == "LIGADO":
        hora_ligado = datetime.strptime(hora_ligado_str, "%Y-%m-%d %H:%M:%S")
        tempo_passado = datetime.now() - hora_ligado
        minutos = int(tempo_passado.total_seconds() / 60)
        
        if minutos >= 20:
            alerta = f"<div class='alerta alerta-critico'><h2>🚨 DESLIGA ISSO! ({minutos} min) 🚨</h2></div>"
        else:
            alerta = f"<div class='alerta alerta-ok'><h3>⏱️ Tempo ligado: {minutos} minuto(s)</h3></div>"

        alerta += f"<p style='text-align:center;'>⚠️ Ligado por: <strong>{responsavel}</strong></p>"
        botao_acao = """
        <form action="/boiler/desligar" method="POST">
            <button type="submit" class="btn-vermelho">🔴 DESLIGAR BOILER</button>
        </form>
        """
    else:
        alerta = f"<div class='alerta alerta-ok'><h3>✅ DESLIGADO</h3><p>Último a usar: {responsavel}</p></div>"
        botao_acao = """
        <form action="/boiler/ligar" method="POST">
            <button type="submit" class="btn-verde">🟢 LIGAR BOILER</button>
        </form>
        """

    conteudo = f"""
    <h2>🛁 Controle do Boiler</h2>
    <div class="card">
        {alerta}
        {botao_acao}
    </div>
    <a href='/' class="botao-menu">🏠 Voltar para o início</a>
    """
    
    # O truque de atualização de tela entra aqui!
    cabecalho_extra = '<meta http-equiv="refresh" content="30">'
    
    return renderizar_pagina("Boiler - Arapuca", conteudo, cabecalho_extra)

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
