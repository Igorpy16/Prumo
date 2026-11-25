"""Configuração do aplicativo, lida das variáveis de ambiente.

Todas as opções ficam num único objeto imutável (`Configuracoes`), criado uma vez na
inicialização e entregue às demais classes. Nenhuma outra parte do código lê `os.environ`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO_PADRAO = RAIZ / "data" / "prumo.db"


class ErroDeConfiguracao(RuntimeError):
    """Configuração inválida ou incompleta (por exemplo, produção sem senha)."""


def _como_bool(valor: str | None, padrao: bool) -> bool:
    if valor is None or not valor.strip():
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _como_int(valor: str | None, padrao: int, nome: str, minimo: int = 1) -> int:
    if valor is None or not valor.strip():
        return padrao
    try:
        numero = int(valor)
    except ValueError:
        raise ErroDeConfiguracao(f"{nome} precisa ser um número inteiro.") from None
    if numero < minimo:
        raise ErroDeConfiguracao(f"{nome} precisa ser pelo menos {minimo}.")
    return numero


@dataclass(frozen=True, slots=True)
class Configuracoes:
    """Opções de execução.

    Variáveis de ambiente reconhecidas:
      APP_PASSWORD        senha de acesso (sem ela o app fica aberto: use só no seu computador)
      REQUIRE_AUTH=1      recusa iniciar sem APP_PASSWORD (o Dockerfile já define)
      SECRET_KEY          chave para assinar as sessões (padrão: a própria senha)
      DATABASE_PATH       arquivo do banco SQLite
      SEMEAR_DEMO=0       não cria lançamentos de exemplo na primeira execução
      DEMO_MODE=1         versão pública: somente leitura, dados fictícios, sem login
      REPO_URL            link do repositório, mostrado na faixa da demonstração
      INDICADORES=0       desliga a consulta aos indicadores do Banco Central
    """

    demo: bool = False
    senha: str = ""
    exigir_senha: bool = False
    chave_secreta: str = ""
    caminho_banco: Path = BANCO_PADRAO
    semear_exemplo: bool = True
    url_repositorio: str = ""
    dias_de_sessao: int = 30
    max_tentativas_login: int = 5
    janela_login_s: int = 900
    limite_demo_por_minuto: int = 300
    indicadores_ativos: bool = True
    indicadores_ttl_s: int = 3600
    indicadores_timeout_s: int = 5
    pasta_web: Path = RAIZ / "web"

    @property
    def autenticacao_ativa(self) -> bool:
        """A demonstração nunca pede senha; no modo normal, só pede se houver senha."""
        return (not self.demo) and bool(self.senha)

    @property
    def chave_de_assinatura(self) -> bytes:
        return (self.chave_secreta or self.senha).encode()

    @classmethod
    def do_ambiente(cls, env: Mapping[str, str] | None = None) -> Configuracoes:
        env = os.environ if env is None else env
        demo = _como_bool(env.get("DEMO_MODE"), False)
        senha = "" if demo else env.get("APP_PASSWORD", "")
        exigir = _como_bool(env.get("REQUIRE_AUTH"), False) and not demo

        if exigir and not senha:
            raise ErroDeConfiguracao("Defina a variável de ambiente APP_PASSWORD (a senha de acesso ao app).")
        if exigir and len(senha) < 8:
            raise ErroDeConfiguracao("APP_PASSWORD precisa ter pelo menos 8 caracteres.")

        if demo:
            # A demonstração usa SEMPRE um banco temporário novo e nunca abre o banco real.
            caminho = Path(tempfile.gettempdir()) / "prumo_demo.db"
        else:
            caminho = Path(env["DATABASE_PATH"]) if env.get("DATABASE_PATH") else BANCO_PADRAO

        repo = env.get("REPO_URL", "").strip()
        return cls(
            demo=demo,
            senha=senha,
            exigir_senha=exigir,
            chave_secreta=env.get("SECRET_KEY", ""),
            caminho_banco=caminho,
            semear_exemplo=True if demo else _como_bool(env.get("SEMEAR_DEMO"), True),
            url_repositorio=repo if repo.startswith("https://") else "",
            dias_de_sessao=_como_int(env.get("SESSION_DAYS"), 30, "SESSION_DAYS"),
            indicadores_ativos=_como_bool(env.get("INDICADORES"), True),
        )
