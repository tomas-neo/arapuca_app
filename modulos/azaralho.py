import re
from datetime import date, timedelta

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from database import conectar_db
from modulos.contas import deslocar_mes, mes_valido, nome_mes
from modulos.escalas import DIAS, turnos_do_dia

azaralho_bp = Blueprint('azaralho', __name__, url_prefix='/azaralho')

MOTIVOS = {"prato": "🍽️ Prato sujo", "funcao": "🧹 Função não feita",
           "passeio": "🐕 Passeio do Buddha não feito", "outro": "⚠️ Outro"}


def dia_da_semana(dia):
    return (dia.weekday() + 1) % 7  # 0 = domingo, igual às escalas


def pontos_do_mes(conn, mes, morador_id=None):
    sql = '''SELECT COALESCE(SUM(pontos), 0) FROM azaralho WHERE substr(data, 1, 7) = ?'''
    args = [mes]
    if morador_id is not None:
        sql += ' AND morador_id = ?'
        args.append(morador_id)
    return conn.execute(sql, args).fetchone()[0]


def meus_pontos_do_mes(morador_id):
    conn = conectar_db()
    total = pontos_do_mes(conn, date.today().strftime("%Y-%m"), morador_id)
    conn.close()
    return total


def funcoes_para_cobrar(conn, hoje):
    """Funções de ontem e de hoje, para marcar 'não fez' com um toque. Lavar roupa não conta."""
    lista = []
    for dia in (hoje - timedelta(days=1), hoje):
        for t in turnos_do_dia(conn, dia_da_semana(dia)):
            if t['escala'].lower().startswith('lavar'):
                continue
            motivo = 'passeio' if 'buddha' in t['escala'].lower() or 'passeio' in t['escala'].lower() else 'funcao'
            descricao = f"{t['escala']} · {t['linha']}"
            ja = conn.execute(
                'SELECT 1 FROM azaralho WHERE morador_id = ? AND data = ? AND descricao = ?',
                (t['morador_id'], dia.isoformat(), descricao)).fetchone()
            lista.append({'dia': dia.isoformat(), 'nome_dia': 'Hoje' if dia == hoje else f"Ontem ({DIAS[dia_da_semana(dia)]})",
                          'icone': t['icone'], 'descricao': descricao, 'motivo': motivo,
                          'morador_id': t['morador_id'], 'apelido': t['apelido'], 'ja_marcado': ja is not None})
    return lista


@azaralho_bp.route("/")
def index():
    mes = request.args.get("mes") or date.today().strftime("%Y-%m")
    if not mes_valido(mes):
        abort(400)
    conn = conectar_db()
    ranking = conn.execute(
        '''SELECT m.id, m.apelido, COALESCE(SUM(a.pontos), 0) AS pontos
           FROM moradores m
           LEFT JOIN azaralho a ON a.morador_id = m.id AND substr(a.data, 1, 7) = ?
           WHERE m.ativo = 1 GROUP BY m.id ORDER BY pontos DESC, m.apelido''', (mes,)).fetchall()
    historico = conn.execute(
        '''SELECT a.id, a.data, a.motivo, a.descricao, a.pontos, a.registrado_por,
                  m.apelido, r.apelido AS quem_registrou
           FROM azaralho a JOIN moradores m ON m.id = a.morador_id
           LEFT JOIN moradores r ON r.id = a.registrado_por
           WHERE substr(a.data, 1, 7) = ? ORDER BY a.data DESC, a.id DESC''', (mes,)).fetchall()
    moradores = conn.execute('SELECT id, apelido FROM moradores WHERE ativo = 1 ORDER BY apelido').fetchall()
    hoje = date.today()
    cobrar = funcoes_para_cobrar(conn, hoje) if mes == hoje.strftime("%Y-%m") else []
    conn.close()
    return render_template("azaralho.html", mes=mes, nome_mes=nome_mes(mes),
                           anterior=deslocar_mes(mes, -1), proximo=deslocar_mes(mes, 1),
                           ranking=ranking, historico=historico, moradores=moradores, motivos=MOTIVOS,
                           cobrar=cobrar, hoje=hoje.isoformat(), erro=request.args.get("erro", ""))


def voltar(mes, erro=None):
    if erro:
        return redirect(url_for('azaralho.index', mes=mes, erro=erro))
    return redirect(url_for('azaralho.index', mes=mes))


@azaralho_bp.route("/novo", methods=["POST"])
def novo():
    """Qualquer morador pode dar ponto; fica registrado quem deu."""
    data = request.form.get('data', '') or date.today().isoformat()
    motivo = request.form.get('motivo', '')
    descricao = request.form.get('descricao', '').strip()[:80]
    try:
        morador_id = int(request.form.get('morador_id', ''))
        pontos = int(request.form.get('pontos', '1') or 1)
    except ValueError:
        abort(400)
    if motivo not in MOTIVOS or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
        abort(400)
    mes = data[:7]
    try:
        quando = date.fromisoformat(data)
    except ValueError:
        abort(400)
    if quando > date.today():
        return voltar(mes, "Não dá pra dar ponto no futuro")
    if not 1 <= pontos <= 10:
        return voltar(mes, "Pontos precisa ser de 1 a 10")

    conn = conectar_db()
    if conn.execute('SELECT 1 FROM moradores WHERE id = ? AND ativo = 1', (morador_id,)).fetchone() is None:
        conn.close()
        abort(400)
    duplicado = descricao and conn.execute(
        'SELECT 1 FROM azaralho WHERE morador_id = ? AND data = ? AND descricao = ?',
        (morador_id, data, descricao)).fetchone()
    if not duplicado:
        conn.execute('''INSERT INTO azaralho (morador_id, motivo, descricao, data, pontos, registrado_por)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (morador_id, motivo, descricao, data, pontos, g.morador['id']))
        conn.commit()
    conn.close()
    return voltar(mes)


@azaralho_bp.route("/<int:ponto_id>/apagar", methods=["POST"])
def apagar(ponto_id):
    """Quem registrou ou um admin pode tirar o ponto."""
    conn = conectar_db()
    ponto = conn.execute('SELECT data, registrado_por FROM azaralho WHERE id = ?', (ponto_id,)).fetchone()
    if ponto is None:
        conn.close()
        abort(404)
    if not g.morador['admin'] and ponto['registrado_por'] != g.morador['id']:
        conn.close()
        abort(403)
    conn.execute('DELETE FROM azaralho WHERE id = ?', (ponto_id,))
    conn.commit()
    conn.close()
    return voltar(ponto['data'][:7])
