# -*- coding: utf-8 -*-
"""Teste ServerCRON: so imprime um hello (sem abrir janelas)."""
from datetime import datetime
import sys

def main() -> None:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[teste] hello_cron OK @ {agora}")

if __name__ == "__main__":
    main()
    sys.exit(0)
