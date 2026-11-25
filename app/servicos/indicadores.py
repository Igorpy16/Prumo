"""Indicadores de mercado (Banco Central) com cache e tolerância a falhas."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..database import Database
from ..integracoes.bcb import LICENCA, PORTAL, FonteDeIndicadores, Indicador
from ..repositorios import ConfiguracaoRepositorio

log = logging.getLogger("prumo.indicadores")

CHAVE_SNAPSHOT = "indicadores_snapshot"
ESPERA_APOS_FALHA_S = 60

FONTE = {
    "nome": "Banco Central do Brasil, Dados Abertos (SGS)",
    "url": PORTAL,
    "licenca": "ODbL",
    "licenca_url": LICENCA,
}


class IndicadoresServico:
    """Entrega os indicadores sem nunca derrubar a tela.

    * Cache em memória por `ttl_s` (os dados do BCB mudam, no máximo, uma vez por dia).
    * Só uma consulta externa por vez (as demais esperam o resultado).
    * Se o BCB falhar, devolve o último valor conhecido marcado como `desatualizado`,
      e só volta a tentar depois de alguns segundos.
    * O último resultado bom fica salvo no banco, para sobreviver a reinícios.
    """

    def __init__(
        self,
        fonte: FonteDeIndicadores | None,
        db: Database,
        configuracoes: ConfiguracaoRepositorio,
        ttl_s: int = 3600,
        relogio: Callable[[], float] = time.time,
    ):
        self._fonte = fonte
        self._db = db
        self._configuracoes = configuracoes
        self._ttl_s = ttl_s
        self._relogio = relogio
        self._trava = threading.Lock()
        self._itens: list[dict[str, Any]] | None = None
        self._obtido_em: float = 0.0
        self._proxima_tentativa: float = 0.0

    # ------------------------------------------------------------------ persistência
    def _carregar_snapshot(self) -> None:
        if self._itens is not None:
            return
        try:
            with self._db.leitura() as con:
                bruto = self._configuracoes.obter(con, CHAVE_SNAPSHOT)
            if bruto:
                dados = json.loads(bruto)
                self._itens, self._obtido_em = dados["itens"], float(dados["obtido_em"])
        except (ValueError, KeyError, TypeError):
            log.warning("Snapshot de indicadores ignorado (formato inesperado).")

    def _salvar_snapshot(self) -> None:
        try:
            with self._db.transacao() as con:
                self._configuracoes.salvar(
                    con, CHAVE_SNAPSHOT, json.dumps({"itens": self._itens, "obtido_em": self._obtido_em})
                )
        except Exception:  # noqa: BLE001 - guardar o cache nunca pode quebrar a resposta
            log.exception("Não foi possível salvar o snapshot de indicadores.")

    # ------------------------------------------------------------------ consulta
    def _atualizar(self) -> None:
        agora = self._relogio()
        try:
            itens: list[Indicador] = self._fonte.buscar() if self._fonte else []
        except Exception:  # noqa: BLE001
            log.exception("Falha inesperada ao buscar indicadores.")
            itens = []
        if itens:
            self._itens = [i.para_dict() for i in itens]
            self._obtido_em = agora
            self._proxima_tentativa = 0.0
            self._salvar_snapshot()
        else:
            self._proxima_tentativa = agora + ESPERA_APOS_FALHA_S

    def obter(self) -> dict[str, Any]:
        if self._fonte is None:
            return {"itens": [], "ativo": False, "desatualizado": False, "atualizado_em": None, "fonte": FONTE}
        with self._trava:
            self._carregar_snapshot()
            agora = self._relogio()
            vencido = self._itens is None or agora - self._obtido_em >= self._ttl_s
            if vencido and agora >= self._proxima_tentativa:
                self._atualizar()
            itens = self._itens or []
            desatualizado = bool(itens) and (agora - self._obtido_em >= self._ttl_s)
            atualizado_em = (
                datetime.fromtimestamp(self._obtido_em, UTC).isoformat(timespec="seconds") if itens else None
            )
        return {
            "itens": itens,
            "ativo": True,
            "desatualizado": desatualizado,
            "atualizado_em": atualizado_em,
            "fonte": FONTE,
        }
