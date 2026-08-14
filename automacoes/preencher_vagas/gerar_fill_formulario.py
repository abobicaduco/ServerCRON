# -*- coding: utf-8 -*-
"""Le HTML de formulario de vaga e gera JS IIFE para colar no console do Chrome."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

_SCRIPT = Path(__file__).resolve()
BASE_DIR = _SCRIPT.parent
_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

HTML_PADRAO = Path.home() / "Desktop" / "gupy.txt"
SAIDA_JS = Path.home() / "Desktop" / "fill_formulario.js"
PERFIL_MD = Path("D:/docs_pessoais/perfil_completo_carlos_eduardo.md")
PROMPT_SISTEMA = BASE_DIR / "prompt_sistema.md"
RESPOSTAS_FIXAS = BASE_DIR / "respostas_fixas.json"
# Zen gemini-3.5-flash exige billing; free/auth locais funcionam
MODELO_PADRAO = "opencode/deepseek-v4-flash-free"
HTML_MAX_CHARS = 80_000
PERFIL_MAX_CHARS = 12_000
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

OnLog = Callable[[str], None]

_log_fp = None
_on_log_extra: OnLog | None = None


def set_on_log_extra(callback: OnLog | None) -> None:
    """Callback opcional para espelhar logs na interface web."""
    global _on_log_extra
    _on_log_extra = callback


def _avisar_ui(msg: str) -> None:
    if _on_log_extra is not None:
        try:
            _on_log_extra(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Logs (padrao ServerCRON)
# ---------------------------------------------------------------------------


def iniciar_log_execucao() -> Path:
    """Cria logs/<AREA>/<stem_lower>_<timestamp>.log e devolve o path."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    caminho = LOG_DIR / f"{_SCRIPT.stem.lower()}_{stamp}.log"
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    _escrever_ficheiro(f"INFO: Log da execucao: {caminho}")
    _escrever_ficheiro(f"INFO: Script: {_SCRIPT}")
    _escrever_ficheiro(f"INFO: Area: {AREA_NAME}")
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
    stream = sys.stderr if erro else sys.stdout
    print(msg, file=stream, flush=True)
    _escrever_ficheiro(msg)
    _avisar_ui(msg)


def log_info(msg: str) -> None:
    _emit(f"INFO: {msg}")


def log_ok(msg: str) -> None:
    _emit(f"OK: {msg}")


def log_no_data(msg: str) -> None:
    _emit(f"NO_DATA: {msg}")


def log_erro(msg: str, *, com_traceback: bool = True) -> None:
    _emit(f"ERRO: {msg}", erro=True)
    if com_traceback:
        tb = traceback.format_exc()
        if tb and tb.strip() != "NoneType: None":
            _emit(tb.rstrip("\n"), erro=True)


def encerrar(code: int, msg: str = "") -> int:
    """Padroniza a saida: mensagem + RETCODE. code: 0 success, 1 error, 2 no_data."""
    if code == 0:
        if msg:
            log_ok(msg)
    elif code == 2:
        log_no_data(msg or "Nada para processar.")
    else:
        if msg:
            _emit(f"ERRO: {msg}", erro=True)
    _emit(f"RETCODE: {code}")
    return code


# ---------------------------------------------------------------------------
# HTML e prompt
# ---------------------------------------------------------------------------


def limpar_html(html: str) -> str:
    """Remove scripts/estilos/ruido e prioriza o bloco main do formulario."""
    texto = html
    texto = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", texto)
    texto = re.sub(r"(?is)<style\b[^>]*>.*?</style>", "", texto)
    texto = re.sub(r"(?is)<noscript\b[^>]*>.*?</noscript>", "", texto)
    texto = re.sub(r"(?is)<!--.*?-->", "", texto)

    main = re.search(r"(?is)<main\b[^>]*>.*?</main>", texto)
    if main:
        texto = main.group(0)

    # Remove blocos tipicos de ruido restantes
    ruido_ids = (
        r"byRemovePortal|fb-root|gupy-news|ht-skip|beamerUtilities|"
        r"privacytools|cookie|Consent"
    )
    texto = re.sub(
        rf'(?is)<div[^>]*(?:id|class)=["\'][^"\']*(?:{ruido_ids})[^"\']*["\'][^>]*>.*?</div>',
        "",
        texto,
    )

    texto = re.sub(r"\s{2,}", " ", texto).strip()
    if len(texto) > HTML_MAX_CHARS:
        texto = texto[:HTML_MAX_CHARS] + "\n<!-- HTML truncado -->"
    return texto


def ler_texto(path: Path, *, max_chars: int | None = None) -> str:
    """Le ficheiro UTF-8; se falhar encoding, tenta latin-1."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="latin-1")
    if max_chars is not None and len(raw) > max_chars:
        return raw[:max_chars] + "\n\n[... truncado ...]"
    return raw


def montar_pedido(
    *,
    html_limpo: str,
    perfil: str,
    respostas: dict,
    tipo: str,
    submit: bool,
) -> str:
    """Monta o prompt completo enviado ao OpenCode."""
    sistema = ler_texto(PROMPT_SISTEMA)
    respostas_txt = json.dumps(respostas, ensure_ascii=False, indent=2)
    submit_flag = "true" if submit else "false"
    return (
        f"{sistema}\n\n"
        f"## Parametros desta execucao\n\n"
        f"- TIPO_CONTRATO: {tipo}\n"
        f"- SUBMIT: {submit_flag}\n\n"
        f"## respostas_fixas.json\n\n"
        f"```json\n{respostas_txt}\n```\n\n"
        f"## Resumo do perfil\n\n"
        f"{perfil}\n\n"
        f"## HTML limpo do formulario\n\n"
        f"```html\n{html_limpo}\n```\n\n"
        f"Gere agora APENAS o IIFE JavaScript para preencher este formulario no console."
    )


def extrair_iife(texto: str) -> str | None:
    """Extrai o primeiro IIFE completo da resposta do modelo."""
    limpo = texto.strip()
    # Remove fences markdown se existirem
    limpo = re.sub(r"^```(?:javascript|js)?\s*", "", limpo, flags=re.I)
    limpo = re.sub(r"\s*```$", "", limpo)

    inicio = limpo.find("(function")
    if inicio < 0:
        inicio = limpo.find("(() =>")
    if inicio < 0:
        inicio = limpo.find("(async function")
    if inicio < 0:
        return None

    trecho = limpo[inicio:]
    # Corta lixo apos o fechamento tipico })();
    m = re.search(r"\)\s*\(\s*\)\s*;?", trecho)
    if not m:
        return None
    fim = m.end()
    codigo = trecho[:fim].strip()
    if not codigo.endswith(";"):
        codigo += ";"
    return codigo


def resolver_opencode() -> str:
    """Prefere o opencode.exe do WinGet (evita wrapper do PowerShell profile)."""
    candidatos = [
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "SST.opencode_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "opencode.exe",
        Path.home() / ".local" / "bin" / "opencode.exe",
    ]
    for cand in candidatos:
        if cand.is_file():
            return str(cand)
    return "opencode"


def limpar_saida_modelo(texto: str) -> str:
    """Remove ANSI e linhas de status do OpenCode TUI."""
    limpo = _ANSI_RE.sub("", texto)
    linhas = []
    for linha in limpo.splitlines():
        s = linha.strip()
        if not s:
            continue
        if s.startswith("> build") or s.startswith("→") or s.startswith("->"):
            continue
        if s.startswith("Read ") and s.endswith(".md"):
            continue
        linhas.append(linha)
    return "\n".join(linhas).strip()


def chamar_opencode(pedido: str, modelo: str) -> str:
    """Chama `opencode run` com o pedido em ficheiro anexado (stdout em streaming)."""
    exe = resolver_opencode()

    with tempfile.TemporaryDirectory(prefix="fill_form_") as tmp:
        pedido_path = Path(tmp) / "pedido_fill.md"
        pedido_path.write_text(pedido, encoding="utf-8")
        # Mensagem ANTES de --file: senao o OpenCode trata o texto como path
        cmd = [
            exe,
            "run",
            "--model",
            modelo,
            (
                "Leia o ficheiro anexado pedido_fill.md. "
                "Responda APENAS com o IIFE JavaScript pedido, sem markdown."
            ),
            "--file",
            str(pedido_path),
        ]
        log_info(f"Chamando OpenCode exe={exe} modelo={modelo}")
        log_info("Aguardando resposta da IA (pode demorar 10-60s)...")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        bruto_linhas: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            bruto_linhas.append(line)
            limpa = _ANSI_RE.sub("", line).rstrip()
            if not limpa:
                continue
            trecho = limpa if len(limpa) <= 400 else limpa[:400] + "..."
            log_info(f"[IA] {trecho}")

        code = proc.wait()
        saida = limpar_saida_modelo("".join(bruto_linhas))
        log_info(f"OpenCode finalizou com code={code}")

        if code != 0 and not saida:
            raise RuntimeError(
                f"opencode falhou (code={code}): {saida[:2000] or 'sem saida'}"
            )
        if not saida:
            raise RuntimeError("opencode devolveu saida vazia.")
        return saida


def copiar_clipboard(path: Path) -> bool:
    """Copia o conteudo do ficheiro para a area de transferencia (Windows)."""
    ps = (
        "$p = Join-Path $env:USERPROFILE 'Desktop\\fill_formulario.js'; "
        "Get-Content -LiteralPath $p -Raw -Encoding UTF8 | Set-Clipboard"
    )
    # Usa o path real passado
    ps = (
        f"$p = '{path}'; "
        "Get-Content -LiteralPath $p -Raw -Encoding UTF8 | Set-Clipboard"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def gerar_js_de_html(
    html_bruto: str,
    *,
    tipo: str = "clt",
    submit: bool = False,
    modelo: str = MODELO_PADRAO,
    on_log: OnLog | None = None,
) -> str:
    """
    Gera o IIFE JavaScript a partir do HTML bruto do formulario.
    Usado pela CLI e pela interface web.
    """
    if on_log is not None:
        set_on_log_extra(on_log)

    try:
        if not html_bruto.strip():
            raise ValueError("HTML vazio.")
        if tipo not in ("estagio", "clt"):
            raise ValueError("tipo deve ser 'estagio' ou 'clt'.")
        if not PROMPT_SISTEMA.exists():
            raise FileNotFoundError(f"prompt_sistema.md ausente: {PROMPT_SISTEMA}")
        if not RESPOSTAS_FIXAS.exists():
            raise FileNotFoundError(f"respostas_fixas.json ausente: {RESPOSTAS_FIXAS}")

        log_info("Lendo respostas_fixas.json e perfil...")
        respostas = json.loads(ler_texto(RESPOSTAS_FIXAS))
        perfil = ""
        if PERFIL_MD.exists():
            perfil = ler_texto(PERFIL_MD, max_chars=PERFIL_MAX_CHARS)
            log_info(f"Perfil carregado ({len(perfil)} chars).")
        else:
            log_info("Perfil.md nao encontrado; usando so respostas_fixas.")

        log_info("Limpando HTML (scripts, banners, ruido)...")
        html_limpo = limpar_html(html_bruto)
        log_info(
            f"HTML recebido ({len(html_bruto)} chars brutos, {len(html_limpo)} limpos)"
        )
        log_info(f"Tipo={tipo} submit={submit} modelo={modelo}")

        log_info("Montando pedido para a IA...")
        pedido = montar_pedido(
            html_limpo=html_limpo,
            perfil=perfil,
            respostas=respostas,
            tipo=tipo,
            submit=submit,
        )
        log_info(f"Pedido pronto ({len(pedido)} chars). Enviando ao OpenCode...")

        resposta = chamar_opencode(pedido, modelo)
        log_info("Extraindo IIFE da resposta...")
        iife = extrair_iife(resposta)
        if not iife:
            raise RuntimeError(
                "Nao foi possivel extrair IIFE da resposta do modelo. "
                f"Trecho: {resposta[:800]}"
            )
        log_ok(f"IIFE extraido ({len(iife)} chars).")
        return iife
    finally:
        if on_log is not None:
            set_on_log_extra(None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera JS de preenchimento a partir do HTML colado da vaga."
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=HTML_PADRAO,
        help="Path do HTML colado (padrao: Desktop/gupy.txt)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SAIDA_JS,
        help="Path do JS de saida (padrao: Desktop/fill_formulario.js)",
    )
    parser.add_argument(
        "--tipo",
        choices=("estagio", "clt"),
        default="clt",
        help="Pretensao salarial: estagio=2000, clt=2500",
    )
    parser.add_argument(
        "--model",
        default=MODELO_PADRAO,
        help=f"Modelo OpenCode (padrao: {MODELO_PADRAO})",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Permite o JS clicar em Salvar/Continuar",
    )
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Nao copia o JS para a area de transferencia",
    )
    return parser.parse_args()


def main() -> int:
    """Retorna 0 success, 1 error, 2 no_data."""
    iniciar_log_execucao()
    args = parse_args()

    html_path: Path = args.html.expanduser().resolve()
    out_path: Path = args.out.expanduser().resolve()

    if not html_path.exists():
        return encerrar(2, f"HTML nao encontrado: {html_path}")

    html_bruto = ler_texto(html_path)
    if not html_bruto.strip():
        return encerrar(2, f"HTML vazio: {html_path}")

    log_info(f"HTML: {html_path}")
    try:
        iife = gerar_js_de_html(
            html_bruto,
            tipo=args.tipo,
            submit=args.submit,
            modelo=args.model,
        )
    except ValueError as exc:
        return encerrar(2, str(exc))
    except Exception as exc:
        log_erro(f"Falha ao gerar JS: {exc}")
        return encerrar(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(iife + "\n", encoding="utf-8")
    log_ok(f"JS gravado em: {out_path}")

    if not args.no_clipboard:
        if copiar_clipboard(out_path):
            log_ok("JS copiado para a area de transferencia.")
        else:
            log_info("Nao foi possivel copiar para o clipboard (abra o ficheiro manualmente).")

    return encerrar(0, "Pronto. Cole o JS no console da aba da vaga.")


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception as exc:
        try:
            log_erro(f"Falha nao tratada: {exc}")
            code = encerrar(1)
        except Exception:
            print(f"ERRO: {exc}", file=sys.stderr)
            traceback.print_exc()
            print("RETCODE: 1", file=sys.stderr)
            code = 1
    finally:
        fechar_log_execucao()
    if code not in (0, 1, 2):
        code = 1
    sys.exit(code)
