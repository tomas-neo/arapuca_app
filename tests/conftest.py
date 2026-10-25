import pytest


@pytest.fixture(autouse=True)
def ambiente_de_teste(monkeypatch):
    """Testes não acessam a internet e testam também os módulos em quarentena."""
    monkeypatch.setenv("ARAPUCA_SINCRONIZAR", "0")
    monkeypatch.setenv("ARAPUCA_AZARALHO", "1")
    monkeypatch.setenv("ARAPUCA_BOILER", "1")
