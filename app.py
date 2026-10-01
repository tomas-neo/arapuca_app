from flask import Flask
from database import inicializar_db
from modulos.mercado import mercado_bp
from modulos.boiler import boiler_bp
from estilo import renderizar_pagina

app = Flask(__name__)

inicializar_db()

app.register_blueprint(mercado_bp)
app.register_blueprint(boiler_bp)

@app.route("/")
def home():
    conteudo = """
    <h1>🏠 ARAPUCA App</h1>
    <p>Central de Controle da República</p>
    <br>
    <a href="/mercado" class="botao-menu">🛒 Mercado (Dispensa)</a>
    <a href="/boiler" class="botao-menu">🛁 Controle do Boiler</a>
    """
    return renderizar_pagina("Arapuca App", conteudo)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
