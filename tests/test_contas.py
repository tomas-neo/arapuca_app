import importlib
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from modulos.contas import deslocar_mes, dividir, formatar, ler_valor  # noqa: E402


# ---------- regras de dinheiro ----------

def test_dividir_igual_sem_perder_centavo():
    partes = dividir(10000, {1: 1, 2: 1, 3: 1})
    assert sum(partes.values()) == 10000
    assert sorted(partes.values()) == [3333, 3333, 3334]


def test_dividir_com_peso():
    partes = dividir(350000, {1: 1, 2: 1.5, 3: 1})
    assert partes == {1: 100000, 2: 150000, 3: 100000}


def test_dividir_casos_vazios():
    assert dividir(0, {1: 1}) == {1: 0}
    assert dividir(500, {}) == {}


@pytest.mark.parametrize("texto,centavos", [
    ("1.234,56", 123456), ("1234,56", 123456), ("1234.56", 123456),
    ("R$ 80", 8000), ("80,5", 8050), ("1.234", 123400), ("0,99", 99),
])
def test_ler_valor(texto, centavos):
    assert ler_valor(texto) == centavos


@pytest.mark.parametrize("texto", ["", "abc", "1,2,3", "-5", "12.345.6"])
def test_ler_valor_invalido(texto):
    assert ler_valor(texto) is None


def test_formatar_e_meses():
    assert formatar(123456) == "R$ 1.234,56"
    assert formatar(5) == "R$ 0,05"
    assert deslocar_mes("2026-01", -1) == "2025-12"
    assert deslocar_mes("2026-12", 1) == "2027-01"


# ---------- páginas ----------

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # banco e chave ficam numa pasta temporária
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    sys.modules.pop("app", None)
    modulo = importlib.import_module("app")
    from database import conectar_db
    conn = conectar_db()
    conn.executemany(
        "INSERT INTO moradores (apelido, senha_hash, admin, peso) VALUES (?, ?, ?, ?)",
        [("Oca", generate_password_hash("segredo1"), 1, 1),
         ("Xamã", generate_password_hash("segredo1"), 0, 1.5),
         ("Mic", generate_password_hash("segredo1"), 0, 1)],
    )
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    cliente = app.test_client()
    assert cliente.post("/login", data={"apelido": apelido, "senha": "segredo1"}).status_code == 302
    return cliente


def test_fluxo_do_mes(app):
    admin = logar(app, "Oca")
    for desc, valor in [("Aluguel", "3.000,00"), ("Luz", "350,00"), ("Internet", "150")]:
        admin.post("/contas/nova?mes=2026-10", data={"descricao": desc, "valor": valor})

    pagina = admin.get("/contas/?mes=2026-10").text
    assert "R$ 3.500,00" in pagina          # total
    assert "R$ 1.000,00" in pagina          # parte de quem tem peso 1
    assert "R$ 1.500,00" in pagina          # parte de quem tem peso 1,5

    admin.post("/contas/fechar?mes=2026-10")
    # Mudar o peso depois de fechar não mexe no mês fechado
    from database import conectar_db
    conn = conectar_db()
    conn.execute("UPDATE moradores SET peso = 1")
    xama = conn.execute("SELECT id FROM moradores WHERE apelido = 'Xamã'").fetchone()[0]
    conn.commit()
    conn.close()

    morador = logar(app, "Xamã")
    pagina = morador.get("/contas/?mes=2026-10").text
    assert "R$ 1.500,00" in pagina and "Ainda não pago" in pagina
    assert "Lançar conta" not in pagina      # morador comum não lança conta

    admin.post(f"/contas/pago/{xama}?mes=2026-10")
    assert "✅ Pago" in morador.get("/contas/?mes=2026-10").text

    # Mês fechado não aceita conta nova
    r = admin.post("/contas/nova?mes=2026-10", data={"descricao": "Gás", "valor": "100"})
    assert "fechado" in r.headers["Location"]


def test_morador_comum_nao_mexe_nas_contas(app):
    morador = logar(app, "Mic")
    assert morador.post("/contas/nova?mes=2026-10", data={"descricao": "x", "valor": "10"}).status_code == 403
    assert morador.post("/contas/fechar?mes=2026-10").status_code == 403


def test_mes_invalido(app):
    assert logar(app, "Oca").get("/contas/?mes=2026-13").status_code == 400


def test_valor_invalido_mostra_erro(app):
    admin = logar(app, "Oca")
    r = admin.post("/contas/nova?mes=2026-10", data={"descricao": "Luz", "valor": "dez reais"})
    assert "Valor+inv" in r.headers["Location"]
