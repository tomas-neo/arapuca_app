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

    # Quartos da casa, igual à planilha Financeiro: ponderação = fatia do aluguel
    # dos quartos; vagas = quantas pessoas o quarto comporta (vaga vazia também entra na conta)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quartos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
            ponderacao REAL NOT NULL CHECK (ponderacao >= 0),
            vagas INTEGER NOT NULL CHECK (vagas >= 1)
        )
    ''')
    if conn.execute('SELECT COUNT(*) FROM quartos').fetchone()[0] == 0:
        # Quartos da planilha Financeiro Arapuca 2K26 (outubro/2026)
        conn.executemany('INSERT INTO quartos (nome, ponderacao, vagas) VALUES (?, ?, ?)', [
            ("Zoológico", 0.18, 4), ("Nós Fumamos", 0.153, 3), ("Suíte", 0.2, 3), ("Motel", 0.112, 2),
            ("Produção", 0.115, 1), ("Mega house", 0.08, 1), ("Laboratório", 0.089, 1), ("Açougue", 0.071, 1),
        ])

    colunas = [c['name'] for c in conn.execute('PRAGMA table_info(moradores)')]
    if 'quarto_id' not in colunas:
        conn.execute('ALTER TABLE moradores ADD COLUMN quarto_id INTEGER REFERENCES quartos(id) ON DELETE SET NULL')

    # Configurações da divisão (caixinha por morador, fatia do aluguel que é área comum)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    ''')
    conn.executemany('INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)',
                     [("caixinha_centavos", "5000"), ("fracao_area_comum", "0.5")])

    # Foto de perfil: foto_versao 0 = sem foto; muda a cada troca (evita cache velho no celular)
    if 'foto_versao' not in [c['name'] for c in conn.execute('PRAGMA table_info(moradores)')]:
        conn.execute('ALTER TABLE moradores ADD COLUMN foto_versao INTEGER NOT NULL DEFAULT 0')

    # Contas da casa lançadas em cada mês (valores em centavos para não errar arredondamento).
    # tipo: 'aluguel' (vai metade área comum, metade quartos) ou 'despesa' (igual por vaga)
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
    colunas = [c['name'] for c in conn.execute('PRAGMA table_info(contas)')]
    if 'tipo' not in colunas:
        conn.execute("ALTER TABLE contas ADD COLUMN tipo TEXT NOT NULL DEFAULT 'despesa'")
        conn.execute("UPDATE contas SET tipo = 'aluguel' WHERE descricao LIKE 'aluguel%'")

    # Ajustes de um morador no mês: outros, pendências (somam) e desconto (subtrai)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ajustes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT NOT NULL,
            morador_id INTEGER NOT NULL REFERENCES moradores(id),
            tipo TEXT NOT NULL CHECK (tipo IN ('outros', 'pendencia', 'desconto')),
            descricao TEXT NOT NULL,
            valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0)
        )
    ''')

    # Divisão congelada quando o mês é fechado. Uma linha por vaga: morador_id NULL = vaga livre.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fechamentos (
            mes TEXT NOT NULL,
            vaga INTEGER NOT NULL,
            quarto TEXT NOT NULL,
            morador_id INTEGER REFERENCES moradores(id),
            casa_centavos INTEGER NOT NULL,
            despesas_centavos INTEGER NOT NULL,
            caixinha_centavos INTEGER NOT NULL,
            ajustes_centavos INTEGER NOT NULL,
            total_centavos INTEGER NOT NULL,
            pago_centavos INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (mes, vaga)
        )
    ''')

    # Escalas da casa (limpeza, passeio do Buddha, lavar roupa...).
    # Cada escala tem linhas (ex: Cozinha, Garagem / 1ª máquina) e, em cada linha,
    # quem fica com cada dia da semana (0 = domingo ... 6 = sábado).
    conn.execute('''
        CREATE TABLE IF NOT EXISTS escalas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            icone TEXT NOT NULL DEFAULT ''
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
    # prazo_dias: quantos dias depois do dia escalado ainda dá pra fazer (limpeza = 1)
    if 'prazo_dias' not in [c['name'] for c in conn.execute('PRAGMA table_info(escalas)')]:
        conn.execute('ALTER TABLE escalas ADD COLUMN prazo_dias INTEGER NOT NULL DEFAULT 0')
        conn.execute("UPDATE escalas SET prazo_dias = 1 WHERE nome = 'Limpeza'")
    if conn.execute('SELECT COUNT(*) FROM escalas').fetchone()[0] == 0:
        # Mesmas escalas da planilha "Funções - Arapuca"
        padrao = [("Limpeza", "", ["Cozinha", "Garagem"]),
                  ("Passeio do Buddha", "", ["Passeio"]),
                  ("Lavar roupa", "", ["1ª máquina", "2ª máquina"])]
        for nome, icone, linhas in padrao:
            escala_id = conn.execute('INSERT INTO escalas (nome, icone, prazo_dias) VALUES (?, ?, ?)',
                                     (nome, icone, 1 if nome == "Limpeza" else 0)).lastrowid
            conn.executemany('INSERT INTO escala_linhas (escala_id, nome) VALUES (?, ?)',
                             [(escala_id, linha) for linha in linhas])

    # Pontos de azaralho: prato sujo, função ou passeio do Buddha não feito...
    conn.execute('''
        CREATE TABLE IF NOT EXISTS azaralho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            morador_id INTEGER NOT NULL REFERENCES moradores(id),
            motivo TEXT NOT NULL CHECK (motivo IN ('prato', 'funcao', 'passeio', 'outro')),
            descricao TEXT NOT NULL DEFAULT '',
            data TEXT NOT NULL,
            pontos INTEGER NOT NULL DEFAULT 1 CHECK (pontos BETWEEN 1 AND 10),
            registrado_por INTEGER REFERENCES moradores(id),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Mercado: itens da planilha "Mercado anti reclamação" e tudo que entra e sai do estoque
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mercado_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
            local TEXT NOT NULL DEFAULT 'Mercado',
            categoria TEXT NOT NULL DEFAULT 'essencial'
                CHECK (categoria IN ('essencial', 'repor_sempre', 'ganha_brisa', 'quando_precisar')),
            unidade TEXT NOT NULL DEFAULT 'un',
            qtd_mensal REAL,
            estoque REAL NOT NULL DEFAULT 0 CHECK (estoque >= 0),
            ativo INTEGER NOT NULL DEFAULT 1
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mercado_movimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES mercado_itens(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL CHECK (tipo IN ('compra', 'reposicao', 'uso')),
            quantidade REAL NOT NULL CHECK (quantidade > 0),
            morador_id INTEGER REFERENCES moradores(id),
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    ''')
    if conn.execute('SELECT COUNT(*) FROM mercado_itens').fetchone()[0] == 0:
        from modulos.mercado_itens import ITENS_PADRAO
        conn.executemany(
            'INSERT INTO mercado_itens (nome, local, categoria, unidade, qtd_mensal) VALUES (?, ?, ?, ?, ?)',
            ITENS_PADRAO)

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
