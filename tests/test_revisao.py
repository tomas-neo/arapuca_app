"""Revisão de qualidade: login tolerante, freio de senha, reset pelo root, cabeçalhos, erros e boiler."""
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
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin, ano) VALUES (?, ?, ?, ?)",
                     [("Oca", generate_password_hash("segredo1"), 1, 2025),
                      ("Cidão", generate_password_hash("segredo1"), 0, 2026),
                      ("Kiko", generate_password_hash("segredo1"), 0, None)])
    conn.commit()
    conn.close()
    from modulos import auth
    auth._erros_login.clear()
    return importlib.import_module("app").app


def entrar(app, apelido, senha="segredo1"):
    c = app.test_client()
    return c, c.post("/login", data={"apelido": apelido, "senha": senha})


def id_de(apelido):
    from database import conectar_db
    conn = conectar_db()
    linha = conn.execute("SELECT id FROM moradores WHERE apelido = ?", (apelido,)).fetchone()
    conn.close()
    return linha["id"]


@pytest.mark.parametrize("digitado", ["Cidão", "cidao", "CIDAO", " cidão ", "Cidao"])
def test_login_aceita_acento_e_maiuscula(app, digitado):
    _, r = entrar(app, digitado)
    assert r.status_code == 302 and "/login" not in r.headers["Location"]


def test_freio_depois_de_5_erros(app):
    for _ in range(5):
        assert entrar(app, "kiko", "errada")[1].status_code == 401
    _, r = entrar(app, "kiko")   # até a senha certa espera
    assert r.status_code == 429 and "Muitas tentativas" in r.text
    assert entrar(app, "oca")[1].status_code == 302   # os outros continuam entrando


def test_root_reseta_senha(app):
    root, _ = entrar(app, "oca")
    r = root.post(f"/moradores/{id_de('Cidão')}/senha", follow_redirects=True)
    assert "cidao@26" in r.text
    c, r = entrar(app, "cidao", "cidao@26")
    assert r.status_code == 302
    assert "senha inicial" in c.get("/").text   # aviso pra trocar
    # sem ano não dá pra montar a senha inicial
    r = root.post(f"/moradores/{id_de('Kiko')}/senha", follow_redirects=True)
    assert "Coloque o ano de Kiko" in r.text


def test_so_root_reseta_senha(app):
    c, _ = entrar(app, "kiko")
    assert c.post(f"/moradores/{id_de('Cidão')}/senha").status_code == 403
    assert entrar(app, "cidao")[1].status_code == 302   # senha não mudou


def test_cabecalhos_de_seguranca(app):
    c, _ = entrar(app, "oca")
    r = c.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"


def test_pagina_404_amigavel(app):
    c, _ = entrar(app, "oca")
    r = c.get("/nao-existe")
    assert r.status_code == 404 and "Página não encontrada" in r.text and "Voltar ao início" in r.text


def test_boiler_liga_e_desliga(app):
    app.config["BOILER_ATIVO"] = True
    c, _ = entrar(app, "oca")
    c.post("/boiler/ligar")
    from database import conectar_db
    conn = conectar_db()
    assert conn.execute("SELECT status, responsavel FROM boiler").fetchone()[:] == ("LIGADO", "Oca")
    conn.close()
    c.post("/boiler/desligar")
    conn = conectar_db()
    assert conn.execute("SELECT status FROM boiler").fetchone()[0] == "DESLIGADO"
    conn.close()


def test_sem_modo_debug_por_padrao():
    texto = (Path(__file__).resolve().parent.parent / "app.py").read_text()
    assert 'os.environ.get("ARAPUCA_DEBUG") == "1"' in texto
