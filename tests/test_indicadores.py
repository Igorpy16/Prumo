import json
from datetime import date

import pytest

from app.integracoes.bcb import ClienteBCB, ErroBCB, Ponto, _acumulado_12_meses, _vigente
from app.servicos.indicadores import IndicadoresServico
from conftest import FonteFalsa, indicador

HOJE = date(2026, 11, 10)


class Resposta:
    def __init__(self, dados):
        self._b = dados if isinstance(dados, bytes) else json.dumps(dados).encode()

    def read(self, n=-1):
        return self._b[:n] if n > 0 else self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def abrir_falso(pedido, timeout):
    url = pedido.full_url
    if "sgs.432/" in url:  # Selic: contém datas futuras
        return Resposta([{"data": "29/10/2026", "valor": "14.50"}, {"data": "10/12/2026", "valor": "14.00"}])
    if "sgs.433/" in url:
        return Resposta([{"data": f"01/{m:02d}/2026", "valor": "0.50"} for m in range(1, 12)]
                        + [{"data": "01/12/2025", "valor": "0.50"}])
    if "sgs.4389/" in url:
        return Resposta([{"data": "09/11/2026", "valor": "14.40"}])
    raise OSError("sem rede")  # dólar falha


def test_vigente_ignora_data_futura():
    p = [Ponto(date(2026, 10, 29), 14.5), Ponto(date(2026, 12, 10), 14.0)]
    assert _vigente(p, HOJE).valor == 14.5


def test_ipca_encadeia_em_vez_de_somar():
    p = [Ponto(date(2025, m, 1), 1.0) for m in range(1, 13)]
    r = _acumulado_12_meses(p, HOJE)
    assert round(r.valor, 4) == round((1.01**12 - 1) * 100, 4) != 12.0


def test_ipca_com_poucos_meses_falha():
    with pytest.raises(ErroBCB):
        _acumulado_12_meses([Ponto(date(2026, 1, 1), 1.0)], HOJE)


def test_cliente_isola_falhas_por_indicador():
    itens = ClienteBCB(abrir=abrir_falso, hoje=lambda: HOJE).buscar()
    codigos = {i.codigo for i in itens}
    assert codigos == {"selic", "cdi", "ipca12"}  # dólar caiu, o resto segue
    assert next(i for i in itens if i.codigo == "selic").valor == 14.5


@pytest.mark.parametrize("bruto", [b"<html>", b"[]", b'[{"data":"x","valor":"1"}]', b'[{"data":"01/01/2026","valor":"NaN"}]'])
def test_resposta_invalida_e_rejeitada(bruto):
    with pytest.raises(ErroBCB):
        ClienteBCB._interpretar(1, bruto)


def test_cliente_respeita_limite_de_20():
    with pytest.raises(ValueError):
        ClienteBCB(abrir=abrir_falso)._baixar(433, 21)


def servico(container, fonte, relogio):
    return IndicadoresServico(fonte, container.db, container._configuracoes_repo, ttl_s=100, relogio=relogio)


def test_cache_evita_nova_consulta(container):
    t = [1000.0]
    fonte = FonteFalsa([indicador()])
    s = servico(container, fonte, lambda: t[0])
    s.obter(); t[0] += 50; s.obter()
    assert fonte.chamadas == 1


def test_falha_devolve_ultimo_valor_marcado_como_desatualizado(container):
    t = [1000.0]
    fonte = FonteFalsa([indicador()])
    s = servico(container, fonte, lambda: t[0])
    s.obter()
    fonte.falhar = True
    t[0] += 500
    r = s.obter()
    assert r["desatualizado"] is True and r["itens"][0]["valor"] == 14.5
    chamadas = fonte.chamadas
    t[0] += 10; s.obter()
    assert fonte.chamadas == chamadas  # espera antes de tentar de novo


def test_snapshot_sobrevive_a_reinicio(container):
    t = [1000.0]
    servico(container, FonteFalsa([indicador()]), lambda: t[0]).obter()
    novo = servico(container, FonteFalsa(falhar=True), lambda: t[0] + 500)
    r = novo.obter()
    assert r["itens"] and r["desatualizado"] is True


def test_sem_fonte_endpoint_responde_inativo(cliente):
    r = cliente.get("/api/indicadores").json()
    assert r["ativo"] is False and r["itens"] == []


def test_endpoint_com_fonte_falsa(tmp_path):
    from fastapi.testclient import TestClient

    from app.fabrica import criar_app
    from conftest import montar

    c = TestClient(criar_app(montar(tmp_path), FonteFalsa([indicador("cdi", 14.4)])))
    r = c.get("/api/indicadores").json()
    assert r["itens"][0]["codigo"] == "cdi" and r["fonte"]["licenca"] == "ODbL"
