# -*- coding: utf-8 -*-
"""
Teste de email Outlook Classic (success / error / no_data).
Envia os tres cenarios para EMAIL_DEV com o padrao novo de assunto/corpo/anexo.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import time
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
PYTHON_NAME = STEM_LOWER

_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

EMAIL_DEV = "abobicarlo@gmail.com"
ENVIAR_EMAIL = True

STATUS_POR_RETCODE = {
    0: "SUCCESS",
    1: "ERROR",
    2: "NO DATA",
}

DEPENDENCIAS: list[tuple[str, str]] = [
    ("win32com", "pywin32"),
]

_log_fp = None


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def iniciar_log_execucao(*, sufixo: str = "") -> Path:
    """Cria LOG_DIR e o ficheiro {STEM_LOWER}_{timestamp}[_{sufixo}].log."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    extra = f"_{sufixo}" if sufixo else ""
    caminho = LOG_DIR / f"{STEM_LOWER}_{stamp}{extra}.log"
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    log_info(f"Log da execucao: {caminho}")
    log_info(f"Script: {_SCRIPT}")
    log_info(f"STEM_LOWER: {STEM_LOWER}")
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


def log_erro(msg: str, *, com_traceback: bool = False) -> None:
    _emit(f"ERRO: {msg}", erro=True)
    if com_traceback:
        _emit(traceback.format_exc(), erro=True)


def garantir_dependencias() -> None:
    """Instala pacotes em falta com o pip do interpretador atual."""
    em_falta: list[str] = []
    for import_name, pip_name in DEPENDENCIAS:
        try:
            importlib.import_module(import_name)
        except ImportError:
            em_falta.append(pip_name)
    if not em_falta:
        print("INFO: Dependencias OK.", flush=True)
        return
    print(f"INFO: A instalar: {', '.join(em_falta)}", flush=True)
    cmd = [sys.executable, "-m", "pip", "install", *em_falta]
    subprocess.run(cmd, check=True)


def formatar_momento(dt: datetime) -> str:
    """YYYY-MM-DD - HH:MM:SS no fuso America/Sao_Paulo."""
    return dt.astimezone(TZ).strftime("%Y-%m-%d - %H:%M:%S")


def formatar_duracao(inicio: datetime, fim: datetime) -> str:
    """Duracao legivel a partir de inicio/fim."""
    total = max(0, int((fim - inicio).total_seconds()))
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}h {minutos}m {segundos}s"


def montar_assunto_email(code: int) -> str:
    """Assunto sempre em maiusculas: MONITRACAO PYTHON - NAME - STATUS."""
    status = STATUS_POR_RETCODE.get(code, "ERROR")
    return f"MONITRACAO PYTHON - {PYTHON_NAME.upper()} - {status}"


CORES_STATUS = {
    "SUCCESS": {"faixa": "#1B7A4E", "fundo": "#E8F6EE", "texto": "#0F3D27"},
    "ERROR": {"faixa": "#B42318", "fundo": "#FDECEC", "texto": "#7A1610"},
    "NO DATA": {"faixa": "#B8860B", "fundo": "#FFF8E1", "texto": "#6B4E00"},
}


def montar_corpo_email(
    code: int,
    inicio: datetime,
    fim: datetime,
    resumo: str,
) -> str:
    """Corpo HTML padronizado: faixa colorida + tipografia + tempos + resumo."""
    import html

    status = STATUS_POR_RETCODE.get(code, "ERROR")
    cores = CORES_STATUS.get(status, CORES_STATUS["ERROR"])
    resumo_html = html.escape(resumo.strip()).replace("\n", "<br>")
    nome = html.escape(PYTHON_NAME.upper())
    inicio_txt = html.escape(formatar_momento(inicio))
    fim_txt = html.escape(formatar_momento(fim))
    duracao_txt = html.escape(formatar_duracao(inicio, fim))

    return f"""\
<html>
<body style="margin:0;padding:0;background:#F4F4F1;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         style="background:#F4F4F1;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellspacing="0" cellpadding="0"
               style="max-width:560px;width:100%;background:#FFFFFF;
                      border:1px solid #E2E2DE;border-radius:8px;
                      font-family:'Segoe UI',Calibri,Candara,Arial,sans-serif;
                      color:#1A1A1A;">
          <tr>
            <td style="background:{cores['faixa']};color:#FFFFFF;padding:18px 24px;
                       font-size:13px;letter-spacing:0.08em;font-weight:700;
                       text-transform:uppercase;">
              MONITRACAO PYTHON
            </td>
          </tr>
          <tr>
            <td style="padding:22px 24px 8px 24px;">
              <div style="font-size:22px;line-height:1.25;font-weight:700;
                          color:{cores['faixa']};margin:0 0 6px 0;">
                {status}
              </div>
              <div style="font-size:14px;color:#555555;margin:0 0 18px 0;">
                {nome}
              </div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                     style="background:{cores['fundo']};border-radius:6px;">
                <tr>
                  <td style="padding:14px 16px;font-size:14px;line-height:1.55;
                             color:{cores['texto']};">
                    <div style="margin:0 0 8px 0;">
                      <strong>INICIO AUTOMACAO:</strong> {inicio_txt}
                    </div>
                    <div style="margin:0 0 8px 0;">
                      <strong>FIM AUTOMACAO:</strong> {fim_txt}
                    </div>
                    <div style="margin:0;">
                      <strong>DURACAO:</strong> {duracao_txt}
                    </div>
                  </td>
                </tr>
              </table>
              <div style="margin:20px 0 6px 0;font-size:12px;letter-spacing:0.06em;
                          font-weight:700;color:#666666;text-transform:uppercase;">
                RESUMO
              </div>
              <div style="font-size:15px;line-height:1.55;color:#222222;
                          padding:12px 14px;background:#FAFAF8;border-radius:6px;
                          border:1px solid #E8E8E4;">
                {resumo_html}
              </div>
              <div style="margin:18px 0 4px 0;font-size:12px;color:#888888;">
                Log completo da execucao em anexo (.log).
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px 20px 24px;font-size:11px;color:#999999;">
              ServerCRON - notificacao automatica
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def enviar_email_outlook(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    anexo_log: Path | None = None,
) -> None:
    """Envia email HTML pelo Outlook Classic com .log anexado."""
    import pythoncom
    import win32com.client

    if not destinatarios:
        print("INFO: Nenhum destinatario de email; a saltar envio.", flush=True)
        return

    para = "; ".join(destinatarios)
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # olMailItem
        mail.To = para
        mail.Subject = assunto
        mail.HTMLBody = corpo_html
        if anexo_log is not None and anexo_log.is_file():
            mail.Attachments.Add(str(anexo_log.resolve()))
            print(f"INFO: Anexo: {anexo_log.name}", flush=True)
        mail.Send()
        print(f"INFO: Email Outlook enviado para: {para}", flush=True)
    finally:
        pythoncom.CoUninitialize()


def correr_cenario(code: int, resumo: str) -> None:
    """Uma corrida completa: log -> fechar -> email com anexo."""
    status = STATUS_POR_RETCODE[code]
    inicio = datetime.now(TZ)
    caminho_log = iniciar_log_execucao(sufixo=status.lower().replace(" ", "_"))
    try:
        log_info(f"Cenario status={status} retcode={code}")
        log_info(resumo)
        time.sleep(1.2)
        print(f"RETCODE: {code}", flush=True)
        _escrever_ficheiro(f"RETCODE: {code}")
    finally:
        fechar_log_execucao()

    fim = datetime.now(TZ)
    assunto = montar_assunto_email(code)
    corpo_html = montar_corpo_email(code, inicio, fim, resumo)
    print(f"INFO: A enviar assunto={assunto!r}", flush=True)
    enviar_email_outlook([EMAIL_DEV], assunto, corpo_html, anexo_log=caminho_log)
    print(f"OK: Cenario {status} enviado.", flush=True)


def main() -> int:
    """Envia os tres emails de teste e devolve 0 se todos forem OK."""
    garantir_dependencias()
    cenarios = (
        (0, "Teste success: processamento simulado concluiu (3 ficheiros)."),
        (1, "Teste error: falha simulada RuntimeError('falha de teste')."),
        (2, "Teste no_data: pasta de entrada vazia, nada para processar."),
    )
    for code, resumo in cenarios:
        correr_cenario(code, resumo)

    print("OK: Tres emails (SUCCESS, ERROR, NO DATA) enviados para EMAIL_DEV.", flush=True)
    print("RETCODE: 0", flush=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print(f"ERRO: Falha nao tratada: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        code = 1
        print("RETCODE: 1", flush=True)
    if code not in (0, 1, 2):
        code = 1
    sys.exit(code)
