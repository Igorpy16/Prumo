"""Comandos de manutenção: `python -m app.cli migrar | backup | healthcheck`."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from .config import Configuracoes
from .database import Database


def _migrar(config: Configuracoes, _: argparse.Namespace) -> int:
    db = Database(config.caminho_banco)
    db.migrar()
    print(f"Banco na versão {db.versao()}: {config.caminho_banco}")
    return 0


def _backup(config: Configuracoes, args: argparse.Namespace) -> int:
    destino = Path(args.pasta)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"prumo-{datetime.now():%Y%m%d-%H%M%S}.db"
    Database(config.caminho_banco).copia_de_seguranca(arquivo)
    antigos = sorted(destino.glob("prumo-*.db"))[: -args.manter]
    for velho in antigos:
        velho.unlink()
    print(f"Cópia criada: {arquivo} (mantidas as {args.manter} mais recentes)")
    return 0


def _healthcheck(_: Configuracoes, args: argparse.Namespace) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{args.porta}/healthz", timeout=3) as r:  # noqa: S310
            return 0 if r.status == 200 else 1
    except Exception:
        return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("migrar", help="aplica as migrações do banco").set_defaults(acao=_migrar)
    b = sub.add_parser("backup", help="cria uma cópia consistente do banco")
    b.add_argument("--pasta", default="backups")
    b.add_argument("--manter", type=int, default=14)
    b.set_defaults(acao=_backup)
    h = sub.add_parser("healthcheck", help="consulta /healthz (usado pelo Docker)")
    h.add_argument("--porta", type=int, default=int(__import__("os").environ.get("PORT", "8000")))
    h.set_defaults(acao=_healthcheck)
    args = p.parse_args(argv)
    from .config import Configuracoes as C

    return args.acao(C.do_ambiente() if args.comando != "healthcheck" else None, args)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
