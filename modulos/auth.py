from functools import wraps

from flask import Blueprint, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import conectar_db

auth_bp = Blueprint('auth', __name__)

# Páginas que abrem sem estar logado
ROTAS_PUBLICAS = {'auth.login', 'static', 'service_worker'}


def buscar_morador(morador_id):
    conn = conectar_db()
    morador = conn.execute(
        'SELECT id, apelido, admin FROM moradores WHERE id = ? AND ativo = 1', (morador_id,)
    ).fetchone()
    conn.close()
    return morador


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
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.morador or not g.morador['admin']:
            return render_template("sem_permissao.html"), 403
        return view(*args, **kwargs)
    return wrapper


def destino_seguro(proximo):
    # Só aceita caminhos internos, para ninguém usar o login para redirecionar a outro site
    if proximo and proximo.startswith('/') and not proximo.startswith('//'):
        return proximo
    return url_for('home')


def pagina_login(erro="", apelido="", proximo=""):
    return render_template("login.html", erro=erro, apelido=apelido, proximo=proximo)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.morador:
            return redirect(url_for('home'))
        return pagina_login(proximo=request.args.get('proximo', ''))

    apelido = request.form.get('apelido', '').strip()
    senha = request.form.get('senha', '')
    proximo = request.form.get('proximo', '')

    conn = conectar_db()
    morador = conn.execute(
        'SELECT id, senha_hash FROM moradores WHERE apelido = ? AND ativo = 1', (apelido,)
    ).fetchone()
    conn.close()

    if morador is None or not check_password_hash(morador['senha_hash'], senha):
        return pagina_login("Apelido ou senha errados", apelido, proximo), 401

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
            conn.execute('UPDATE moradores SET senha_hash = ? WHERE id = ?',
                         (generate_password_hash(nova), g.morador['id']))
            conn.commit()
            sucesso = True
        conn.close()

    return render_template("senha.html", erro=erro, sucesso=sucesso)
