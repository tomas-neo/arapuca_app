# Arapuca App

App da República Arapuca, feito em Flask + SQLite + PWA para rodar num Raspberry Pi 3.

## Rodando

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask
flask --app app criar-admin SeuApelido   # só na primeira vez
python app.py                            # abre em http://<ip-da-máquina>:5000
```

Depois de entrar como admin, cadastre os outros moradores em **Moradores**. Cada um troca a própria senha em **Trocar senha**.

A chave das sessões fica em `.secret_key` (criada sozinha no primeiro start, fora do git). Para usar outra, defina `ARAPUCA_SECRET_KEY`.
