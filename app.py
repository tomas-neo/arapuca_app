from flask import Flask, render_template_string

app = Flask(__name__)

# Banco de dados simulado em memória (depois passamos para um arquivo SQLite)
estoque_mercado = {
    "Papel Higiênico": 3,
    "Café": 2,
    "Leite": 5
}

status_boiler = {
    "ligado": False,
    "responsavel": "Ninguém"
}

@app.route("/")
def home():
    return """
    <h1>🏠 ARAPUCA App - Central da República</h1>
    <ul>
        <li><a href="/mercado">Ir para o Mercado da República</a></li>
        <li><a href="/boiler">Ir para o Controle do Boiler</a></li>
    </ul>
    """

@app.route("/mercado")
def mercado():
    # Mostra o status atual da dispensa
    itens_html = "".join([f"<li>{item}: {qtd} unidades</li>" for item, qtd in estoque_mercado.items()])
    return f"""
    <h2>🛒 Mercado da Arapuca</h2>
    <ul>{itens_html}</ul>
    <br><a href='/'>Voltar para o início</a>
    """

@app.route("/boiler")
def boiler():
    estado = "LIGADO ⚡" if status_boiler["ligado"] else "DESLIGADO 💤"
    return f"""
    <h2>🛁 Controle do Boiler</h2>
    <p>Status atual: <strong>{estado}</strong></p>
    <p>Último a ligar: {status_boiler['responsavel']}</p>
    <br><a href='/'>Voltar para o início</a>
    """

if __name__ == "__main__":
    # Host '0.0.0.0' significa que ele aceita visitas de outros celulares na mesma rede Wi-Fi!
    app.run(host="0.0.0.0", port=5000, debug=True)
