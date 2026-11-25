"""Entidades do domínio (objetos simples, sem acesso a banco)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .util import Moeda


class TipoLancamento(str, Enum):
    RECEITA = "receita"
    DESPESA = "despesa"


class Situacao(str, Enum):
    PAGO = "pago"
    PENDENTE = "pendente"


@dataclass(frozen=True, slots=True)
class Categoria:
    id: int
    nome: str
    tipo: TipoLancamento

    def para_dict(self) -> dict[str, Any]:
        return {"id": self.id, "nome": self.nome, "tipo": self.tipo.value}


@dataclass(frozen=True, slots=True)
class Conta:
    id: int
    nome: str

    def para_dict(self) -> dict[str, Any]:
        return {"id": self.id, "nome": self.nome}


@dataclass(frozen=True, slots=True)
class NovoLancamento:
    """Dados já resolvidos (ids de categoria e conta) prontos para gravar."""

    data: date
    descricao: str
    valor_centavos: int
    tipo: TipoLancamento
    categoria_id: int
    conta_id: int
    pago: bool = True


@dataclass(frozen=True, slots=True)
class Lancamento:
    id: int
    data: date
    descricao: str
    valor_centavos: int
    tipo: TipoLancamento
    pago: bool
    categoria_id: int
    categoria: str
    conta_id: int
    conta: str

    @classmethod
    def da_linha(cls, linha: sqlite3.Row) -> Lancamento:
        return cls(
            id=linha["id"],
            data=date.fromisoformat(linha["data"]),
            descricao=linha["descricao"],
            valor_centavos=linha["valor_centavos"],
            tipo=TipoLancamento(linha["tipo"]),
            pago=bool(linha["pago"]),
            categoria_id=linha["categoria_id"],
            categoria=linha["categoria"],
            conta_id=linha["conta_id"],
            conta=linha["conta"],
        )

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "data": self.data.isoformat(),
            "descricao": self.descricao,
            "valor": Moeda.para_reais(self.valor_centavos),
            "tipo": self.tipo.value,
            "pago": self.pago,
            "categoria_id": self.categoria_id,
            "categoria": self.categoria,
            "conta_id": self.conta_id,
            "conta": self.conta,
        }


@dataclass(frozen=True, slots=True)
class Totais:
    receitas: int
    despesas: int
    a_pagar: int
    qtd_a_pagar: int
    quantidade: int

    @property
    def saldo(self) -> int:
        return self.receitas - self.despesas


@dataclass(frozen=True, slots=True)
class PontoMensal:
    mes: str  # AAAA-MM
    receitas: int
    despesas: int
    acumulado: int

    @property
    def saldo(self) -> int:
        return self.receitas - self.despesas


@dataclass(frozen=True, slots=True)
class ItemAgrupado:
    id: int
    nome: str
    total: int
    quantidade: int


@dataclass(frozen=True, slots=True)
class ConsumoDeMeta:
    categoria_id: int
    categoria: str
    limite: int
    gasto: int


@dataclass(frozen=True, slots=True)
class Meta:
    categoria_id: int
    categoria: str
    limite: int
