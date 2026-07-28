from flask import Blueprint, request, redirect, url_for
from database import conectar_db
from datetime import datetime

boiler_bp = Blueprint('boiler', __name__, url_prefix='/boiler')

@boiler_bp.route("/")
def index():
    conn = conectar_db()
    boiler_info = conn.execute('SELECT status, responsavel, hora_ligado FROM boiler WHERE id = 1').fetchone()
    conn.close()
    
    status = boiler_info['status']
    responsavel = boiler_info['responsavel']
    hora_ligado_str = boiler_info['hora_ligado']
    
    alerta_tempo = ""
    
    if status == "LIGADO":
        # Converte a hora salva no banco para um objeto de tempo do Python
        hora_ligado = datetime.strptime(hora_ligado_str, "%Y-%m-%d %H:%M:%S")
        tempo_passado = datetime.now() - hora_ligado
        minutos = int(tempo_passado.total_seconds() / 60)
        
        # Se bater 20 minutos, a tela berra!
        if minutos >= 20:
            alerta_tempo = f"<h2 style='color: white; background-color: red; padding: 15px;'>🚨 DESLIGA ISSO! JÁ PASSOU DOS 20 MINUTOS ({minutos} min) 🚨</h2>"
        else:
            alerta_tempo = f"<h3 style='color: orange;'>⏱️ Tempo ligado: {minutos} minuto(s)</h3>"
            
        alerta = f"{alerta_tempo}<h3 style='color: red;'>⚠️ LIGADO POR: {responsavel}</h3>"
        botao_acao = """
        <form action="/boiler/desligar" method="POST">
            <button type="submit" style="background-color: red; color: white; padding: 15px; font-size: 18px;">🔴 DESLIGAR BOILER</button>
        </form>
        """
    else:
        alerta = f"<h3 style='color: green;'>✅ DESLIGADO</h3><p>Último a usar: {responsavel}</p>"
        botao_acao = """
        <form action="/boiler/ligar" method="POST">
            <input type="text" name="nome" placeholder="Quem é você? (ex: CJ, Patati)" required style="padding: 10px;">
            <br><br>
            <button type="submit" style="background-color: green; color: white; padding: 15px; font-size: 18px;">🟢 LIGAR BOILER</button>
        </form>
        """
        
    return f"""
    <!-- Esse comando abaixo faz a tela atualizar sozinha a cada 30 segundos -->
    <meta http-equiv="refresh" content="30"> 
    <h2>🛁 Controle do Boiler da Arapuca</h2>
    {alerta}
    <hr>
    {botao_acao}
    <br><br><a href='/'>Voltar para o início</a>
    """

@boiler_bp.route("/ligar", methods=["POST"])
def ligar():
    nome = request.form['nome'].strip().title()
    # Pega o exato segundo em que o botão foi clicado
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
