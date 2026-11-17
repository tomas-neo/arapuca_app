import threading
import time
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import conectar_db

auth_bp = Blueprint('auth', __name__)

# Páginas que abrem sem estar logado
ROTAS_PUBLICAS = {'auth.login', 'static', 'service_worker'}


# Cargos que o root distribui. O root (coluna admin) pode tudo.
CARGOS = {
    "financeiro": "Financeiro",
    "mercado": "Mercado",
    "estrutura": "Estrutura",
}


def ler_cargos(texto):
    return [c for c in (texto or "").split(",") if c in CARGOS]


def buscar_morador(morador_id):
    conn = conectar_db()
    linha = conn.execute(
        'SELECT id, apelido, admin, foto_versao, ano, cargos, senha_padrao FROM moradores WHERE id = ? AND ativo = 1', (morador_id,)
    ).fetchone()
    conn.close()
    if linha is None:
        return None
    morador = dict(linha)
    morador['cargos'] = ler_cargos(linha['cargos'])
    return morador


def pode(cargo):
    """Root pode tudo; os outros só o que o cargo deles permite."""
    m = g.get('morador')
    return bool(m) and (bool(m['admin']) or cargo in m['cargos'])


@auth_bp.before_app_request
def exigir_login():
    """Carrega o morador logado em g.morador e manda para o login quem não estiver."""
    g.morador = None
    morador_id = session.get('morador_id')
    if morador_id is not None:
        g.morador = buscar_morador(morador_id)
        if g.morador is None:
            session.clear()  # morador foi desativado

    if g.morador is None and request.endpoint not in ROTAS_PUBLICAS:
        return redirect(url_for('auth.login', proximo=request.path))


def somente_admin(view):
    """Só o root (admin geral)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.morador or not g.morador['admin']:
            return render_template("sem_permissao.html"), 403
        return view(*args, **kwargs)
    return wrapper


def exigir_cargo(cargo):
    """Root ou quem tem o cargo."""
    def decorador(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not pode(cargo):
                return render_template("sem_permissao.html", cargo=CARGOS.get(cargo)), 403
            return view(*args, **kwargs)
        return wrapper
    return decorador


def destino_seguro(proximo):
    # Só aceita caminhos internos, para ninguém usar o login para redirecionar a outro site
    if proximo and proximo.startswith('/') and not proximo.startswith('//'):
        return proximo
    return url_for('home')


def pagina_login(erro="", apelido="", proximo=""):
    return render_template("login.html", erro=erro, apelido=apelido, proximo=proximo)


# Freio contra chute de senha: depois de 5 erros seguidos no mesmo usuário, espera 5 minutos
TENTATIVAS_MAX = 5
ESPERA_SEGUNDOS = 5 * 60
_erros_login = {}  # usuário -> (erros seguidos, hora do último erro)
_trava_login = threading.Lock()


def bloqueado(chave):
    with _trava_login:
        erros, quando = _erros_login.get(chave, (0, 0))
        if erros >= TENTATIVAS_MAX and time.time() - quando < ESPERA_SEGUNDOS:
            return True
        if erros >= TENTATIVAS_MAX:
            _erros_login.pop(chave, None)  # já esperou: zera
        return False


def anotar_erro(chave):
    with _trava_login:
        if len(_erros_login) > 1000:  # alguém chutando nomes a esmo: não deixa a memória crescer
            _erros_login.clear()
        erros, _ = _erros_login.get(chave, (0, 0))
        _erros_login[chave] = (erros + 1, time.time())


def achar_por_login(conn, texto):
    """Aceita o apelido do jeito que a pessoa digitar: Cidão, cidao, CIDAO ou "cidao " dão no mesmo."""
    from modulos.casa import login_de
    procurado = login_de(texto)
    if not procurado:
        return None
    for m in conn.execute('SELECT id, apelido, senha_hash FROM moradores WHERE ativo = 1'):
        if login_de(m['apelido']) == procurado:
            return m
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.morador:
            return redirect(url_for('home'))
        return pagina_login(proximo=request.args.get('proximo', ''))

    apelido = request.form.get('apelido', '').strip()
    senha = request.form.get('senha', '')
    proximo = request.form.get('proximo', '')

    from modulos.casa import login_de
    chave = login_de(apelido)
    if bloqueado(chave):
        return pagina_login("Muitas tentativas erradas. Espere 5 minutos ou peça pro root resetar sua senha.",
                            apelido, proximo), 429

    conn = conectar_db()
    morador = achar_por_login(conn, apelido)
    conn.close()

    if morador is None or not check_password_hash(morador['senha_hash'], senha):
        anotar_erro(chave)
        return pagina_login("Usuário ou senha errados", apelido, proximo), 401
    with _trava_login:
        _erros_login.pop(chave, None)

    session.clear()
    session.permanent = True  # continua logado no celular
    session['morador_id'] = morador['id']
    return redirect(destino_seguro(proximo))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route("/senha", methods=["GET", "POST"])
def trocar_senha():
    erro = ""
    sucesso = False
    if request.method == "POST":
        atual = request.form.get('atual', '')
        nova = request.form.get('nova', '')
        conn = conectar_db()
        row = conn.execute('SELECT senha_hash FROM moradores WHERE id = ?', (g.morador['id'],)).fetchone()
        if not check_password_hash(row['senha_hash'], atual):
            erro = "Senha atual errada"
        elif len(nova) < 6:
            erro = "A nova senha precisa de 6 caracteres ou mais"
        else:
            conn.execute('UPDATE moradores SET senha_hash = ?, senha_padrao = 0 WHERE id = ?',
                         (generate_password_hash(nova), g.morador['id']))
            conn.commit()
            g.morador['senha_padrao'] = 0
            sucesso = True
        conn.close()

    return render_template("senha.html", erro=erro, sucesso=sucesso)


# ---------- foto de perfil ----------

PASTA_FOTOS = Path("fotos")  # junto do arapuca.db
TAMANHO_FOTO = 320


def caminho_foto(morador_id):
    return PASTA_FOTOS / f"{morador_id}.jpg"


@auth_bp.route("/perfil/foto", methods=["POST"])
def enviar_foto():
    from PIL import Image, ImageOps, UnidentifiedImageError

    arquivo = request.files.get("foto")
    if not arquivo or not arquivo.filename:
        return render_template("senha.html", erro="Escolha uma foto", sucesso=False), 400
    try:
        imagem = Image.open(arquivo.stream)
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")  # gira certo foto de celular
        imagem = ImageOps.fit(imagem, (TAMANHO_FOTO, TAMANHO_FOTO), Image.LANCZOS)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return render_template("senha.html", erro="Não consegui abrir essa imagem", sucesso=False), 400

    PASTA_FOTOS.mkdir(exist_ok=True)
    imagem.save(caminho_foto(g.morador['id']), "JPEG", quality=85)
    conn = conectar_db()
    conn.execute('UPDATE moradores SET foto_versao = ? WHERE id = ?', (int(time.time()), g.morador['id']))
    conn.commit()
    conn.close()
    return redirect(url_for('auth.trocar_senha'))


@auth_bp.route("/perfil/foto/remover", methods=["POST"])
def remover_foto():
    caminho_foto(g.morador['id']).unlink(missing_ok=True)
    conn = conectar_db()
    conn.execute('UPDATE moradores SET foto_versao = 0 WHERE id = ?', (g.morador['id'],))
    conn.commit()
    conn.close()
    return redirect(url_for('auth.trocar_senha'))


@auth_bp.route("/fotos/<int:morador_id>.jpg")
def foto(morador_id):
    caminho = caminho_foto(morador_id)
    if not caminho.exists():
        abort(404)
    resposta = send_file(caminho.resolve(), mimetype="image/jpeg", max_age=60 * 60 * 24 * 30)
    return resposta
