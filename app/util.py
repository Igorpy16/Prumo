"""Funções pequenas e puras, usadas por várias camadas."""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

_ESPACOS = re.compile(r"\s+")
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def colapsar_espacos(texto: str) -> str:
    """'  Mercado   Central ' -> 'Mercado Central'."""
    return _ESPACOS.sub(" ", texto).strip()


def normalizar(texto: str | None) -> str:
    """Chave de comparação: sem acentos, sem diferença de caixa, espaços colapsados.

    Usada para evitar duplicatas ('Cartão' x 'cartao') e na busca por texto.
    """
    if not texto:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return colapsar_espacos(sem_acento).casefold()


def escapar_like(termo: str) -> str:
    """Escapa %, _ e \\ para uso em `LIKE ... ESCAPE '\\'`."""
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def neutralizar_formula(texto: str) -> str:
    """Evita 'injeção de fórmula' ao abrir um CSV no Excel (texto começando por = + - @)."""
    return "'" + texto if texto.startswith(_INICIO_DE_FORMULA) else texto


def somar_meses(ano: int, mes: int, n: int) -> tuple[int, int]:
    """Soma (ou subtrai) meses de um par (ano, mês)."""
    indice = ano * 12 + (mes - 1) + n
    return indice // 12, indice % 12 + 1


class Moeda:
    """Dinheiro no banco é sempre inteiro em centavos; só vira decimal nas bordas."""

    @staticmethod
    def para_centavos(valor: Decimal) -> int:
        return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def para_reais(centavos: int | None) -> float:
        return round((centavos or 0) / 100, 2)

    @staticmethod
    def formatar_csv(centavos: int) -> str:
        """12345 -> '123,45' (formato que o Excel em português entende)."""
        return f"{centavos // 100},{centavos % 100:02d}"
