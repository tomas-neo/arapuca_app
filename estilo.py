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
        
        <title>{titulo}</title>
        {extra_head}
        <style>
            body {{
                background-color: #000000; 
                color: #F5F5F5;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            
            .container {{
                width: 100%;
                max-width: 400px;
                text-align: center;
            }}

            h1, h2, h3 {{ color: #FF6600; }}

            a.botao-menu {{
                display: block;
                background-color: #1A1A1A;
                color: #FFFFFF;
                text-decoration: none;
                padding: 20px;
                margin: 15px 0;
                border-radius: 15px;
                font-size: 18px;
                font-weight: bold;
                border-left: 5px solid #FF6600;
                box-shadow: 0 4px 6px rgba(255, 102, 0, 0.2);
            }}

            button {{
                border: none;
                border-radius: 12px;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                width: 100%;
                margin-top: 10px;
                cursor: pointer;
            }}
            
            .btn-laranja {{ background-color: #FF6600; color: #000; }}
            .btn-vermelho {{ background-color: #CC0000; color: #FFF; }}
            .btn-verde {{ background-color: #00CC00; color: #FFF; }}
            
            input {{
                width: 90%;
                padding: 15px;
                border-radius: 10px;
                border: 1px solid #FF6600;
                background-color: #1A1A1A;
                color: white;
                font-size: 16px;
                box-sizing: border-box;
            }}
            
            hr {{ border-color: #333; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
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
