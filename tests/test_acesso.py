from fastapi.testclient import TestClient

from app.fabrica import criar_app
from conftest import lancamento, montar


def app_com_senha(tmp_path, **extra):
    return TestClient(criar_app(montar(tmp_path, APP_PASSWORD="senha-bem-longa", **extra)))


def test_api_exige_login(tmp_path):
    c = app_com_senha(tmp_path)
    assert c.get("/api/meta").status_code == 401
    assert c.get("/", follow_redirects=False).headers["location"] == "/login"
    assert c.get("/healthz").status_code == 200


def test_login_correto_e_cookie_seguro(tmp_path):
    c = app_com_senha(tmp_path)
    assert c.post("/api/login", json={"senha": "errada"}).status_code == 401
    r = c.post("/api/login", json={"senha": "senha-bem-longa"})
    assert r.status_code == 200 and "httponly" in r.headers["set-cookie"].lower()
    assert c.get("/api/meta").status_code == 200
    c.post("/api/logout")
    assert c.get("/api/meta").status_code == 401


def test_cookie_adulterado_e_recusado(tmp_path):
    c = app_com_senha(tmp_path)
    c.cookies.set("prumo_sessao", "9999999999.abc")
    assert c.get("/api/meta").status_code == 401


def test_bloqueio_apos_tentativas(tmp_path):
    c = app_com_senha(tmp_path)
    for _ in range(5):
        c.post("/api/login", json={"senha": "x"})
    assert c.post("/api/login", json={"senha": "senha-bem-longa"}).status_code == 429


def test_producao_sem_senha_nao_inicia(tmp_path):
    import pytest

    from app.config import Configuracoes, ErroDeConfiguracao

    with pytest.raises(ErroDeConfiguracao):
        Configuracoes.do_ambiente({"REQUIRE_AUTH": "1", "DATABASE_PATH": str(tmp_path / "a.db")})


def test_demo_somente_leitura_e_isolada(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    real = tmp_path / "real.db"
    real.write_bytes(b"dados reais")
    c = TestClient(criar_app(montar(tmp_path, DEMO_MODE="1", DATABASE_PATH=str(real))))
    assert real.read_bytes() == b"dados reais"  # a demo nunca toca no banco real
    assert c.get("/api/lancamentos").json()["total"] > 50
    assert c.post("/api/lancamentos", json=lancamento()).status_code == 403
    assert c.delete("/api/lancamentos?confirmar=true").status_code == 403
    assert c.get("/docs").status_code == 404
    assert c.get("/api/sessao").json()["demo"] is True


def test_banco_padrao_sem_variavel_de_ambiente():
    from app.config import BANCO_PADRAO, Configuracoes

    assert Configuracoes.do_ambiente({}).caminho_banco == BANCO_PADRAO
