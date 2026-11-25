"""Repositórios: a única camada que escreve SQL.

Cada método recebe a conexão aberta pelo serviço, para que várias operações
possam participar da mesma transação.
"""

from .catalogo import CatalogoRepositorio
from .configuracoes import ConfiguracaoRepositorio
from .lancamentos import LancamentoRepositorio
from .orcamento import OrcamentoRepositorio
from .relatorios import RelatorioRepositorio

__all__ = [
    "CatalogoRepositorio",
    "ConfiguracaoRepositorio",
    "LancamentoRepositorio",
    "OrcamentoRepositorio",
    "RelatorioRepositorio",
]
