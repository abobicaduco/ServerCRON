r"""
ServerCRON — portal Python unificado (`ServerCRON.html`, `ServerCRON.css`, `ServerCRON.js`, sqlite local).
Stack Uploaders + Cron; branding e caminhos via env.

Arranque:
    python ServerCRON.py
    python server.py

No arranque como programa principal (``python ServerCRON.py`` ou ``python server.py``), se existir ``requirements.txt`` na mesma pasta, corre **sempre** ``pip install -r requirements.txt`` antes de carregar o resto (comportamento idempotente), salvo se ``SERVERCRON_SKIP_REQUIREMENTS_PIP=1`` (útil quando o ambiente já tem as dependências e o ``pip`` falharia). O atalho ``server.py`` apenas delega para ``ServerCRON.py``.

Painel: `ServerCRON.html` (vistas Cron + Uploaders via `portal_view`). Assets: `ServerCRON.css`, `ServerCRON.js`.

Modos: (1) predefinido — uma porta (SERVERCRON_DUO_PORTS=0): Uploaders em / e Cron em /cron/, mesma sessão; (2) opcional — SERVERCRON_DUO_PORTS=1 com SERVERCRON_UP_PORT / SERVERCRON_CRON_PORT.
Dados do Cron (sqlite local + planilha ``registro_automacoes.xlsx``): mesma pasta que este ficheiro (`server_cron.sqlite`; legado: nome antigo com prefixo ser+vidor_cron.sqlite).
Tabela de permissões e cadastro: ficheiro **registro_automacoes.xlsx** (folhas ``USERS`` e ``AUTOMACOES``); caminho via ``SERVERCRON_REGISTRO_XLSX`` / ``SERVERCRON_REGISTRO_DIR``.
Logs (Uploaders + Cron): ``<pasta do ServerCRON>/logs/AAAA-MM-DD/<uuid>.log`` (fuso ``America/Sao_Paulo``); novo UUID em cada arranque; à meia-noite SP abre novo ficheiro e recarrega agendamentos da planilha (o processo não reinicia).

Variáveis de ambiente: além do SO, o processo lê opcionalmente um ficheiro ``.env`` na mesma pasta que este script (ou pasta do ``.exe`` em modo frozen). Chaves já definidas no ambiente **não** são sobrescritas. Ver ``.env.example`` no repositório.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import subprocess


def _load_dotenv_if_present(base_dir: Path) -> None:
    """Populate os.environ from base_dir/.env (KEY=VALUE lines). Does not override existing keys."""
    path = base_dir / ".env"
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        if not key or key.startswith("#"):
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key not in os.environ:
            os.environ[key] = val


_env_base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
_load_dotenv_if_present(_env_base)


def _skip_requirements_pip_on_boot() -> bool:
    return str(os.environ.get("SERVERCRON_SKIP_REQUIREMENTS_PIP", "")).lower() in ("1", "true", "yes")


def _pip_sync_requirements_txt(base_dir: Path) -> None:
    """Run ``pip install -r requirements.txt`` when that file exists (idempotent). Only for ``python ServerCRON.py``."""
    req = base_dir / "requirements.txt"
    if not req.is_file():
        return
    print("[BOOT] pip install -r requirements.txt …", flush=True)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
        )
    except subprocess.CalledProcessError as exc:
        print("[BOOT] Falha ao instalar dependências a partir de requirements.txt.", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc


# Operator defaults when this process is the main script — must run before PANEL_HTML_DIR.
if __name__ == "__main__":
    if not _skip_requirements_pip_on_boot():
        _pip_sync_requirements_txt(_env_base)
    else:
        print("[BOOT] SERVERCRON_SKIP_REQUIREMENTS_PIP=1 — a saltar pip install -r requirements.txt", flush=True)
    _op_root = Path(__file__).resolve().parent
    os.environ.setdefault("SERVERCRON_PANEL_DIR", str(_op_root))
    os.environ.setdefault("SERVERCRON_DUO_PORTS", "0")
    os.environ.setdefault("SERVERCRON_UP_PORT", "5001")
    os.environ.setdefault("SERVERCRON_CRON_PORT", "5002")

import json
import logging
import random
import secrets
import re
from html import escape
import socket
import string
import uuid
import threading
import time
import webbrowser
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Optional

import pytz

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import pythoncom
    import win32com.client as win32
    HAS_OUTLOOK = True
except ImportError:
    HAS_OUTLOOK = False

from flask import (
    Flask, Response, flash, jsonify, redirect,
    render_template, request, send_file, session, stream_with_context, url_for,
)
from werkzeug.utils import secure_filename

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys.executable).parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).lower() in ("1", "true", "yes")


_p_dir = (os.environ.get("SERVERCRON_PANEL_DIR") or "").strip()
PANEL_HTML_DIR: Path = Path(_p_dir) if _p_dir else SCRIPT_DIR
if not PANEL_HTML_DIR.is_dir():
    PANEL_HTML_DIR = SCRIPT_DIR


def _panel_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    for d in (PANEL_HTML_DIR, SCRIPT_DIR, Path.cwd()):
        if d and d.is_dir():
            r = d.resolve()
            if r not in candidates:
                candidates.append(r)
    return candidates


def _resolve_panel_file(filename: str) -> Optional[Path]:
    for base in _panel_dir_candidates():
        fp = base / filename
        if fp.is_file():
            return fp
    return None


TIMEZONE = pytz.timezone("America/Sao_Paulo")
START_TIME = datetime.now(TIMEZONE).replace(microsecond=0)

HOME = Path.home()
# Data root for automations and shared config (default: ~/Documents/ServerCRON). Override with SERVERCRON_DATA_ROOT (absolute path).
_data_root_raw = (os.environ.get("SERVERCRON_DATA_ROOT") or "").strip()
DATA_ROOT: Path = Path(_data_root_raw) if _data_root_raw else (HOME / "Documents" / "ServerCRON")
CONFIG_MODULES_DIR: Path = DATA_ROOT / "config" / "modules"


def _prefer_new_home_file(parent: Path, new_name: str, legacy_suffix: str) -> Path:
    """Prefer new on-disk names; optional legacy file/dir via split suffix (no deprecated token in source)."""
    new_p = parent / new_name
    legacy = parent / ("ser" + legacy_suffix)
    if new_p.exists():
        return new_p
    if legacy.exists():
        return legacy
    return new_p


BASE_PATH: Path = DATA_ROOT / "automacoes"
# Inbox of this Outlook mailbox (Store.DisplayName in the left tree). If env not set, "Monitoracao Python". If set to empty string, profile default Inbox.
_mbx = os.environ.get("SERVERCRON_OUTLOOK_MONITOR_MAILBOX")
OUTLOOK_MONITOR_MAILBOX_NAME: str = "Monitoracao Python" if _mbx is None else _mbx.strip()
del _mbx
# --- registro_automacoes.xlsx (folhas USERS + AUTOMACOES) — sem BigQuery ---


def _resolve_registro_automacoes_path() -> Path:
    raw = (os.environ.get("SERVERCRON_REGISTRO_XLSX") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    d = (os.environ.get("SERVERCRON_REGISTRO_DIR") or "").strip()
    if d:
        return (Path(d).expanduser().resolve() / "registro_automacoes.xlsx")
    return (SCRIPT_DIR / "registro_automacoes.xlsx").resolve()


REGISTRO_AUTOMAOES_PATH: Path = _resolve_registro_automacoes_path()
SHEET_USERS: str = "USERS"
SHEET_AUTOMAOES: str = "AUTOMACOES"
HAS_REGISTRY_XLSX: bool = False  # updated after logger init

# Cache USERS (mesmos envs que o antigo cache BQ, nomes mantidos por compatibilidade)
_SERVERCRON_CACHE_TTL_SEC: float = float(
    (os.environ.get("SERVERCRON_BQ_PERMS_FRESH_TTL_SEC") or "120").strip() or 120
)
_SERVERCRON_STALE_MAX_SEC: float = float(
    (os.environ.get("SERVERCRON_BQ_PERMS_STALE_MAX_SEC") or "86400").strip() or 86400
)
_servercron_cache: dict = {"df": None, "loaded_at": 0.0, "src_mtime": 0.0}
_servercron_bq_lock = threading.Lock()
_servercron_bg_schedule_lock = threading.Lock()
_servercron_last_bg_schedule: float = 0.0

# Cache folha AUTOMACOES (TTL; nome interno legado _bq_cache)
_BQ_CACHE_TTL_SECONDS = 600
_bq_cache: dict = {"records": [], "ts": 0.0}
_bq_cache_lock = threading.Lock()


def _registry_automacoes_cache_clear() -> None:
    with _bq_cache_lock:
        _bq_cache["records"] = []
        _bq_cache["ts"] = 0.0


def _email_domain_suffix() -> str:
    """Login e-mail suffix (e.g. `@example.com`). Override with env SERVERCRON_EMAIL_DOMAIN."""
    raw = (os.environ.get("SERVERCRON_EMAIL_DOMAIN") or "@example.com").strip()
    return raw if raw.startswith("@") else f"@{raw.lstrip('@')}"


SECRET_KEY: str = "chave_super_secreta_para_sessao_server_monitoracao_fg78"
DOMAIN: str = _email_domain_suffix()


def _unified_portal_with_cron() -> bool:
    """True when the unified single-port app exposes Cron (mount or same-process link)."""
    if _env_truthy("SERVERCRON_DUO_PORTS"):
        return False
    return str(os.environ.get("SERVERCRON_UNIFIED_PORTAL", "")).lower() in ("1", "true", "yes")
# Uploaders default port; with SERVERCRON_DUO_PORTS=1 the Cron app uses SERVERCRON_CRON_PORT (default 5002).
PORT: int = 5001
DEBUG: bool = False
MOCK_EMAIL: bool = False

# Admins: folha USERS (level_access ADM / admin na linha do usuario).
ADMIN_USERS: list[str] = []

ANALYTICS_DB_PATH: Path = _prefer_new_home_file(
    CONFIG_MODULES_DIR, "server_uploaders_analytics.json", "vidor_uploaders_analytics.json"
)
_BRAND_LOGO_CANDIDATES: tuple[Path, ...] = (
    CONFIG_MODULES_DIR / "organization_logo.png",
    CONFIG_MODULES_DIR / "logo.png",
    PANEL_HTML_DIR / "assets" / "logo.png",
)
# Server file logs: SCRIPT_DIR/logs/YYYY-MM-DD/<uuid>.log (America/Sao_Paulo calendar day).
_LOG_DAY_STR: str = START_TIME.date().isoformat()
_LOG_SESSION_UUID: str = str(uuid.uuid4())
UPLOADERS_LOG_DIR: Path = SCRIPT_DIR / "logs" / _LOG_DAY_STR
_SERVER_LOG_FILE_PATH: Path = UPLOADERS_LOG_DIR / f"{_LOG_SESSION_UUID}.log"
_SERVER_LOG_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════
# LOGGER
# ═══════════════════════════════════════════════════════════════════════

class LoggerMaster:
    """Unified console + file logger."""

    @staticmethod
    def setup(name: str = "ServerCRON") -> logging.Logger:
        UPLOADERS_LOG_DIR.mkdir(parents=True, exist_ok=True)

        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False

        if not lg.handlers:
            fh = logging.FileHandler(_SERVER_LOG_FILE_PATH, encoding="utf-8")
            fh.setFormatter(_SERVER_LOG_FORMATTER)
            lg.addHandler(fh)

            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(_SERVER_LOG_FORMATTER)
            lg.addHandler(ch)

        return lg


logger = LoggerMaster.setup()
logger.info("Log em ficheiro (sessao): %s", _SERVER_LOG_FILE_PATH)
HAS_REGISTRY_XLSX = bool(HAS_PANDAS and REGISTRO_AUTOMAOES_PATH.is_file())
if HAS_REGISTRY_XLSX:
    logger.info("Registro local: %s", REGISTRO_AUTOMAOES_PATH)
else:
    logger.warning(
        "registro_automacoes.xlsx nao encontrado em %s — defina SERVERCRON_REGISTRO_XLSX ou "
        "SERVERCRON_REGISTRO_DIR, ou coloque o ficheiro junto a ServerCRON.py.",
        REGISTRO_AUTOMAOES_PATH,
    )

# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS SERVICE
# ═══════════════════════════════════════════════════════════════════════

class AnalyticsService:
    """JSON-backed usage analytics (recent & frequent folders)."""
    _lock = threading.Lock()

    @classmethod
    def _read(cls) -> dict:
        if not ANALYTICS_DB_PATH.exists():
            legacy = SCRIPT_DIR / "db" / "user_analytics.json"
            if legacy.is_file():
                try:
                    data = json.loads(legacy.read_text(encoding="utf-8"))
                    cls._write(data)
                    return data
                except Exception:
                    pass
            return {}
        try:
            return json.loads(ANALYTICS_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def _write(cls, data: dict) -> None:
        ANALYTICS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with suppress(Exception):
            ANALYTICS_DB_PATH.write_text(
                json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8"
            )

    @classmethod
    def track_usage(cls, username: str, folder_path: str) -> None:
        with cls._lock:
            data = cls._read()
            user_data = data.setdefault(username, {
                "recent_folders": [], "folder_frequency": {},
            })
            freq = user_data.setdefault("folder_frequency", {})
            freq[folder_path] = freq.get(folder_path, 0) + 1

            recents = user_data.setdefault("recent_folders", [])
            if folder_path in recents:
                recents.remove(folder_path)
            recents.insert(0, folder_path)
            user_data["recent_folders"] = recents[:5]
            cls._write(data)

    @classmethod
    def get_user_prefs(cls, username: str) -> dict:
        with cls._lock:
            data = cls._read()
            user_data = data.get(username, {
                "recent_folders": [], "folder_frequency": {},
            })
            freq = user_data.get("folder_frequency", {})
            frequent = sorted(freq, key=lambda x: freq[x], reverse=True)[:5]
            return {
                "recent": user_data.get("recent_folders", []),
                "frequent": frequent,
            }

# ═══════════════════════════════════════════════════════════════════════
# PERMISSION SERVICE
# ═══════════════════════════════════════════════════════════════════════

def _split_user_tokens(cell) -> list[str]:
    if cell is None or (HAS_PANDAS and pd.isna(cell)):
        return []
    return [u.strip().lower() for u in re.split(r"[,;]", str(cell)) if u.strip()]


def _normalize_level_admin(level_val) -> bool:
    s = str(level_val).strip().upper()
    return s in {"ADMIN", "ADM", "ADMINISTRATOR", "ADMINISTRADOR"}


class PermissionService:
    """Permissions from worksheet USERS in registro_automacoes.xlsx (users, level_access, folder_access)."""

    @staticmethod
    def get_todas_pastas_raiz() -> list[str]:
        base = BASE_PATH
        if not base.exists():
            return []
        return [
            d.name for d in base.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]

    @staticmethod
    def _get_servercron_dataframe() -> Optional[object]:
        """Cached USERS sheet; stale-while-revalidate."""
        return _servercron_resolve_dataframe()

    @staticmethod
    def _bq_permissions_active(df) -> bool:
        return df is not None and not df.empty

    @staticmethod
    def _user_in_servercron_row(username_limpo: str, users_cell) -> bool:
        return username_limpo in _split_user_tokens(users_cell)

    @staticmethod
    def _user_has_admin_level_in_df(username_limpo: str, bq_df) -> bool:
        """Any row for this user with admin `level_access` (ignores `folder_access`)."""
        if "users" not in bq_df.columns or "level_access" not in bq_df.columns:
            return False
        mask = bq_df["users"].apply(
            lambda c: PermissionService._user_in_servercron_row(username_limpo, c)
        )
        if HAS_PANDAS and hasattr(mask, "any") and not bool(mask.any()):
            return False
        for lv in bq_df.loc[mask, "level_access"]:
            if _normalize_level_admin(lv):
                return True
        return False

    @staticmethod
    def ler_pastas_permitidas(username: str) -> list[str]:
        pastas: list[str] = []
        username_limpo = username.strip().lower()

        bq_df = PermissionService._get_servercron_dataframe()
        if PermissionService._bq_permissions_active(bq_df):
            if "users" not in bq_df.columns:
                logger.error("Tabela servercron sem coluna 'users'.")
                return pastas
            if "level_access" in bq_df.columns and PermissionService._user_has_admin_level_in_df(
                username_limpo, bq_df
            ):
                return ["ALL"]
            mask = bq_df["users"].apply(
                lambda c: PermissionService._user_in_servercron_row(username_limpo, c)
            )
            for cell in bq_df.loc[mask, "folder_access"] if "folder_access" in bq_df.columns else []:
                raw = "" if (cell is None or (HAS_PANDAS and pd.isna(cell))) else str(cell).strip()
                for p in re.split(r"[,;]", raw):
                    t = p.strip()
                    if t:
                        pastas.append(t)
            if any(p.upper() == "ALL" for p in pastas):
                return ["ALL"]
            return list(dict.fromkeys(pastas))

        logger.warning(
            "Permissoes: folha USERS indisponivel, vazia ou sem pastas para user=%s (ver %s).",
            username_limpo,
            REGISTRO_AUTOMAOES_PATH,
        )
        return pastas

    @staticmethod
    def is_admin_user(username: str) -> bool:
        username_limpo = username.strip().lower()
        bq_df = PermissionService._get_servercron_dataframe()
        if not PermissionService._bq_permissions_active(bq_df):
            return False
        return PermissionService._user_has_admin_level_in_df(username_limpo, bq_df)

    @staticmethod
    def get_all_recipients() -> str:
        """All unique user e-mails from `users` in USERS sheet, semicolon-separated."""

        def _to_emails(user_ids: list[str]) -> set[str]:
            return {
                u if u.endswith(DOMAIN) else f"{u}{DOMAIN}"
                for u in user_ids
            }

        bq_df = PermissionService._get_servercron_dataframe()
        if PermissionService._bq_permissions_active(bq_df) and "users" in bq_df.columns:
            all_ids: list[str] = []
            for cell in bq_df["users"].fillna("").astype(str):
                all_ids.extend(_split_user_tokens(cell))
            return ";".join(sorted(_to_emails(list(dict.fromkeys(all_ids)))))

        return ""

    @staticmethod
    def invalidate_servercron_cache() -> None:
        _servercron_cache["df"] = None
        _servercron_cache["loaded_at"] = 0.0
        _servercron_cache["src_mtime"] = 0.0
        _registry_automacoes_cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# WORKBOOK ADMIN — folha USERS em registro_automacoes.xlsx (sessão admin)
# ═══════════════════════════════════════════════════════════════════════

_FIELD_USERS_MAX = 4000
_FIELD_FOLDER_MAX = 4000
_USERS_SANITIZE = re.compile(r"^[a-z0-9\s.,;\-]+$", re.IGNORECASE)


def _coerce_bq_str(val: object) -> str | None:
    if val is None:
        return None
    if HAS_PANDAS and isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def _validate_servercron_users(users_raw: str) -> str:
    u = (users_raw or "").strip()
    if not u or len(u) > _FIELD_USERS_MAX:
        raise ValueError("Campo 'users' vazio ou excede tamanho máximo.")
    if not _USERS_SANITIZE.match(u):
        raise ValueError("Use apenas letras, números, ponto, vírgula, ponto e vírgula, espaço ou hífen.")
    return re.sub(r"\s+", " ", u).strip().lower()


def _validate_level_access(level_raw: str) -> str:
    s = (level_raw or "").strip().lower()
    if s in {"admin", "adm", "administrator", "administrador"}:
        return "admin"
    if s in {"viewer", "read", "view", "leitor", "leitura", "user", "usuario", "ver"}:
        return "viewer"
    raise ValueError("Nível inválido. Use admin ou viewer.")


def _validate_folder_access(raw: str | None) -> str | None:
    if raw is None or str(raw).strip() == "":
        return None
    t = str(raw).strip()
    if len(t) > _FIELD_FOLDER_MAX:
        raise ValueError("Campo folder_access excede tamanho máximo.")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f<>`'\"\\\\]", t):
        raise ValueError("Caracteres de controle ou proibidos em folder_access.")
    return t


class AccessAdminService:
    """INSERT/UPDATE/DELETE na folha USERS do ficheiro registro_automacoes.xlsx."""

    @staticmethod
    def _load_frames() -> tuple[dict[str, pd.DataFrame], list[str]]:
        if not HAS_PANDAS:
            raise RuntimeError("pandas não disponível.")
        p = REGISTRO_AUTOMAOES_PATH
        if not p.is_file():
            raise FileNotFoundError(str(p))
        xl = pd.ExcelFile(p, engine="openpyxl")
        order = list(xl.sheet_names)
        frames = {s: pd.read_excel(p, sheet_name=s, engine="openpyxl") for s in order}
        if SHEET_USERS not in frames:
            raise ValueError(f"Folha {SHEET_USERS!r} em falta no workbook.")
        return frames, order

    @staticmethod
    def _save_frames(frames: dict[str, pd.DataFrame], order: list[str]) -> None:
        p = REGISTRO_AUTOMAOES_PATH
        with pd.ExcelWriter(p, engine="openpyxl") as writer:
            for sn in order:
                frames[sn].to_excel(writer, sheet_name=sn, index=False)

    @staticmethod
    def _col(df: object, key: str) -> str:
        kl = key.lower()
        for c in df.columns:
            if str(c).strip().lower() == kl:
                return str(c)
        raise ValueError(f"Coluna {key!r} em falta na folha {SHEET_USERS}. Colunas: {list(df.columns)}")

    @staticmethod
    def _fa_eq(cell: object, expect: str | None) -> bool:
        if cell is None or (HAS_PANDAS and isinstance(cell, float) and pd.isna(cell)) or str(cell).strip() == "":
            cur: str | None = None
        else:
            cur = _validate_folder_access(str(cell))
        return cur == expect

    @staticmethod
    def fetch_all_rows() -> list[dict]:
        PermissionService.invalidate_servercron_cache()
        df = PermissionService._get_servercron_dataframe()
        if df is None or not HAS_PANDAS:
            return []
        if df.empty:
            return []
        return AccessAdminService._df_to_json_records(df)

    @staticmethod
    def _df_to_json_records(df: object) -> list[dict]:
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        rows: list[dict] = []
        for _, r in df.iterrows():
            row: dict = {}
            for col in df.columns:
                v = r[col]
                if HAS_PANDAS and pd.isna(v):
                    row[col] = None
                else:
                    row[col] = None if v is None else str(v)
            rows.append(row)
        return rows

    @staticmethod
    def insert_row(
        users: str, level_access: str, folder_access: str | None
    ) -> tuple[list[dict], str | None, int | None]:
        u = _validate_servercron_users(users)
        lv = _validate_level_access(level_access)
        fa = _validate_folder_access(folder_access)
        frames, order = AccessAdminService._load_frames()
        udf = frames[SHEET_USERS].copy()
        cu = AccessAdminService._col(udf, "users")
        cl = AccessAdminService._col(udf, "level_access")
        try:
            cf = AccessAdminService._col(udf, "folder_access")
        except ValueError:
            udf["folder_access"] = None
            cf = "folder_access"
        new_row = {cu: u, cl: lv, cf: fa}
        frames[SHEET_USERS] = pd.concat([udf, pd.DataFrame([new_row])], ignore_index=True)
        AccessAdminService._save_frames(frames, order)
        logger.info("Admin INSERT na folha %s (%s).", SHEET_USERS, REGISTRO_AUTOMAOES_PATH)
        rows = AccessAdminService.fetch_all_rows()
        return rows, None, 1

    @staticmethod
    def delete_row(
        users: str, level_access: str, folder_access: str | None
    ) -> tuple[list[dict], str | None, int | None]:
        u = (users or "").strip()
        if not u:
            raise ValueError("Identificação da linha inválida.")
        lv = (level_access or "").strip()
        raw_fa = folder_access
        if raw_fa is None:
            fa: str | None = None
        else:
            s = str(raw_fa).strip()
            fa = None if s == "" else s
        frames, order = AccessAdminService._load_frames()
        udf = frames[SHEET_USERS].copy()
        cu = AccessAdminService._col(udf, "users")
        cl = AccessAdminService._col(udf, "level_access")
        try:
            cf = AccessAdminService._col(udf, "folder_access")
        except ValueError:
            cf = None
        mask = udf[cu].astype(str).str.strip().str.lower() == u.lower()
        mask &= udf[cl].astype(str).str.strip().str.lower() == lv.lower()
        if cf is not None:
            mask &= udf[cf].apply(lambda cell: AccessAdminService._fa_eq(cell, fa))
        else:
            if fa is not None:
                mask &= False
        n_hit = int(mask.sum())
        if n_hit != 1:
            raise ValueError("Nenhuma ou várias linhas correspondem ao filtro DELETE.")
        frames[SHEET_USERS] = udf.loc[~mask].reset_index(drop=True)
        AccessAdminService._save_frames(frames, order)
        logger.info("Admin DELETE na folha %s (%s).", SHEET_USERS, REGISTRO_AUTOMAOES_PATH)
        rows = AccessAdminService.fetch_all_rows()
        return rows, None, 1

    @staticmethod
    def update_row(
        old_users: str,
        old_level_access: str,
        old_folder_access: str | None,
        new_users: str,
        new_level_access: str,
        new_folder_access: str | None,
    ) -> tuple[list[dict], str | None, int | None]:
        o_u = (old_users or "").strip()
        o_lv = (old_level_access or "").strip()
        if not o_u:
            raise ValueError("Identificação da linha (users) inválida.")
        raw_ofa = old_folder_access
        if raw_ofa is None:
            o_fa: str | None = None
        else:
            os_ = str(raw_ofa).strip()
            o_fa = None if os_ == "" else os_
        n_u = _validate_servercron_users(new_users)
        n_lv = _validate_level_access(new_level_access)
        n_fa = _validate_folder_access(new_folder_access)
        frames, order = AccessAdminService._load_frames()
        udf = frames[SHEET_USERS].copy()
        cu = AccessAdminService._col(udf, "users")
        cl = AccessAdminService._col(udf, "level_access")
        try:
            cf = AccessAdminService._col(udf, "folder_access")
        except ValueError:
            cf = None
        mask = udf[cu].astype(str).str.strip().str.lower() == o_u.lower()
        mask &= udf[cl].astype(str).str.strip().str.lower() == o_lv.lower()
        if cf is not None:
            mask &= udf[cf].apply(lambda cell: AccessAdminService._fa_eq(cell, o_fa))
        else:
            if o_fa is not None:
                mask &= False
        idx = udf.index[mask]
        if len(idx) != 1:
            raise ValueError("Nenhuma ou várias linhas correspondem ao filtro UPDATE.")
        i = int(idx[0])
        udf.at[i, cu] = n_u
        udf.at[i, cl] = n_lv
        if cf is not None:
            udf.at[i, cf] = n_fa
        frames[SHEET_USERS] = udf
        AccessAdminService._save_frames(frames, order)
        logger.info("Admin UPDATE na folha %s (%s).", SHEET_USERS, REGISTRO_AUTOMAOES_PATH)
        rows = AccessAdminService.fetch_all_rows()
        return rows, None, 1


# ═══════════════════════════════════════════════════════════════════════
# FILE SERVICE
# ═══════════════════════════════════════════════════════════════════════

class FileService:
    """Maps directory trees and locates automation scripts."""

    @staticmethod
    def mapear_diretorios(pastas_permitidas: list[str]) -> tuple[dict, set]:
        grouped: dict[str, dict[str, str]] = {}
        valid_paths: set[str] = set()

        if any(p.upper() == "ALL" for p in pastas_permitidas):
            pastas_permitidas = PermissionService.get_todas_pastas_raiz()

        for pasta_raiz in pastas_permitidas:
            caminho_base = BASE_PATH / pasta_raiz
            caminho_input = caminho_base / "arquivos_input"

            if not caminho_input.exists():
                continue

            display_name = f"{pasta_raiz} - PASTA PARA INPUT"
            grouped.setdefault(display_name, {})

            try:
                for entry in caminho_input.iterdir():
                    if not entry.is_dir():
                        continue
                    script_esperado = caminho_base / "metodos" / f"{entry.name}.py"
                    if script_esperado.exists():
                        abs_path = str(entry.resolve())
                        grouped[display_name][abs_path] = entry.name
                        valid_paths.add(abs_path)
                    else:
                        logger.warning(
                            f"Processo ocultado (sem script correspondente): {entry.name}"
                        )
            except Exception:
                logger.exception(f"Erro ao listar processos em {caminho_input}")

        return grouped, valid_paths

    @staticmethod
    def localizar_script(target_path: str) -> tuple[Optional[str], bool, str]:
        try:
            caminho = Path(target_path).resolve()
            partes = [p.lower() for p in caminho.parts]
            needle = "arquivos_input"
            if needle not in partes:
                return None, False, "Desconhecido"

            idx = partes.index(needle)
            if len(caminho.parts) <= idx + 1:
                return None, False, "arquivos_input"

            nome_automacao = caminho.parts[idx + 1]
            raiz_parts = caminho.parts[:idx]
            if not raiz_parts:
                return None, False, "Desconhecido"
            caminho_raiz = Path(*raiz_parts)
            script = caminho_raiz / "metodos" / f"{nome_automacao}.py"

            return str(script), script.exists(), nome_automacao
        except Exception:
            logger.exception("Erro ao localizar script")
            return None, False, "Desconhecido"

# ═══════════════════════════════════════════════════════════════════════
# EMAIL SERVICE
# ═══════════════════════════════════════════════════════════════════════

class EmailService:
    """Sends token emails via Outlook COM automation."""

    @staticmethod
    def send_token_email(destinatario: str, token: str) -> bool:
        if MOCK_EMAIL:
            logger.info(f"[MOCK EMAIL] Token para {destinatario}: {token}")
            return True

        if not HAS_OUTLOOK:
            logger.error("win32com não disponível. Email não enviado.")
            return False

        pythoncom.CoInitialize()
        try:
            outlook = win32.Dispatch("outlook.application")
            mail = outlook.CreateItem(0)
            mail.To = destinatario
            mail.Subject = "Seu Token de Acesso - ServerCRON"
            mail.HTMLBody = f"""
                <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
                    <h2 style="color: #242424; border-bottom: 2px solid #d3ad65; padding-bottom: 10px;">Messaging portal — automation stack</h2>
                    <p>Olá,</p>
                    <p>Seu código de autenticação seguro (Token) para upload de arquivos é:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <h1 style="color: #242424; background-color: #f3f4f6; padding: 15px 30px; display: inline-block; border-radius: 8px; letter-spacing: 8px; margin: 0; font-size: 32px; border: 1px solid #ccc;">{token}</h1>
                    </div>
                    <p style="color: #d32f2f; font-size: 13px;"><b>Atenção:</b> Este código expira em 15 minutos. Não o compartilhe com ninguém.</p>
                    <br>
                    <p>Atenciosamente,<br><b>ServerCRON</b></p>
                </div>
            """
            mail.Send()
            logger.info(f"Token enviado com sucesso para {destinatario}")
            return True
        except Exception:
            logger.exception("Erro ao enviar email de token")
            return False
        finally:
            with suppress(Exception):
                pythoncom.CoUninitialize()

# ═══════════════════════════════════════════════════════════════════════
# EXECUTOR SERVICE
# ═══════════════════════════════════════════════════════════════════════

_python_exec_lock = threading.Lock()
_python_exec_active: set[str] = set()
_pending_script_by_user_lock = threading.Lock()
_pending_script_by_user: dict[str, str] = {}

def _normalize_python_exec_name(value: str) -> str:
    return Path(value).stem.lower().strip()

def _try_acquire_python_exec_slot(value: str) -> bool:
    python_name = _normalize_python_exec_name(value)
    with _python_exec_lock:
        if python_name in _python_exec_active:
            return False
        _python_exec_active.add(python_name)
        return True

def _release_python_exec_slot(value: str) -> None:
    python_name = _normalize_python_exec_name(value)
    with _python_exec_lock:
        _python_exec_active.discard(python_name)


def _set_pending_script_for_user(username: str, script_path: str) -> None:
    with _pending_script_by_user_lock:
        _pending_script_by_user[username.lower().strip()] = str(Path(script_path).resolve())


def _pop_pending_script_for_user(username: str) -> str | None:
    key = username.lower().strip()
    with _pending_script_by_user_lock:
        return _pending_script_by_user.pop(key, None)

class ExecutorService:
    """Runs Python scripts as subprocesses, streaming output via SSE."""
    _lock = threading.Lock()
    _active_users: dict[str, int] = {}
    _active_scripts: dict[str, int] = {}
    _script_history: dict[str, list[float]] = {}

    @staticmethod
    def run_script(script_path: str, username: str):
        script_path = str(Path(script_path).resolve())
        python_name = Path(script_path).name
        python_key = _normalize_python_exec_name(script_path)
        slot_acquired = False

        with ExecutorService._lock:
            if ExecutorService._active_users.get(username, 0) >= 1:
                yield "data: [CONCLUIDO_ERRO] Você já possui uma automação em execução. Aguarde finalizar.\n\n"
                return
            if not _try_acquire_python_exec_slot(script_path):
                yield f"data: [CONCLUIDO_ERRO] A automação '{python_key}' já está em execução.\n\n"
                return
            slot_acquired = True
            if ExecutorService._active_scripts.get(script_path, 0) >= 1:
                yield "data: [CONCLUIDO_ERRO] Esta automação já está em execução.\n\n"
                _release_python_exec_slot(script_path)
                return
            now = time.time()
            history = [t for t in ExecutorService._script_history.get(script_path, []) if now - t < 180]
            if len(history) >= 3:
                yield "data: [CONCLUIDO_ERRO] Limite de frequência atingido (máx 3 exec / 3 min).\n\n"
                _release_python_exec_slot(script_path)
                return

            ExecutorService._active_users[username] = ExecutorService._active_users.get(username, 0) + 1
            ExecutorService._active_scripts[script_path] = ExecutorService._active_scripts.get(script_path, 0) + 1
            history.append(now)
            ExecutorService._script_history[script_path] = history

        try:
            python_cmd = sys.executable if not getattr(sys, "frozen", False) else "python"
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["ENV_EXEC_MODE"] = "SOLICITACAO"
            env["ENV_EXEC_USER"] = f"{username}{DOMAIN}"

            yield f"data: [*] Iniciando automação: {python_name}...\n\n"

            process = subprocess.Popen(
                [python_cmd, "-u", script_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env, bufsize=1,
                cwd=str(Path(script_path).parent)
            )

            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    yield ": heartbeat\n\n"
                    time.sleep(0.5)
                    continue
                yield f"data: {line}\n\n"

            process.stdout.close()
            rc = process.wait()

            if rc == 0:
                logger.info(f"Automação '{python_name}' finalizada com SUCESSO.")
                yield "data: [CONCLUIDO_SUCESSO]\n\n"
            elif rc == 2:
                yield "data: [CONCLUIDO_AVISO] Não foram encontrados arquivos para processar.\n\n"
            else:
                yield f"data: [CONCLUIDO_ERRO] Automação finalizou com código {rc}.\n\n"
        except Exception as e:
            logger.exception(f"Falha ao iniciar processo: {e}")
            yield f"data: [ERRO_INTERNO] Falha ao iniciar processo: {e}\n\n"
        finally:
            with ExecutorService._lock:
                if username in ExecutorService._active_users:
                    ExecutorService._active_users[username] -= 1
                    if ExecutorService._active_users[username] <= 0:
                        del ExecutorService._active_users[username]
                if script_path in ExecutorService._active_scripts:
                    ExecutorService._active_scripts[script_path] -= 1
                    if ExecutorService._active_scripts[script_path] <= 0:
                        del ExecutorService._active_scripts[script_path]
                if slot_acquired:
                    _release_python_exec_slot(script_path)

# ═══════════════════════════════════════════════════════════════════════
# OUTLOOK MONITOR SERVICE
# ═══════════════════════════════════════════════════════════════════════

class OutlookMonitorService:
    """A cada 1 minuto: lê a Inbox da caixa configurada; se o assunto for um .py em pasta metodos, executa e notifica o remetente."""
    _processed_ids = set()
    _ol_folder_inbox: int = 6  # olFolderInbox
    _logged_inbox_source: bool = False
    _logged_store_fallback: bool = False

    @staticmethod
    def _resolve_inbox_folder(namespace) -> object:
        """Inbox of the configured mailbox (Store) or default profile Inbox if name not found / empty."""
        want = (OUTLOOK_MONITOR_MAILBOX_NAME or "").strip().lower()
        if not want:
            return namespace.GetDefaultFolder(OutlookMonitorService._ol_folder_inbox)
        try:
            stores = namespace.Session.Stores
            n = int(getattr(stores, "Count", 0) or 0)
            for i in range(1, n + 1):
                try:
                    st = stores.Item(i)
                    dn = (getattr(st, "DisplayName", None) or "").strip()
                    if dn.lower() == want:
                        inbox = st.GetDefaultFolder(OutlookMonitorService._ol_folder_inbox)
                        if not OutlookMonitorService._logged_inbox_source:
                            OutlookMonitorService._logged_inbox_source = True
                            logger.info(
                                "[MONITOR] Lendo e-mails da Inbox da caixa: %s",
                                dn,
                            )
                        return inbox
                except Exception:
                    continue
        except Exception as e:
            logger.debug("[MONITOR] Session.Stores: %s", e)
        # Legacy: some accounts appear under Namespace.Folders
        try:
            roots = namespace.Folders
            m = int(getattr(roots, "Count", 0) or 0)
            for j in range(1, m + 1):
                try:
                    root = roots.Item(j)
                    rname = (getattr(root, "Name", None) or "").strip()
                    if rname.lower() == want:
                        for sub in ("Inbox", "Caixa de Entrada"):
                            try:
                                inbox = root.Folders.Item(sub)
                                if not OutlookMonitorService._logged_inbox_source:
                                    OutlookMonitorService._logged_inbox_source = True
                                    logger.info(
                                        "[MONITOR] Lendo e-mails da Inbox (subpasta %r) em: %s",
                                        sub,
                                        rname,
                                    )
                                return inbox
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception as e:
            logger.debug("[MONITOR] Namespace.Folders: %s", e)
        if not OutlookMonitorService._logged_store_fallback:
            OutlookMonitorService._logged_store_fallback = True
            try:
                names = []
                st2 = namespace.Session.Stores
                n2 = int(getattr(st2, "Count", 0) or 0)
                for k in range(1, n2 + 1):
                    try:
                        names.append((getattr(st2.Item(k), "DisplayName", None) or "?").strip())
                    except Exception:
                        pass
                logger.warning(
                    "[MONITOR] Caixa '%s' nao encontrada no Outlook. Stores: %s — usando Inbox padrao do perfil. "
                    "Ajuste o nome (igual ao Outlook) ou SERVERCRON_OUTLOOK_MONITOR_MAILBOX.",
                    OUTLOOK_MONITOR_MAILBOX_NAME,
                    names,
                )
            except Exception:
                logger.warning(
                    "[MONITOR] Caixa '%s' nao encontrada — usando Inbox padrao do perfil.",
                    OUTLOOK_MONITOR_MAILBOX_NAME,
                )
        return namespace.GetDefaultFolder(OutlookMonitorService._ol_folder_inbox)

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _html_body_automation_started(python_name: str) -> str:
        """HTML reply: automation started (copy in Portuguese for end users)."""
        safe = escape(python_name, quote=True)
        return (
            f'<html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background-color:#0a0a0a;">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#0a0a0a;padding:24px 12px;">'
            f'<tr><td align="center">'
            f'<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">'
            f'<tr><td style="background:linear-gradient(135deg,#1a1a1a 0%,#121212 100%);padding:20px 24px;border-bottom:2px solid #D3AD65;">'
            f'<p style="margin:0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#D3AD65;">Célula Python Monitoração</p>'
            f'<h1 style="margin:8px 0 0 0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:20px;font-weight:700;color:#f5f5f5;">Automação em execução</h1>'
            f"</td></tr>"
            f'<tr><td style="background-color:#121212;padding:24px 28px;">'
            f'<p style="margin:0 0 16px 0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.55;color:#e5e5e5;">Olá,</p>'
            f'<p style="margin:0 0 16px 0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.55;color:#e5e5e5;">'
            f"A automação <strong style=\"color:#D3AD65;\">{safe}</strong> <strong>começou a executar</strong>."
            f"</p>"
            f'<p style="margin:0 0 0 0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.55;color:#a3a3a3;">'
            f"Em breve você receberá o e-mail de devolutiva com o resultado."
            f"</p>"
            f"</td></tr>"
            f'<tr><td style="background-color:#0a0a0a;padding:16px 24px;border-top:1px solid #2a2a2a;">'
            f'<p style="margin:0;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:12px;color:#737373;">Atenciosamente,<br/>Célula Python Monitoração</p>'
            f"</td></tr></table></td></tr></table></body></html>"
        )

    @staticmethod
    def _run_script_in_bg(script_path: str, entry_id: str):
        slot_acquired = False
        script_name = _normalize_python_exec_name(script_path)
        try:
            if not _try_acquire_python_exec_slot(script_path):
                logger.warning(f"[MONITOR] Execução ignorada: '{script_name}' já está em execução.")
                return
            slot_acquired = True

            logger.info(f"[MONITOR] Iniciando execução em background: {script_path}")
            
            # Identificar o solicitante via Outlook antes de rodar o script
            solicitante = "SISTEMA"
            if HAS_OUTLOOK:
                pythoncom.CoInitialize()
                try:
                    outlook = win32.Dispatch("outlook.application")
                    namespace = outlook.GetNamespace("MAPI")
                    item = namespace.GetItemFromID(entry_id)
                    solicitante = getattr(item, "SenderEmailAddress", "SISTEMA")
                    logger.info(f"[MONITOR] Solicitante identificado: {solicitante}")
                except Exception:
                    logger.warning(f"[MONITOR] Não foi possível extrair o remetente do EntryID {entry_id}.")
                finally:
                    with suppress(Exception):
                        pythoncom.CoUninitialize()

            python_cmd = sys.executable if not getattr(sys, "frozen", False) else "python"
            
            # Garantir a execução na pasta nativa do script para não quebrar caminhos relativos
            cwd_path = str(Path(script_path).parent)
            
            # Injetar variáveis de ambiente para o script capturar via metricsmanager
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["ENV_EXEC_MODE"] = "SOLICITACAO"
            env["ENV_EXEC_USER"] = solicitante.lower()

            # Subir o processo isolado no Windows de forma segura
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE

            process = subprocess.Popen(
                [python_cmd, script_path], 
                cwd=cwd_path,
                env=env,
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                **kwargs
            )
            
            # Aguarda a conclusão total do código que foi chamado
            rc = process.wait()

            time.sleep(10)
            
            logger.info(f"[MONITOR] Execução finalizada (código {rc}) para {script_path}. Verificando se o email ainda existe para movê-lo para a lixeira.")
            if HAS_OUTLOOK:
                pythoncom.CoInitialize()
                try:
                    outlook = win32.Dispatch("outlook.application")
                    namespace = outlook.GetNamespace("MAPI")
                    item = namespace.GetItemFromID(entry_id)
                    item.Delete()
                    logger.info(f"[MONITOR] Email movido para lixeira com sucesso pelo Server.")
                except Exception:
                    logger.info(f"[MONITOR] O email já foi movido/deletado pelo próprio script ou não foi encontrado.")
                finally:
                    with suppress(Exception):
                        pythoncom.CoUninitialize()
                
        except Exception as e:
            logger.exception(f"[MONITOR] Erro ao iniciar {script_path}: {e}")
        finally:
            if slot_acquired:
                _release_python_exec_slot(script_path)

    @classmethod
    def monitor_loop(cls):
        logger.info("[MONITOR] Serviço de monitoramento do Outlook iniciado.")
        logger.info(
            "[MONITOR] Caixa alvo (Inbox): %s",
            OUTLOOK_MONITOR_MAILBOX_NAME or "(Inbox padrao do perfil — SERVERCRON_OUTLOOK_MONITOR_MAILBOX=)",
        )
        while True:
            try:
                if not HAS_OUTLOOK:
                    time.sleep(60)
                    continue

                pythoncom.CoInitialize()
                try:
                    outlook = win32.Dispatch("outlook.application")
                    namespace = outlook.GetNamespace("MAPI")
                    inbox = cls._resolve_inbox_folder(namespace)

                    items = inbox.Items
                    items.Sort("[ReceivedTime]", True)

                    # Apenas scripts .py diretamente em uma pasta "metodos" (área = metodos/..)
                    script_map = {}
                    base_dir = BASE_PATH
                    if base_dir.exists():
                        for p in base_dir.rglob("*.py"):
                            if "venv" in p.parts or ".venv" in p.parts or p.name.startswith("__"):
                                continue
                            if p.parent.name.lower() != "metodos":
                                continue
                            python_name = p.stem.lower()
                            area_dir = p.parent.parent
                            input_dir = area_dir / "arquivos_input" / python_name
                            if python_name in script_map:
                                logger.warning(
                                    "[MONITOR] Nome de script duplicado em metodos ignorado: %s (mantido: %s)",
                                    p,
                                    script_map[python_name]["script_path"],
                                )
                                continue
                            script_map[python_name] = {
                                "script_path": str(p),
                                "input_dir": input_dir,
                            }
                    else:
                        logger.warning(f"[MONITOR] BASE_PATH não encontrado: {base_dir}")

                    hoje = datetime.now().date()

                    for item in items:
                        try:
                            # 1. Ignorar itens que não sejam emails reais (Class 43 = MailItem)
                            if getattr(item, "Class", 0) != 43:
                                continue

                            received = getattr(item, "ReceivedTime", None)
                            if not received:
                                continue
                            
                            # Conversão segura de pywintypes.datetime para datetime puro da stdlib
                            item_date = datetime(received.year, received.month, received.day).date()
                            
                            if item_date < hoje:
                                break  # Como está decrescente, chegamos nos dias anteriores; podemos sair do for

                            entry_id = getattr(item, "EntryID", None)
                            if not entry_id or entry_id in cls._processed_ids:
                                continue

                            subject = getattr(item, "Subject", "")
                            if not subject:
                                cls._processed_ids.add(entry_id)
                                continue
                                
                            subject_lower = str(subject).strip().lower()
                            subject_norm = cls._normalize_text(subject_lower)
                            
                            matched_script_info = None
                            matched_python_name = None
                            
                            # Dispara quando o assunto é EXATAMENTE o python_name (só entradas em script_map = metodos)
                            for python_name, script_info in script_map.items():
                                if (
                                    subject_lower == python_name
                                    or subject_lower == f"{python_name}.py"
                                    or subject_norm == python_name
                                ):
                                    matched_script_info = script_info
                                    matched_python_name = python_name
                                    break
                                
                            if matched_script_info:
                                cls._processed_ids.add(entry_id)
                                logger.info(f"[MONITOR] Email recebido com script no assunto: '{matched_python_name}'")
                                
                                # Processar anexos antes de chamar a automação
                                input_dir_path = matched_script_info["input_dir"]
                                
                                if item.Attachments.Count > 0:
                                    if input_dir_path.exists():
                                        for f in input_dir_path.iterdir():
                                            if f.is_file():
                                                try:
                                                    f.unlink()
                                                except Exception as e:
                                                    logger.error(f"[MONITOR] Erro ao deletar arquivo antigo {f.name}: {e}")
                                    else:
                                        input_dir_path.mkdir(parents=True, exist_ok=True)
                                        
                                    for i_att in range(1, item.Attachments.Count + 1):
                                        att = item.Attachments.Item(i_att)
                                        try:
                                            att_path = input_dir_path / att.FileName
                                            att.SaveAsFile(str(att_path))
                                            logger.info(f"[MONITOR] Anexo '{att.FileName}' baixado na pasta {input_dir_path}")
                                        except Exception as e:
                                            logger.error(f"[MONITOR] Erro ao salvar anexo '{att.FileName}': {e}")
                                
                                # Marca o e-mail como lido para não pegar de novo caso o cache limpe
                                item.UnRead = False
                                item.Save()
                                
                                try:
                                    reply = item.Reply()
                                    reply.BodyFormat = 2  # olFormatHTML
                                    reply.HTMLBody = cls._html_body_automation_started(matched_python_name)
                                    reply.Send()
                                    logger.info(f"[MONITOR] Resposta HTML enviada (inicio automacao '{matched_python_name}').")
                                except Exception as e:
                                    logger.error(f"[MONITOR] Falha ao responder email: {e}")
                                
                                threading.Thread(
                                    target=cls._run_script_in_bg, 
                                    args=(matched_script_info["script_path"], entry_id), 
                                    daemon=True
                                ).start()
                            else:
                                # Assunto não bate com nenhum .py em metodos (ou vazio). Cache só para não revistorar.
                                cls._processed_ids.add(entry_id)

                        except AttributeError:
                            continue
                        except Exception as e:
                            logger.error(f"[MONITOR] Erro processando email em lote: {e}")

                except Exception as e:
                    logger.error(f"[MONITOR] Erro ao interagir com o Outlook: {e}")
                finally:
                    with suppress(Exception):
                        pythoncom.CoUninitialize()

            except Exception as e:
                logger.error(f"[MONITOR] Erro geral no loop: {e}")

            time.sleep(60)

    @classmethod
    def start(cls):
        t = threading.Thread(target=cls.monitor_loop, daemon=True)
        t.start()

# ═══════════════════════════════════════════════════════════════════════
# FLASK APPLICATION
# ═══════════════════════════════════════════════════════════════════════

app = Flask(__name__, template_folder=str(PANEL_HTML_DIR), static_folder=str(PANEL_HTML_DIR))
app.secret_key = SECRET_KEY
# Distinct from _app (ServerCron) so both portals can stay logged in on the same host/port (unified mode).
app.config["SESSION_COOKIE_NAME"] = "server_uploaders_session"
UPLOADERS_TEMPLATE: str = (
    "ServerCRON.html"
    if _resolve_panel_file("ServerCRON.html") is not None
    else (
        "Server.html"
        if _resolve_panel_file("Server.html") is not None
        else (
            "ServerUploaders.html"
            if _resolve_panel_file("ServerUploaders.html") is not None
            else "ServerCRON.html"
        )
    )
)


def _uploaders_cron_embed() -> bool:
    return request.args.get("cron_embed") == "1" or request.form.get("cron_embed") == "1"


def _safe_after_login_param(raw: Optional[str]) -> Optional[str]:
    """Allow only same-site relative paths (blocks open redirects)."""
    s = (raw or "").strip()
    if not s:
        return None
    low = s.lower()
    if "\\" in s or "://" in low:
        return None
    if not s.startswith("/"):
        return None
    if s.startswith("//"):
        return None
    return s


def _form_after_login() -> str:
    v = (request.form.get("after_login") or request.args.get("after_login") or "").strip()
    ok = _safe_after_login_param(v)
    return ok or ""


def _uploaders_index_redirect(**extra):
    """Preserva cron_embed nos redirects do fluxo token."""
    if _uploaders_cron_embed():
        return redirect(url_for("index", cron_embed="1", **extra))
    return redirect(url_for("index", **extra))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Sliding refresh: resend the signed session cookie on each request while logged in.
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
# Allow larger automation inputs without requiring .env (tune if needed).
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024


def _serve_uploaders_logo() -> Response:
    """Brand logo: first existing file under CONFIG_MODULES_DIR or panel assets."""
    for _logo_path in _BRAND_LOGO_CANDIDATES:
        if _logo_path.is_file():
            return send_file(_logo_path, mimetype="image/png", max_age=3600)
    return Response(status=404)


@app.route("/assets/logo.png")
def logo_brand():
    """Organization logo served from the shared modules folder (PNG)."""
    return _serve_uploaders_logo()


auth_tokens: dict[str, dict] = {}
# 6-digit e-mail OTP: window to type the code (separate from logged-in session length, 24h).
EMAIL_OTP_VALID = timedelta(minutes=15)
# Minimum seconds between e-mail token requests (anti-flood), per user who passed permission check.
TOKEN_REQUEST_COOLDOWN_SEC: float = 180.0
_uploaders_token_request_at: dict[str, float] = {}


def _prune_expired_auth_tokens() -> None:
    """Remove expired e-mail OTPs from memory (best-effort). Logged-in sessions use the Flask cookie (24h)."""
    now = datetime.now()
    for user in list(auth_tokens.keys()):
        if now > auth_tokens[user]["expires"]:
            auth_tokens.pop(user, None)


def _script_path_trusted(script_path: str) -> bool:
    """Ensure SSE execution only runs .py files under BASE_PATH (defense in depth)."""
    try:
        p = Path(script_path).resolve()
        if p.suffix.lower() != ".py":
            return False
        p.relative_to(BASE_PATH.resolve())
        return True
    except (ValueError, OSError):
        return False


_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}


def _get_client_ip() -> str:
    h = request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-IP")
    if h:
        return h.split(",")[0].strip()[:100]
    return (request.remote_addr or "unknown")[:100]


def _rate_limit_ok(key: str, max_events: int, window_sec: float = 60.0) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window_sec]
        if len(bucket) >= max_events:
            return False
        bucket.append(now)
    return True


def _ensure_csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return str(session["csrf_token"])


def _csrf_valid() -> bool:
    p = request.get_json(silent=True) or {}
    t = request.headers.get("X-CSRF-Token") or p.get("csrf_token") or request.form.get("csrf_token")
    return bool(t) and t == session.get("csrf_token")


@app.before_request
def _uploaders_session_refresh_permanent() -> None:
    """Keep permanent session and cookie max-age sliding while username is in session (24h)."""
    if "username" in session:
        session.permanent = True
        session.modified = True


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    cron_embed = request.args.get("cron_embed") == "1"
    # Unified portal: default entrypoint is Cron; Uploaders is accessed via the Uploaders tab (embedded iframe).
    if not cron_embed and not _env_truthy("SERVERCRON_DUO_PORTS"):
        return redirect("/cron/")
    if "username" not in session:
        return render_template(
            UPLOADERS_TEMPLATE,
            portal_view="uploaders",
            page="login",
            username="",
            is_admin=False,
            all_recipients="",
            path_to_name={},
            diretorios={},
            user_prefs={"recent": [], "frequent": []},
            csrf_token="",
            show_cron_link=_unified_portal_with_cron(),
            cron_embed=cron_embed,
        )

    username = session["username"]
    pastas = PermissionService.ler_pastas_permitidas(username)
    grouped, valid_paths = FileService.mapear_diretorios(pastas)
    is_admin = PermissionService.is_admin_user(username)
    all_recipients = PermissionService.get_all_recipients()

    user_prefs = AnalyticsService.get_user_prefs(username)
    user_prefs["recent"] = [p for p in user_prefs.get("recent", []) if p in valid_paths]
    user_prefs["frequent"] = [p for p in user_prefs.get("frequent", []) if p in valid_paths]

    path_to_name: dict[str, str] = {}
    for subpastas in grouped.values():
        path_to_name.update(subpastas)

    return render_template(
        UPLOADERS_TEMPLATE,
        portal_view="uploaders",
        page="upload",
        username=username,
        is_admin=is_admin,
        diretorios=grouped,
        all_recipients=all_recipients,
        user_prefs=user_prefs,
        path_to_name=path_to_name,
        csrf_token=_ensure_csrf_token(),
        show_cron_link=_unified_portal_with_cron(),
        cron_embed=cron_embed,
        after_login="",
    )


@app.route("/api/admin/servercron", methods=["GET"])
def api_admin_get_servercron():
    if "username" not in session:
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401
    if not PermissionService.is_admin_user(session["username"]):
        return jsonify({"ok": False, "message": "Acesso reservado a administradores."}), 403
    if not _rate_limit_ok(f"admbq:GET:{_get_client_ip()}", 45):
        return jsonify({"ok": False, "message": "Muitas requisições. Aguarde 1 minuto."}), 429
    if not HAS_REGISTRY_XLSX:
        return jsonify(
            {
                "ok": False,
                "message": "registro_automacoes.xlsx indisponível ou pandas em falta.",
                "rows": [],
                "table_id": f"{REGISTRO_AUTOMAOES_PATH}::{SHEET_USERS}",
            }
        )
    try:
        rows = AccessAdminService.fetch_all_rows()
        return jsonify(
            {
                "ok": True,
                "rows": rows,
                "table_id": f"{REGISTRO_AUTOMAOES_PATH}::{SHEET_USERS}",
                "job_state": "DONE",
            }
        )
    except Exception as e:
        logger.exception("api_admin_get_servercron")
        return jsonify({"ok": False, "message": str(e), "rows": []}), 500


@app.route("/api/admin/servercron/add", methods=["POST"])
def api_admin_add_servercron():
    if "username" not in session:
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401
    actor = session["username"]
    if not PermissionService.is_admin_user(actor):
        return jsonify({"ok": False, "message": "Apenas administradores."}), 403
    if not _csrf_valid():
        return jsonify({"ok": False, "message": "Token CSRF inválido. Recarregue a página."}), 403
    if not _rate_limit_ok(f"admbq:ADD:{_get_client_ip()}", 25):
        return jsonify({"ok": False, "message": "Limite de alterações. Aguarde 1 minuto."}), 429
    if not HAS_REGISTRY_XLSX:
        return jsonify({"ok": False, "message": "Planilha de registo indisponível neste Server."}), 503
    p = request.get_json(silent=True) or {}
    try:
        rows, bq_jid, bq_dml = AccessAdminService.insert_row(
            p.get("users", ""),
            p.get("level_access", ""),
            p.get("folder_access") or p.get("folder_acess") or None,
        )
        logger.info("Admin %s inseriu linha na folha USERS (%s).", actor, REGISTRO_AUTOMAOES_PATH)
        return jsonify(
            {
                "ok": True,
                "rows": rows,
                "message": "Linha inserida e folha USERS regravada no ficheiro.",
                "bq_job_id": bq_jid,
                "bq_dml_affected_rows": bq_dml,
            }
        )
    except ValueError as ve:
        return jsonify({"ok": False, "message": str(ve), "rows": []}), 400
    except Exception as e:
        logger.exception("api_admin_add_servercron")
        return jsonify({"ok": False, "message": str(e), "rows": []}), 500


@app.route("/api/admin/servercron/delete", methods=["POST"])
def api_admin_delete_servercron():
    if "username" not in session:
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401
    actor = session["username"]
    if not PermissionService.is_admin_user(actor):
        return jsonify({"ok": False, "message": "Apenas administradores."}), 403
    if not _csrf_valid():
        return jsonify({"ok": False, "message": "Token CSRF inválido. Recarregue a página."}), 403
    if not _rate_limit_ok(f"admbq:DEL:{_get_client_ip()}", 25):
        return jsonify({"ok": False, "message": "Limite de alterações. Aguarde 1 minuto."}), 429
    if not HAS_REGISTRY_XLSX:
        return jsonify({"ok": False, "message": "Planilha de registo indisponível neste Server."}), 503
    p = request.get_json(silent=True) or {}
    try:
        rows, bq_jid, bq_dml = AccessAdminService.delete_row(
            p.get("users", ""),
            p.get("level_access", ""),
            p.get("folder_access"),
        )
        logger.info("Admin %s removeu linha na folha USERS (%s).", actor, REGISTRO_AUTOMAOES_PATH)
        return jsonify(
            {
                "ok": True,
                "rows": rows,
                "message": "Linha removida e folha USERS regravada no ficheiro.",
                "bq_job_id": bq_jid,
                "bq_dml_affected_rows": bq_dml,
            }
        )
    except ValueError as ve:
        return jsonify({"ok": False, "message": str(ve), "rows": []}), 400
    except Exception as e:
        logger.exception("api_admin_delete_servercron")
        return jsonify({"ok": False, "message": str(e), "rows": []}), 500


@app.route("/api/admin/servercron/update", methods=["POST"])
def api_admin_update_servercron():
    if "username" not in session:
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401
    actor = session["username"]
    if not PermissionService.is_admin_user(actor):
        return jsonify({"ok": False, "message": "Apenas administradores."}), 403
    if not _csrf_valid():
        return jsonify({"ok": False, "message": "Token CSRF inválido. Recarregue a página."}), 403
    if not _rate_limit_ok(f"admbq:UPD:{_get_client_ip()}", 25):
        return jsonify({"ok": False, "message": "Limite de alterações. Aguarde 1 minuto."}), 429
    if not HAS_REGISTRY_XLSX:
        return jsonify({"ok": False, "message": "Planilha de registo indisponível neste Server."}), 503
    p = request.get_json(silent=True) or {}

    def _none_if_empty(x: object) -> str | None:
        if x is None:
            return None
        s = str(x).strip()
        return None if s == "" else s

    try:
        o_fa = p.get("old_folder_access", p.get("old_folder_acess"))
        o_fa = _none_if_empty(o_fa)
        n_fa = _none_if_empty(p.get("folder_access", p.get("folder_acess")))

        rows, bq_jid, bq_dml = AccessAdminService.update_row(
            p.get("old_users", "") or "",
            p.get("old_level_access", "") or "",
            o_fa,
            p.get("users", ""),
            p.get("level_access", ""),
            n_fa,
        )
        logger.info("Admin %s alterou linha na folha USERS (%s).", actor, REGISTRO_AUTOMAOES_PATH)
        return jsonify(
            {
                "ok": True,
                "rows": rows,
                "message": "Linha atualizada e folha USERS regravada no ficheiro.",
                "bq_job_id": bq_jid,
                "bq_dml_affected_rows": bq_dml,
            }
        )
    except ValueError as ve:
        return jsonify({"ok": False, "message": str(ve), "rows": []}), 400
    except Exception as e:
        logger.exception("api_admin_update_servercron")
        return jsonify({"ok": False, "message": str(e), "rows": []}), 500


@app.route("/request_token", methods=["POST"])
def request_token():
    logger.info(
        "[AUTH] Uploaders request_token POST | IP=%s | keys=%s",
        _get_client_ip(),
        list(request.form.keys()),
    )
    _al = _form_after_login()
    # Light per-IP cap (in addition to per-user 3 min cooldown).
    if not _rate_limit_ok(f"rt_ip:{_get_client_ip()}", 10, window_sec=600.0):
        flash("Muitas tentativas a partir desta rede. Tente em alguns minutos.", "error")
        return _uploaders_index_redirect()
    username = request.form.get("username", "").strip().lower()
    if not username:
        logger.warning("[AUTH] Uploaders request_token rejeitado: username vazio | IP=%s", _get_client_ip())
        flash("Digite um usuário válido.", "error")
        return _uploaders_index_redirect()

    pastas = PermissionService.ler_pastas_permitidas(username)
    if not pastas:
        logger.warning(
            "[AUTH] Uploaders request_token negado: sem pastas para user=%s | IP=%s",
            username,
            _get_client_ip(),
        )
        flash("Sem acesso configurado.", "error")
        return _uploaders_index_redirect()

    now = time.time()
    last = _uploaders_token_request_at.get(username, 0.0)
    if now - last < TOKEN_REQUEST_COOLDOWN_SEC:
        rem = int(TOKEN_REQUEST_COOLDOWN_SEC - (now - last)) + 1
        m, s = rem // 60, rem % 60
        logger.warning(
            "[AUTH] Uploaders request_token cooldown: user=%s aguarde=%sm%ss",
            username,
            m,
            s,
        )
        flash(
            f"Aguarde {m}m{s:02d}s entre um pedido de token e outro (máximo 1 a cada 3 minutos).",
            "error",
        )
        return _uploaders_index_redirect()

    _prune_expired_auth_tokens()
    # New e-mail supersedes any previous pending OTP for this user.
    token = "".join(random.choices(string.digits, k=6))
    auth_tokens[username] = {
        "token": token,
        "expires": datetime.now() + EMAIL_OTP_VALID,
    }
    _uploaders_token_request_at[username] = now
    dest = f"{username}{DOMAIN}"
    logger.info("[AUTH] Uploaders request_token aceito: user=%s dest=%s", username, dest)

    def _uploaders_token_mail_worker() -> None:
        if EmailService.send_token_email(dest, token):
            logger.info("E-mail de token enviado para %s (envio assíncrono).", dest)
        else:
            auth_tokens.pop(username, None)
            _uploaders_token_request_at.pop(username, None)
            logger.error("Falha ao enviar e-mail de token (envio assíncrono) para %s", dest)

    threading.Thread(target=_uploaders_token_mail_worker, daemon=True, name="uploaders-token-mail").start()
    flash(
        "Token gerado. O Outlook pode levar alguns segundos para enviar — verifique o e-mail.",
        "info",
    )
    return render_template(
        UPLOADERS_TEMPLATE,
        portal_view="uploaders",
        page="verify",
        username=username,
        is_admin=False,
        all_recipients="",
        path_to_name={},
        diretorios={},
        user_prefs={"recent": [], "frequent": []},
        csrf_token="",
        show_cron_link=_unified_portal_with_cron(),
        cron_embed=_uploaders_cron_embed(),
        after_login=_al,
    )


@app.route("/verify_token", methods=["POST"])
def verify_token():
    username = request.form.get("username", "").strip().lower()
    token_inserido = request.form.get("token")
    _al = _form_after_login()

    if username in auth_tokens:
        dados = auth_tokens[username]
        if datetime.now() > dados["expires"]:
            auth_tokens.pop(username, None)
            flash("Token expirado.", "error")
            return _uploaders_index_redirect(after_login=_al)
        if token_inserido == dados["token"]:
            auth_tokens.pop(username, None)
            session["username"] = username
            session["role"] = "admin" if PermissionService.is_admin_user(username) else "viewer"
            session.permanent = True
            session["login_at"] = datetime.now().isoformat(timespec="seconds")
            session.modified = True
            dest = _safe_after_login_param(request.form.get("after_login", ""))
            if dest:
                return redirect(dest)
            if _uploaders_cron_embed():
                return redirect(url_for("index", cron_embed="1"))
            return redirect(url_for("index"))

    _prune_expired_auth_tokens()
    flash("Token inválido.", "error")
    return _uploaders_index_redirect(after_login=_al)


@app.route("/upload_ajax", methods=["POST"])
def upload_ajax():
    if "username" not in session:
        return jsonify({"status": "error", "message": "Sessão expirada."}), 401

    username = session["username"]
    pastas = PermissionService.ler_pastas_permitidas(username)
    _, valid_paths = FileService.mapear_diretorios(pastas)

    raw_target = (request.form.get("target_folder") or "").strip()
    try:
        target_resolved = str(Path(raw_target).resolve())
    except OSError:
        target_resolved = raw_target

    valid_paths_lower = {p.lower(): p for p in valid_paths}
    target_path_lower = target_resolved.lower()

    upload_files = [f for f in request.files.getlist("files") if f and (f.filename or "").strip()]
    if not upload_files:
        one = request.files.get("file")
        if one and (one.filename or "").strip():
            upload_files = [one]

    if not upload_files or target_path_lower not in valid_paths_lower:
        if target_path_lower not in valid_paths_lower:
            logger.error(f"[UPLOAD] Pasta inválida: recebido='{target_resolved}'")
            logger.error(f"[UPLOAD] Paths válidos: {list(valid_paths)}")
        return jsonify({"status": "error", "message": "Arquivo(s) ou pasta inválida. Verifique o log no console."})

    target_path = valid_paths_lower[target_path_lower]
    saved_names: list[str] = []
    try:
        for up in upload_files:
            fn = secure_filename(up.filename or "")
            if not fn:
                continue
            caminho_final = Path(target_path) / fn
            up.save(str(caminho_final))
            saved_names.append(fn)
        if not saved_names:
            return jsonify({"status": "error", "message": "Nenhum nome de arquivo válido após sanitização."})

        AnalyticsService.track_usage(username, target_path)

        if request.form.get("execution_mode") == "upload_only":
            return jsonify(
                {
                    "status": "success",
                    "execution_mode": "upload_only",
                    "file_saved": ", ".join(saved_names),
                    "files_saved": saved_names,
                }
            )

        script_path, existe, nome_alvo = FileService.localizar_script(target_path)
        if existe:
            _set_pending_script_for_user(username, script_path)
            return jsonify({"status": "success", "script_exists": True, "python_name": f"{nome_alvo}.py"})
        return jsonify({"status": "success", "script_exists": False, "folder_name": nome_alvo})
    except Exception as e:
        logger.exception("[UPLOAD] Erro interno durante o upload: ")
        return jsonify({"status": "error", "message": f"Erro interno (veja o console): {str(e)}"})


@app.route("/prepare_execution", methods=["POST"])
def prepare_execution():
    if "username" not in session:
        return jsonify({"status": "error", "message": "Sessão expirada."}), 401

    username = session["username"]
    pastas = PermissionService.ler_pastas_permitidas(username)
    _, valid_paths = FileService.mapear_diretorios(pastas)

    raw_target = (request.form.get("target_folder") or "").strip()
    try:
        target_resolved = str(Path(raw_target).resolve())
    except OSError:
        target_resolved = raw_target

    valid_paths_lower = {p.lower(): p for p in valid_paths}
    target_path_lower = target_resolved.lower()

    if target_path_lower not in valid_paths_lower:
        logger.error(f"[PREPARE_EXEC] Pasta inválida: recebido='{target_resolved}'")
        logger.error(f"[PREPARE_EXEC] Paths válidos disponíveis: {list(valid_paths)}")
        return jsonify({"status": "error", "message": "Pasta inválida. Verifique os logs no console."})

    target_path = valid_paths_lower[target_path_lower]

    try:
        script_path, existe, nome_alvo = FileService.localizar_script(str(target_path))
        if existe:
            _set_pending_script_for_user(username, script_path)
            AnalyticsService.track_usage(username, target_path)
            return jsonify({"status": "success", "script_exists": True, "python_name": f"{nome_alvo}.py"})
        return jsonify({"status": "success", "script_exists": False, "folder_name": nome_alvo})
    except Exception as e:
        logger.exception("[PREPARE_EXEC] Erro interno ao preparar execução: ")
        return jsonify({"status": "error", "message": f"Erro interno (veja o console): {str(e)}"})


@app.route("/stream_logs")
def stream_logs():
    username = session.get("username", "desconhecido")
    script_path = _pop_pending_script_for_user(username)
    if not script_path or not _script_path_trusted(script_path):
        return Response(
            "data: [CONCLUIDO_ERRO] Sem script pendente para execução. Tente clicar em 'Apenas Start' novamente.\n\n",
            mimetype="text/event-stream",
        )

    resp = Response(
        stream_with_context(ExecutorService.run_script(script_path, username)),
        mimetype="text/event-stream",
    )
    resp.headers["Cache-Control"] = "no-cache, no-transform"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.route("/api/server_info")
def api_server_info():
    """Identifies this service; when unified, ServerCron is at /cron/ on the same port."""
    return jsonify(
        {
            "service": "ServerUploaders",
            "port": PORT,
            "unified_cron_href": "/cron/" if _unified_portal_with_cron() else None,
        }
    )


@app.route("/api/log_event", methods=["POST"])
def log_event():
    if not _rate_limit_ok(f"evt:{_get_client_ip()}", 120):
        return jsonify({"status": "rate_limited"}), 429
    data = request.json
    if not data:
        return jsonify({"status": "error"}), 400

    user = data.get("user", "Desconhecido")
    event_type = data.get("type", "CLICK")
    label = data.get("label", "N/A")

    logger.info(f"[USER-EVENT] {user} | {event_type} | Element: {label}")

    traceback_info = data.get("traceback")
    if traceback_info:
        logger.error(f"TRACEBACK DETECTADO:\n{traceback_info}")

    return jsonify({"status": "logged"}), 200


@app.route("/api/share_outlook", methods=["POST"])
def share_outlook():
    """Opens Outlook Classic compose window via win32com with pre-filled recipients and body."""
    if "username" not in session:
        return jsonify({"status": "error", "message": "Sessão expirada."}), 401
    if not _rate_limit_ok(f"sho:{_get_client_ip()}", 12):
        return jsonify({"status": "error", "message": "Muitas requisições. Aguarde 1 minuto."}), 429
    if not _csrf_valid():
        return jsonify({"status": "error", "message": "Sessão inválida (CSRF). Recarregue a página."}), 403

    if not PermissionService.is_admin_user(session["username"]):
        return jsonify({"status": "error", "message": "Apenas administradores podem disparar e-mails de acesso em massa."}), 403

    if not HAS_OUTLOOK:
        return jsonify({"status": "error", "message": "Outlook COM não disponível neste Server."}), 500

    try:
        all_recipients = PermissionService.get_all_recipients()
        urls = _shared_portal_urls()
        html_body = _build_shared_invite_html(
            uploaders_url=urls["uploaders_url_lan"],
            cron_url=urls["cron_url_lan"],
        )

        def _open_outlook():
            try:
                pythoncom.CoInitialize()
                outlook = win32.Dispatch("outlook.application")
                mail = outlook.CreateItem(0)
                mail.Subject = "ServerCRON | Server"
                mail.HTMLBody = html_body
                mail.To = all_recipients.replace(",", ";")
                mail.Display()
                logger.info("[SHARE] Janela de composição do Outlook aberta com sucesso.")
            except Exception:
                logger.exception("[SHARE] Erro ao abrir Outlook via COM")
            finally:
                with suppress(Exception):
                    pythoncom.CoUninitialize()

        t = threading.Thread(target=_open_outlook, daemon=True)
        t.start()

        logger.info(f"[SHARE] Outlook aberto por {session.get('username')} com {len(all_recipients.split(';'))} destinatários")
        return jsonify({"status": "success", "message": "Outlook aberto com email de compartilhamento."})

    except Exception as e:
        logger.exception("Erro ao abrir Outlook para compartilhamento")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/logout")
def logout():
    u = session.get("username")
    if isinstance(u, str):
        u_lower = u.strip().lower()
        auth_tokens.pop(u_lower, None)
        _uploaders_token_request_at.pop(u_lower, None)
    session.clear()
    return redirect(url_for("index"))


# ═══════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════

def _get_local_ip() -> str:
    s: Optional[socket.socket] = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        if s is not None:
            s.close()
    return ip


def _shared_portal_urls() -> dict[str, str]:
    """Canonical LAN links for Uploaders and Cron used in invite e-mails."""
    lan_ip = _get_local_ip()
    if _env_truthy("SERVERCRON_DUO_PORTS"):
        up_port = int((os.environ.get("SERVERCRON_UP_PORT") or os.environ.get("PORT") or "5001").strip() or "5001")
        cr_port = int((os.environ.get("SERVERCRON_CRON_PORT") or "5002").strip() or "5002")
        return {
            "uploaders_url_lan": f"http://{lan_ip}:{up_port}/",
            "cron_url_lan": f"http://{lan_ip}:{cr_port}/",
        }
    unified = int((os.environ.get("SERVERCRON_UNIFIED_PORT", str(PORT)) or str(PORT)).strip())
    return {
        "uploaders_url_lan": f"http://{lan_ip}:{unified}/",
        "cron_url_lan": f"http://{lan_ip}:{unified}/cron/",
    }


_STARTUP_INVITE_SENT_FILE = SCRIPT_DIR / "startup_invite_last_sent.txt"


def _startup_invite_today_key() -> str:
    return datetime.now(TIMEZONE).date().isoformat()


def _startup_invite_already_sent_today() -> bool:
    try:
        if not _STARTUP_INVITE_SENT_FILE.is_file():
            return False
        return _STARTUP_INVITE_SENT_FILE.read_text(encoding="utf-8").strip() == _startup_invite_today_key()
    except Exception:
        return False


def _mark_startup_invite_sent_today() -> None:
    try:
        _STARTUP_INVITE_SENT_FILE.write_text(_startup_invite_today_key() + "\n", encoding="utf-8")
    except Exception:
        logger.warning("[INVITE] Não foi possível gravar startup_invite_last_sent.txt.")


def _build_shared_invite_html(uploaders_url: str, cron_url: str) -> str:
    """Single HTML body used by Uploaders and Cron invite endpoints."""
    return f"""
    <div style="font-family: Segoe UI, Arial, sans-serif; color: #333; max-width: 760px;">
        <h2 style="color: #242424; border-bottom: 2px solid #d3ad65; padding-bottom: 10px;">
            ServerCRON — Convite de acesso
        </h2>
        <p>Prezados,</p>
        <p>Segue abaixo os links oficiais de acesso:</p>
        <div style="margin: 20px 0 24px 0;">
            <p style="margin:0 0 10px 0;">
                <b>ServerUploaders:</b>
                <a href="{uploaders_url}">{uploaders_url}</a>
            </p>
            <p style="margin:0;">
                <b>ServerCron:</b>
                <a href="{cron_url}">{cron_url}</a>
            </p>
        </div>
        <p style="color: #555; font-size: 13px; background: #f3f4f6; padding: 12px; border-radius: 6px;">
            <b>Como acessar:</b><br>
            1. Abra o link no Google Chrome.<br>
            2. Informe seu usuário de rede (sem o sufixo corporativo configurado em SERVERCRON_EMAIL_DOMAIN).<br>
            3. O token será enviado ao e-mail corporativo.<br>
            4. Digite o token para concluir o acesso.
        </p>
        <p>Atenciosamente,<br><b>ServerCRON</b></p>
    </div>
    """


def _send_startup_access_invite(uploaders_url: str, cron_url: str) -> None:
    """Send one Outlook invite e-mail to all users from servercron."""
    if not HAS_OUTLOOK:
        logger.warning("[INVITE] Outlook COM indisponível. Convite automático não enviado.")
        return

    if _startup_invite_already_sent_today():
        logger.info(
            "[INVITE] Convite de arranque já enviado hoje (%s) — ignorando nova tentativa.",
            _startup_invite_today_key(),
        )
        return

    recipients = PermissionService.get_all_recipients().strip()
    if not recipients:
        logger.warning("[INVITE] Nenhum destinatário encontrado na folha USERS (%s). Convite não enviado.", REGISTRO_AUTOMAOES_PATH)
        return

    html_body = _build_shared_invite_html(uploaders_url=uploaders_url, cron_url=cron_url)

    def _send_mail() -> None:
        pythoncom.CoInitialize()
        try:
            outlook = win32.Dispatch("outlook.application")
            mail = outlook.CreateItem(0)
            mail.Subject = "ServerCRON | Server"
            mail.HTMLBody = html_body
            mail.To = recipients.replace(";", ",")
            mail.Send()
            _mark_startup_invite_sent_today()
            logger.info(
                "[INVITE] Convite enviado para %d destinatário(s).",
                len([r for r in re.split(r"[;,]", recipients) if r.strip()]),
            )
        except Exception:
            logger.exception("[INVITE] Falha ao enviar convite automático.")
        finally:
            with suppress(Exception):
                pythoncom.CoUninitialize()

    threading.Thread(target=_send_mail, daemon=True, name="startup-invite-mail").start()


def _start_browser(url: str) -> None:
    def _open():
        try:
            chrome = "C:/Program Files/Google/Chrome/Application/chrome.exe"
            chrome_x86 = "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"

            if Path(chrome).exists():
                webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome))
                browser = webbrowser.get("chrome")
            elif Path(chrome_x86).exists():
                webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome_x86))
                browser = webbrowser.get("chrome")
            else:
                browser = webbrowser.get()

            browser.open(url)
            logger.info(f"Navegador aberto: {url}")
        except Exception:
            logger.exception("Erro ao abrir navegador")

    threading.Timer(1.5, _open).start()


# EMBEDDED_CRON_MERGED_V1 — env before embedded Cron (CRON_URL_PREFIX read at cron block load)
if _env_truthy("SERVERCRON_DUO_PORTS"):
    os.environ["SERVERCRON_CRON_URL_PREFIX"] = ""
    os.environ["SERVERCRON_UNIFIED_PORTAL"] = "0"
else:
    os.environ.setdefault("SERVERCRON_CRON_URL_PREFIX", "/cron")
    os.environ.setdefault("SERVERCRON_UNIFIED_PORT", str(PORT))
    os.environ["SERVERCRON_UNIFIED_PORTAL"] = "1"

# ======================================================================
# SERVERCRON (embedded Cron scheduler + API; same repo as Uploaders Flask app above)
# ======================================================================

# ==============================================================
# IMPORTS
# ==============================================================
import json
import os
import random
import re
import signal
import string
import subprocess
import sys
import threading
import time
import logging
import platform
import socket
import webbrowser
from collections import deque
from contextlib import suppress
from datetime import datetime, timedelta
from queue import PriorityQueue
from pathlib import Path
import sqlite3
from typing import Optional

def bootstrap():
    """Instala silenciosamente as dependências se estiverem faltando."""
    import importlib.util
    
    deps = {
        "apscheduler": "apscheduler==3.10.4",
        "flask": "flask==3.0.3",
        "flask_cors": "flask-cors==4.0.1",
        "pandas": "pandas==2.2.2",
        "openpyxl": "openpyxl==3.1.2",
        "psutil": "psutil==5.9.8",
        "pytz": "pytz==2024.1",
        "croniter": "croniter==2.0.5",
        "waitress": "waitress==3.0.0",
        "sqlalchemy": "sqlalchemy==2.0.30"
    }
    
    missing = []
    for mod, pkg in deps.items():
        try:
            if "." in mod:
                import importlib
                importlib.import_module(mod)
            else:
                if importlib.util.find_spec(mod) is None:
                    missing.append(pkg)
        except Exception:
            missing.append(pkg)
            
    if missing:
        print(f"[BOOTSTRAP] Instalando {len(missing)} dependência(s) ausente(s): {', '.join(missing)}...", flush=True)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("[BOOTSTRAP] Dependências instaladas com sucesso.", flush=True)
        except subprocess.CalledProcessError:
            print("[BOOTSTRAP] Falha ao instalar as dependências. Verifique a internet e permissões.", flush=True)
            sys.exit(1)

bootstrap()

import pandas as pd
import pytz
import psutil
from flask import Flask, jsonify, request, send_file, Response, session
from flask_cors import CORS
from waitress import serve

try:
    import pythoncom
    import win32com.client as win32
    HAS_OUTLOOK = True
except ImportError:
    HAS_OUTLOOK = False

# Agendador APScheduler + SQLAlchemy job store
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# ==============================================================
# CAMINHOS — ajuste apenas aqui
# Dados do Cron: mesma pasta do ServerCRON.py
# Um único ficheiro SQLite: agendador (APScheduler) + tabela execution_runs.
# Ficheiros .sqlite-wal / .sqlite-shm = modo WAL do SQLite (não são “duas bases”, são o mesmo ficheiro).
# ==============================================================
_HOME = Path.home()
CRON_PATH_SCRIPT_DIR = Path(__file__).resolve().parent
PATH_SERVER_APP = CRON_PATH_SCRIPT_DIR
PATH_CRON_SQLITE = _prefer_new_home_file(PATH_SERVER_APP, "server_cron.sqlite", "vidor_cron.sqlite")
PATH_JOBSTORE_SQLITE = PATH_CRON_SQLITE
PATH_EXECUTION_SQLITE = PATH_CRON_SQLITE
_db_path = PATH_CRON_SQLITE

PATH_AUTOMACOES = DATA_ROOT / "automacoes"

# HTML (same folder as this package; optional: SERVERCRON_PANEL_DIR)
PATH_DASHBOARD_HTML = CRON_PATH_SCRIPT_DIR / "ServerCRON.html"
if not PATH_DASHBOARD_HTML.is_file():
    _alt_dash = CRON_PATH_SCRIPT_DIR / "Server.html"
    if _alt_dash.is_file():
        PATH_DASHBOARD_HTML = _alt_dash
    else:
        _alt_dash2 = CRON_PATH_SCRIPT_DIR / "ServerCron.html"
        if _alt_dash2.is_file():
            PATH_DASHBOARD_HTML = _alt_dash2
_panel_dir_raw = (os.environ.get("SERVERCRON_PANEL_DIR") or "").strip()
if _panel_dir_raw:
    _p_panel = Path(_panel_dir_raw)
    if _p_panel.is_dir():
        for _dash_name in ("ServerCRON.html", "Server.html", "ServerCron.html"):
            _dash_try = _p_panel / _dash_name
            if _dash_try.is_file():
                PATH_DASHBOARD_HTML = _dash_try
                break

# Chrome no Windows (abrir dashboard); ordem de tentativa
PATH_CHROME_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Google"
    / "Chrome"
    / "Application"
    / "chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    / "Google"
    / "Chrome"
    / "Application"
    / "chrome.exe",
    _HOME / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
)

# --- Aliases usados no restante do modulo (nao duplicar logica) ---
DIRETORIO_AUTOMACOES = PATH_AUTOMACOES
_DASHBOARD_FILE = PATH_DASHBOARD_HTML

# ==============================================================
# LOGGING (Cron) — consola + mesmo ficheiro que ServerCRON (logs/AAAA-MM-DD/uuid.log)
# ==============================================================
_log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger_cron = logging.getLogger("ServerCron")
logger_cron.setLevel(logging.INFO)
logger_cron.propagate = False
_cron_console_handler = logging.StreamHandler(sys.stdout)
_cron_console_handler.setFormatter(_log_formatter)
logger_cron.addHandler(_cron_console_handler)
_cron_file_handler = logging.FileHandler(_SERVER_LOG_FILE_PATH, encoding="utf-8")
_cron_file_handler.setFormatter(_SERVER_LOG_FORMATTER)
logger_cron.addHandler(_cron_file_handler)
_root_console = logging.StreamHandler(sys.stdout)
_root_console.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_root_console])

try:
    from croniter import croniter as _Croniter
    _HAS_CRONITER = True
except ImportError:
    _HAS_CRONITER = False
    logger_cron.warning("'croniter' nao instalado - catch-up desabilitado.")

# ==============================================================
# CONFIGURACAO SERVER (nao-caminhos)
# ==============================================================
MAX_PROCESSOS_SIMULTANEOS = 5
RELOAD_INTERVAL_MINUTES   = 30
RELOAD_COOLDOWN_SECONDS   = 180
MAX_CPU_PERCENT           = 90
MAX_RAM_PERCENT           = 90
DEFAULT_TIMEOUT_SECONDS   = 7200  # 2h

HOST     = "0.0.0.0"
# Standalone: 5002. When using unified single-port mode (DispatcherMiddleware), SERVERCRON_UNIFIED_PORT + /cron is used.
CRON_STANDALONE_PORT     = 5002
# Public path prefix e.g. "/cron" when Cron app is mounted under Uploaders (set before import).
CRON_URL_PREFIX: str = os.environ.get("SERVERCRON_CRON_URL_PREFIX", "").strip().rstrip("/")
CRON_TZ_NAME = "America/Sao_Paulo"
TZ       = pytz.timezone(CRON_TZ_NAME)

OPEN_BROWSER = True
BROWSER_DELAY_SEC = 1.2

CRON_ON_DEMAND     = "ON DEMAND"
_SERVER_START_TIME = time.time()
_SERVER_VERSION    = "2.3.6"

# --- Dashboard auth (token via e-mail, same pattern as ServerUploaders) ---
CRON_SECRET_KEY: str = "chave_super_secreta_sessao_server_cron_monitoracao_x9k2"
MOCK_EMAIL: bool = False
# Login Cron e papel admin/viewer: somente `servercron` (users com virgulas; level_access ADM|user|...).
ALLOWED_LOGIN_USERS: list[str] = []

_ACCESS_REGISTRY_TTL_SECONDS = 120
_access_registry_cache: dict = {"data": {}, "ts": 0.0}
_access_registry_lock = threading.Lock()

_cron_auth_tokens: dict[str, dict] = {}
_cron_token_request_at: dict[str, float] = {}

# -- History (persistent SQLite, mesma pasta do ServerCRON.py) --------------------------------
_MAX_HISTORY = 1000
_history_lock = threading.Lock()
def _normalize_history_entry(entry: dict) -> dict:
    """Exit code 2 = NO_DATA (sem dados), distinto de sucesso (0). Corrige linhas antigas gravadas como success."""
    if entry.get("exit_code") == 2:
        entry["status"] = "no_data"
    return entry


def _ensure_execution_sqlite() -> None:
    """Cria tabela de histórico no mesmo ficheiro que o job store (server_cron.sqlite)."""
    with sqlite3.connect(str(PATH_EXECUTION_SQLITE), check_same_thread=False) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS execution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                python_name TEXT NOT NULL,
                area_name TEXT,
                priority INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_seconds REAL,
                duration_label TEXT,
                exit_code INTEGER,
                status TEXT,
                trigger_reason TEXT,
                error_message TEXT,
                stdout_tail TEXT,
                stderr_tail TEXT
            );
            """
        )
        conn.commit()


def _row_to_entry(row: sqlite3.Row) -> dict:
    d = {k: row[k] for k in row.keys()}
    d.pop("id", None)
    return _normalize_history_entry(d)


def _load_history_from_sqlite() -> deque:
    history = deque(maxlen=_MAX_HISTORY)
    if not PATH_EXECUTION_SQLITE.is_file():
        return history
    try:
        with sqlite3.connect(str(PATH_EXECUTION_SQLITE), check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                f"""
                SELECT * FROM execution_runs
                ORDER BY id DESC
                LIMIT {_MAX_HISTORY}
                """
            )
            rows = [_row_to_entry(r) for r in cur]
        # rows: mais recente primeiro; appendleft do mais antigo ao mais recente
        for entry in reversed(rows):
            history.appendleft(entry)
        logger_cron.info(
            f"[BOOT] Histórico carregado: {len(history)} execução(ões) de {PATH_EXECUTION_SQLITE.name}"
        )
    except Exception:
        logger_cron.exception(f"[BOOT] Falha ao carregar histórico de {PATH_EXECUTION_SQLITE}. Iniciando vazio.")
    return history


def _insert_execution_and_trim(entry: dict) -> None:
    with sqlite3.connect(str(PATH_EXECUTION_SQLITE), check_same_thread=False) as conn:
        conn.execute(
            """
            INSERT INTO execution_runs (
                python_name, area_name, priority, start_time, end_time,
                duration_seconds, duration_label, exit_code, status,
                trigger_reason, error_message, stdout_tail, stderr_tail
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                entry.get("python_name", ""),
                entry.get("area_name", ""),
                entry.get("priority"),
                entry.get("start_time", ""),
                entry.get("end_time", ""),
                entry.get("duration_seconds"),
                entry.get("duration_label", ""),
                entry.get("exit_code"),
                entry.get("status", ""),
                entry.get("trigger_reason", ""),
                entry.get("error_message"),
                entry.get("stdout_tail"),
                entry.get("stderr_tail"),
            ),
        )
        conn.execute(
            f"""
            DELETE FROM execution_runs WHERE id NOT IN (
                SELECT id FROM execution_runs ORDER BY id DESC LIMIT {_MAX_HISTORY}
            );
            """
        )
        conn.commit()


_ensure_execution_sqlite()
_execution_history: deque = _load_history_from_sqlite()

# ==============================================================
# UTILITÁRIOS DE PARSING
# ==============================================================

def _safe_str(val) -> str:
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).strip()

def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return _safe_str(val).lower() in ("true", "1", "yes", "sim")

def _parse_priority(val) -> int:
    try:
        p = int(float(_safe_str(val)))
        return p if p in (1, 2, 3) else 2
    except Exception:
        return 2

def _parse_int_safe(val, default=0) -> int:
    try:
        s = _safe_str(val)
        return int(float(s)) if s else default
    except (ValueError, TypeError):
        return default

def _normalize_name(raw: str) -> str:
    s = str(raw).strip().lower()
    return s[:-3] if s.endswith(".py") else s


def _normalize_access_role(level_access: str) -> str:
    s = _safe_str(level_access).strip().lower()
    if s in ("admin", "administrador", "adm", "administrator"):
        return "admin"
    return "viewer"


def _fetch_servercron_access_bq() -> dict[str, str]:
    """Cada login em `users` (célula pode listar vários separados por vírgula) -> admin|viewer.

    Usa o mesmo cache que PermissionService (folha USERS).
    """
    out: dict[str, str] = {}
    try:
        df = PermissionService._get_servercron_dataframe()
        if df is None:
            return out
        if df.empty:
            logger_cron.info("[AUTH] Folha USERS vazia.")
            return out
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "users" not in df.columns or "level_access" not in df.columns:
            logger_cron.warning(
                "[AUTH] USERS: colunas inesperadas (esperado users, level_access). Encontrado: %s",
                list(df.columns),
            )
            return out
        for _, row in df.iterrows():
            role = _normalize_access_role(_safe_str(row.get("level_access", "")))
            for token in _split_user_tokens(row.get("users", "")):
                if not token:
                    continue
                prev = out.get(token)
                if prev == "admin" or role == "admin":
                    out[token] = "admin"
                else:
                    out[token] = role
        logger_cron.info("[AUTH] USERS: %d token(s) com nível de acesso (cache).", len(out))
    except Exception:
        logger_cron.exception("[AUTH] Falha ao montar mapa de acesso a partir da folha USERS.")
    return out


def _build_access_registry() -> dict[str, str]:
    """Folha USERS + lista extra ALLOWED_LOGIN_USERS."""
    bq = _fetch_servercron_access_bq()
    merged: dict[str, str] = dict(bq)
    if not bq:
        logger_cron.warning(
            "[AUTH] Nenhum utilizador na folha USERS ou ficheiro em falta: %s",
            REGISTRO_AUTOMAOES_PATH,
        )
    for u in ALLOWED_LOGIN_USERS:
        ul = u.strip().lower()
        if ul and ul not in merged:
            merged[ul] = "viewer"
    logger_cron.info(
        "[AUTH] Registo de acesso | planilha=%d token(s) | total_apos_lista_extra=%d",
        len(bq),
        len(merged),
    )
    return merged


def _get_access_registry() -> dict[str, str]:
    with _access_registry_lock:
        age = time.time() - _access_registry_cache["ts"]
        if _access_registry_cache["data"] and age < _ACCESS_REGISTRY_TTL_SECONDS:
            return dict(_access_registry_cache["data"])
    merged = _build_access_registry()
    with _access_registry_lock:
        _access_registry_cache["data"] = merged
        _access_registry_cache["ts"] = time.time()
    return dict(merged)


def _invalidate_access_registry_cache() -> None:
    with _access_registry_lock:
        _access_registry_cache["data"] = {}
        _access_registry_cache["ts"] = 0.0


def _servercron_registro_mtime() -> float:
    try:
        return float(REGISTRO_AUTOMAOES_PATH.stat().st_mtime)
    except OSError:
        return 0.0


def _servercron_fetch_users_df_once() -> Optional[object]:
    """Lê a folha USERS; None em falha."""
    if not HAS_PANDAS:
        return None
    if not REGISTRO_AUTOMAOES_PATH.is_file():
        logger.warning("registro_automacoes.xlsx não encontrado: %s", REGISTRO_AUTOMAOES_PATH)
        return None
    try:
        df = pd.read_excel(REGISTRO_AUTOMAOES_PATH, sheet_name=SHEET_USERS, engine="openpyxl")
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "users" not in df.columns or "level_access" not in df.columns:
            logger.error("Folha USERS sem colunas users/level_access. Colunas: %s", list(df.columns))
            return None
        if "folder_access" not in df.columns:
            df["folder_access"] = None
        return df
    except Exception:
        logger.exception("Erro ao ler folha USERS de %s", REGISTRO_AUTOMAOES_PATH)
        return None


def _servercron_schedule_background_refresh() -> None:
    """Recarrega folha USERS em thread (stale-while-revalidate)."""
    global _servercron_last_bg_schedule
    if not HAS_PANDAS or not REGISTRO_AUTOMAOES_PATH.is_file():
        return
    now = time.time()
    with _servercron_bg_schedule_lock:
        if now - _servercron_last_bg_schedule < 15.0:
            return
        _servercron_last_bg_schedule = now

    def _worker() -> None:
        with _servercron_bq_lock:
            tnow = time.time()
            df = _servercron_cache["df"]
            loaded = float(_servercron_cache["loaded_at"] or 0.0)
            if df is not None and (tnow - loaded) < _SERVERCRON_CACHE_TTL_SEC:
                return
            new_df = _servercron_fetch_users_df_once()
            if new_df is None:
                return
            _servercron_cache["df"] = new_df
            _servercron_cache["loaded_at"] = time.time()
            _servercron_cache["src_mtime"] = _servercron_registro_mtime()
        _invalidate_access_registry_cache()

    threading.Thread(target=_worker, daemon=True, name="servercron-users-refresh").start()


def _servercron_resolve_dataframe() -> Optional[object]:
    """Cache da folha USERS; bloqueia só quando não há cópia stale utilizável."""
    if not HAS_PANDAS:
        return None

    mtime = _servercron_registro_mtime()
    with _servercron_bq_lock:
        if mtime and float(_servercron_cache.get("src_mtime") or 0.0) != mtime:
            _servercron_cache["df"] = None
            _servercron_cache["loaded_at"] = 0.0

    def _age_seconds() -> tuple[Optional[object], float]:
        df0 = _servercron_cache["df"]
        loaded0 = float(_servercron_cache["loaded_at"] or 0.0)
        ag = time.time() - loaded0 if df0 is not None else float("inf")
        return df0, ag

    df, age = _age_seconds()
    if df is not None and age < _SERVERCRON_CACHE_TTL_SEC:
        return df
    if df is not None and age < _SERVERCRON_STALE_MAX_SEC:
        _servercron_schedule_background_refresh()
        return df

    with _servercron_bq_lock:
        df, age = _age_seconds()
        if df is not None and age < _SERVERCRON_CACHE_TTL_SEC:
            return df
        if df is not None and age < _SERVERCRON_STALE_MAX_SEC:
            _servercron_schedule_background_refresh()
            return df
        new_df = _servercron_fetch_users_df_once()
        if new_df is None:
            return df
        _servercron_cache["df"] = new_df
        _servercron_cache["loaded_at"] = time.time()
        _servercron_cache["src_mtime"] = mtime
    _invalidate_access_registry_cache()
    return new_df


def _is_valid_cron(cron_str: str) -> bool:
    s = str(cron_str).strip().upper()
    if not s or s == CRON_ON_DEMAND:
        return False
    try:
        CronTrigger.from_crontab(s, timezone=TZ)
        return True
    except ValueError:
        return False

def _now_br() -> datetime:
    """Current datetime in São Paulo timezone (naive)."""
    return datetime.now(TZ).replace(tzinfo=None)

def _history_entry_start_date(entry: dict):
    """Calendar date of execution start from stored ISO `start_time` (timezone do Server)."""
    st = entry.get("start_time") or ""
    if len(st) >= 10:
        try:
            return datetime.strptime(st[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def _has_error_recorded_today(python_name: str, ref_date) -> bool:
    """Check if this script already has an error entry on the provided date."""
    for entry in _execution_history:
        if entry.get("python_name") != python_name:
            continue
        if entry.get("status") != "error":
            continue
        if _history_entry_start_date(entry) == ref_date:
            return True
    return False


def _format_duration(seconds: float) -> str:
    """Human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h{mins:02d}m{secs:02d}s"

# ==============================================================
# HISTORY RECORDER
# ==============================================================

def _record_execution(
    python_name: str, area_name: str, priority: int,
    start_ts: float, end_ts: float, exit_code: int | None,
    trigger_reason: str, error_msg: str | None = None,
    stdout_tail: str | None = None, stderr_tail: str | None = None,
) -> None:
    """Append a finished execution to in-memory history."""
    elapsed = round(end_ts - start_ts, 1)
    if exit_code == 0:
        status = "success"
    elif exit_code == 2:
        status = "no_data"
    elif exit_code is None:
        status = "killed"
    else:
        status = "error"
    entry = {
        "python_name":    python_name,
        "area_name":      area_name,
        "priority":       priority,
        "start_time":     datetime.fromtimestamp(start_ts, TZ).isoformat(),
        "end_time":       datetime.fromtimestamp(end_ts, TZ).isoformat(),
        "duration_seconds": elapsed,
        "duration_label":   _format_duration(elapsed),
        "exit_code":      exit_code,
        "status":         status,
        "trigger_reason": trigger_reason,
        "error_message":  error_msg,
        "stdout_tail":    stdout_tail,
        "stderr_tail":    stderr_tail,
    }
    entry_date = _history_entry_start_date(entry)
    with _history_lock:
        if status == "error" and entry_date and _has_error_recorded_today(python_name, entry_date):
            logger_cron.info(
                f"[HISTORY] Erro repetido suprimido para {python_name} em {entry_date.isoformat()} "
                "(limite: 1 erro/dia/script)."
            )
            return
        _execution_history.appendleft(entry)
    try:
        _insert_execution_and_trim(entry)
    except Exception:
        logger_cron.exception("[HISTORY] Falha ao gravar execução em SQLite.")

# ==============================================================
# SCANNER (OTIMIZADO + cache em memória)
# ==============================================================

_LOCAL_FILES_TTL_SECONDS = 180
_local_files_cache: dict = {"data": {}, "ts": 0.0}
_local_files_lock = threading.Lock()


def _invalidate_local_files_cache() -> None:
    with _local_files_lock:
        _local_files_cache["data"] = {}
        _local_files_cache["ts"] = 0.0


def buscar_arquivos_locais() -> dict[str, Path]:
    """Varre o disco por .py; resultado fica em cache ~3 min para acelerar o dashboard."""
    with _local_files_lock:
        age = time.time() - _local_files_cache["ts"]
        if _local_files_cache["data"] and age < _LOCAL_FILES_TTL_SECONDS:
            return dict(_local_files_cache["data"])

    found: dict[str, Path] = {}
    if not DIRETORIO_AUTOMACOES or not DIRETORIO_AUTOMACOES.exists():
        logger_cron.warning(f"DIRETORIO_AUTOMACOES não encontrado: {DIRETORIO_AUTOMACOES}")
        return found

    ignore_dirs = {".git", ".vscode", "__pycache__", "venv", "env", "node_modules", ".venv"}

    for root, dirs, files in os.walk(DIRETORIO_AUTOMACOES):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        root_path = Path(root)
        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            name = _normalize_name(filename)
            full = root_path / filename
            if name in found:
                continue
            found[name] = full

    logger_cron.info(f"[SCAN] Disco: {len(found)} arquivos .py (cache {_LOCAL_FILES_TTL_SECONDS}s).")
    with _local_files_lock:
        _local_files_cache["data"] = found
        _local_files_cache["ts"] = time.time()
    return dict(found)

# ==============================================================
# REGISTRY READER — folha AUTOMACOES (cache TTL; ver _BQ_CACHE_TTL_SECONDS no topo)
# ==============================================================

def _ler_registro_planilha(force: bool = False) -> list[dict]:
    """Lê o cadastro na folha AUTOMACOES de registro_automacoes.xlsx (cache em memória)."""
    with _bq_cache_lock:
        age = time.time() - _bq_cache["ts"]
        if not force and _bq_cache["records"] and age < _BQ_CACHE_TTL_SECONDS:
            return _bq_cache["records"]

    logger_cron.info("[REGISTRY] A ler folha %s de %s …", SHEET_AUTOMAOES, REGISTRO_AUTOMAOES_PATH)
    if not HAS_PANDAS:
        logger_cron.warning("[REGISTRY] pandas indisponível.")
        with _bq_cache_lock:
            return _bq_cache["records"]
    if not REGISTRO_AUTOMAOES_PATH.is_file():
        logger_cron.warning("[REGISTRY] Ficheiro inexistente: %s", REGISTRO_AUTOMAOES_PATH)
        with _bq_cache_lock:
            return _bq_cache["records"]
    try:
        df = pd.read_excel(
            REGISTRO_AUTOMAOES_PATH, sheet_name=SHEET_AUTOMAOES, engine="openpyxl"
        )
        df = df.dropna(how="all")
        df.columns = [str(c).strip().upper() for c in df.columns]
        logger_cron.info("[REGISTRY] %s linhas na folha %s.", len(df), SHEET_AUTOMAOES)
    except Exception as e:
        logger_cron.exception("[REGISTRY] Erro ao ler planilha: %s", e)
        with _bq_cache_lock:
            return _bq_cache["records"]

    records = []
    for _, row in df.iterrows():
        python_name = _safe_str(row.get("PYTHON_NAME", ""))
        if not python_name:
            continue

        normalized = _normalize_name(python_name)
        cron_raw = _safe_str(row.get("CRON", ""))

        val_fin_mov = row.get("MOVIMENTACAO_FINANCEIRA", row.get("MOVIMENTACAO FINANCEIRA", False))
        val_cli_int = row.get("INTERACAO_CLIENTE", row.get("INTERACAO CLIENTE", False))
        val_tempo   = row.get("TEMPO_MANUAL_MINUTOS", row.get("TEMPO MANUAL MINUTOS", 0))

        records.append({
            "python_name":             normalized,
            "area_name":               _safe_str(row.get("AREA_NAME", "sem area")).lower(),
            "cron_raw":                cron_raw,
            "is_valid_cron":           _is_valid_cron(cron_raw),
            "cron_source":             "workbook",
            "is_active":               _parse_bool(row.get("IS_ACTIVE", False)),
            "priority":                _parse_priority(row.get("PRIORITY", 2)),
            "emails_principal":        _safe_str(row.get("EMAILS_PRINCIPAL", "")),
            "emails_cc":               _safe_str(row.get("EMAILS_CC", "")),
            "move_file":               _parse_bool(row.get("MOVE_FILE", False)),
            "movimentacao_financeira": _parse_bool(val_fin_mov),
            "interacao_cliente":       _parse_bool(val_cli_int),
            "tempo_manual":            _parse_int_safe(val_tempo, 0),
            "objetivo":                _safe_str(row.get("OBJETIVO", "")),
            "responsavel":             _safe_str(row.get("RESPONSAVEL", "")),
        })

    with _bq_cache_lock:
        _bq_cache["records"] = records
        _bq_cache["ts"] = time.time()
    logger_cron.info("[REGISTRY] Cache atualizado (%s entradas).", len(records))
    return records

def _get_all_scripts(local_files: dict[str, Path], force_bq: bool = False) -> list[dict]:
    result = []
    for r in _ler_registro_planilha(force=force_bq):
        r = dict(r)  # copy to avoid mutating cache
        r["available_locally"] = r["python_name"] in local_files
        r["path"] = str(local_files[r["python_name"]]) if r["available_locally"] else None
        result.append(r)
    return result

def _get_schedulable_scripts(local_files: dict[str, Path], force_bq: bool = False) -> list[dict]:
    schedulable = []
    for s in _get_all_scripts(local_files, force_bq=force_bq):
        if not s["is_active"]:
            continue
        if s["cron_raw"].strip().upper() == CRON_ON_DEMAND:
            continue
        if not s["is_valid_cron"]:
            logger_cron.warning(
                f"[IGNORADO] '{s['python_name']}': CRON inválido ('{s['cron_raw']}'). "
                "Corrija na folha AUTOMACOES (coluna CRON)."
            )
            continue
        if not s["available_locally"]:
            logger_cron.warning(f"[IGNORADO] '{s['python_name']}': Arquivo .py não encontrado no disco local.")
            continue
        schedulable.append(s)
    return schedulable

# ==============================================================
# CATCH-UP ENGINE - detecta e executa scripts pendentes do dia
# ==============================================================

def _detect_pending_scripts() -> list[dict]:
    """Return scripts whose cron window already passed today but haven't run.
    Each entry includes python_name, area_name, cron_raw, priority,
    expected_time, available_locally, and path.
    """
    if not _HAS_CRONITER:
        return []

    today_str = _now_br().strftime("%Y-%m-%d")
    local_files = buscar_arquivos_locais()
    all_scripts = _get_all_scripts(local_files)
    schedulable = [
        s for s in all_scripts
        if s["is_active"] and s["is_valid_cron"]
        and s["cron_raw"].strip().upper() != CRON_ON_DEMAND
    ]

    with _history_lock:
        today_history = {
            e["python_name"] for e in _execution_history
            if e.get("start_time", "").startswith(today_str)
        }
    with _running_lock:
        running_names = {d["python_name"] for d in _running.values()}
    queued_names = {task["python_name"] for _, _, _, task in list(_task_queue.queue)}

    pending = []
    # Naive America/Sao_Paulo wall clock — matches croniter output and avoids aware/naive compare issues.
    now_dt = _now_br()
    today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    for s in schedulable:
        name = s["python_name"]
        if name in today_history or name in running_names or name in queued_names:
            continue
        try:
            cron = _Croniter(s["cron_raw"], today_start)
            next_fire = cron.get_next(datetime)
            if next_fire <= now_dt:
                pending.append({
                    "python_name": name,
                    "area_name": s["area_name"],
                    "cron_raw": s["cron_raw"],
                    "priority": s["priority"],
                    "expected_time": next_fire.strftime("%H:%M"),
                    "available_locally": s["available_locally"],
                    "path": s.get("path"),
                })
        except Exception:
            pass

    # Sort by priority (P1=1 first, then P2=2, then P3=3), then by expected_time
    pending.sort(key=lambda x: (x["priority"], x["expected_time"]))
    return pending


def _catchup_pending_scripts() -> None:
    """Detect scripts that missed their cron window today and enqueue them.
    Order: all P1 first, then P2, then P3.
    Only enqueues scripts that are available locally.
    """
    pending = _detect_pending_scripts()
    if not pending:
        logger_cron.info("[CATCH-UP] Nenhum script pendente do dia.")
        return

    enqueued = 0
    skipped = 0
    for s in pending:
        if not s["available_locally"] or not s.get("path"):
            logger_cron.warning(f"[CATCH-UP] '{s['python_name']}' sem arquivo local. Pulando.")
            skipped += 1
            continue

        ok = enqueue_script(
            python_name=s["python_name"],
            path=s["path"],
            area_name=s["area_name"],
            priority=s["priority"],
            scheduled_ts=time.time(),
            trigger_reason="catch-up",
        )
        if ok:
            enqueued += 1
            logger_cron.info(f"[CATCH-UP] Enfileirado: {s['python_name']} (P{s['priority']}, esperado {s['expected_time']})")
        else:
            skipped += 1

    logger_cron.info(f"[CATCH-UP] Concluído: {enqueued} enfileirado(s), {skipped} pulado(s) de {len(pending)} pendente(s).")

# ==============================================================
# PROCESS METRICS COLLECTOR
# ==============================================================

def _get_process_metrics(pid: int) -> dict:
    """Collect CPU% and memory for a given PID."""
    try:
        proc = psutil.Process(pid)
        mem_info = proc.memory_info()
        cpu = proc.cpu_percent(interval=0)
        children = proc.children(recursive=True)
        child_mem = sum(c.memory_info().rss for c in children)
        return {
            "rss_mb": round((mem_info.rss + child_mem) / (1024 * 1024), 1),
            "cpu_percent": cpu,
            "num_children": len(children),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"rss_mb": 0.0, "cpu_percent": 0.0, "num_children": 0}

# ==============================================================
# EXECUTOR & HEALTH GOVERNOR
# ==============================================================

_semaphore          = threading.Semaphore(MAX_PROCESSOS_SIMULTANEOS)
_task_queue: PriorityQueue = PriorityQueue()
_running: dict[int, dict]  = {}
_running_lock               = threading.Lock()
_killed_by_user_pids: set[int] = set()
_killed_by_user_lock = threading.Lock()

def _mark_killed_by_user(pid: int) -> None:
    with _killed_by_user_lock:
        _killed_by_user_pids.add(pid)

def _consume_killed_by_user(pid: int) -> bool:
    with _killed_by_user_lock:
        return pid in _killed_by_user_pids and not _killed_by_user_pids.remove(pid)

def _priority_to_tier(priority: int) -> int:
    return {1: 0, 2: 1, 3: 2}.get(priority, 1)

def enqueue_script(python_name: str, path: str, area_name: str, priority: int, scheduled_ts: float, trigger_reason: str = "scheduled") -> bool:
    normalized_name = _normalize_python_exec_name(python_name)
    with _running_lock:
        if any(d["python_name"] == normalized_name for d in _running.values()):
            return False
        if any(task["python_name"] == normalized_name for _, _, _, task in list(_task_queue.queue)):
            return False

    tier = _priority_to_tier(priority)
    task_data = {
        "python_name":   normalized_name, "path": path, "area_name": area_name,
        "priority":      priority, "tier": tier, "trigger_reason": trigger_reason,
        "scheduled_ts":  scheduled_ts,
    }
    _task_queue.put((tier, scheduled_ts, time.time(), task_data))
    logger_cron.info(f"[QUEUE] {normalized_name} | p={priority} | motivo={trigger_reason}")
    return True

def _register_pid(proc, task_data: dict) -> None:
    with _running_lock:
        _running[proc.pid] = {
            "pid": proc.pid, "proc_obj": proc, "python_name": task_data["python_name"],
            "area_name": task_data["area_name"], "priority": task_data["priority"],
            "start_time": time.time(), "trigger_reason": task_data["trigger_reason"],
            "slot_managed": True,
        }

def _unregister_pid(pid: int) -> None:
    with _running_lock:
        _running.pop(pid, None)

def _wait_for_resources():
    """
    HEALTH GOVERNOR: Impede que o Server seja sufocado.
    Se o disco/CPU chegar no talo, ele segura os processos da fila P2 e P3
    """
    while True:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        if cpu <= MAX_CPU_PERCENT and ram <= MAX_RAM_PERCENT:
            break
        logger_cron.warning(f"[RECURSOS ALTO] CPU: {cpu}% | RAM: {ram}%. Aguardando estabilização para rodar novos processos...")
        time.sleep(5)

def _run_p2p3(task_data: dict) -> None:
    _wait_for_resources()

    name = task_data["python_name"]
    path = task_data["path"]
    proc = None
    t_start = time.time()
    stdout_tail = None
    stderr_tail = None
    error_msg = None
    exit_code = None
    logger_cron.info(f"[>] Iniciando: {name}")
    slot_acquired = False
    try:
        if not _try_acquire_python_exec_slot(name):
            logger_cron.warning(f"[DUPLICADO] '{name}' já em execução. Ignorando novo disparo.")
            error_msg = "Duplicate execution prevented"
            exit_code = None
            return
        slot_acquired = True
        proc = subprocess.Popen(
            [sys.executable, str(path)],
            shell=False,
            cwd=str(Path(path).parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _register_pid(proc, task_data)
        try:
            raw_stdout, raw_stderr = proc.communicate(timeout=DEFAULT_TIMEOUT_SECONDS)
            stdout_tail = raw_stdout.decode("utf-8", errors="replace")[-2000:] if raw_stdout else None
            stderr_tail = raw_stderr.decode("utf-8", errors="replace")[-2000:] if raw_stderr else None
        except subprocess.TimeoutExpired:
            logger_cron.warning(f"[TIMEOUT] {name} excedeu {DEFAULT_TIMEOUT_SECONDS}s. Matando...")
            with suppress(Exception):
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    with suppress(psutil.NoSuchProcess):
                        child.kill()
                parent.kill()
            proc.wait(timeout=10)
            error_msg = f"Timeout after {DEFAULT_TIMEOUT_SECONDS}s"

        exit_code = proc.returncode
        elapsed = round(time.time() - t_start, 1)
        if exit_code == 0:
            tag = "[OK]"
        elif exit_code == 2:
            tag = "[NO_DATA]"
        else:
            tag = "[ERR]"
        logger_cron.info(f"{tag} {name} | exit={exit_code} | elapsed={elapsed}s")
    except Exception as exc:
        logger_cron.critical(f"[CRIT] {name}: {exc}")
        error_msg = str(exc)
    finally:
        t_end = time.time()
        killed_by_user = False
        if proc:
            killed_by_user = _consume_killed_by_user(proc.pid)
            _unregister_pid(proc.pid)
        if slot_acquired:
            _release_python_exec_slot(name)
        _semaphore.release()
        if killed_by_user:
            logger_cron.info(f"[KILL] {name} finalizado manualmente. Sem registro no histórico.")
            return
        _record_execution(
            python_name=name, area_name=task_data["area_name"],
            priority=task_data["priority"], start_ts=t_start, end_ts=t_end,
            exit_code=exit_code, trigger_reason=task_data["trigger_reason"],
            error_msg=error_msg, stdout_tail=stdout_tail, stderr_tail=stderr_tail,
        )

def _run_p1(task_data: dict) -> None:
    name = task_data["python_name"]
    path = task_data["path"]
    proc = None
    t_start = time.time()
    stdout_tail = None
    stderr_tail = None
    error_msg = None
    exit_code = None
    logger_cron.info(f"[P1] Início preemptivo: {name}")
    slot_acquired = False
    try:
        if not _try_acquire_python_exec_slot(name):
            logger_cron.warning(f"[DUPLICADO] '{name}' já em execução. Ignorando novo disparo P1.")
            error_msg = "Duplicate execution prevented"
            exit_code = None
            return
        slot_acquired = True
        proc = subprocess.Popen(
            [sys.executable, str(path)],
            shell=False,
            cwd=str(Path(path).parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _register_pid(proc, task_data)
        try:
            raw_stdout, raw_stderr = proc.communicate(timeout=DEFAULT_TIMEOUT_SECONDS)
            stdout_tail = raw_stdout.decode("utf-8", errors="replace")[-2000:] if raw_stdout else None
            stderr_tail = raw_stderr.decode("utf-8", errors="replace")[-2000:] if raw_stderr else None
        except subprocess.TimeoutExpired:
            logger_cron.warning(f"[TIMEOUT] {name} (P1) excedeu {DEFAULT_TIMEOUT_SECONDS}s. Matando...")
            with suppress(Exception):
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    with suppress(psutil.NoSuchProcess):
                        child.kill()
                parent.kill()
            proc.wait(timeout=10)
            error_msg = f"Timeout after {DEFAULT_TIMEOUT_SECONDS}s"

        exit_code = proc.returncode
        elapsed = round(time.time() - t_start, 1)
        if exit_code == 0:
            tag = "[OK]"
        elif exit_code == 2:
            tag = "[NO_DATA]"
        else:
            tag = "[ERR]"
        logger_cron.info(f"{tag} {name} (P1) | exit={exit_code} | elapsed={elapsed}s")
    except Exception as exc:
        logger_cron.critical(f"[CRIT] {name} (P1): {exc}")
        error_msg = str(exc)
    finally:
        t_end = time.time()
        killed_by_user = False
        if proc:
            killed_by_user = _consume_killed_by_user(proc.pid)
            _unregister_pid(proc.pid)
        if slot_acquired:
            _release_python_exec_slot(name)
        _semaphore.release()
        if killed_by_user:
            logger_cron.info(f"[KILL] {name} (P1) finalizado manualmente. Sem registro no histórico.")
            return
        _record_execution(
            python_name=name, area_name=task_data["area_name"],
            priority=task_data["priority"], start_ts=t_start, end_ts=t_end,
            exit_code=exit_code, trigger_reason=task_data["trigger_reason"],
            error_msg=error_msg, stdout_tail=stdout_tail, stderr_tail=stderr_tail,
        )

def _queue_processor() -> None:
    while True:
        sem_acquired = False
        try:
            _tier, _sched_ts, _enq_ts, task_data = _task_queue.get()
            _semaphore.acquire()
            sem_acquired = True
            if task_data["priority"] == 1:
                t = threading.Thread(target=_run_p1, args=(task_data,), daemon=True, name=f"p1-{task_data['python_name']}")
                t.start()
            else:
                t = threading.Thread(target=_run_p2p3, args=(task_data,), daemon=True, name=f"worker-{task_data['python_name']}")
                t.start()
        except Exception as e:
            logger_cron.exception(f"Erro no processador da fila: {e}")
            if sem_acquired:
                _semaphore.release()
        finally:
            _task_queue.task_done()

def kill_process(pid: int) -> bool:
    with _running_lock:
        info = _running.get(pid)
    if not info:
        return False
    t_start = info.get("start_time", time.time())
    try:
        _mark_killed_by_user(pid)
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            with suppress(psutil.NoSuchProcess):
                child.kill()
        parent.kill()
        logger_cron.info(f"[KILL] {info['python_name']} (PID {pid})")
    except psutil.NoSuchProcess:
        pass
    except Exception as exc:
        logger_cron.warning(f"Erro ao matar PID {pid}: {exc}")
    finally:
        _unregister_pid(pid)
        logger_cron.info(f"[KILL] {info['python_name']} removido da execução ativa. Histórico suprimido por ação manual.")
    return True

def kill_by_name(python_name: str) -> list[int]:
    """Kill all running processes matching a script name. Returns killed PIDs."""
    killed_pids = []
    target_name = python_name.lower().strip()
    with _running_lock:
        targets = [
            (pid, info) for pid, info in _running.items()
            if info["python_name"].lower() == target_name
        ]
    for pid, _info in targets:
        if kill_process(pid):
            killed_pids.append(pid)
    return killed_pids

def graceful_shutdown() -> None:
    logger_cron.info("[SHUTDOWN] Matando todos os processos filhos...")
    with _running_lock:
        all_pids = list(_running.keys())
    for pid in all_pids:
        kill_process(pid)
    logger_cron.info("[SHUTDOWN] Processos filhos encerrados.")

threading.Thread(target=_queue_processor, daemon=True, name="queue-processor").start()

# ==============================================================
# SCHEDULER ENGINE (COM SQLITE JOBSTORE)
# ==============================================================

_jobstores = {
    "default": SQLAlchemyJobStore(url=f"sqlite:///{_db_path}")
}
_scheduler = BackgroundScheduler(jobstores=_jobstores, timezone=TZ)
_last_reload_ts: float = 0.0
_reload_ts_lock = threading.Lock()
# Never remove these when rebuilding per-script cron jobs (catch-up was being dropped on every BQ reload).
_SCHEDULER_PROTECTED_JOB_IDS = frozenset({"hot_reload_job", "catchup_job"})


def _remove_all_file_handlers(lg: logging.Logger) -> None:
    for h in list(lg.handlers):
        if isinstance(h, logging.FileHandler):
            lg.removeHandler(h)
            with suppress(Exception):
                h.flush()
                h.close()


def _rollover_server_calendar_day() -> None:
    """New America/Sao_Paulo calendar day: new log file + reload scheduler from workbook."""
    global _LOG_DAY_STR, _LOG_SESSION_UUID, _SERVER_LOG_FILE_PATH, UPLOADERS_LOG_DIR, _cron_file_handler
    new_day = datetime.now(TIMEZONE).date().isoformat()
    if new_day == _LOG_DAY_STR:
        return
    old_day = _LOG_DAY_STR
    _LOG_DAY_STR = new_day
    _LOG_SESSION_UUID = str(uuid.uuid4())
    new_dir = SCRIPT_DIR / "logs" / _LOG_DAY_STR
    new_dir.mkdir(parents=True, exist_ok=True)
    new_path = new_dir / f"{_LOG_SESSION_UUID}.log"
    for lg in (logger, logger_cron):
        _remove_all_file_handlers(lg)
    fh_main = logging.FileHandler(new_path, encoding="utf-8")
    fh_main.setFormatter(_SERVER_LOG_FORMATTER)
    logger.addHandler(fh_main)
    _cron_file_handler = logging.FileHandler(new_path, encoding="utf-8")
    _cron_file_handler.setFormatter(_SERVER_LOG_FORMATTER)
    logger_cron.addHandler(_cron_file_handler)
    _SERVER_LOG_FILE_PATH = new_path
    UPLOADERS_LOG_DIR = new_dir
    logger.info(
        "[DAY_ROLL] America/Sao_Paulo: %s -> %s | novo ficheiro %s",
        old_day,
        _LOG_DAY_STR,
        new_path.name,
    )
    try:
        if getattr(_scheduler, "running", False):
            recarregar_agendamentos()
            logger.info("[DAY_ROLL] Agendamentos e folha AUTOMACOES recarregados.")
    except Exception:
        logger.exception("[DAY_ROLL] Falha ao recarregar agendamentos.")


def _day_rollover_watcher_loop() -> None:
    while True:
        time.sleep(45)
        try:
            _rollover_server_calendar_day()
        except Exception:
            with suppress(Exception):
                logger.exception("[DAY_ROLL] watcher")


def _job_wrapper(python_name: str, path: str, area_name: str, priority: int) -> None:
    enqueue_script(
        python_name=python_name, path=path, area_name=area_name,
        priority=priority, scheduled_ts=time.time(), trigger_reason="scheduled"
    )

def recarregar_agendamentos() -> list[dict]:
    logger_cron.info("[RELOAD] Recarregando agendamentos da planilha…")
    # Permissoes servercron: Uploaders + registo de login Cron alinham no mesmo reload BQ.
    PermissionService.invalidate_servercron_cache()
    _invalidate_access_registry_cache()
    _invalidate_local_files_cache()
    for job in _scheduler.get_jobs():
        if job.id in _SCHEDULER_PROTECTED_JOB_IDS:
            continue
        job.remove()

    local_files = buscar_arquivos_locais()
    scripts = _get_schedulable_scripts(local_files, force_bq=True)

    jobs_criados = 0
    for s in scripts:
        try:
            trigger = CronTrigger.from_crontab(s["cron_raw"], timezone=TZ)
            _scheduler.add_job(
                _job_wrapper, trigger,
                id=f"{s['python_name']}_cron",
                name=f"{s['python_name']} [{s['cron_raw']}] (p={s['priority']})",
                args=[s["python_name"], s["path"], s["area_name"], s["priority"]],
                replace_existing=True,
                misfire_grace_time=86400,
                coalesce=True,
            )
            jobs_criados += 1
        except Exception as e:
            logger_cron.warning(f"Cron inválido '{s['cron_raw']}' para {s['python_name']}: {e}")

    logger_cron.info(f"[RELOAD OK] {jobs_criados} jobs criados de {len(scripts)} scripts ativos")
    # After BQ reload, enqueue missed windows (same as periodic catch-up; job must stay registered — see _SCHEDULER_PROTECTED_JOB_IDS).
    threading.Thread(target=_catchup_pending_scripts, daemon=True, name="reload-catchup").start()
    return scripts

def iniciar_scheduler() -> None:
    recarregar_agendamentos()
    _scheduler.add_job(
        recarregar_agendamentos, "interval", minutes=RELOAD_INTERVAL_MINUTES,
        id="hot_reload_job", name=f"Hot-Reload automático BQ (a cada {RELOAD_INTERVAL_MINUTES}min)",
        replace_existing=True
    )
    # Catch-up job: every 10 min, detect pending scripts and enqueue them
    _scheduler.add_job(
        _catchup_pending_scripts, "interval", minutes=10,
        id="catchup_job", name="Catch-Up pendentes (a cada 10min)",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )
    _scheduler.start()
    logger_cron.info(f"[BOOT] APScheduler iniciado | tz={CRON_TZ_NAME}")
    # Fire catch-up once on boot (separate thread to not block startup)
    threading.Thread(
        target=_catchup_pending_scripts, daemon=True, name="boot-catchup"
    ).start()
    threading.Thread(
        target=_day_rollover_watcher_loop, daemon=True, name="servercron-day-rollover"
    ).start()
    jobs = []
    for job in _scheduler.get_jobs():
        nrt = job.next_run_time
        jobs.append({
            "id":          job.id,
            "name":        job.name or job.id,
            "next_run_br": nrt.astimezone(TZ).isoformat() if nrt else None,
        })
    return sorted(jobs, key=lambda j: j["next_run_br"] or "")


def _next_hot_reload_iso() -> str | None:
    """Next run time of the hot-reload job (for dashboard countdown without extra /api/jobs calls)."""
    try:
        job = _scheduler.get_job("hot_reload_job")
        if not job or not job.next_run_time:
            return None
        return job.next_run_time.astimezone(TZ).isoformat()
    except Exception:
        return None


class _CronEmailService:
    """Sends login token e-mails via Outlook COM (same approach as ServerUploaders)."""

    @staticmethod
    def send_token_email(destinatario: str, token: str) -> bool:
        if MOCK_EMAIL:
            logger_cron.info(f"[MOCK EMAIL] ServerCron token para {destinatario}: {token}")
            return True
        if not HAS_OUTLOOK:
            logger_cron.error("win32com não disponível. E-mail de token não enviado.")
            return False
        pythoncom.CoInitialize()
        try:
            outlook = win32.Dispatch("outlook.application")
            mail = outlook.CreateItem(0)
            mail.To = destinatario
            mail.Subject = "Seu token - ServerCron | ServerCRON"
            mail.HTMLBody = f"""
                <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
                    <h2 style="color: #242424; border-bottom: 2px solid #d3ad65; padding-bottom: 10px;">ServerCron — automation stack</h2>
                    <p>Olá,</p>
                    <p>Seu código de autenticação para o dashboard do ServerCron é:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <h1 style="color: #242424; background-color: #f3f4f6; padding: 15px 30px; display: inline-block; border-radius: 8px; letter-spacing: 8px; margin: 0; font-size: 32px; border: 1px solid #ccc;">{token}</h1>
                    </div>
                    <p style="color: #d32f2f; font-size: 13px;"><b>Atenção:</b> Este código expira em 15 minutos. Não o compartilhe.</p>
                    <p>Atenciosamente,<br><b>ServerCRON</b></p>
                </div>
            """
            mail.Send()
            logger_cron.info(f"[AUTH] Token enviado para {destinatario}")
            return True
        except Exception:
            logger_cron.exception("[AUTH] Erro ao enviar e-mail de token")
            return False
        finally:
            with suppress(Exception):
                pythoncom.CoUninitialize()


def _cron_require_admin():
    if session.get("role") != "admin":
        return jsonify({
            "status": "error",
            "message": "Acesso negado (somente administrador).",
        }), 403
    return None


def _effective_http_port_for_links() -> int:
    """Port shown in e-mails/URLs: unified portal uses SERVERCRON_UNIFIED_PORT, standalone uses PORT."""
    if CRON_URL_PREFIX:
        try:
            return int(os.environ.get("SERVERCRON_UNIFIED_PORT", "5001").strip() or "5001")
        except ValueError:
            return 5001
    return CRON_STANDALONE_PORT


# ==============================================================
# FLASK API
# ==============================================================

_app = Flask(__name__, template_folder=str(PANEL_HTML_DIR), static_folder=str(PANEL_HTML_DIR))
_app.secret_key = CRON_SECRET_KEY
_app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
_app.config["SESSION_COOKIE_HTTPONLY"] = True
_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
_app.config["SESSION_REFRESH_EACH_REQUEST"] = True
# Must differ from app.config SESSION_COOKIE_NAME: same browser can keep Uploaders + Cron sessions (any mode).
_app.config["SESSION_COOKIE_NAME"] = "server_cron_session"
if CRON_URL_PREFIX:
    # Unified single-port: scope cookie to /cron so the root app does not receive it as the same "session" bucket.
    _p = CRON_URL_PREFIX if CRON_URL_PREFIX.startswith("/") else f"/{CRON_URL_PREFIX}"
    _app.config["SESSION_COOKIE_PATH"] = _p.rstrip("/") or "/"
# Duo ports: default SESSION_COOKIE_PATH (/) is fine; cookie name already differs from Uploaders.
CORS(_app, supports_credentials=True)
_reload_last: float = 0.0
_reload_lock = threading.Lock()


def _manual_bq_resync_shared() -> tuple[dict, int]:
    """Recarrega jobs do BQ; `recarregar_agendamentos` ja invalida caches de permissoes. Cooldown global 3 min."""
    global _reload_last
    now = time.time()
    with _reload_lock:
        wait = RELOAD_COOLDOWN_SECONDS - (now - _reload_last)
        if wait > 0:
            return ({"status": "cooldown", "wait_seconds": int(wait)}, 429)
        _reload_last = now
    scripts = recarregar_agendamentos()
    return (
        {
            "status": "success",
            "script_count": len(scripts),
            "next_hot_reload_iso": _next_hot_reload_iso(),
        },
        200,
    )


@app.route("/api/bq_sync_status", methods=["GET"])
def api_bq_sync_status():
    if "username" not in session:
        return jsonify({"ok": False, "message": "Sessão expirada."}), 401
    return jsonify(
        {
            "ok": True,
            "interval_minutes": RELOAD_INTERVAL_MINUTES,
            "next_hot_reload_iso": _next_hot_reload_iso(),
            "cooldown_seconds": RELOAD_COOLDOWN_SECONDS,
        }
    )


@app.route("/api/admin/bq_resync", methods=["POST"])
def api_admin_bq_resync():
    if "username" not in session:
        return jsonify({"status": "error", "message": "Sessão expirada."}), 401
    if not PermissionService.is_admin_user(session["username"]):
        return jsonify({"status": "error", "message": "Apenas administradores."}), 403
    if not _csrf_valid():
        return jsonify(
            {"status": "error", "message": "Token CSRF inválido. Recarregue a página."}
        ), 403
    data, code = _manual_bq_resync_shared()
    return jsonify(data), code


@_app.before_request
def _cron_auth_gate():
    p = request.path
    if p in ("/", "/favicon.ico"):
        return None
    public_api = frozenset({
        "/api/auth/status",
        "/api/auth/request-token",
        "/api/auth/verify",
        "/api/auth/logout",
    })
    if p in public_api:
        return None
    if p.startswith("/api/") and "username" not in session:
        return jsonify({"error": "unauthorized", "message": "Login required."}), 401
    return None


@_app.before_request
def _cron_session_refresh_permanent() -> None:
    if "username" in session:
        session.permanent = True
        session.modified = True


@_app.after_request
def _cron_security_headers(response: Response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@_app.route("/api/auth/status")
def api_auth_status():
    if "username" not in session:
        return jsonify({"logged_in": False, "username": None, "role": None})
    return jsonify({
        "logged_in": True,
        "username": session["username"],
        "role": session.get("role", "viewer"),
    })


@_app.route("/api/auth/request-token", methods=["POST"])
def api_auth_request_token():
    logger_cron.info("[AUTH] request-token: POST recebido | IP=%s", _get_client_ip())
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    if not username:
        logger_cron.warning("[AUTH] request-token: rejeitado | motivo=username vazio")
        return jsonify({"status": "error", "message": "Informe o usuário."}), 400

    reg = _get_access_registry()
    if username not in reg:
        logger_cron.warning(
            "[AUTH] request-token: NEGADO | user=%s | nao consta na folha USERS | "
            "registro atual tem %d usuario(s)",
            username,
            len(reg),
        )
        return jsonify({"status": "error", "message": "Usuário não autorizado a solicitar token."}), 403

    now = time.time()
    last = _cron_token_request_at.get(username, 0.0)
    if now - last < TOKEN_REQUEST_COOLDOWN_SEC:
        rem = int(TOKEN_REQUEST_COOLDOWN_SEC - (now - last)) + 1
        m, s = rem // 60, rem % 60
        return jsonify(
            {
                "status": "error",
                "message": f"Aguarde {m}m{s:02d}s entre um pedido de token e outro (mínimo 3 minutos).",
            }
        ), 429

    logger_cron.info("[AUTH] request-token: aceito | user=%s | role=%s", username, reg[username])

    token = "".join(random.choices(string.digits, k=6))
    _cron_auth_tokens[username] = {
        "token": token,
        "expires": datetime.now() + EMAIL_OTP_VALID,
    }
    # Evita duplo clique enquanto o Outlook envia (o envio corre em thread separada).
    _cron_token_request_at[username] = now
    destinatario = f"{username}{DOMAIN}"

    def _cron_token_mail_worker() -> None:
        if _CronEmailService.send_token_email(destinatario, token):
            logger_cron.info(
                "[AUTH] request-token: e-mail de token enviado | user=%s | dest=%s",
                username,
                destinatario,
            )
        else:
            _cron_auth_tokens.pop(username, None)
            _cron_token_request_at.pop(username, None)
            logger_cron.error("[AUTH] request-token: falha ao enviar e-mail Outlook | user=%s", username)

    threading.Thread(target=_cron_token_mail_worker, daemon=True, name="cron-token-mail").start()
    return jsonify(
        {
            "status": "success",
            "message": (
                "Pedido aceito. O envio pelo Outlook pode levar alguns segundos — verifique o e-mail corporativo."
            ),
        }
    )


@_app.route("/api/auth/verify", methods=["POST"])
def api_auth_verify():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    token_in = (data.get("token") or "").strip()
    reg = _get_access_registry()
    if username not in reg:
        logger_cron.warning(
            "[AUTH] verify: NEGADO | user=%s | nao cadastrado na folha USERS",
            username,
        )
        return jsonify({"status": "error", "message": "Usuário não autorizado."}), 403
    if username not in _cron_auth_tokens:
        logger_cron.warning("[AUTH] verify: rejeitado | user=%s | nenhum token pendente", username)
        return jsonify({"status": "error", "message": "Solicite um token primeiro."}), 400
    dados = _cron_auth_tokens[username]
    if datetime.now() > dados["expires"]:
        logger_cron.warning("[AUTH] verify: rejeitado | user=%s | token expirado", username)
        return jsonify({"status": "error", "message": "Token expirado."}), 400
    if token_in != dados["token"]:
        logger_cron.warning("[AUTH] verify: rejeitado | user=%s | codigo invalido", username)
        return jsonify({"status": "error", "message": "Token inválido."}), 400
    _cron_auth_tokens.pop(username, None)
    session["username"] = username
    session["role"] = "admin" if reg[username] == "admin" else "viewer"
    session.permanent = True
    session["login_at"] = datetime.now().isoformat(timespec="seconds")
    session.modified = True
    logger_cron.info("[AUTH] verify: sessao aberta | user=%s | role=%s", username, session["role"])
    return jsonify({
        "status": "success",
        "username": username,
        "role": session["role"],
    })


@_app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    u = session.get("username")
    if isinstance(u, str):
        u_l = u.strip().lower()
        _cron_auth_tokens.pop(u_l, None)
        _cron_token_request_at.pop(u_l, None)
    session.clear()
    return jsonify({"status": "success"})


def _cron_access_urls() -> dict[str, str]:
    """URLs for sharing: LAN (mesma rede) e localhost (apenas na máquina do Server)."""
    lan_ip = _get_local_ip()
    p = _effective_http_port_for_links()
    if not CRON_URL_PREFIX:
        base = "/"
    else:
        seg = CRON_URL_PREFIX.strip().lstrip("/")
        base = f"/{seg}/"
    return {
        "access_url_lan": f"http://{lan_ip}:{p}{base}",
        "access_url_local": f"http://127.0.0.1:{p}{base}",
        "cron_url_prefix": CRON_URL_PREFIX or None,
    }


@_app.route("/api/share_outlook", methods=["POST"])
def api_share_outlook():
    """Abre o Outlook com convite HTML (link do ServerCron). Apenas admin. Destinatários preenchidos no próprio Outlook."""
    denied = _cron_require_admin()
    if denied:
        return denied
    if not HAS_OUTLOOK:
        return jsonify({"status": "error", "message": "Outlook COM não disponível neste Server."}), 500

    recipients = PermissionService.get_all_recipients()
    urls = _shared_portal_urls()
    html_body = _build_shared_invite_html(
        uploaders_url=urls["uploaders_url_lan"],
        cron_url=urls["cron_url_lan"],
    )

    def _open_outlook() -> None:
        pythoncom.CoInitialize()
        try:
            outlook = win32.Dispatch("outlook.application")
            mail = outlook.CreateItem(0)
            mail.Subject = "ServerCRON | Server"
            mail.HTMLBody = html_body
            mail.To = recipients.replace(",", ";")
            mail.Display()
            logger_cron.info("[SHARE] Janela do Outlook aberta para compartilhamento ServerCron.")
        except Exception:
            logger_cron.exception("[SHARE] Erro ao abrir Outlook para compartilhamento")
        finally:
            with suppress(Exception):
                pythoncom.CoUninitialize()

    threading.Thread(target=_open_outlook, daemon=True, name="share-outlook-cron").start()
    logger_cron.info(f"[SHARE] Convite Outlook aberto por {session.get('username')}")
    return jsonify({
        "status": "success",
        "message": "Outlook aberto com e-mail de compartilhamento.",
        "uploaders_url_lan": urls["uploaders_url_lan"],
        "cron_url_lan": urls["cron_url_lan"],
    })


# -- Dashboard Route -----------------------------------------

@_app.route("/")
def root():
    # Cron is the default landing page; Uploaders is available from the Uploaders tab.
    for _cron_tpl in ("ServerCRON.html", "Server.html"):
        if _resolve_panel_file(_cron_tpl) is not None:
            return render_template(_cron_tpl, portal_view="cron")
    if _DASHBOARD_FILE.exists():
        return send_file(str(_DASHBOARD_FILE), mimetype="text/html")
    return jsonify({"status": "ok", "mode": "backend-only", "docs": f"http://{HOST}:{CRON_STANDALONE_PORT}/api/status"})

# -- API Routes ----------------------------------------------

@_app.route("/api/status")
def api_status():
    now = time.time()
    with _running_lock:
        running = []
        for info in _running.values():
            metrics = _get_process_metrics(info["pid"])
            running.append({
                "pid": info["pid"], "python_name": info["python_name"], "area_name": info["area_name"],
                "running_time_seconds": int(now - info["start_time"]),
                "trigger_reason": info.get("trigger_reason", "scheduled"), "priority": info.get("priority", 2),
                "rss_mb": metrics["rss_mb"], "cpu_percent": metrics["cpu_percent"],
                "num_children": metrics["num_children"],
            })
    running.sort(key=lambda x: x["running_time_seconds"], reverse=True)

    q_snap = sorted(list(_task_queue.queue))
    queued = [
        {
            "python_name": task["python_name"], "area_name": task["area_name"], "priority": task["priority"],
            "tier": task["tier"], "scheduled_ts": sched_ts, "position": i + 1, "waiting_seconds": int(now - enq_ts),
            "trigger_reason": task.get("trigger_reason", "scheduled"),
        }
        for i, (_, sched_ts, enq_ts, task) in enumerate(q_snap)
    ]

    vm = psutil.virtual_memory()
    return jsonify({
        "running_processes": running, "queued_processes": queued,
        "running_count": len(running), "queued_count": len(queued),
        "max_concurrent": MAX_PROCESSOS_SIMULTANEOS,
        "next_hot_reload_iso": _next_hot_reload_iso(),
        "server_metrics": {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": vm.percent,
            "ram_used_gb": round(vm.used / (1024 ** 3), 1),
            "ram_total_gb": round(vm.total / (1024 ** 3), 1),
        },
    })

@_app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok", "uptime_seconds": round(time.time() - _SERVER_START_TIME, 1),
        "running": len(_running), "queued": _task_queue.qsize(),
    })

@_app.route("/api/server/info")
def api_server_info():
    vm = psutil.virtual_memory()
    urls = _cron_access_urls()
    p = _effective_http_port_for_links()
    duo = _env_truthy("SERVERCRON_DUO_PORTS")
    up_port = int((os.environ.get("SERVERCRON_UP_PORT") or "5001").strip() or 5001)
    uploaders_base = "" if not duo else f"http://{_get_local_ip()}:{up_port}"
    return jsonify({
        "version": _SERVER_VERSION,
        "unified_cron_mounted": bool(CRON_URL_PREFIX),
        "servercron_duo_ports": duo,
        "uploaders_base_url": uploaders_base,
        "http_link_port": p,
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "uptime_seconds": round(time.time() - _SERVER_START_TIME, 1),
        "timezone": CRON_TZ_NAME,
        "max_concurrent": MAX_PROCESSOS_SIMULTANEOS,
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_total_gb": round(vm.total / (1024 ** 3), 1),
        "cron_data_dir": str(PATH_SERVER_APP),
        "cron_sqlite": str(PATH_CRON_SQLITE),
        "dir_automacoes": str(DIRETORIO_AUTOMACOES),
        "dir_automacoes_exists": DIRETORIO_AUTOMACOES.exists(),
        "reload_interval_min": RELOAD_INTERVAL_MINUTES,
        "default_timeout_sec": DEFAULT_TIMEOUT_SECONDS,
        "max_cpu_percent": MAX_CPU_PERCENT,
        "max_ram_percent": MAX_RAM_PERCENT,
        **urls,
    })

def _annotate(scripts: list[dict]) -> list[dict]:
    with _running_lock:
        running_names = {d["python_name"] for d in _running.values()}
    queued_names = {task["python_name"] for _, _, _, task in list(_task_queue.queue)}
    for s in scripts:
        s["is_running"] = s["python_name"] in running_names
        s["is_queued"]  = s["python_name"] in queued_names
    return scripts

@_app.route("/api/scripts")
def api_scripts():
    local_files = buscar_arquivos_locais()
    return jsonify(_annotate(_get_all_scripts(local_files)))

@_app.route("/api/scripts/<python_name>")
def api_script_detail(python_name: str):
    local_files = buscar_arquivos_locais()
    name = python_name.lower().strip()
    all_scripts = _annotate(_get_all_scripts(local_files))
    found = next((s for s in all_scripts if s["python_name"] == name), None)
    if not found:
        return jsonify({"status": "error", "message": f"'{name}' não encontrado."}), 404
    # Attach recent history for this script
    with _history_lock:
        found["recent_history"] = [
            h for h in _execution_history
            if h["python_name"] == name and h.get("status") in ("success", "error", "no_data")
        ][:20]
    return jsonify(found)

@_app.route("/api/areas")
def api_areas():
    local_files = buscar_arquivos_locais()
    areas: dict = {}
    for s in _annotate(_get_all_scripts(local_files)):
        areas.setdefault(s["area_name"], []).append(s)
    # Sort scripts within each area alphabetically
    for area_name in areas:
        areas[area_name].sort(key=lambda s: s["python_name"])
    return jsonify(areas)


@_app.route("/api/areas/summary")
def api_areas_summary():
    """Counts per area from AUTOMACOES sheet (fast; no disk walk)."""
    counts: dict[str, int] = {}
    for r in _ler_registro_planilha():
        a = r["area_name"]
        counts[a] = counts.get(a, 0) + 1
    areas = [{"name": k, "count": counts[k]} for k in sorted(counts.keys())]
    return jsonify({"areas": areas})


@_app.route("/api/scripts/by-area")
def api_scripts_by_area():
    """Scripts for one area only (smaller payload than /api/areas)."""
    area = (request.args.get("area") or "").strip().lower()
    if not area:
        return jsonify({"status": "error", "message": "Query parameter 'area' is required."}), 400
    local_files = buscar_arquivos_locais()
    scripts = [
        s for s in _annotate(_get_all_scripts(local_files))
        if s["area_name"] == area
    ]
    scripts.sort(key=lambda x: x["python_name"])
    return jsonify(scripts)


@_app.route("/api/scripts/search")
def api_scripts_search():
    """Busca scripts por nome ou área em todo o cadastro (usa cache de disco + BQ)."""
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify([])
    local_files = buscar_arquivos_locais()
    all_scripts = _annotate(_get_all_scripts(local_files))
    out = [
        s for s in all_scripts
        if q in s["python_name"] or q in s.get("area_name", "")
    ]
    out.sort(key=lambda x: (x["area_name"], x["python_name"]))
    return jsonify(out[:500])


@_app.route("/api/run/<python_name>", methods=["POST"])
def api_run(python_name: str):
    denied = _cron_require_admin()
    if denied:
        return denied
    local_files = buscar_arquivos_locais()
    name = python_name.lower().strip()
    path = local_files.get(name)
    if not path:
        return jsonify({"status": "error", "message": f"'{name}' não encontrado no disco."}), 404

    all_scripts = {s["python_name"]: s for s in _get_all_scripts(local_files)}
    info = all_scripts.get(name, {})
    ok = enqueue_script(
        python_name=name, path=str(path), area_name=info.get("area_name", "manual"),
        priority=info.get("priority", 2), scheduled_ts=time.time(), trigger_reason="manual",
    )
    if ok:
        return jsonify({"status": "success", "message": f"'{name}' enfileirado."})
    return jsonify({"status": "duplicate", "message": f"'{name}' já rodando ou na fila."})

@_app.route("/api/kill/<int:pid>", methods=["POST"])
def api_kill(pid: int):
    denied = _cron_require_admin()
    if denied:
        return denied
    if kill_process(pid):
        return jsonify({"status": "success", "message": f"PID {pid} encerrado."})
    return jsonify({"status": "error", "message": "PID não encontrado."}), 404

@_app.route("/api/kill/by-name/<python_name>", methods=["POST"])
def api_kill_by_name(python_name: str):
    denied = _cron_require_admin()
    if denied:
        return denied
    killed = kill_by_name(python_name)
    if killed:
        return jsonify({"status": "success", "killed_pids": killed, "message": f"'{python_name}' encerrado ({len(killed)} processos)."})
    return jsonify({"status": "error", "message": f"'{python_name}' não está rodando."}), 404

@_app.route("/api/reload", methods=["POST"])
def api_reload():
    denied = _cron_require_admin()
    if denied:
        return denied
    data, code = _manual_bq_resync_shared()
    return jsonify(data), code

@_app.route("/api/jobs")
def api_jobs():
    return jsonify(get_jobs_info())

@_app.route("/api/history")
def api_history():
    limit = request.args.get("limit", 100, type=int)
    script_filter = request.args.get("script", "").lower().strip()
    area_filter = request.args.get("area", "").lower().strip()
    status_filter = request.args.get("status", "").lower().strip()

    with _history_lock:
        entries = list(_execution_history)

    if script_filter:
        entries = [e for e in entries if script_filter in e["python_name"]]
    if area_filter:
        entries = [e for e in entries if area_filter in e["area_name"]]
    if status_filter:
        entries = [e for e in entries if e["status"] == status_filter]

    return jsonify({
        "history": entries[:limit],
        "total": len(entries),
        "max_stored": _MAX_HISTORY,
    })


def _aggregate_history_stats(entries: list[dict]) -> dict:
    """SUCCESS vs ERROR shares for the dashboard; NO_DATA não entra nessa taxa. killed excluído."""
    counts = {"success": 0, "error": 0}
    by_script: dict[str, dict[str, int]] = {}
    for e in entries:
        st = e.get("status", "")
        if st == "killed":
            continue
        pn = e.get("python_name") or "?"
        if pn not in by_script:
            by_script[pn] = {"success": 0, "error": 0, "total": 0}
        by_script[pn]["total"] += 1
        if st == "success":
            counts["success"] += 1
            by_script[pn]["success"] += 1
        elif st == "error":
            counts["error"] += 1
            by_script[pn]["error"] += 1
    total = counts["success"] + counts["error"]
    pct = {k: round(100.0 * counts[k] / total, 1) if total else 0.0 for k in ("success", "error")}
    return {"total": total, "counts": counts, "percent": pct, "by_script": by_script}


@_app.route("/api/history/stats")
def api_history_stats():
    """Aggregates for dashboard: today vs last 7 calendar days (incl. today). Optional `script` substring filter."""
    try:
        script_filter = request.args.get("script", "").lower().strip()
        with _history_lock:
            entries = list(_execution_history)
        if script_filter:
            entries = [e for e in entries if script_filter in (e.get("python_name") or "").lower()]

        today = datetime.now(TZ).date()
        week_start = today - timedelta(days=6)

        def in_today(e: dict) -> bool:
            d = _history_entry_start_date(e)
            return d == today if d else False

        def in_week(e: dict) -> bool:
            d = _history_entry_start_date(e)
            return d is not None and week_start <= d <= today

        today_entries = [e for e in entries if in_today(e)]
        week_entries = [e for e in entries if in_week(e)]

        return jsonify({
            "today": _aggregate_history_stats(today_entries),
            "last_7_days": _aggregate_history_stats(week_entries),
            "timezone": CRON_TZ_NAME,
            "script_filter": script_filter or None,
            "max_stored": _MAX_HISTORY,
            "note": "Stats use only executions still in the rolling history buffer (see max_stored).",
        })
    except Exception:
        logger_cron.exception("[API] /api/history/stats failed")
        return jsonify({"status": "error", "message": "stats aggregation failed"}), 500


@_app.route("/api/pending")
def api_pending():
    """Scripts that should have run today but haven't yet."""
    today_str = _now_br().strftime("%Y-%m-%d")
    pending = _detect_pending_scripts()
    # Strip internal 'path' key from API response
    sanitized = [{k: v for k, v in p.items() if k != "path"} for p in pending]
    return jsonify({"pending": sanitized, "date": today_str, "total": len(sanitized)})


if __name__ == "__main__":
    try:
        from waitress import serve as waitress_serve
    except ImportError as e:
        print("Instale waitress:  python -m pip install waitress", file=sys.stderr)
        raise SystemExit(1) from e

    host = "0.0.0.0"
    my_ip = _get_local_ip()

    if _env_truthy("SERVERCRON_DUO_PORTS"):
        up_port = int((os.environ.get("SERVERCRON_UP_PORT") or os.environ.get("PORT") or "5001").strip() or 5001)
        cr_port = int((os.environ.get("SERVERCRON_CRON_PORT") or "5002").strip() or 5002)
        os.environ["SERVERCRON_UNIFIED_PORTAL"] = "0"
        logger.info("=" * 70)
        logger.info(
            "SERVERCRON DUO PORTS — Uploaders :%s | ServerCron :%s (HTML: SERVERCRON_PANEL_DIR if set)",
            up_port,
            cr_port,
        )
        logger.info("  Uploaders  -> http://%s:%s/", my_ip, up_port)
        logger.info("  ServerCron -> http://%s:%s/", my_ip, cr_port)
        logger.info("=" * 70)
        _send_startup_access_invite(
            uploaders_url=f"http://{my_ip}:{up_port}/",
            cron_url=f"http://{my_ip}:{cr_port}/",
        )
        iniciar_scheduler()
        t_out = threading.Thread(target=OutlookMonitorService.start, daemon=True, name="outlook-monitor")
        t_out.start()

        def _run_cron_http() -> None:
            waitress_serve(_app, host=host, port=cr_port, threads=6, channel_timeout=300)

        threading.Thread(target=_run_cron_http, daemon=True, name="waitress-cron").start()
        if os.environ.get("SERVERCRON_OPEN_BROWSER", "1") != "0" and os.environ.get("WERKZEUG_RUN_MAIN", "") != "true":
            threading.Timer(0.0, lambda: webbrowser.open(f"http://{my_ip}:{up_port}/")).start()
            threading.Timer(0.45, lambda: webbrowser.open(f"http://{my_ip}:{cr_port}/")).start()
        try:
            waitress_serve(app, host=host, port=up_port, threads=10, channel_timeout=300)
        except OSError as e:
            logger.error("Falha ao abrir a porta %s: %s", up_port, e)
            raise
    else:
        from werkzeug.middleware.dispatcher import DispatcherMiddleware

        # Uma sessão no mesmo origin: login no Cron ou no Uploaders vale para o iframe de envio.
        _portal_secret = SECRET_KEY
        app.secret_key = _portal_secret
        _app.secret_key = _portal_secret
        app.config["SESSION_COOKIE_NAME"] = "servercron_portal_session"
        _app.config["SESSION_COOKIE_NAME"] = "servercron_portal_session"
        app.config["SESSION_COOKIE_PATH"] = "/"
        _app.config["SESSION_COOKIE_PATH"] = "/"

        unified = int((os.environ.get("SERVERCRON_UNIFIED_PORT", str(PORT)) or str(PORT)).strip())
        application = DispatcherMiddleware(app, {"/cron": _app})
        os.environ["SERVERCRON_UNIFIED_PORTAL"] = "1"

        logger.info("=" * 70)
        logger.info("SERVERCRON UNIFIED — SERVERUPLOADERS + SERVERCRON (one .py, one port)")
        logger.info("  Uploaders  -> http://%s:%s/", my_ip, unified)
        logger.info("  Cron        -> http://%s:%s/cron/", my_ip, unified)
        logger.info("  (Unified session: servercron_portal_session on / — send flow embedded in Cron.)")
        logger.info("=" * 70)
        _send_startup_access_invite(
            uploaders_url=f"http://{my_ip}:{unified}/",
            cron_url=f"http://{my_ip}:{unified}/cron/",
        )

        iniciar_scheduler()
        t_out2 = threading.Thread(target=OutlookMonitorService.start, daemon=True, name="outlook-monitor")
        t_out2.start()

        if os.environ.get("SERVERCRON_OPEN_BROWSER", "1") != "0" and os.environ.get("WERKZEUG_RUN_MAIN", "") != "true":
            _start_browser(f"http://{my_ip}:{unified}/")
        try:
            waitress_serve(
                application,
                host=host,
                port=unified,
                threads=10,
                channel_timeout=300,
            )
        except OSError as e:
            logger.error("Falha ao abrir a porta %s: %s", unified, e)
            raise
