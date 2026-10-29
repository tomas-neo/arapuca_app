"""Logins automáticos, escalas e funças iniciais, edição pelo cargo de estrutura."""
import importlib
import json
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
    (pasta / "moradores.json").write_text(json.dumps({
        "Zangado": {"ano": 2024, "conta": True, "cargos": ["financeiro"], "quarto": "Suíte"},
        "Chuveiro": {"ano": 2023, "conta": True, "nomes": ["Chuverin"], "cargos": ["estrutura"]},
        "Chupeta": {"ano": 2025, "conta": True, "nomes": ["Xupeta"]},
        "Xama": {"ano": 2022, "nomes": ["Xamã"]},          # sem "conta": não cria
    }), encoding="utf-8")
    (pasta / "escalas.json").write_text(json.dumps({
        "Lavar roupa": {"prazo": 0, "linhas": {"1ª máquina": {"dom": ["Zangado"], "seg": ["Xupeta"]}}},
        "Limpeza": {"prazo": 1, "linhas": {"Cozinha": {}, "Sala": {}}},
    }), encoding="utf-8")
    (pasta / "funcas.json").write_text(json.dumps([
        {"nome": "Estrutura", "descricao": "Cuida da casa", "membros": ["Chuverin", "Fulano"]},
        {"nome": "Aquisição", "membros": "todos"},
    ]), encoding="utf-8")

    sys.modules.pop("app", None)
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    conn.execute("INSERT INTO moradores (apelido, senha_hash, admin) VALUES ('Oca', ?, 1)",
                 (generate_password_hash("segredo1"),))
    conn.commit()
    conn.close()
    return importlib.import_module("app").app


def entrar(app, usuario, senha):
    c = app.test_client()
    r = c.post("/login", data={"apelido": usuario, "senha": senha})
    return c, r


def sql(query, *args):
    from database import conectar_db
    conn = conectar_db()
    linhas = conn.execute(query, args).fetchall()
    conn.close()
    return linhas


def test_contas_criadas_com_senha_inicial(app):
    assert [m["apelido"] for m in sql("SELECT apelido FROM moradores ORDER BY id")] == ["Oca", "Zangado", "Chuveiro", "Chupeta"]
    zangado, r = entrar(app, "zangado", "zangado@24")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    assert "senha inicial" in zangado.get("/").text
    assert sql("SELECT q.nome FROM moradores m JOIN quartos q ON q.id = m.quarto_id WHERE apelido = 'Zangado'")[0][0] == "Suíte"
    _, r = entrar(app, "zangado", "zangado@25")
    assert r.status_code != 302
    zangado.post("/senha", data={"atual": "zangado@24", "nova": "outrasenha"})
    assert "senha inicial" not in zangado.get("/").text
    _, r = entrar(app, "Chupeta", "chupeta@25")
    assert r.status_code == 302


def test_escalas_e_funcas_iniciais(app):
    turnos = sql("""SELECT l.nome, t.dia, m.apelido FROM escala_turnos t JOIN escala_linhas l ON l.id = t.linha_id
                    JOIN moradores m ON m.id = t.morador_id ORDER BY t.dia""")
    assert [tuple(t) for t in turnos] == [("Máquina", 0, "Zangado"), ("Máquina", 1, "Chupeta")]  # Xupeta = Chupeta
    assert {l[0] for l in sql("SELECT nome FROM escala_linhas")} >= {"Cozinha", "Sala"}
    membros = sql("""SELECT f.nome, m.apelido FROM funca_membros fm JOIN funcas f ON f.id = fm.funca_id
                     JOIN moradores m ON m.id = fm.morador_id WHERE f.nome = 'Estrutura'""")
    assert [m[1] for m in membros] == ["Chuveiro"]
    assert len(sql("SELECT * FROM funca_membros fm JOIN funcas f ON f.id = fm.funca_id WHERE f.nome = 'Aquisição'")) == 4
    pagina = entrar(app, "chuveiro", "chuveiro@23")[0].get("/").text
    assert "Estrutura · Aquisição" in pagina


def test_importa_uma_vez_so(app):
    from database import conectar_db
    from modulos import casa
    conn = conectar_db()
    conn.execute("DELETE FROM escala_turnos")
    conn.commit()
    casa.importar(conn)
    conn.close()
    assert sql("SELECT COUNT(*) FROM escala_turnos")[0][0] == 0   # o que mudou no app fica


def test_estrutura_edita_escalas_e_funcas(app):
    chuveiro, _ = entrar(app, "chuveiro", "chuveiro@23")
    zangado, _ = entrar(app, "zangado", "zangado@24")
    cozinha = sql("SELECT id FROM escala_linhas WHERE nome = 'Cozinha'")[0][0]
    zid = sql("SELECT id FROM moradores WHERE apelido = 'Zangado'")[0][0]

    assert zangado.post("/escalas/turno", data={"linha_id": cozinha, "dia": 2, "morador_id": zid}).status_code == 403
    r = chuveiro.post("/escalas/turno", data={"linha_id": cozinha, "dia": 2, "morador_id": zid, "aba": "3"})
    assert r.status_code == 302 and "editar=1" in r.headers["Location"] and "aba=3" in r.headers["Location"]
    assert len(sql("SELECT * FROM escala_turnos WHERE linha_id = ? AND dia = 2", cozinha)) == 1
    chuveiro.post("/escalas/turno/remover", data={"linha_id": cozinha, "dia": 2, "morador_id": zid})
    assert len(sql("SELECT * FROM escala_turnos WHERE linha_id = ?", cozinha)) == 0

    pagina = chuveiro.get("/escalas/?editar=1").text
    assert "+ pessoa" in pagina and "Nova área" in pagina
    assert "+ pessoa" not in zangado.get("/escalas/?editar=1").text

    estrutura = sql("SELECT id FROM funcas WHERE nome = 'Estrutura'")[0][0]
    assert zangado.post(f"/funcas/{estrutura}/membro", data={"morador_id": zid}).status_code == 403
    chuveiro.post(f"/funcas/{estrutura}/membro", data={"morador_id": zid})
    assert len(sql("SELECT * FROM funca_membros WHERE funca_id = ?", estrutura)) == 2
    chuveiro.post(f"/funcas/{estrutura}/membro/{zid}/remover")
    assert len(sql("SELECT * FROM funca_membros WHERE funca_id = ?", estrutura)) == 1


def test_aba_vazia_da_planilha_nao_apaga(app):
    from modulos import planilha
    vazia = [["Passeio", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"], [], []]
    maquina = [["MÁQUINA", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
               ["1°", "Chuverin", "", "", "", "", "", ""]]
    abas = {893878957: vazia, 1189699078: vazia, 737358181: maquina}
    resultado = planilha.sincronizar(baixar=lambda _p, gid: abas[gid])
    assert any("mantive" in e for e in resultado["erros"])
    assert {l[0] for l in sql("SELECT nome FROM escala_linhas")} >= {"Cozinha", "Sala"}   # limpeza ficou
    turnos = sql("""SELECT m.apelido FROM escala_turnos t JOIN moradores m ON m.id = t.morador_id
                    JOIN escala_linhas l ON l.id = t.linha_id JOIN escalas e ON e.id = l.escala_id
                    WHERE e.nome = 'Lavar roupa'""")
    assert [t[0] for t in turnos] == ["Chuveiro"]   # Chuverin = Chuveiro
