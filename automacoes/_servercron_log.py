# -*- coding: utf-8 -*-
"""Helpers de log ServerCRON: console + ficheiro .log por execucao.

Usado pelos scripts em automacoes/ conforme INSTRUCOES_AUTOMACAO_PYTHON.md.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

_log_fp = None
_script_path: Path | None = None
_area_name = "."


def _data_root() -> Path:
    """Mesma regra do server.py: SERVERCRON_DATA_ROOT ou ~/Documents/ServerCRON.

    Antes este modulo escrevia sempre em ~/Desktop/ServerCRON/logs, divergindo
    do LOGS_DIR real do servidor (~/Documents/ServerCRON/logs por defeito).
    """
    raw = (os.environ.get("SERVERCRON_DATA_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "Documents" / "ServerCRON").resolve()


def configurar(script_file: str | Path) -> None:
    """Define o script atual (passe __file__) para area e nome do .log."""
    global _script_path, _area_name
    _script_path = Path(script_file).resolve()
    root = next(
        (p for p in _script_path.parents if p.name.lower() == "automacoes"),
        _script_path.parent,
    )
    try:
        rel = _script_path.parent.relative_to(root)
        _area_name = "." if str(rel) == "." else str(rel).replace("\\", "/")
    except ValueError:
        _area_name = _script_path.parent.name


def log_dir() -> Path:
    return _data_root() / "logs" / _area_name


def iniciar_log_execucao(script_file: str | Path | None = None) -> Path:
    """Cria logs/<AREA>/<stem_lower>_<timestamp>.log e devolve o path."""
    global _log_fp
    if script_file is not None:
        configurar(script_file)
    if _script_path is None:
        raise RuntimeError("Chame configurar(__file__) ou passar script_file")
    destino = log_dir()
    destino.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    caminho = destino / f"{_script_path.stem.lower()}_{stamp}.log"
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    log_info(f"Log da execucao: {caminho}")
    log_info(f"Script: {_script_path}")
    log_info(f"Area: {_area_name}")
    return caminho


def fechar_log_execucao() -> None:
    global _log_fp
    if _log_fp is not None:
        _log_fp.close()
        _log_fp = None


def _escrever_ficheiro(linha: str) -> None:
    if _log_fp is not None:
        _log_fp.write(linha.rstrip("\n") + "\n")
        _log_fp.flush()


def _emit(msg: str, *, erro: bool = False) -> None:
    print(msg, file=(sys.stderr if erro else sys.stdout), flush=True)
    _escrever_ficheiro(msg)


def log_info(msg: str) -> None:
    _emit(f"INFO: {msg}")


def log_ok(msg: str) -> None:
    _emit(f"OK: {msg}")


def log_no_data(msg: str) -> None:
    _emit(f"NO_DATA: {msg}")


def log_erro(msg: str, *, com_traceback: bool = True) -> None:
    _emit(f"ERRO: {msg}", erro=True)
    if com_traceback:
        _emit(traceback.format_exc().rstrip("\n"), erro=True)


def encerrar(code: int, msg: str = "") -> int:
    if code == 0 and msg:
        log_ok(msg)
    elif code == 2:
        log_no_data(msg or "Nada para processar.")
    elif code != 0 and msg:
        _emit(f"ERRO: {msg}", erro=True)
    _emit(f"RETCODE: {code}")
    return code
