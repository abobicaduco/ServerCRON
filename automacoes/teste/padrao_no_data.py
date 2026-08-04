# -*- coding: utf-8 -*-
"""Padrao ServerCRON: retcode 2 (no_data) - pasta/email sem material."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _servercron_log import (  # noqa: E402
    encerrar,
    fechar_log_execucao,
    iniciar_log_execucao,
    log_erro,
    log_info,
)


def main() -> int:
    """Devolve 2 no_data."""
    log_info("Padrao no_data: a simular pasta/email vazio.")
    return encerrar(2, "Nenhum ficheiro/anexo para processar.")


if __name__ == "__main__":
    iniciar_log_execucao(__file__)
    try:
        try:
            code = main()
        except Exception as exc:
            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            code = encerrar(1)
        sys.exit(code)
    finally:
        fechar_log_execucao()
