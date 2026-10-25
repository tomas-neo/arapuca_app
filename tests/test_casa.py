import importlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modulos.casa import formatar_ano  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    pasta = tmp_path / "dados_iniciais"
    (pasta / "fotos").mkdir(parents=True)
    (pasta / "moradores.json").write_text(json.dumps({
        "Oca": {"ano": 2025, "saldo": -824.99, "nomes": ["Cabeça Oca"]},
        "Mictorio": {"ano": 2024, "saldo": -1019.27, "nomes": ["Mic"]},
        "Xama": {"ano": 2022, "saldo": 9.5, "nomes": ["Xamã"]},
    }), encoding="utf-8")
    Image.new("RGB", (600, 400), "orange").save(pasta / "fotos" / "Oca.png")
    Image.new("RGB", (300, 300), "blue").save(pasta / "fotos" / "Xama.jpg")

    sys.modules.pop("app", None)
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)",
                     [("Oca", generate_password_hash("segredo1"), 1), ("Mic", generate_password_hash("segredo1"), 0)])
    conn.commit()
    conn.close()
    return importlib.import_module("app").app  # importar o app roda a importação


def logar(app, apelido):
    c = app.test_client()
    c.post("/login", data={"apelido": apelido, "senha": "segredo1"})
    return c


def morador(apelido):
    from database import conectar_db
    conn = conectar_db()
    linha = conn.execute("SELECT * FROM moradores WHERE apelido = ?", (apelido,)).fetchone()
    conn.close()
    return linha


def test_formatar_ano():
    assert formatar_ano(2022) == "022" and formatar_ano(2026) == "026" and formatar_ano(None) == ""


def test_importa_ano_saldo_e_foto(app):
    oca, mic = morador("Oca"), morador("Mic")
    assert oca["ano"] == 2025 and oca["saldo_anterior_centavos"] == -82499 and oca["foto_versao"]
    assert mic["ano"] == 2024 and mic["saldo_anterior_centavos"] == -101927 and not mic["foto_versao"]
    with Image.open(f"fotos/{oca['id']}.jpg") as foto:
        assert foto.size == (320, 320)


def test_nao_sobrescreve_o_que_mudou(app):
    from database import conectar_db
    from modulos import casa
    conn = conectar_db()
    conn.execute("UPDATE moradores SET saldo_anterior_centavos = 0, ano = 2023 WHERE apelido = 'Oca'")
    conn.commit()
    casa.importar(conn)
    conn.close()
    assert morador("Oca")["saldo_anterior_centavos"] == 0 and morador("Oca")["ano"] == 2023


def test_morador_novo_ja_entra_com_foto(app):
    admin = logar(app, "Oca")
    admin.post("/moradores/novo", data={"apelido": "Xamã", "senha": "segredo1"})
    xama = morador("Xamã")
    assert xama["ano"] == 2022 and xama["saldo_anterior_centavos"] == 950 and xama["foto_versao"]


def test_home_com_foto_ano_e_funcoes(app):
    pagina = logar(app, "Oca").get("/").text
    assert "Olá, Oca" in pagina and ">025<" in pagina and "Você não tem funções hoje" in pagina
    assert "/fotos/" in pagina


def test_divida_em_contas(app):
    pagina = logar(app, "Mic").get("/contas/").text
    assert "Sua dívida com a rep" in pagina and "R$ 1.019,27" in pagina
    pagina = logar(app, "Oca").get("/contas/").text
    assert "R$ 824,99" in pagina and "1.019,27" not in pagina   # cada um vê só a sua


def test_admin_edita_ano_e_saldo(app):
    admin = logar(app, "Oca")
    mic_id = morador("Mic")["id"]
    admin.post(f"/moradores/{mic_id}/dados", data={"ano": "024", "sentido": "credito", "saldo": "10,50"})
    assert morador("Mic")["ano"] == 2024 and morador("Mic")["saldo_anterior_centavos"] == 1050
    pagina = logar(app, "Mic").get("/contas/").text
    assert "A rep te deve" in pagina and "R$ 10,50" in pagina
    assert logar(app, "Mic").post(f"/moradores/{mic_id}/dados", data={"ano": "2020"}).status_code in (302, 403)
    assert morador("Mic")["ano"] == 2024   # só admin muda


def test_busca_no_mercado(app):
    pagina = logar(app, "Mic").get("/mercado/").text
    assert "var ITENS = [" in pagina and "Arroz" in pagina and "ligarBusca" in pagina
