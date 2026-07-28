from flask import Flask
from database import inicializar_db
from modulos.mercado import mercado_bp

app = Flask(__name__)

# 1. Garante que o banco de dados (o caderno) está criado
inicializar_db()

# 2. Registra a planta baixa (Blueprint) do mercado no aplicativo principal
app.register_blueprint(mercado_bp)

@app.route("/")
def home():
    return """
    <h1>🏠 ARAPUCA App - Central da República</h1>
    <ul>
        <li><a href="/mercado">🛒 Ir para o Mercado da República</a></li>
        <li><a href="/boiler">🛁 Ir para o Controle do Boiler</a></li>
    </ul>
    """

@app.route("/boiler")
def boiler():
    return """
    <h2>🛁 Controle do Boiler</h2>
    <p>Módulo em construção...</p>
    <br><a href='/'>Voltar para o início</a>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

