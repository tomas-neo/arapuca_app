# Arapuca App

App da República Arapuca, feito em Flask + SQLite + PWA para rodar num Raspberry Pi 3.

## Rodando

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app criar-admin SeuApelido   # só na primeira vez
python app.py                            # abre em http://<ip-da-máquina>:5000
```

`python app.py` usa o servidor **waitress** (feito para ficar no ar). Para programar com recarga automática e
mensagens de erro detalhadas, rode `ARAPUCA_DEBUG=1 python app.py`, só no seu PC: o modo debug deixa quem está
na rede rodar código no servidor.

Depois de entrar como root, cadastre os outros moradores em **Moradores**. Cada um troca a própria senha no
**Perfil**. Quem esquecer a senha: o root abre o morador em Moradores e toca em **Resetar senha** (volta para
apelido@ano). Depois de 5 senhas erradas seguidas, aquele usuário espera 5 minutos.

A chave das sessões fica em `.secret_key` (criada sozinha no primeiro start, fora do git). Para usar outra, defina `ARAPUCA_SECRET_KEY`.

## Testes

```bash
python -m pytest -q
```
