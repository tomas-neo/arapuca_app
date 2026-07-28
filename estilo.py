def renderizar_pagina(titulo, conteudo, extra_head=""):
    """Função que envelopa o conteúdo em um layout moderno de App (Tema Laranja e Preto)"""
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{titulo}</title>
        {extra_head}
        <style>
            /* Fundo Preto Puro */
            body {{
                background-color: #000000; 
                color: #F5F5F5; /* Texto branco suave */
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

            /* Títulos em Laranja */
            h1, h2, h3 {{ color: #FF6600; }}

            /* Botões do Menu */
            a.botao-menu {{
                display: block;
                background-color: #1A1A1A; /* Cinza bem escuro para dar contraste */
                color: #FFFFFF;
                text-decoration: none;
                padding: 20px;
                margin: 15px 0;
                border-radius: 15px;
                font-size: 18px;
                font-weight: bold;
                border-left: 5px solid #FF6600; /* Detalhe Laranja */
                box-shadow: 0 4px 6px rgba(255, 102, 0, 0.2); /* Sombra alaranjada */
            }}

            /* Botões Gerais */
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
            
            /* Paleta de Cores dos Botões */
            .btn-laranja {{ background-color: #FF6600; color: #000; }}
            .btn-vermelho {{ background-color: #CC0000; color: #FFF; }}
            .btn-verde {{ background-color: #00CC00; color: #FFF; }}
            
            /* Caixas de Texto */
            input {{
                width: 90%;
                padding: 15px;
                border-radius: 10px;
                border: 1px solid #FF6600; /* Borda Laranja */
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
    </body>
    </html>
    """
