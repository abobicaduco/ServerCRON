# -*- coding: utf-8 -*-
"""Sonda a pasta Downloads/ServerCRON_probe_entrada e conta PDFs presentes."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite importar _servercron_log na pasta automacoes/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _servercron_log import (  # noqa: E402
    encerrar,
    fechar_log_execucao,
    iniciar_log_execucao,
    log_erro,
    log_info,
)

PASTA_ENTRADA = Path.home() / "Downloads" / "ServerCRON_probe_entrada"


def listar_pdfs(pasta: Path) -> list[Path]:
    """Lista os PDFs da pasta de entrada (nao recursivo)."""
    return sorted(pasta.glob("*.pdf"))


def main() -> int:
    """Conta PDFs e devolve 0 (success) ou 2 (no_data)."""
    try:
        PASTA_ENTRADA.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log_erro(f"Falha ao criar a pasta de entrada: {exc}", com_traceback=True)
        return encerrar(1)

    pdfs = listar_pdfs(PASTA_ENTRADA)
    if not pdfs:
        return encerrar(2, "Nenhum PDF na pasta de entrada.")

    log_info(f"Encontrados {len(pdfs)} PDF(s) em {PASTA_ENTRADA}.")
    return encerrar(0, f"Contados {len(pdfs)} PDF(s).")


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
