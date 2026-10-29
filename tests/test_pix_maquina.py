"""Pix do aluguel em Contas e uma máquina de lavar só."""
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    pasta = tmp_path / "dados_iniciais"
    pasta.mkdir()
    (pasta / "casa.json").write_text(json.dumps({"pix_aluguel": "dono@exemplo.com"}), encoding="utf-8")
    sys.modules.pop("app", None)
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin, cargos) VALUES (?, ?, ?, ?)",
                     [("Oca", generate_password_hash("segredo1"), 1, ""),
                      ("Zangado", generate_password_hash("segredo1"), 0, "financeiro"),
                      ("Kiko", generate_password_hash("segredo1"), 0, "")])
    conn.commit()
    conn.close()
    return importlib.import_module("app").app


def logar(app, apelido):
    c = app.test_client()
    c.post("/login", data={"apelido": apelido, "senha": "segredo1"})
    return c


def test_pix_aparece_pra_todos(app):
    pagina = logar(app, "Kiko").get("/contas/").text
    assert "Pix do aluguel" in pagina and "dono@exemplo.com" in pagina and "data-copiar" in pagina
    assert "Trocar a chave pix" not in pagina   # quem não é do financeiro só vê


def test_financeiro_troca_pix(app):
    zangado = logar(app, "Zangado")
    assert "Trocar a chave pix" in zangado.get("/contas/").text
    zangado.post("/contas/pix", data={"pix": "novo@exemplo.com"})
    assert "novo@exemplo.com" in logar(app, "Kiko").get("/contas/").text
    assert logar(app, "Kiko").post("/contas/pix", data={"pix": "golpe"}).status_code in (302, 403)
    assert "golpe" not in logar(app, "Kiko").get("/contas/").text

    from database import conectar_db
    from modulos import casa
    conn = conectar_db()
    casa.importar(conn)   # reiniciar o app não volta a chave antiga
    conn.close()
    assert "novo@exemplo.com" in logar(app, "Kiko").get("/contas/").text


def test_banco_antigo_junta_as_maquinas(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    # simula o banco de antes: 1ª e 2ª máquina com gente
    conn.execute("DELETE FROM config WHERE chave = 'maquina_unica_em'")
    lavar = conn.execute("SELECT id FROM escalas WHERE nome = 'Lavar roupa'").fetchone()[0]
    conn.execute("DELETE FROM escala_linhas WHERE escala_id = ?", (lavar,))
    a = conn.execute("INSERT INTO escala_linhas (escala_id, nome) VALUES (?, '1ª máquina')", (lavar,)).lastrowid
    b = conn.execute("INSERT INTO escala_linhas (escala_id, nome) VALUES (?, '2ª máquina')", (lavar,)).lastrowid
    m1 = conn.execute("INSERT INTO moradores (apelido, senha_hash) VALUES ('A', 'x')").lastrowid
    m2 = conn.execute("INSERT INTO moradores (apelido, senha_hash) VALUES ('B', 'x')").lastrowid
    conn.executemany("INSERT INTO escala_turnos VALUES (?, ?, ?)", [(a, 0, m1), (b, 0, m2), (b, 3, m2)])
    conn.commit()
    conn.close()

    inicializar_db()
    conn = sqlite3.connect("arapuca.db")
    linhas = conn.execute("SELECT nome FROM escala_linhas WHERE escala_id = ?", (lavar,)).fetchall()
    turnos = conn.execute("SELECT dia, morador_id FROM escala_turnos ORDER BY dia, morador_id").fetchall()
    conn.close()
    assert linhas == [("Máquina",)]
    assert turnos == [(0, m1), (0, m2), (3, m2)]


def test_planilha_com_duas_maquinas_vira_uma():
    from modulos.planilha import juntar_maquinas
    grade = {"1ª máquina": {0: ["Olinda"], 1: ["Xamã"]}, "2ª máquina": {0: ["Chuveiro"], 1: []}}
    assert juntar_maquinas(grade) == {"Máquina": {0: ["Olinda", "Chuveiro"], 1: ["Xamã"]}}
