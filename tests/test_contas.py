import importlib
import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from modulos.contas import calcular_mes, deslocar_mes, formatar, ler_valor  # noqa: E402

# Outubro/2026 da planilha "Financeiro Arapuca 2K26": quarto, ponderação, vagas, moradores e total esperado
OUTUBRO = [
    ("Zoológico", 0.18, 4, ["Kiko", "cidão", "alek"], 80538),
    ("Nós Fumamos", 0.153, 3, ["Xamã", "Cariok", "xupeta"], 82364),
    ("Suíte", 0.2, 3, ["Chuverin", "maroto", "Zangado"], 87132),
    ("Motel", 0.112, 2, ["Oca", "Buah"], 83886),
    ("Produção", 0.115, 1, ["Olinda"], 101840),
    ("Mega house", 0.08, 1, ["Mic"], 91189),
    ("Laboratório", 0.089, 1, ["Féla"], 93928),
    ("Açougue", 0.071, 1, ["Araraquaro"], 88450),
]


def quartos_de_outubro():
    quartos, ids = [], iter(range(1, 100))
    for nome, pond, vagas, moradores, _ in OUTUBRO:
        quartos.append({"nome": nome, "ponderacao": pond, "vagas": vagas,
                        "moradores": [{"id": next(ids), "apelido": m} for m in moradores]})
    return quartos


# ---------- regra da planilha ----------

def test_outubro_bate_com_a_planilha():
    # aluguel 6.086,25; despesas (água, luz, Dona Eleonora, internet...) 6.851,95; caixinha 50
    linhas, avisos = calcular_mes(608625, 685195, quartos_de_outubro(), 5000)
    assert avisos == []
    assert len(linhas) == 16  # 15 moradores + a vaga livre do Zoológico
    esperado = {}
    for nome, _, _, moradores, total in OUTUBRO:
        for m in moradores:
            esperado[m] = total
    assert {l["apelido"]: l["total_centavos"] for l in linhas if l["apelido"]} == esperado
    vaga = [l for l in linhas if l["morador_id"] is None]
    assert len(vaga) == 1 and vaga[0]["quarto"] == "Zoológico" and vaga[0]["total_centavos"] == 80538


def test_partes_somam_o_total():
    linhas, _ = calcular_mes(608625, 685195, quartos_de_outubro(), 5000)
    for l in linhas:
        assert l["casa_centavos"] + l["despesas_centavos"] + l["caixinha_centavos"] == l["total_centavos"]
    # cada um arredonda sozinho como na planilha: a soma fica a no máximo 1 centavo por vaga
    assert abs(sum(l["casa_centavos"] + l["despesas_centavos"] for l in linhas) - (608625 + 685195)) <= 16


def test_ajustes_somam_e_descontam():
    quartos = quartos_de_outubro()
    olinda = quartos[4]["moradores"][0]["id"]
    linhas, _ = calcular_mes(608625, 685195, quartos, 5000, ajustes={olinda: -2000})
    assert next(l for l in linhas if l["morador_id"] == olinda)["total_centavos"] == 101840 - 2000


def test_avisos_de_quarto_lotado_e_ponderacao():
    quartos = [{"nome": "A", "ponderacao": 0.5, "vagas": 1, "moradores": [{"id": 1, "apelido": "x"}, {"id": 2, "apelido": "y"}]},
               {"nome": "B", "ponderacao": 0.3, "vagas": 1, "moradores": []}]
    linhas, avisos = calcular_mes(100000, 0, quartos, 0)
    assert len(linhas) == 3  # quarto lotado conta os dois moradores
    assert any("A tem 2 moradores" in a for a in avisos)
    assert any("somam 0.800" in a for a in avisos)
    assert abs(sum(l["total_centavos"] for l in linhas) - 100000) <= 3  # proporção corrigida


def test_sem_quartos():
    assert calcular_mes(1000, 0, [], 5000) == ([], ["Cadastre os quartos para dividir as contas"])


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
    assert formatar(-5) == "-R$ 0,05"
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
    # deixa só dois quartos para a conta ficar simples: A (0,6, 2 vagas) e B (0,4, 1 vaga)
    conn.execute("DELETE FROM quartos")
    conn.executemany("INSERT INTO quartos (id, nome, ponderacao, vagas) VALUES (?, ?, ?, ?)",
                     [(1, "A", 0.6, 2), (2, "B", 0.4, 1)])
    conn.executemany(
        "INSERT INTO moradores (apelido, senha_hash, admin, quarto_id) VALUES (?, ?, ?, ?)",
        [("Oca", generate_password_hash("segredo1"), 1, 1),
         ("Xamã", generate_password_hash("segredo1"), 0, 1),
         ("Mic", generate_password_hash("segredo1"), 0, 2)],
    )
    conn.commit()
    conn.close()
    return modulo.app


def logar(app, apelido):
    cliente = app.test_client()
    assert cliente.post("/login", data={"apelido": apelido, "senha": "segredo1"}).status_code == 302
    return cliente


def lancar_outubro(admin):
    admin.post("/contas/nova?mes=2026-10", data={"tipo": "aluguel", "descricao": "Aluguel", "valor": "3.000,00"})
    admin.post("/contas/nova?mes=2026-10", data={"tipo": "despesa", "descricao": "Luz", "valor": "300"})
    # caixinha 50: área comum 1500/3 = 500; quartos 1500: A 900/2 = 450, B 600; despesas 100
    # Oca e Xamã: 500 + 450 + 100 + 50 = 1.100 | Mic: 500 + 600 + 100 + 50 = 1.250


def test_fluxo_do_mes(app):
    admin = logar(app, "Oca")
    lancar_outubro(admin)
    pagina = admin.get("/contas/?mes=2026-10").text
    assert "R$ 1.100,00" in pagina and "R$ 1.250,00" in pagina
    assert "Prévia" in pagina

    admin.post("/contas/fechar?mes=2026-10")
    # mudar quarto depois de fechar não mexe no mês fechado
    admin.post("/moradores/3/quarto", data={"quarto_id": "1"})
    pagina = admin.get("/contas/?mes=2026-10").text
    assert "R$ 1.250,00" in pagina and "Reabrir" in pagina

    # mês fechado não aceita conta nova
    r = admin.post("/contas/nova?mes=2026-10", data={"tipo": "despesa", "descricao": "Gás", "valor": "10"})
    assert "fechado" in admin.get(r.headers["Location"]).text


def test_ajuste_e_saldo(app):
    admin = logar(app, "Oca")
    lancar_outubro(admin)
    admin.post("/contas/ajuste?mes=2026-10", data={"morador_id": "3", "tipo": "pendencia", "valor": "40"})
    admin.post("/contas/ajuste?mes=2026-10", data={"morador_id": "3", "tipo": "desconto", "descricao": "Comprou cloro", "valor": "15"})
    admin.post("/contas/fechar?mes=2026-10")

    mic = logar(app, "Mic")
    pagina = mic.get("/contas/?mes=2026-10").text
    assert "R$ 1.275,00" in pagina          # 1.250 + 40 − 15
    assert "Ainda não pago" in pagina

    from database import conectar_db
    conn = conectar_db()
    vaga = conn.execute("SELECT vaga FROM fechamentos WHERE morador_id = 3").fetchone()[0]
    conn.close()
    admin.post(f"/contas/pagamento/{vaga}?mes=2026-10", data={"valor": "1.000,00"})
    pagina = mic.get("/contas/?mes=2026-10").text
    assert "Pagou R$ 1.000,00" in pagina and "-R$ 275,00" in pagina   # saldo devendo

    admin.post(f"/contas/pagamento/{vaga}?mes=2026-10", data={"valor": ""})  # vazio = pagou tudo
    pagina = mic.get("/contas/?mes=2026-10").text
    assert "✅ Pago" in pagina and "Saldo" not in pagina


def test_vaga_livre_aparece(app):
    admin = logar(app, "Oca")
    admin.post("/moradores/2/ativo")  # Xamã sai, sobra uma vaga no quarto A
    lancar_outubro(admin)
    assert "Vaga livre" in admin.get("/contas/?mes=2026-10").text


def test_morador_comum_nao_lanca(app):
    mic = logar(app, "Mic")
    r = mic.post("/contas/nova?mes=2026-10", data={"tipo": "despesa", "descricao": "Luz", "valor": "300"})
    assert r.status_code == 403
    assert mic.post("/contas/fechar?mes=2026-10").status_code == 403
    assert mic.post("/moradores/quartos/1", data={"nome": "A", "ponderacao": "1", "vagas": "2"}).status_code == 403


def test_reabrir(app):
    admin = logar(app, "Oca")
    lancar_outubro(admin)
    admin.post("/contas/fechar?mes=2026-10")
    admin.post("/contas/reabrir?mes=2026-10")
    assert "Prévia" in admin.get("/contas/?mes=2026-10").text


def test_mes_invalido(app):
    admin = logar(app, "Oca")
    assert admin.get("/contas/?mes=2026-13").status_code == 400


def test_quartos_e_config(app):
    admin = logar(app, "Oca")
    assert admin.post("/moradores/quartos/novo", data={"nome": "C", "ponderacao": "0,2", "vagas": "1"}).status_code == 302
    r = admin.post("/moradores/quartos/novo", data={"nome": "D", "ponderacao": "2", "vagas": "1"})
    assert "Ponderação" in admin.get(r.headers["Location"]).text
    admin.post("/moradores/config", data={"caixinha": "60,00", "fracao_comum": "50"})
    pagina = admin.get("/moradores/").text
    assert "R$ 60,00" in pagina and "1,200" in pagina   # soma das ponderações avisada


def test_migra_banco_antigo(tmp_path, monkeypatch):
    """Banco do PR #3 (peso por morador + tabela rateio) continua abrindo."""
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect("arapuca.db")
    conn.executescript("""
        CREATE TABLE moradores (id INTEGER PRIMARY KEY AUTOINCREMENT, apelido TEXT NOT NULL UNIQUE COLLATE NOCASE,
            senha_hash TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0, ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, peso REAL NOT NULL DEFAULT 1);
        CREATE TABLE contas (id INTEGER PRIMARY KEY AUTOINCREMENT, mes TEXT NOT NULL, descricao TEXT NOT NULL,
            valor_centavos INTEGER NOT NULL, criado_por INTEGER, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE rateio (mes TEXT, morador_id INTEGER, valor_centavos INTEGER, peso REAL, pago INTEGER);
        INSERT INTO contas (mes, descricao, valor_centavos) VALUES ('2026-09', 'Aluguel setembro', 100), ('2026-09', 'Luz', 50);
    """)
    conn.commit()
    conn.close()
    from database import conectar_db, inicializar_db
    inicializar_db()
    conn = conectar_db()
    tipos = dict(conn.execute("SELECT descricao, tipo FROM contas").fetchall())
    assert tipos == {"Aluguel setembro": "aluguel", "Luz": "despesa"}
    assert conn.execute("SELECT COUNT(*) FROM quartos").fetchone()[0] == 8
    assert "quarto_id" in [c[1] for c in conn.execute("PRAGMA table_info(moradores)")]
    conn.close()
