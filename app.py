from flask import Flask
from database import inicializar_db
from modulos.mercado import mercado_bp
from modulos.boiler import boiler_bp
from estilo import renderizar_pagina # <--- Importamos a mágica aqui!

app = Flask(__name__)

inicializar_db()

app.register_blueprint(mercado_bp)
app.register_blueprint(boiler_bp)

@app.route("/")
def home():
    # Aqui a gente monta só o "miolo" da página inicial
    conteudo = """
    <h1>🏠 ARAPUCA App</h1>
    <p>Central de Controle da República</p>
    <br>
    <a href="/mercado" class="botao-menu">🛒 Mercado (Dispensa)</a>
    <a href="/boiler" class="botao-menu">🛁 Controle do Boiler</a>
    """
    
    # E aqui passamos o miolo para a nossa função que envelopa com o visual moderno!
    return renderizar_pagina("Arapuca App", conteudo)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
