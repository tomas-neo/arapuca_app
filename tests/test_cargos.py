import importlib
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    sys.modules.pop("app", None)
    modulo = importlib.import_module("app")
    from database import conectar_db
    conn = conectar_db()
    senha = generate_password_hash("segredo1")
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin, cargos, quarto_id) VALUES (?, ?, ?, ?, 1)", [
        ("Oca", senha, 1, ""), ("Zangado", senha, 0, "financeiro"),
        ("Kiko", senha, 0, "mercado"), ("Alek", senha, 0, None)])
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    c = app.test_client()
    c.post("/login", data={"apelido": apelido, "senha": "segredo1"})
    return c


def id_de(apelido):
    from database import conectar_db
    conn = conectar_db()
    linha = conn.execute("SELECT id FROM moradores WHERE apelido = ?", (apelido,)).fetchone()
    conn.close()
    return linha[0]


def contas_do_mes():
    from database import conectar_db
    conn = conectar_db()
    n = conn.execute("SELECT COUNT(*) FROM contas WHERE mes = '2026-10'").fetchone()[0]
    conn.close()
    return n


def test_financeiro_lanca_contas_e_os_outros_nao(app):
    conta = {"descricao": "Luz", "valor": "610", "tipo": "despesa"}
    assert logar(app, "Alek").post("/contas/nova?mes=2026-10", data=conta).status_code == 403
    assert logar(app, "Kiko").post("/contas/nova?mes=2026-10", data=conta).status_code == 403
    assert contas_do_mes() == 0
    zangado = logar(app, "Zangado")
    zangado.post("/contas/nova?mes=2026-10", data=conta)
    assert contas_do_mes() == 1
    assert "Lançar" in zangado.get("/contas/?mes=2026-10").text
    assert "Lançar" not in logar(app, "Alek").get("/contas/?mes=2026-10").text
    logar(app, "Oca").post("/contas/nova?mes=2026-10", data={**conta, "descricao": "Sinuca"})
    assert contas_do_mes() == 2   # root pode tudo


def test_so_root_mexe_em_moradores(app):
    zangado = logar(app, "Zangado")
    assert zangado.get("/moradores/").status_code == 403
    assert zangado.post(f"/moradores/{id_de('Alek')}/quarto", data={"quarto_id": "2"}).status_code == 403
    assert logar(app, "Oca").get("/moradores/").status_code == 200


def test_root_distribui_cargos(app):
    oca = logar(app, "Oca")
    oca.post(f"/moradores/{id_de('Alek')}/cargos", data={"cargo_financeiro": "1", "cargo_estrutura": "1"})
    assert logar(app, "Alek").post("/contas/nova?mes=2026-10", data={"descricao": "Internet", "valor": "130", "tipo": "despesa"}).status_code == 302
    assert contas_do_mes() == 1
    assert "Financeiro · Estrutura" in logar(app, "Alek").get("/senha").text
    oca.post(f"/moradores/{id_de('Oca')}/cargos", data={})   # root não se rebaixa
    assert logar(app, "Oca").get("/moradores/").status_code == 200
    assert logar(app, "Zangado").post(f"/moradores/{id_de('Zangado')}/cargos", data={"root": "1"}).status_code == 403


def test_mercado_cuida_dos_itens(app):
    item = {"nome": "Café solúvel", "local": "Mercado", "categoria": "essencial", "unidade": "un", "qtd_mensal": "2"}
    assert logar(app, "Zangado").post("/mercado/itens/novo", data=item).status_code == 403
    assert logar(app, "Kiko").post("/mercado/itens/novo", data=item).status_code == 302
    assert "Café solúvel" in logar(app, "Alek").get("/mercado/?aba=compra").text
