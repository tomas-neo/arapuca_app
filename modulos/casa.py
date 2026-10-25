"""Dados de quem mora na casa que não ficam no GitHub (o repositório é público).

Pasta `dados_iniciais/` ao lado do app (fica fora do git):
    moradores.json   {"Oca": {"ano": 2025, "saldo": -824.99, "nomes": ["Cabeça Oca"], "cargos": ["mercado"]}, ...}
    fotos/Oca.jpg    foto de cada um, com o apelido no nome do arquivo

Ao iniciar o app e ao criar um morador, cada um recebe o ano, o saldo da planilha
e a foto, mas só o que ainda estiver vazio: nada que o morador ou o admin mudou é sobrescrito.
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


def importar(conn, pasta=None):
    """Preenche ano, saldo anterior e foto de quem ainda não tem. Devolve quantos mudaram."""
    from modulos.auth import caminho_foto

    pasta = Path(pasta or PASTA_DADOS)
    dados = carregar_dados(pasta)
    mudou = 0
    for m in conn.execute('SELECT id, apelido, ano, saldo_anterior_centavos, foto_versao, cargos FROM moradores').fetchall():
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
            from modulos.auth import CARGOS
            cargos = [c for c in info["cargos"] if c in CARGOS]
            conn.execute('UPDATE moradores SET cargos = ? WHERE id = ?', (",".join(cargos), m['id']))
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
    return mudou
