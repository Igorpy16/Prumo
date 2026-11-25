"""Cliente da API de Dados Abertos do Banco Central do Brasil (SGS).

Fonte dos dados: Banco Central do Brasil, Dados Abertos (https://dadosabertos.bcb.gov.br),
licença Open Data Commons Open Database License (ODbL). Este projeto não é afiliado
nem endossado pelo Banco Central.

A API é pública e não exige chave. Detalhes que este cliente respeita:
  * `ultimos/N` aceita no máximo 20 valores (acima disso a API responde HTTP 400);
  * a resposta é uma lista de {"data": "dd/mm/aaaa", "valor": "0.58"} (valor vem como texto);
  * a série da meta Selic traz datas FUTURAS (até a próxima reunião do Copom), então o
    valor vigente é o último com data menor ou igual a hoje;
  * taxas mensais não se somam: o acumulado é o encadeamento ∏(1 + v/100) − 1.
"""

from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

log = logging.getLogger("prumo.bcb")

URL_SERIE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json"
PORTAL = "https://dadosabertos.bcb.gov.br"
LICENCA = "https://opendatacommons.org/licenses/odbl/1-0/"
LIMITE_DE_RESPOSTA = 1_000_000  # bytes


class ErroBCB(RuntimeError):
    """Falha ao consultar ou interpretar a resposta do Banco Central."""


@dataclass(frozen=True, slots=True)
class Ponto:
    data: date
    valor: float


@dataclass(frozen=True, slots=True)
class Indicador:
    codigo: str
    nome: str
    valor: float
    unidade: str
    data: date
    detalhe: str
    serie: int

    def para_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "valor": round(self.valor, 4),
            "unidade": self.unidade,
            "data": self.data.isoformat(),
            "detalhe": self.detalhe,
            "serie": self.serie,
        }


class FonteDeIndicadores(Protocol):
    """Contrato usado pelo serviço; permite trocar a fonte (e testar sem internet)."""

    def buscar(self) -> list[Indicador]: ...


@dataclass(frozen=True, slots=True)
class _Definicao:
    codigo: str
    nome: str
    serie: int
    quantidade: int
    unidade: str
    detalhe: str
    reduzir: Callable[[list[Ponto], date], Ponto]


def _vigente(pontos: list[Ponto], hoje: date) -> Ponto:
    """Último valor com data até hoje (ignora datas futuras)."""
    passados = [p for p in pontos if p.data <= hoje]
    if not passados:
        raise ErroBCB("a série não tem valor vigente")
    return max(passados, key=lambda p: p.data)


def _acumulado_12_meses(pontos: list[Ponto], hoje: date) -> Ponto:
    """IPCA acumulado em 12 meses a partir das 12 variações mensais (encadeamento)."""
    passados = sorted((p for p in pontos if p.data <= hoje), key=lambda p: p.data)[-12:]
    if len(passados) < 12:
        raise ErroBCB("faltam variações mensais para o acumulado de 12 meses")
    fator = 1.0
    for p in passados:
        fator *= 1 + p.valor / 100
    return Ponto(passados[-1].data, (fator - 1) * 100)


DEFINICOES: tuple[_Definicao, ...] = (
    _Definicao("selic", "Selic (meta)", 432, 5, "% a.a.", "Meta definida pelo Copom", _vigente),
    _Definicao("cdi", "CDI", 4389, 3, "% a.a.", "Taxa anualizada, base 252 dias úteis", _vigente),
    _Definicao("ipca12", "IPCA", 433, 12, "% em 12 meses", "Inflação acumulada em 12 meses", _acumulado_12_meses),
    _Definicao("dolar", "Dólar", 1, 3, "R$", "Dólar americano, venda (PTAX)", _vigente),
)


class ClienteBCB:
    """Consulta as séries do SGS. Cada indicador é independente: se um falhar, os outros seguem."""

    def __init__(
        self,
        timeout_s: float = 5.0,
        abrir: Callable[..., Any] = urllib.request.urlopen,
        hoje: Callable[[], date] = date.today,
    ):
        self.timeout_s = timeout_s
        self._abrir = abrir
        self._hoje = hoje

    # -------------------------------------------------------------- rede e interpretação
    def _baixar(self, serie: int, quantidade: int) -> list[Ponto]:
        if not 1 <= quantidade <= 20:
            raise ValueError("a API aceita de 1 a 20 valores em 'ultimos/N'")
        pedido = urllib.request.Request(
            URL_SERIE.format(serie=serie, n=quantidade),
            headers={"Accept": "application/json", "User-Agent": "Prumo/1.0 (controle financeiro pessoal)"},
        )
        try:
            with self._abrir(pedido, timeout=self.timeout_s) as resposta:
                bruto = resposta.read(LIMITE_DE_RESPOSTA + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            raise ErroBCB(f"série {serie}: falha de rede ({erro})") from erro
        if len(bruto) > LIMITE_DE_RESPOSTA:
            raise ErroBCB(f"série {serie}: resposta grande demais")
        return self._interpretar(serie, bruto)

    @staticmethod
    def _interpretar(serie: int, bruto: bytes) -> list[Ponto]:
        try:
            dados = json.loads(bruto)
        except ValueError as erro:
            raise ErroBCB(f"série {serie}: resposta não é JSON") from erro
        if not isinstance(dados, list) or not dados:
            raise ErroBCB(f"série {serie}: resposta vazia ou em formato inesperado")
        pontos: list[Ponto] = []
        for item in dados:
            try:
                data = datetime.strptime(item["data"], "%d/%m/%Y").date()
                valor = float(str(item["valor"]).replace(",", "."))
            except (KeyError, TypeError, ValueError) as erro:
                raise ErroBCB(f"série {serie}: item inválido {item!r}") from erro
            if not math.isfinite(valor):
                raise ErroBCB(f"série {serie}: valor não numérico")
            pontos.append(Ponto(data, valor))
        return pontos

    # -------------------------------------------------------------- API pública
    def _indicador(self, definicao: _Definicao) -> Indicador:
        pontos = self._baixar(definicao.serie, definicao.quantidade)
        ponto = definicao.reduzir(pontos, self._hoje())
        return Indicador(
            codigo=definicao.codigo,
            nome=definicao.nome,
            valor=ponto.valor,
            unidade=definicao.unidade,
            data=ponto.data,
            detalhe=definicao.detalhe,
            serie=definicao.serie,
        )

    def buscar(self) -> list[Indicador]:
        def tentar(definicao: _Definicao) -> Indicador | None:
            try:
                return self._indicador(definicao)
            except (ErroBCB, ValueError) as erro:
                log.warning("Indicador %s indisponível: %s", definicao.codigo, erro)
                return None

        with ThreadPoolExecutor(max_workers=len(DEFINICOES)) as grupo:
            resultados = list(grupo.map(tentar, DEFINICOES))
        return [r for r in resultados if r is not None]
