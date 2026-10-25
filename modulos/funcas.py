"""Funças: os grupos de trabalho da casa (Financeiro, Estrutura, Buda, Mercado...).

Todo mundo vê; quem tem o cargo de estrutura (ou o root) muda quem está em cada uma.
"""
import sqlite3

from flask import Blueprint, abort, redirect, request, url_for

from database import conectar_db
from modulos.auth import exigir_cargo

funcas_bp = Blueprint('funcas', __name__, url_prefix='/funcas')


def listar_funcas(conn):
    funcas = [dict(f, membros=[]) for f in conn.execute('SELECT id, nome, descricao FROM funcas ORDER BY id')]
    por_id = {f['id']: f for f in funcas}
    for m in conn.execute('''SELECT fm.funca_id, m.id, m.apelido, m.foto_versao
                             FROM funca_membros fm JOIN moradores m ON m.id = fm.morador_id
                             WHERE m.ativo = 1 ORDER BY m.apelido'''):
        por_id[m['funca_id']]['membros'].append(dict(m))
    return funcas


def funcas_do_morador(conn, morador_id):
    return [f['nome'] for f in conn.execute(
        '''SELECT f.nome FROM funcas f JOIN funca_membros fm ON fm.funca_id = f.id
           WHERE fm.morador_id = ? ORDER BY f.id''', (morador_id,))]


def voltar():
    return redirect(url_for('escalas.index', editar=1) + '#funcas')


def ler_id(nome):
    texto = request.form.get(nome, '')
    if not texto.isdigit():
        abort(400)
    return int(texto)


@funcas_bp.route("/<int:funca_id>/membro", methods=["POST"])
@exigir_cargo('estrutura')
def adicionar_membro(funca_id):
    conn = conectar_db()
    try:
        conn.execute('INSERT OR IGNORE INTO funca_membros (funca_id, morador_id) VALUES (?, ?)',
                     (funca_id, ler_id('morador_id')))
        conn.commit()
    except sqlite3.IntegrityError:
        abort(400)
    finally:
        conn.close()
    return voltar()


@funcas_bp.route("/<int:funca_id>/membro/<int:morador_id>/remover", methods=["POST"])
@exigir_cargo('estrutura')
def remover_membro(funca_id, morador_id):
    conn = conectar_db()
    conn.execute('DELETE FROM funca_membros WHERE funca_id = ? AND morador_id = ?', (funca_id, morador_id))
    conn.commit()
    conn.close()
    return voltar()


@funcas_bp.route("/nova", methods=["POST"])
@exigir_cargo('estrutura')
def nova():
    nome = request.form.get('nome', '').strip()
    if not nome or len(nome) > 40:
        return redirect(url_for('escalas.index', editar=1, erro="Nome da funça inválido (até 40 letras)"))
    conn = conectar_db()
    try:
        conn.execute('INSERT INTO funcas (nome, descricao) VALUES (?, ?)',
                     (nome, request.form.get('descricao', '').strip()[:400]))
        conn.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for('escalas.index', editar=1, erro=f"Já existe a funça \"{nome}\""))
    finally:
        conn.close()
    return voltar()


@funcas_bp.route("/<int:funca_id>/apagar", methods=["POST"])
@exigir_cargo('estrutura')
def apagar(funca_id):
    conn = conectar_db()
    conn.execute('DELETE FROM funcas WHERE id = ?', (funca_id,))
    conn.commit()
    conn.close()
    return voltar()
