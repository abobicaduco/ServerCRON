# -*- coding: utf-8 -*-
"""
Exemplo de web scraping com Playwright (modelo para agents).
Extrai citacoes de https://quotes.toscrape.com e grava CSV local.
Dependencias sao instaladas sozinhas ao correr (ver DEPENDENCIAS).
"""
from __future__ import annotations

import csv
import importlib
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

TZ = ZoneInfo("America/Sao_Paulo")
_SCRIPT = Path(__file__).resolve()
STEM_LOWER = _SCRIPT.stem.lower()
_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

PASTA_BASE = Path.home() / "Documents" / "Automacoes" / STEM_LOWER
PASTA_SAIDA = PASTA_BASE / "saida"
PASTA_ERROS = PASTA_BASE / "erros"

URL_ALVO = "https://quotes.toscrape.com/"
TIMEOUT_MS = 30_000
VIEWPORT = {"width": 1920, "height": 1080}
# False = abre Chrome visivel (bom para testar). True = sem janela (ServerCRON).
HEADLESS = False
MAX_PAGINAS = 2

# (nome_do_import, nome_do_pacote_pip)
DEPENDENCIAS: list[tuple[str, str]] = [
    ("playwright", "playwright"),
]
POS_INSTALL_CMDS: list[list[str]] = [
    [sys.executable, "-m", "playwright", "install", "chrome"],
]

_log_fp = None


# ---------------------------------------------------------------------------
# Log (console + ficheiro .log da execucao)
# ---------------------------------------------------------------------------

def iniciar_log_execucao() -> Path:
    """Cria LOG_DIR e o ficheiro {STEM_LOWER}_{timestamp}.log."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    caminho = LOG_DIR / f"{STEM_LOWER}_{stamp}.log"
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    log_info(f"Log da execucao: {caminho}")
    log_info(f"Script: {_SCRIPT}")
    log_info(f"STEM_LOWER: {STEM_LOWER}")
    log_info(f"Area: {AREA_NAME}")
    return caminho


def fechar_log_execucao() -> None:
    """Fecha o ficheiro .log da execucao."""
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
    """Padroniza a saida: mensagem + RETCODE. Devolve o codigo para sys.exit."""
    if code == 0 and msg:
        log_ok(msg)
    elif code == 2:
        log_no_data(msg or "Nada para processar.")
    elif code != 0 and msg:
        _emit(f"ERRO: {msg}", erro=True)
    _emit(f"RETCODE: {code}")
    return code


def garantir_dependencias() -> None:
    """Instala pacotes em falta com o pip do interpretador atual."""
    faltando: list[str] = []
    for modulo, pacote in DEPENDENCIAS:
        try:
            importlib.import_module(modulo)
        except ImportError:
            faltando.append(pacote)

    if faltando:
        log_info(f"A instalar dependencias: {', '.join(faltando)}")
        cmd = [sys.executable, "-m", "pip", "install", *faltando]
        subprocess.run(cmd, check=True)
        log_info("Dependencias instaladas.")
        for extra in POS_INSTALL_CMDS:
            log_info(f"A executar pos-install: {' '.join(extra)}")
            subprocess.run(extra, check=True)
    else:
        log_info("Dependencias ja satisfeitas.")


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _gravar_screenshot_erro(page, motivo: str) -> Path | None:
    """Grava screenshot em PASTA_ERROS; devolve o path ou None."""
    try:
        PASTA_ERROS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        destino = PASTA_ERROS / f"erro_{stamp}.png"
        page.screenshot(path=str(destino), full_page=True)
        log_info(f"Screenshot de erro ({motivo}): {destino}")
        return destino
    except Exception as exc:
        log_info(f"Nao foi possivel gravar screenshot: {exc}")
        return None


def extrair_citacoes_da_pagina(page) -> list[dict[str, str]]:
    """Le as citacoes visiveis na pagina atual."""
    cards = page.locator(".quote")
    total = cards.count()
    itens: list[dict[str, str]] = []
    for i in range(total):
        card = cards.nth(i)
        texto = card.locator(".text").inner_text().strip()
        autor = card.locator(".author").inner_text().strip()
        tags = [t.strip() for t in card.locator(".tag").all_inner_texts() if t.strip()]
        if not texto:
            continue
        itens.append(
            {
                "texto": texto,
                "autor": autor,
                "tags": ", ".join(tags),
            }
        )
    return itens


def coletar_citacoes() -> list[dict[str, str]]:
    """Abre Chrome, navega no site e devolve citacoes de ate MAX_PAGINAS."""
    # Import local: so depois de garantir_dependencias() no __main__
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    coletadas: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=HEADLESS)
        context = browser.new_context(viewport=VIEWPORT, locale="pt-BR")
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            log_info(f"Abrindo: {URL_ALVO}")
            page.goto(URL_ALVO, wait_until="domcontentloaded")
            page.locator(".quote").first.wait_for(state="visible")

            for pagina_num in range(1, MAX_PAGINAS + 1):
                log_info(f"Extraindo pagina {pagina_num}...")
                lote = extrair_citacoes_da_pagina(page)
                log_info(f"Pagina {pagina_num}: {len(lote)} citacao(oes).")
                coletadas.extend(lote)

                if pagina_num >= MAX_PAGINAS:
                    break

                botao_next = page.locator("li.next > a")
                if botao_next.count() == 0:
                    log_info("Nao ha pagina seguinte.")
                    break

                botao_next.click()
                page.locator(".quote").first.wait_for(state="visible")

        except PlaywrightTimeoutError as exc:
            _gravar_screenshot_erro(page, "timeout")
            raise RuntimeError(f"Timeout ao carregar ou ler a pagina: {exc}") from exc
        except Exception:
            _gravar_screenshot_erro(page, "falha")
            raise
        finally:
            context.close()
            browser.close()

    return coletadas


def gravar_csv(citacoes: list[dict[str, str]]) -> Path:
    """Grava as citacoes em CSV UTF-8 na pasta de saida."""
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    destino = PASTA_SAIDA / f"quotes_{stamp}.csv"
    with destino.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["texto", "autor", "tags"])
        writer.writeheader()
        writer.writerows(citacoes)
    return destino


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def main() -> int:
    """Retorna 0 success, 1 error, 2 no_data."""
    log_info("Inicio do scraping de citacoes (exemplo Playwright).")
    log_info(f"Saida: {PASTA_SAIDA}")

    try:
        citacoes = coletar_citacoes()
    except Exception as exc:
        log_erro(f"Falha no scraping: {exc}", com_traceback=True)
        return encerrar(1)

    if not citacoes:
        return encerrar(2, "Nenhuma citacao encontrada no site.")

    try:
        csv_path = gravar_csv(citacoes)
    except Exception as exc:
        log_erro(f"Falha ao gravar CSV: {exc}", com_traceback=True)
        return encerrar(1)

    log_info(f"CSV gerado: {csv_path}")
    return encerrar(0, f"Concluido: {len(citacoes)} citacao(oes) gravada(s).")


if __name__ == "__main__":
    iniciar_log_execucao()
    try:
        try:
            garantir_dependencias()
            code = main()
        except Exception as exc:
            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            code = encerrar(1)
        sys.exit(code)
    finally:
        fechar_log_execucao()
