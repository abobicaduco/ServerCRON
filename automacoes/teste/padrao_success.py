# -*- coding: utf-8 -*-
"""Padrao ServerCRON: termina com retcode 0 (success)."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite importar _servercron_log na pasta automacoes/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _servercron_log import (  # noqa: E402
    encerrar,
    fechar_log_execucao,
    iniciar_log_execucao,
    log_info,
)


def main() -> int:
    """Devolve 0 success."""
    log_info("Padrao success: simulacao de processamento OK.")
    return encerrar(0, "Processamento concluido.")


if __name__ == "__main__":
    iniciar_log_execucao(__file__)
    try:
        try:
            code = main()
        except Exception as exc:
            from _servercron_log import log_erro

            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            code = encerrar(1)
        sys.exit(code)
    finally:
        fechar_log_execucao()
