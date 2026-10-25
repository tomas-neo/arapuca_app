import importlib
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modulos.planilha import ler_grade, separar_nomes  # noqa: E402

# Abas como estão na planilha "Funções - Arapuca" (out/2026)
LAVAR = [["Novo"],
         ["MÁQUINA", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
         ["1°", "Olinda", "Xamã", "Fela", "Oca", "Alek", "Zangado", "Buah"],
         ["2°", "Chuveiro", "Kiko", "Maroto", "Xupeta", "Mic", "", "Cidão"],
         ["3°"], [], [],
         ["ANO", "MORADOR", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "SOMA"],
         ["22", "Xamã", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE", "FALSE", "2"]]
LIMPEZA = [[],
           ["", "", "SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO", "", "MORADOR", "FUNÇAS"],
           ["", "GARAGEM", "Olinda", "", "", "", "", "", "", "", "Olinda", "0"],
           ["", "", "Xamã", "", "", "", "", "", "Oca", "", "Cariok", "0"],
           ["", "COZINHA ", "", "Mic / Buah", "", "", "", "", "", "", "Xamã", "0"],
           ["", "SALA DE  ESTUDO E CORREDOR", "", "", "", "", "", "", "", "", "A5", "0"],
           [], ["", "SECAR LOUÇA"]]
PASSEIO = [["Passeio", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
           ["", "Mic", "", "Oca"], [], [],
           ["ANO", "MORADOR", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
           ["22", "Xamã", "TRUE", "FALSE"]]


def test_le_maquinas():
    grade = ler_grade(LAVAR, "Máquina")
    assert list(grade) == ["1ª máquina", "2ª máquina", "3ª máquina"]   # para antes da tabela de disponibilidade
    assert grade["1ª máquina"][0] == ["Olinda"] and grade["1ª máquina"][6] == ["Buah"]
    assert grade["2ª máquina"][5] == []


def test_le_limpeza_com_varias_pessoas_por_area():
    grade = ler_grade(LIMPEZA, "Limpeza")
    assert list(grade) == ["Garagem", "Cozinha", "Sala de estudo e corredor", "Secar louça"]
    assert grade["Garagem"][1] == ["Olinda", "Xamã"]       # segunda: duas linhas da mesma área
    assert grade["Garagem"][0] == ["Oca"]                  # domingo é a última coluna
    assert grade["Cozinha"][2] == ["Mic", "Buah"]          # "Mic / Buah" na mesma célula


def test_le_passeio_sem_rotulo():
    grade = ler_grade(PASSEIO, "Passeio")
    assert list(grade) == ["Passeio"]
    assert grade["Passeio"][0] == ["Mic"] and grade["Passeio"][2] == ["Oca"]


def test_aba_sem_dias():
    assert ler_grade([["qualquer"], ["coisa"]], "X") is None


def test_separar_nomes():
    assert separar_nomes("Mic e Buah") == ["Mic", "Buah"]
    assert separar_nomes("Vaga vazia") == []


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARAPUCA_SECRET_KEY", "teste")
    sys.modules.pop("app", None)
    modulo = importlib.import_module("app")
    from database import conectar_db
    conn = conectar_db()
    conn.executemany("INSERT INTO moradores (apelido, senha_hash, admin) VALUES (?, ?, ?)",
                     [(n, generate_password_hash("segredo1"), 1 if n == "Oca" else 0)
                      for n in ["Oca", "Olinda", "Xamã", "Mic", "Buah", "Cidão"]])
    conn.commit()
    conn.close()
    return modulo.app


def test_sincronizar_troca_escalas(app):
    from database import conectar_db
    from modulos import planilha
    abas = {893878957: LIMPEZA, 1189699078: PASSEIO, 737358181: LAVAR}
    resultado = planilha.sincronizar(baixar=lambda _id, gid: abas[gid])
    assert resultado["erros"] == []
    assert "Chuveiro" in resultado["nao_achados"] and "Olinda" not in resultado["nao_achados"]

    conn = conectar_db()
    cidao = conn.execute(
        """SELECT COUNT(*) FROM escala_turnos t JOIN escala_linhas l ON l.id = t.linha_id
           JOIN moradores m ON m.id = t.morador_id
           WHERE l.nome = '2ª máquina' AND t.dia = 6 AND m.apelido = 'Cidão'""").fetchone()[0]
    assert cidao == 1   # "Cidão" da planilha casou com o morador (sem ligar pra acento/maiúscula)
    assert conn.execute("SELECT prazo_dias FROM escalas WHERE nome = 'Limpeza'").fetchone()[0] == 1
    conn.close()

    # uma aba que falha não apaga o que já estava
    def falha(_id, gid):
        if gid == 737358181:
            raise OSError("sem internet")
        return abas[gid]
    resultado = planilha.sincronizar(baixar=falha)
    assert resultado["erros"] == ["Lavar roupa: OSError"]
    conn = conectar_db()
    assert conn.execute("SELECT COUNT(*) FROM escala_linhas WHERE nome = '1ª máquina'").fetchone()[0] == 1
    conn.close()

    admin = app.test_client()
    admin.post("/login", data={"apelido": "Oca", "senha": "segredo1"})
    pagina = admin.get("/escalas/").text
    assert "OSError" in pagina   # admin vê o que falhou
