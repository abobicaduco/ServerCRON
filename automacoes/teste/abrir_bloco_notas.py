# -*- coding: utf-8 -*-
"""Teste ServerCRON: abre o Bloco de Notas."""
import subprocess
import sys

def main() -> None:
    print("[teste] Abrindo Bloco de Notas…")
    subprocess.Popen(["notepad.exe"], shell=False)
    print("[teste] Bloco de Notas disparado.")

if __name__ == "__main__":
    main()
    sys.exit(0)
