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
    
    # Adicionamos a coluna "hora_ligado" aqui
    conn.execute('''
        CREATE TABLE IF NOT EXISTS boiler (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            status TEXT NOT NULL,
            responsavel TEXT,
            hora_ligado TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS moradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apelido TEXT NOT NULL UNIQUE COLLATE NOCASE,
            senha_hash TEXT NOT NULL,
            admin INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor_mercado = conn.execute('SELECT COUNT(*) FROM mercado')
    if cursor_mercado.fetchone()[0] == 0:
        itens_iniciais = [("Papel Higiênico", 4), ("Café", 2), ("Leite", 6), ("Sabão em Pó", 1)]
        conn.executemany('INSERT INTO mercado (item, quantidade) VALUES (?, ?)', itens_iniciais)
    
    cursor_boiler = conn.execute('SELECT COUNT(*) FROM boiler')
    if cursor_boiler.fetchone()[0] == 0:
        # Iniciamos com a hora_ligado nula (NULL)
        conn.execute('INSERT INTO boiler (id, status, responsavel, hora_ligado) VALUES (1, "DESLIGADO", "Ninguém", NULL)')
        
    conn.commit()
    conn.close()
