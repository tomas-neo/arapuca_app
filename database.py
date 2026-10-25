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

    # Peso de cada morador na divisão (1 = parte normal; quarto maior pode ser 1.5 etc.)
    colunas = [c['name'] for c in conn.execute('PRAGMA table_info(moradores)')]
    if 'peso' not in colunas:
        conn.execute('ALTER TABLE moradores ADD COLUMN peso REAL NOT NULL DEFAULT 1')

    # Contas da casa lançadas em cada mês (valores em centavos para não errar arredondamento)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
            criado_por INTEGER REFERENCES moradores(id),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Divisão congelada quando o mês é fechado: quem estava na casa, com qual peso e quanto deve
    conn.execute('''
        CREATE TABLE IF NOT EXISTS rateio (
            mes TEXT NOT NULL,
            morador_id INTEGER NOT NULL REFERENCES moradores(id),
            peso REAL NOT NULL,
            valor_centavos INTEGER NOT NULL,
            pago INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (mes, morador_id)
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
