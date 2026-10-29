"""Puxa as escalas da planilha "Funções - Arapuca" do Drive.

A planilha está aberta para quem tem o link, então o app baixa cada aba como CSV
(sem login do Google). Cada aba tem uma grade com os dias da semana no cabeçalho
e, em cada linha, a área/máquina e quem fica com cada dia.
"""
import csv
import io
import json
import re
import threading
import unicodedata
import urllib.request
from datetime import datetime, timedelta

from database import conectar_db

PLANILHA_PADRAO = "1-ZJy6vfgPTU7qYUBs6opO7N3Iu_iKvy3Q_0kJqRq040"

# escala no app, aba (gid), nome da linha quando a aba não tem rótulo, prazo em dias
ABAS = [
    ("Limpeza", 893878957, "Limpeza", 1),       # limpeza: o dia e mais 1
    ("Passeio do Buddha", 1189699078, "Passeio", 0),
    ("Lavar roupa", 737358181, "Máquina", 0),
]

DIAS = {"domingo": 0, "segunda": 1, "terca": 2, "quarta": 3, "quinta": 4, "sexta": 5, "sabado": 6}
IGNORAR = {"", "-", "x", "vaga vazia", "vago", "ninguem"}
INTERVALO = timedelta(hours=1)
_trava = threading.Lock()


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


def dia_da_celula(celula):
    t = normalizar(celula).replace("-feira", "")
    return DIAS.get(t)


def nome_bonito(rotulo):
    t = re.sub(r"\s+", " ", rotulo).strip()
    m = re.fullmatch(r"(\d+)\s*[°ºª.]?", t)
    if m:
        return f"{m.group(1)}ª máquina"
    return t[:1].upper() + t[1:].lower() if t.isupper() else t


def separar_nomes(celula):
    partes = re.split(r"\s*(?:/|,|;|\+|&|\n|\se\s)\s*", celula or "")
    return [p.strip() for p in partes if normalizar(p) not in IGNORAR]


def ler_grade(linhas, rotulo_padrao):
    """Lê a primeira grade de dias da aba. Devolve {nome_da_linha: {dia: [nomes]}} ou None."""
    cabecalho = None
    for i, linha in enumerate(linhas):
        colunas = {c: dia_da_celula(v) for c, v in enumerate(linha)}
        colunas = {c: d for c, d in colunas.items() if d is not None}
        if len(colunas) >= 5:
            cabecalho, dias_col = i, colunas
            break
    if cabecalho is None:
        return None

    col_rotulo = min(dias_col) - 1
    titulo = linhas[cabecalho][col_rotulo].strip() if col_rotulo >= 0 else ""
    padrao = nome_bonito(titulo) if titulo and normalizar(titulo) not in ("maquina",) else rotulo_padrao

    grade, atual = {}, None
    for linha in linhas[cabecalho + 1:]:
        if sum(1 for v in linha if dia_da_celula(v) is not None) >= 5:
            break  # começou outra tabela na aba
        rotulo = linha[col_rotulo].strip() if 0 <= col_rotulo < len(linha) else ""
        if rotulo:
            atual = nome_bonito(rotulo)
        celulas = {d: (linha[c] if c < len(linha) else "") for c, d in dias_col.items()}
        if not atual and not any(v.strip() for v in celulas.values()):
            continue
        dias = grade.setdefault(atual or padrao, {d: [] for d in range(7)})
        for d, celula in celulas.items():
            for nome in separar_nomes(celula):
                if nome not in dias[d]:
                    dias[d].append(nome)
    return grade


def baixar_aba(planilha_id, gid, timeout=10):
    url = f"https://docs.google.com/spreadsheets/d/{planilha_id}/export?format=csv&gid={gid}"
    with urllib.request.urlopen(url, timeout=timeout) as resposta:
        return list(csv.reader(io.StringIO(resposta.read().decode("utf-8"))))


MAQUINA = "Máquina"


def juntar_maquinas(grade):
    """A casa tem uma máquina só: quem estava na 1ª e na 2ª máquina vai pra mesma linha."""
    junta = {}
    for dias in grade.values():
        for dia, nomes in dias.items():
            lista = junta.setdefault(dia, [])
            lista.extend(n for n in nomes if n not in lista)
    return {MAQUINA: junta}


def aplicar(conn, escala_nome, prazo, grade, moradores):
    """Troca as linhas e turnos da escala pelo que veio da planilha. Devolve nomes não achados."""
    if normalizar(escala_nome) == "lavar roupa" and grade:
        grade = juntar_maquinas(grade)
    escala = conn.execute("SELECT id FROM escalas WHERE nome = ?", (escala_nome,)).fetchone()
    escala_id = escala["id"] if escala else conn.execute(
        "INSERT INTO escalas (nome, icone) VALUES (?, '')", (escala_nome,)).lastrowid
    conn.execute("UPDATE escalas SET prazo_dias = ? WHERE id = ?", (prazo, escala_id))
    conn.execute("DELETE FROM escala_linhas WHERE escala_id = ?", (escala_id,))  # turnos saem junto
    nao_achados = set()
    for nome_linha, dias in grade.items():
        linha_id = conn.execute("INSERT INTO escala_linhas (escala_id, nome) VALUES (?, ?)",
                                (escala_id, nome_linha[:30])).lastrowid
        for dia, nomes in dias.items():
            for nome in nomes:
                morador_id = moradores.get(normalizar(nome))
                if morador_id:
                    conn.execute("INSERT OR IGNORE INTO escala_turnos (linha_id, dia, morador_id) VALUES (?, ?, ?)",
                                 (linha_id, dia, morador_id))
                else:
                    nao_achados.add(nome)
    return nao_achados


def salvar_config(conn, **valores):
    conn.executemany("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
                     [(k, str(v)) for k, v in valores.items()])


def ler_config(conn, chave, padrao=""):
    linha = conn.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"] if linha else padrao


def sincronizar(baixar=baixar_aba):
    """Baixa as abas e atualiza as escalas. Aba que falhar fica como estava."""
    with _trava:
        conn = conectar_db()
        try:
            planilha = ler_config(conn, "planilha_funcoes", PLANILHA_PADRAO)
            from modulos.casa import mapa_moradores
            moradores = mapa_moradores(conn)  # inclui Mic, Xupeta... do dados_iniciais/
            erros, nao_achados = [], set()
            for escala_nome, gid, rotulo, prazo in ABAS:
                try:
                    grade = ler_grade(baixar(planilha, gid), rotulo)
                except Exception as erro:  # sem internet, planilha fechada...
                    erros.append(f"{escala_nome}: {type(erro).__name__}")
                    continue
                if grade is None:
                    erros.append(f"{escala_nome}: não achei os dias da semana na aba")
                    continue
                if not any(nomes for dias in grade.values() for nomes in dias.values()):
                    erros.append(f"{escala_nome}: aba sem ninguém escalado, mantive a do app")
                    continue
                nao_achados |= aplicar(conn, escala_nome, prazo, grade, moradores)
            salvar_config(conn, escalas_sync_em=datetime.now().isoformat(timespec="minutes"),
                          escalas_sync_erro="; ".join(erros),
                          escalas_nao_achados=json.dumps(sorted(nao_achados), ensure_ascii=False))
            conn.commit()
            return {"erros": erros, "nao_achados": sorted(nao_achados)}
        finally:
            conn.close()


def status(conn):
    em = ler_config(conn, "escalas_sync_em")
    return {
        "em": datetime.fromisoformat(em) if em else None,
        "erro": ler_config(conn, "escalas_sync_erro"),
        "nao_achados": json.loads(ler_config(conn, "escalas_nao_achados", "[]")),
    }


def sincronizar_se_preciso(ativo=True):
    """Atualiza em segundo plano se a última vez foi há mais de 1 hora (não trava a página)."""
    if not ativo or _trava.locked():
        return
    conn = conectar_db()
    ultima = status(conn)["em"]
    conn.close()
    if ultima is None or datetime.now() - ultima > INTERVALO:
        threading.Thread(target=_sincronizar_quieto, daemon=True).start()


def _sincronizar_quieto():
    try:
        sincronizar()
    except Exception:
        pass
