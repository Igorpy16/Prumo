"""Formato dos dados que entram pela API (validação com Pydantic)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .modelos import TipoLancamento
from .util import colapsar_espacos

TETO_VALOR = Decimal("9999999999.99")
DATA_MINIMA, DATA_MAXIMA = date(2000, 1, 1), date(2100, 12, 31)


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class LancamentoEntrada(_Entrada):
    data: date
    descricao: str = Field(min_length=1, max_length=120)
    valor: Decimal = Field(gt=0, le=TETO_VALOR, max_digits=13, decimal_places=2)
    tipo: TipoLancamento
    categoria: str = Field(min_length=1, max_length=60)
    conta: str = Field(default="Conta corrente", min_length=1, max_length=60)
    pago: bool = True

    @field_validator("descricao", "categoria", "conta")
    @classmethod
    def _sem_espacos_repetidos(cls, texto: str) -> str:
        return colapsar_espacos(texto)

    @field_validator("data")
    @classmethod
    def _data_plausivel(cls, valor: date) -> date:
        if not DATA_MINIMA <= valor <= DATA_MAXIMA:
            raise ValueError("Use uma data entre 2000 e 2100.")
        return valor


class PagoEntrada(_Entrada):
    pago: bool


class MetaEntrada(_Entrada):
    categoria_id: int = Field(ge=1)
    limite: Decimal = Field(ge=0, le=Decimal("9999999.99"), max_digits=10, decimal_places=2)


class MetasEntrada(_Entrada):
    metas: list[MetaEntrada] = Field(max_length=200)


class LoginEntrada(_Entrada):
    senha: str = Field(max_length=200)
