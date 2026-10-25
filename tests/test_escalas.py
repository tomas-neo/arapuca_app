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
    conn.executemany(
        "INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)",
        [("Oca", generate_password_hash("segredo1"), 1), ("Olinda", generate_password_hash("segredo1"), 0)],
    )
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    cliente = app.test_client()
    cliente.post("/login", data={"apelido": apelido, "senha": "segredo1"})
    return cliente


def ids(sql, *args):
    from database import conectar_db
    conn = conectar_db()
    row = conn.execute(sql, args).fetchone()
    conn.close()
    return row[0]


def test_escalas_padrao_da_planilha(app):
    pagina = logar(app, "Olinda").get("/escalas/").text
    for nome in ["Limpeza", "Passeio do Buddha", "Lavar roupa"]:
        assert nome in pagina
    assert "Escalar" not in pagina  # morador comum só vê


def test_suas_funcoes_com_prazo(app):
    from datetime import date
    from modulos.escalas import minhas_funcoes
    admin = logar(app, "Oca")
    cozinha = ids("SELECT id FROM escala_linhas WHERE nome = 'Cozinha'")
    passeio = ids("SELECT id FROM escala_linhas WHERE nome = 'Passeio'")
    olinda = ids("SELECT id FROM moradores WHERE apelido = 'Olinda'")
    admin.post("/escalas/turno", data={"linha_id": cozinha, "dia": 2, "morador_id": olinda})   # terça
    admin.post("/escalas/turno", data={"linha_id": cozinha, "dia": 2, "morador_id": olinda})   # repetido não duplica
    admin.post("/escalas/turno", data={"linha_id": passeio, "dia": 2, "morador_id": olinda})
    assert ids("SELECT COUNT(*) FROM escala_turnos") == 2

    terca, quarta, quinta = date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 29)
    no_dia = {f["linha"]: f["prazo"] for f in minhas_funcoes(olinda, terca)}
    assert no_dia == {"Passeio": "Hoje", "Cozinha": "Hoje ou amanhã"}
    dia_seguinte = {f["linha"]: f["prazo"] for f in minhas_funcoes(olinda, quarta)}
    assert dia_seguinte == {"Cozinha": "Último dia (era de terça)"}   # limpeza ganha +1 dia, passeio não
    assert minhas_funcoes(olinda, quinta) == []

    admin.post("/escalas/turno/remover", data={"linha_id": cozinha, "dia": 2, "morador_id": olinda})
    assert [f["linha"] for f in minhas_funcoes(olinda, terca)] == ["Passeio"]
    assert "Folga" in logar(app, "Oca").get("/").text


def test_morador_comum_nao_edita(app):
    morador = logar(app, "Olinda")
    assert morador.post("/escalas/turno", data={"linha_id": 1, "dia": 0, "morador_id": 1}).status_code == 403
    assert morador.post("/escalas/nova", data={"nome": "Lixo"}).status_code == 403


def test_dados_invalidos(app):
    admin = logar(app, "Oca")
    assert admin.post("/escalas/turno", data={"linha_id": 1, "dia": 9, "morador_id": 1}).status_code == 400
    assert admin.post("/escalas/turno", data={"linha_id": 999, "dia": 1, "morador_id": 1}).status_code == 400


def test_nova_escala_e_linha(app):
    admin = logar(app, "Oca")
    admin.post("/escalas/nova", data={"nome": "Tirar o lixo", "icone": "🗑️"})
    lixo = ids("SELECT id FROM escalas WHERE nome = 'Tirar o lixo'")
    admin.post(f"/escalas/{lixo}/linha", data={"nome": "Orgânico"})
    r = admin.post(f"/escalas/{lixo}/linha", data={"nome": "Orgânico"})
    assert "erro=" in r.headers["Location"]
    linha = ids("SELECT id FROM escala_linhas WHERE nome = 'Orgânico'")
    admin.post("/escalas/turno", data={"linha_id": linha, "dia": 3, "morador_id": 1})
    admin.post(f"/escalas/linha/{linha}/apagar")
    assert ids("SELECT COUNT(*) FROM escala_turnos") == 0  # turnos saem junto com a linha


def test_dia_de_hoje_comeca_no_domingo():
    from datetime import date
    import modulos.escalas as escalas
    domingo = date(2026, 10, 25)  # 25/10/2026 é domingo
    assert (domingo.weekday() + 1) % 7 == 0
    assert escalas.DIAS[0] == "Domingo"
