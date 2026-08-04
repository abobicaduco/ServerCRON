# -*- coding: utf-8 -*-
"""Teste ServerCRON: abre a Calculadora do Windows."""
import subprocess
import sys

def main() -> None:
    print("[teste] Abrindo Calculadora…")
    subprocess.Popen(["calc.exe"], shell=False)
    print("[teste] Calculadora disparada.")

if __name__ == "__main__":
    main()
    sys.exit(0)
