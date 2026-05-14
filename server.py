# -*- coding: utf-8 -*-
"""Compat launcher: ``python server.py`` runs ``ServerCRON.py`` as the main script (same as ``python ServerCRON.py``)."""
from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "ServerCRON.py"), run_name="__main__")
