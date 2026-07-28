import sqlite3

def conectar_db():
    conn = sqlite3.connect('arapuca.db')
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    conn = conectar_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mercado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL
        )
    ''')
    cursor = conn.execute('SELECT COUNT(*) FROM mercado')
    if cursor.fetchone()[0] == 0:
        itens_iniciais = [("Papel Higiênico", 4), ("Café", 2), ("Leite", 6), ("Sabão em Pó", 1)]
        conn.executemany('INSERT INTO mercado (item, quantidade) VALUES (?, ?)', itens_iniciais)
        conn.commit()
    conn.close()
