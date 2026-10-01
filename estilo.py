def renderizar_pagina(titulo, conteudo, extra_head=""):
    """Função que envelopa o conteúdo em um layout moderno de App (Tema Laranja e Preto)"""
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

        <!-- PWA: Configurações do App -->
        <link rel="manifest" href="/static/manifest.json?v=2">
        <meta name="theme-color" content="#FF6600">

        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">

        <title>{titulo}</title>
        {extra_head}
        <style>
            :root {{
                --bg: #0a0a0c;
                --card-bg: #16161a;
                --card-border: #26262c;
                --accent: #ff6600;
                --accent-dark: #cc5200;
                --text: #f5f5f5;
                --text-muted: #9a9a9a;
                --danger: #e53935;
                --danger-dark: #b71c1c;
                --success: #2ecc40;
                --success-dark: #1f9c30;
            }}

            * {{ box-sizing: border-box; }}

            body {{
                background: radial-gradient(circle at top, #141416 0%, var(--bg) 60%);
                color: var(--text);
                font-family: 'Poppins', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 24px 16px 48px;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
            }}

            .container {{
                width: 100%;
                max-width: 440px;
                text-align: center;
            }}

            .app-bar {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                margin-bottom: 28px;
            }}

            .app-bar img {{
                width: 36px;
                height: 36px;
                border-radius: 10px;
            }}

            .app-bar span {{
                font-size: 20px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}

            h1, h2, h3 {{ color: var(--accent); font-weight: 600; }}
            h1 {{ font-size: 26px; }}
            h2 {{ font-size: 22px; margin-bottom: 18px; }}
            h3 {{ font-size: 17px; }}

            p {{ color: var(--text-muted); line-height: 1.5; }}

            .card {{
                background-color: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 22px;
                margin-bottom: 20px;
                box-shadow: 0 6px 16px rgba(0, 0, 0, 0.45);
                text-align: left;
            }}

            .card h3 {{
                text-align: center;
                margin-top: 0;
                margin-bottom: 18px;
            }}

            .form-row {{
                display: flex;
                gap: 12px;
                align-items: center;
                justify-content: center;
                flex-wrap: wrap;
            }}

            a.botao-menu {{
                display: block;
                background-color: var(--card-bg);
                border: 1px solid var(--card-border);
                color: #FFFFFF;
                text-decoration: none;
                padding: 18px;
                margin: 14px 0;
                border-radius: 14px;
                font-size: 17px;
                font-weight: 600;
                border-left: 4px solid var(--accent);
                box-shadow: 0 4px 10px rgba(255, 102, 0, 0.12);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }}

            a.botao-menu:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 18px rgba(255, 102, 0, 0.22);
            }}

            button {{
                border: none;
                border-radius: 12px;
                padding: 15px;
                font-size: 15px;
                font-weight: 600;
                width: 100%;
                margin-top: 4px;
                cursor: pointer;
                transition: filter 0.15s ease, transform 0.1s ease;
            }}

            button:hover {{ filter: brightness(1.1); }}
            button:active {{ transform: scale(0.98); }}

            .btn-laranja {{ background: linear-gradient(135deg, var(--accent), var(--accent-dark)); color: #000; }}
            .btn-vermelho {{ background: linear-gradient(135deg, var(--danger), var(--danger-dark)); color: #FFF; }}
            .btn-verde {{ background: linear-gradient(135deg, var(--success), var(--success-dark)); color: #FFF; }}

            input, select {{
                width: 100%;
                padding: 14px;
                border-radius: 10px;
                border: 1px solid var(--card-border);
                background-color: #1e1e24;
                color: var(--text);
                font-family: inherit;
                font-size: 15px;
            }}

            input:focus, select:focus {{
                outline: none;
                border-color: var(--accent);
            }}

            .item-row {{
                list-style-type: none;
                background-color: #1e1e24;
                padding: 14px 16px;
                border-radius: 10px;
                border-left: 3px solid var(--accent);
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}

            .item-row:last-child {{ margin-bottom: 0; }}

            .item-row span {{ font-size: 15px; }}

            .item-row form {{ margin: 0; }}

            .item-row button {{
                width: auto;
                padding: 8px 14px;
                margin-top: 0;
                font-size: 13px;
            }}

            .estoque-vazio {{
                text-align: center;
                color: var(--text-muted);
                font-size: 15px;
                padding: 8px 0;
            }}

            .alerta {{
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                margin-bottom: 16px;
            }}

            .alerta-critico {{ background-color: var(--danger-dark); }}
            .alerta-critico h2 {{ color: #fff; margin: 0; }}

            .alerta-ok {{ background-color: transparent; }}
            .alerta-ok h3 {{ color: var(--success); margin: 4px 0; }}
            .alerta-ok p {{ margin: 4px 0; }}

            hr {{ border: none; border-top: 1px solid var(--card-border); margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="app-bar">
                <img src="/static/icone.png" alt="Arapuca">
                <span>{titulo}</span>
            </div>
            {conteudo}
        </div>

        <!-- Script que contrata o Service Worker -->
        <script>
            if ('serviceWorker' in navigator) {{
                navigator.serviceWorker.register('/sw.js', {{ scope: '/' }})
                .then(function(reg) {{
                    console.log('Service Worker registrado com sucesso:', reg.scope);
                }}).catch(function(err) {{
                    console.log('Falha ao registrar o Service Worker:', err);
                }});
            }}
        </script>
    </body>
    </html>
    """
