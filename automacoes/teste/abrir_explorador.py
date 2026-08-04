# -*- coding: utf-8 -*-
"""Teste ServerCRON: abre o Explorador de Ficheiros na pasta home."""
import os
import subprocess
import sys
from pathlib import Path

def main() -> None:
    pasta = Path.home()
    print(f"[teste] Abrindo Explorador em {pasta}…")
    subprocess.Popen(["explorer.exe", str(pasta)], shell=False)
    print("[teste] Explorador disparado.")

if __name__ == "__main__":
    main()
    sys.exit(0)
