import importlib
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modulos.mercado import formatar_qtd, ler_qtd  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    sys.modules.pop("app", None)
    modulo = importlib.import_module("app")
    from database import conectar_db
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)",
                     [("Oca", generate_password_hash("segredo1"), 1), ("Mic", generate_password_hash("segredo1"), 0)])
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    c = app.test_client()
    c.post("/login", data={"apelido": apelido, "senha": "segredo1"})
    return c


def item(nome):
    from database import conectar_db
    conn = conectar_db()
    linha = conn.execute("SELECT * FROM mercado_itens WHERE nome = ?", (nome,)).fetchone()
    conn.close()
    return linha


def test_quantidades():
    assert ler_qtd("2,5") == 2.5 and ler_qtd("25") == 25 and ler_qtd("0") is None and ler_qtd("abc") is None
    assert formatar_qtd(25.0) == "25" and formatar_qtd(0.75) == "0,75"


def test_lista_da_planilha(app):
    assert item("Arroz")["qtd_mensal"] == 25 and item("Arroz")["unidade"] == "kg"
    assert item("Páprica defumada")["local"] == "Loja de tempero"
    pagina = logar(app, "Mic").get("/mercado/?aba=compra").text
    assert "sempre 25 kg" in pagina and "Hortifrúti" in pagina


def test_compra_mensal_reposicao_e_uso(app):
    mic = logar(app, "Mic")
    arroz, cafe, oleo = item("Arroz")["id"], item("Café")["id"], item("Óleo")["id"]

    r = mic.post("/mercado/compra", data={f"qtd_{arroz}": "25", f"qtd_{cafe}": "2,5", f"qtd_{oleo}": ""})
    assert "Compra mensal registrada: 2 itens" in mic.get(r.headers["Location"]).text
    assert item("Arroz")["estoque"] == 25 and item("Café")["estoque"] == 2.5 and item("Óleo")["estoque"] == 0

    mic.post("/mercado/reposicao", data={"item_id": [str(cafe), str(oleo)], "qtd": ["1", "0,9"]})
    assert item("Café")["estoque"] == 3.5 and item("Óleo")["estoque"] == 0.9

    mic.post(f"/mercado/usar/{oleo}")                  # usa 1, mas só tinha 0,9
    assert item("Óleo")["estoque"] == 0
    mic.post("/mercado/usar", data={"item_id": str(arroz), "qtd": "2"})
    assert item("Arroz")["estoque"] == 23

    pagina = mic.get("/mercado/").text
    assert "Pra comprar" in pagina and "Acabou" in pagina    # óleo zerado aparece na lista de compra


def test_desfazer(app):
    mic = logar(app, "Mic")
    cafe = item("Café")["id"]
    mic.post("/mercado/reposicao", data={"item_id": [str(cafe)], "qtd": ["2"]})
    mic.post(f"/mercado/usar/{cafe}")
    from database import conectar_db
    conn = conectar_db()
    uso, repo = [r[0] for r in conn.execute("SELECT id FROM mercado_movimentos ORDER BY id DESC")]
    conn.close()
    oca = logar(app, "Oca")
    assert mic.post(f"/mercado/movimento/{uso}/desfazer").status_code == 302
    assert item("Café")["estoque"] == 2
    assert oca.post(f"/mercado/movimento/{repo}/desfazer").status_code == 302   # admin pode desfazer de outro
    assert item("Café")["estoque"] == 0


def test_validacoes_e_itens(app):
    mic = logar(app, "Mic")
    cafe = item("Café")["id"]
    r = mic.post("/mercado/compra", data={f"qtd_{cafe}": "muito"})
    assert "Quantidade inválida" in mic.get(r.headers["Location"]).text
    r = mic.post("/mercado/compra", data={})
    assert "pelo menos um item" in mic.get(r.headers["Location"]).text
    assert mic.post("/mercado/itens/novo", data={"nome": "Leite"}).status_code == 403

    oca = logar(app, "Oca")
    oca.post("/mercado/itens/novo", data={"nome": "Leite", "local": "Mercado", "categoria": "repor_sempre",
                                          "unidade": "L", "qtd_mensal": "12"})
    assert item("Leite")["qtd_mensal"] == 12
    oca.post(f"/mercado/itens/{item('Leite')['id']}/remover")
    assert "Leite" not in oca.get("/mercado/").text
