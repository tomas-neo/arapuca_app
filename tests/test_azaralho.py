import importlib
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HOJE = date.today()
MES = HOJE.strftime("%Y-%m")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    sys.modules.pop("app", None)
    modulo = importlib.import_module("app")
    from database import conectar_db
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)",
                     [("Oca", generate_password_hash("segredo1"), 1),
                      ("Xamã", generate_password_hash("segredo1"), 0),
                      ("Mic", generate_password_hash("segredo1"), 0)])
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    c = app.test_client()
    assert c.post("/login", data={"apelido": apelido, "senha": "segredo1"}).status_code == 302
    return c


def pontos(cliente, apelido):
    from database import conectar_db
    conn = conectar_db()
    total = conn.execute("SELECT COALESCE(SUM(pontos), 0) FROM azaralho a JOIN moradores m ON m.id = a.morador_id "
                         "WHERE m.apelido = ?", (apelido,)).fetchone()[0]
    conn.close()
    return total


def test_morador_comum_da_ponto_e_aparece_no_ranking(app):
    mic = logar(app, "Mic")
    r = mic.post("/azaralho/novo", data={"morador_id": "2", "motivo": "prato", "descricao": "panela na pia",
                                         "data": HOJE.isoformat(), "pontos": "2"})
    assert r.status_code == 302
    assert pontos(mic, "Xamã") == 2
    pagina = mic.get("/azaralho/").text
    assert "panela na pia" in pagina and "por Mic" in pagina
    assert "Você tem 2 pontos" in logar(app, "Xamã").get("/").text


def test_so_quem_deu_ou_admin_tira(app):
    mic = logar(app, "Mic")
    mic.post("/azaralho/novo", data={"morador_id": "2", "motivo": "prato", "data": HOJE.isoformat()})
    xama = logar(app, "Xamã")
    assert xama.post("/azaralho/1/apagar").status_code == 403   # o punido não tira o próprio ponto
    assert mic.post("/azaralho/1/apagar").status_code == 302
    mic.post("/azaralho/novo", data={"morador_id": "2", "motivo": "prato", "data": HOJE.isoformat()})
    assert logar(app, "Oca").post("/azaralho/2/apagar").status_code == 302
    assert pontos(mic, "Xamã") == 0


def test_validacoes(app):
    oca = logar(app, "Oca")
    amanha = (HOJE + timedelta(days=1)).isoformat()
    r = oca.post("/azaralho/novo", data={"morador_id": "2", "motivo": "prato", "data": amanha})
    assert "futuro" in oca.get(r.headers["Location"]).text
    assert oca.post("/azaralho/novo", data={"morador_id": "2", "motivo": "xyz"}).status_code == 400
    assert oca.post("/azaralho/novo", data={"morador_id": "99", "motivo": "prato"}).status_code == 400
    assert oca.post("/azaralho/novo", data={"morador_id": "2", "motivo": "prato", "data": "2026-02-30"}).status_code == 400
    assert oca.get("/azaralho/?mes=2026-13").status_code == 400
    assert pontos(oca, "Xamã") == 0


def test_nao_fez_pelas_escalas(app):
    oca = logar(app, "Oca")
    dia = (HOJE.weekday() + 1) % 7
    from database import conectar_db
    conn = conectar_db()
    passeio = conn.execute("SELECT l.id FROM escala_linhas l JOIN escalas e ON e.id = l.escala_id "
                           "WHERE e.nome = 'Passeio do Buddha'").fetchone()[0]
    roupa = conn.execute("SELECT l.id FROM escala_linhas l JOIN escalas e ON e.id = l.escala_id "
                         "WHERE e.nome = 'Lavar roupa' LIMIT 1").fetchone()[0]
    conn.close()
    oca.post("/escalas/turno", data={"linha_id": passeio, "dia": dia, "morador_id": 3})
    oca.post("/escalas/turno", data={"linha_id": roupa, "dia": dia, "morador_id": 2})

    pagina = oca.get("/azaralho/").text
    assert "Passeio do Buddha · Passeio" in pagina and "Não fez" in pagina
    assert "Lavar roupa" not in pagina          # dia de lavar roupa não dá ponto

    dados = {"morador_id": "3", "motivo": "passeio", "descricao": "Passeio do Buddha · Passeio",
             "data": HOJE.isoformat()}
    oca.post("/azaralho/novo", data=dados)
    oca.post("/azaralho/novo", data=dados)      # segundo toque não duplica
    assert pontos(oca, "Mic") == 1
    assert "Marcado" in oca.get("/azaralho/").text


def test_ranking_por_mes(app):
    oca = logar(app, "Oca")
    oca.post("/azaralho/novo", data={"morador_id": "2", "motivo": "outro", "data": "2026-01-10"})
    assert "+1" in oca.get("/azaralho/?mes=2026-01").text
    assert "Ninguém tomou ponto" in oca.get("/azaralho/?mes=2026-02").text
