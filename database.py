import sqlite3

def conectar_db():
    conn = sqlite3.connect('arapuca.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
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

    # Escalas da casa (limpeza, passeio do Buddha, lavar roupa...).
    # Cada escala tem linhas (ex: Cozinha, Garagem / 1ª máquina) e, em cada linha,
    # quem fica com cada dia da semana (0 = domingo ... 6 = sábado).
    conn.execute('''
        CREATE TABLE IF NOT EXISTS escalas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            icone TEXT NOT NULL DEFAULT '📋'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS escala_linhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escala_id INTEGER NOT NULL REFERENCES escalas(id) ON DELETE CASCADE,
            nome TEXT NOT NULL,
            UNIQUE (escala_id, nome)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS escala_turnos (
            linha_id INTEGER NOT NULL REFERENCES escala_linhas(id) ON DELETE CASCADE,
            dia INTEGER NOT NULL CHECK (dia BETWEEN 0 AND 6),
            morador_id INTEGER NOT NULL REFERENCES moradores(id),
            PRIMARY KEY (linha_id, dia, morador_id)
        )
    ''')
    if conn.execute('SELECT COUNT(*) FROM escalas').fetchone()[0] == 0:
        # Mesmas escalas da planilha "Funções - Arapuca"
        padrao = [("Limpeza", "🧹", ["Cozinha", "Garagem"]),
                  ("Passeio do Buddha", "🐕", ["Passeio"]),
                  ("Lavar roupa", "🧺", ["1ª máquina", "2ª máquina"])]
        for nome, icone, linhas in padrao:
            escala_id = conn.execute('INSERT INTO escalas (nome, icone) VALUES (?, ?)', (nome, icone)).lastrowid
            conn.executemany('INSERT INTO escala_linhas (escala_id, nome) VALUES (?, ?)',
                             [(escala_id, linha) for linha in linhas])

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
