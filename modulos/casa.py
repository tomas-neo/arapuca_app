"""Dados de quem mora na casa que não ficam no GitHub (o repositório é público).

Pasta `dados_iniciais/` ao lado do app (fica fora do git):
    moradores.json   {"Oca": {"ano": 2025, "saldo": -824.99, "nomes": ["Cabeça Oca"], "cargos": ["mercado"]}, ...}
    fotos/Oca.jpg    foto de cada um, com o apelido no nome do arquivo

    escalas.json     escalas iniciais (máquina, passeio, limpeza), entram uma vez só
    funcas.json      funças da casa e quem está em cada uma, entram uma vez só

Ao iniciar o app e ao criar um morador, cada um recebe o ano, o saldo da planilha, cargos,
quarto e foto, mas só o que ainda estiver vazio: nada que alguém mudou no app é sobrescrito.
Quem tem "conta": true e ainda não existe ganha login apelido / apelido@ano (ex.: zangado@24).
"""
import json
import time
from pathlib import Path

from modulos.planilha import normalizar

PASTA_DADOS = Path("dados_iniciais")
TAMANHO_FOTO = 320


def formatar_ano(ano):
    """2022 -> "022", do jeito que a casa fala da turma."""
    return f"{ano % 1000:03d}" if ano else ""


def carregar_dados(pasta=None):
    pasta = Path(pasta or PASTA_DADOS)
    arquivo = pasta / "moradores.json"
    if not arquivo.exists():
        return {}
    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    dados = {}
    for apelido, info in bruto.items():
        info = dict(info or {})
        info["apelido"] = apelido
        for nome in [apelido, *info.get("nomes", [])]:
            dados[normalizar(nome)] = info
    return dados


def achar_foto(pasta, apelidos):
    fotos = Path(pasta) / "fotos"
    if not fotos.is_dir():
        return None
    procurados = {normalizar(a) for a in apelidos}
    for arquivo in sorted(fotos.iterdir()):
        if arquivo.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and normalizar(arquivo.stem) in procurados:
            return arquivo
    return None


def salvar_foto(origem, destino):
    from PIL import Image, ImageOps
    with Image.open(origem) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
        imagem = ImageOps.fit(imagem, (TAMANHO_FOTO, TAMANHO_FOTO), Image.LANCZOS)
        destino.parent.mkdir(exist_ok=True)
        imagem.save(destino, "JPEG", quality=85)


def login_de(apelido):
    """Usuário do login: o apelido em minúsculas e sem acento (Xamã -> xama)."""
    return normalizar(apelido).replace(" ", "")


def senha_inicial(apelido, ano):
    """zangado@24: apelido + @ + os dois últimos dígitos do ano em que entrou."""
    return f"{login_de(apelido)}@{ano % 100:02d}"


def mapa_moradores(conn, pasta=None):
    """{nome normalizado: id}, com os apelidos do app e os nomes alternativos do moradores.json
    (a planilha escreve Mic, Xupeta, Chuverin...)."""
    ids = {normalizar(m['apelido']): m['id'] for m in conn.execute('SELECT id, apelido FROM moradores WHERE ativo = 1')}
    for nome, info in carregar_dados(pasta).items():
        alvo = next((ids[normalizar(n)] for n in [info["apelido"], *info.get("nomes", [])] if normalizar(n) in ids), None)
        if alvo and nome not in ids:
            ids[nome] = alvo
    return ids


def criar_contas(conn, dados):
    """Cria o login de quem está no moradores.json com "conta": true e ainda não existe no app."""
    from werkzeug.security import generate_password_hash

    existentes = {normalizar(m['apelido']) for m in conn.execute('SELECT apelido FROM moradores')}
    criados = []
    vistos = set()
    for info in dados.values():
        apelido = info["apelido"]
        if apelido in vistos or not info.get("conta") or not isinstance(info.get("ano"), int):
            continue
        vistos.add(apelido)
        if any(normalizar(n) in existentes for n in [apelido, *info.get("nomes", [])]):
            continue
        conn.execute('INSERT INTO moradores (apelido, senha_hash, senha_padrao) VALUES (?, ?, 1)',
                     (apelido, generate_password_hash(senha_inicial(apelido, info["ano"]))))
        existentes.add(normalizar(apelido))
        criados.append(apelido)
    return criados


def importar(conn, pasta=None):
    """Cria as contas que faltam e preenche ano, saldo anterior, cargos, quarto e foto de quem
    ainda não tem. Depois põe as escalas e funças iniciais (uma vez só). Devolve quantos mudaram."""
    from modulos.auth import CARGOS, caminho_foto

    pasta = Path(pasta or PASTA_DADOS)
    dados = carregar_dados(pasta)
    mudou = len(criar_contas(conn, dados))
    quartos = {normalizar(q['nome']): q['id'] for q in conn.execute('SELECT id, nome FROM quartos')}
    for m in conn.execute('SELECT id, apelido, ano, saldo_anterior_centavos, foto_versao, cargos, quarto_id '
                          'FROM moradores').fetchall():
        info = dados.get(normalizar(m['apelido']))
        if not info:
            continue
        if m['ano'] is None and isinstance(info.get("ano"), int):
            conn.execute('UPDATE moradores SET ano = ? WHERE id = ?', (info["ano"], m['id']))
            mudou += 1
        if m['saldo_anterior_centavos'] is None and isinstance(info.get("saldo"), (int, float)):
            conn.execute('UPDATE moradores SET saldo_anterior_centavos = ? WHERE id = ?',
                         (round(info["saldo"] * 100), m['id']))
            mudou += 1
        if m['cargos'] is None and isinstance(info.get("cargos"), list):
            cargos = [c for c in info["cargos"] if c in CARGOS]
            conn.execute('UPDATE moradores SET cargos = ? WHERE id = ?', (",".join(cargos), m['id']))
            mudou += 1
        quarto = quartos.get(normalizar(info.get("quarto") or ""))
        if m['quarto_id'] is None and quarto:
            conn.execute('UPDATE moradores SET quarto_id = ? WHERE id = ?', (quarto, m['id']))
            mudou += 1
        if not m['foto_versao']:
            origem = achar_foto(pasta, [info["apelido"], m['apelido'], *info.get("nomes", [])])
            if origem:
                try:
                    salvar_foto(origem, caminho_foto(m['id']))
                except OSError:
                    continue
                conn.execute('UPDATE moradores SET foto_versao = ? WHERE id = ?', (int(time.time()), m['id']))
                mudou += 1
    conn.commit()
    mudou += importar_escalas(conn, pasta) + importar_funcas(conn, pasta)
    conn.commit()
    return mudou


def ler_json(arquivo):
    try:
        return json.loads(Path(arquivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ja_importado(conn, chave):
    return conn.execute('SELECT 1 FROM config WHERE chave = ?', (chave,)).fetchone() is not None


def marcar_importado(conn, chave):
    conn.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, datetime('now', 'localtime'))", (chave,))


DIAS_JSON = {"dom": 0, "seg": 1, "ter": 2, "qua": 3, "qui": 4, "sex": 5, "sab": 6}


def importar_escalas(conn, pasta=None):
    """escalas.json: {"Lavar roupa": {"prazo": 0, "linhas": {"1ª máquina": {"dom": ["Olinda"]}}}}.
    Entra uma vez só; depois quem manda é o app (o cargo de estrutura edita lá)."""
    from modulos.planilha import aplicar

    dados = ler_json(Path(pasta or PASTA_DADOS) / "escalas.json")
    if not isinstance(dados, dict) or ja_importado(conn, "escalas_iniciais_em"):
        return 0
    moradores = mapa_moradores(conn, pasta)
    for nome, escala in dados.items():
        grade = {linha: {DIAS_JSON[d]: nomes for d, nomes in (dias or {}).items() if d in DIAS_JSON}
                 for linha, dias in escala.get("linhas", {}).items()}
        aplicar(conn, nome, int(escala.get("prazo", 0)), grade, moradores)
    marcar_importado(conn, "escalas_iniciais_em")
    return len(dados)


def importar_funcas(conn, pasta=None):
    """funcas.json: [{"nome": "Financeiro", "descricao": "...", "membros": ["Zangado", ...]}]. Uma vez só."""
    dados = ler_json(Path(pasta or PASTA_DADOS) / "funcas.json")
    if not isinstance(dados, list) or ja_importado(conn, "funcas_iniciais_em"):
        return 0
    moradores = mapa_moradores(conn, pasta)
    todos = [m['id'] for m in conn.execute('SELECT id FROM moradores WHERE ativo = 1')]
    for funca in dados:
        nome = str(funca.get("nome", "")).strip()[:40]
        if not nome:
            continue
        conn.execute('INSERT OR IGNORE INTO funcas (nome, descricao) VALUES (?, ?)',
                     (nome, str(funca.get("descricao", ""))[:400]))
        funca_id = conn.execute('SELECT id FROM funcas WHERE nome = ?', (nome,)).fetchone()['id']
        membros = todos if funca.get("membros") == "todos" else \
            [moradores[normalizar(n)] for n in funca.get("membros", []) if normalizar(n) in moradores]
        conn.executemany('INSERT OR IGNORE INTO funca_membros (funca_id, morador_id) VALUES (?, ?)',
                         [(funca_id, m) for m in membros])
    marcar_importado(conn, "funcas_iniciais_em")
    return len(dados)
