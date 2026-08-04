# -*- coding: utf-8 -*-
"""Teste ServerCRON: abre o Paint."""
import subprocess
import sys

def main() -> None:
    print("[teste] Abrindo Paint…")
    subprocess.Popen(["mspaint.exe"], shell=False)
    print("[teste] Paint disparado.")

if __name__ == "__main__":
    main()
    sys.exit(0)
