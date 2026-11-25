"""Exceções de domínio. A camada de API as traduz para respostas HTTP."""

from __future__ import annotations


class ErroDeDominio(Exception):
    """Base das falhas previstas pelas regras do sistema."""

    status_http = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class NaoEncontrado(ErroDeDominio):
    status_http = 404


class RegraDeNegocio(ErroDeDominio):
    status_http = 422


class Conflito(ErroDeDominio):
    status_http = 409
