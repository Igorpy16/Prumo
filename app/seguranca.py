"""Autenticação por senha única, sessão assinada e limites de uso."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections.abc import Callable

from .config import Configuracoes


class AssinadorDeSessao:
    """Emite e confere tokens `expira.assinatura` (HMAC-SHA256). Não guarda estado no servidor."""

    def __init__(self, chave: bytes, duracao_s: int, relogio: Callable[[], float] = time.time):
        self._chave = chave
        self._duracao_s = duracao_s
        self._relogio = relogio

    def _assinar(self, expira: int) -> str:
        return hmac.new(self._chave, f"sessao:{expira}".encode(), hashlib.sha256).hexdigest()

    def emitir(self) -> str:
        expira = int(self._relogio()) + self._duracao_s
        return f"{expira}.{self._assinar(expira)}"

    def valido(self, token: str | None) -> bool:
        if not token:
            return False
        texto, _, assinatura = token.partition(".")
        if not (texto.isascii() and texto.isdigit()):
            return False
        expira = int(texto)
        return expira > self._relogio() and hmac.compare_digest(assinatura, self._assinar(expira))


class _JanelaDequantidade:
    """Conta eventos por chave dentro de uma janela de tempo (thread-safe)."""

    def __init__(self, janela_s: float, relogio: Callable[[], float] = time.time, maximo_de_chaves: int = 2000):
        self._janela_s = janela_s
        self._relogio = relogio
        self._maximo_de_chaves = maximo_de_chaves
        self._eventos: dict[str, list[float]] = {}
        self._trava = threading.Lock()

    def _recentes(self, chave: str, agora: float) -> list[float]:
        return [t for t in self._eventos.get(chave, []) if agora - t < self._janela_s]

    def contar(self, chave: str) -> int:
        with self._trava:
            return len(self._recentes(chave, self._relogio()))

    def registrar(self, chave: str) -> int:
        with self._trava:
            agora = self._relogio()
            if len(self._eventos) > self._maximo_de_chaves:
                self._eventos.clear()
            recentes = [*self._recentes(chave, agora), agora]
            self._eventos[chave] = recentes
            return len(recentes)

    def limpar(self, chave: str) -> None:
        with self._trava:
            self._eventos.pop(chave, None)


class LimitadorDeTentativas:
    """Bloqueia o login depois de N senhas erradas em uma janela de tempo (por IP)."""

    def __init__(self, maximo: int, janela_s: float, relogio: Callable[[], float] = time.time):
        self._maximo = maximo
        self._janela = _JanelaDequantidade(janela_s, relogio)

    def bloqueado(self, chave: str) -> bool:
        return self._janela.contar(chave) >= self._maximo

    def registrar_falha(self, chave: str) -> None:
        self._janela.registrar(chave)

    def limpar(self, chave: str) -> None:
        self._janela.limpar(chave)


class LimitadorDeRequisicoes:
    """Limite de requisições por minuto (usado só na demonstração pública)."""

    def __init__(self, limite: int, janela_s: float = 60.0, relogio: Callable[[], float] = time.time):
        self._limite = limite
        self._janela = _JanelaDequantidade(janela_s, relogio)

    def excedeu(self, chave: str) -> bool:
        return self._janela.registrar(chave) > self._limite


class ServicoDeAutenticacao:
    def __init__(self, config: Configuracoes):
        self._config = config
        self.assinador = AssinadorDeSessao(config.chave_de_assinatura, config.dias_de_sessao * 86400)
        self.tentativas = LimitadorDeTentativas(config.max_tentativas_login, config.janela_login_s)

    @property
    def ativa(self) -> bool:
        return self._config.autenticacao_ativa

    def senha_correta(self, senha: str) -> bool:
        return hmac.compare_digest(senha.encode(), self._config.senha.encode())
