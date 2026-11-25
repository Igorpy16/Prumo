"""Filtro de lançamentos: um objeto que sabe virar cláusula SQL parametrizada."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

from .modelos import Situacao, TipoLancamento
from .util import escapar_like, normalizar


@dataclass(frozen=True, slots=True)
class FiltroLancamentos:
    inicio: date | None = None
    fim: date | None = None
    tipo: TipoLancamento | None = None
    situacao: Situacao | None = None
    busca: str | None = None
    categorias: tuple[int, ...] = ()   # vazio = todas
    contas: tuple[int, ...] = ()       # vazio = todas

    def clausula(self, extras: tuple[str, ...] = ()) -> tuple[str, list[Any]]:
        """Devolve ('WHERE ...', parâmetros). Os valores nunca entram no texto do SQL.

        As colunas não têm prefixo, então a cláusula serve tanto para a tabela
        `lancamentos` quanto para a visão `v_lancamentos`.
        """
        partes: list[str] = list(extras)
        params: list[Any] = []
        if self.inicio:
            partes.append("data >= ?")
            params.append(self.inicio.isoformat())
        if self.fim:
            partes.append("data <= ?")
            params.append(self.fim.isoformat())
        if self.tipo:
            partes.append("tipo = ?")
            params.append(self.tipo.value)
        if self.situacao:
            partes.append("pago = ?")
            params.append(1 if self.situacao is Situacao.PAGO else 0)
        termo = normalizar(self.busca)
        if termo:
            partes.append("norm(descricao) LIKE ? ESCAPE '\\'")
            params.append(f"%{escapar_like(termo)}%")
        if self.categorias:
            partes.append(f"categoria_id IN ({','.join('?' * len(self.categorias))})")
            params.extend(self.categorias)
        if self.contas:
            partes.append(f"conta_id IN ({','.join('?' * len(self.contas))})")
            params.extend(self.contas)
        return ("WHERE " + " AND ".join(partes)) if partes else "", params

    def periodo_anterior(self) -> FiltroLancamentos | None:
        """Mesma duração, imediatamente antes. Só existe se o período tem início e fim."""
        if not (self.inicio and self.fim):
            return None
        dias = (self.fim - self.inicio).days + 1
        novo_fim = self.inicio - timedelta(days=1)
        return replace(self, inicio=novo_fim - timedelta(days=dias - 1), fim=novo_fim)
