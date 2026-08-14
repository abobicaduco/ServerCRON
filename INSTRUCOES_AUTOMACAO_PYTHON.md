# Instrucoes para construir automacoes Python (empresas)

Use este ficheiro sempre que um agent for criar ou alterar um script Python de automacao
para empresa (RPA, web, pastas, email, Excel, etc.), inclusive para o ServerCRON.

O utilizador descreve **o que** a automacao deve fazer. O agent segue **estas regras**
ao escrever o codigo.

---

## 1. Objetivo do script

- Um ficheiro `.py` por automacao, focado numa tarefa.
- Codigo claro, direto, sem over-engineering.
- Sem hardcode de caminhos de utilizador (`C:\Users\...`, `/Users/nome`).

---

## 2. Idioma, comentarios e emojis (obrigatorio)

### Sem emojis (nunca)

- **Nunca** usar emojis em: codigo, comentarios, docstrings, `print`, logs, nomes
  de ficheiro, commits, README da automacao, mensagens de erro.
- Nao usar simbolos decorativos (checkmarks unicode, setas ornamentadas, etc.).

### Comentarios e texto em portugues (pt-BR)

- **Todos** os comentarios em portugues do Brasil.
- Docstrings (`"""..."""`) em portugues do Brasil.
- Mensagens de `print` / log para o operador em portugues do Brasil
  (salvo se a empresa exigir outro idioma na UI externa).
- Nomes de funcoes/variaveis: `snake_case` em ingles curto **ou** portugues claro
  (`baixar_anexos`, `pasta_entrada`). Preferir portugues quando o dominio da empresa
  for em PT. Evitar misturar os dois no mesmo identificador (`get_pasta` ruim).
- Evitar travessao tipografico (`—` / `–`) em comentarios e docs; usar virgula,
  ponto, dois pontos ou hifen simples `-`.

```python
# Bom: comentario em pt-BR, sem emoji
# Baixa os PDFs da pasta de entrada e move para processados.

# Ruim:
# Download files from inbox
# Baixa os PDFs
```

---

## 3. Organizacao do ficheiro Python

Ordem fixa no `.py` (de cima para baixo). **Nao misturar**.

1. Shebang opcional / `# -*- coding: utf-8 -*-`
2. Docstring do modulo (1 a 3 linhas: o que a automacao faz)
3. `from __future__ import annotations` (se usar type hints modernas)
4. **Bloco 1 - imports da stdlib** (apenas biblioteca padrao; nada de playwright/openpyxl aqui)
5. **Bloco 2 - todas as variaveis / constantes**
   - `DEPENDENCIAS`, `POS_INSTALL_CMDS`, `HEADLESS`, timeouts, URLs, pastas, `STEM_LOWER`, `LOG_DIR`, etc.
6. Funcoes auxiliares (incluindo `garantir_dependencias` e log)
7. `main() -> int` (fluxo principal; devolve 0, 1 ou 2)
8. Bloco `if __name__ == "__main__":`: log -> `garantir_dependencias()` -> `main()` -> `sys.exit(...)`

**Importante sobre bibliotecas de terceiros (Playwright, openpyxl, etc.):**

- No topo ficam **apenas** imports da **stdlib** (`sys`, `subprocess`, `importlib`, `pathlib`, ...).
- Pacotes de terceiros **nao** devem ser importados no topo se ainda puderem nao estar instalados.
- Lista-os em `DEPENDENCIAS` (variavel do topo).
- Em `__main__` (ou no inicio de `main`): chamar `garantir_dependencias()` **antes** de usar esses pacotes.
- So depois disso importar terceiros (no inicio de `main` / funcoes que precisam).

Assim o script faz o `pip install` sozinho e o operador nao precisa de `pip install -r requirements.txt`.

### Bloco 2 obrigatorio: stem do ficheiro + pasta de logs

Todo script deve, **nas variaveis do topo** (nao dentro de funcoes), definir o nome
do proprio `.py` em execucao e a pasta onde o log da corrida sera gravado:

| Variavel | Como obter | Para que serve |
|----------|------------|----------------|
| `_SCRIPT` | `Path(__file__).resolve()` | Path absoluto do `.py` que esta a correr |
| `STEM_LOWER` | `_SCRIPT.stem.lower()` | Nome do ficheiro sem extensao, em minusculas |
| `LOG_DIR` | pasta `logs` (criar com `mkdir`) | Onde gravar o `.log` desta execucao |
| Nome do log | `{STEM_LOWER}_{YYYYMMDD_HHMMSS}.log` | Um ficheiro por corrida |

Exemplo: se o ficheiro for `scrape_quotes_exemplo.py`, o log fica:

```text
.../logs/.../scrape_quotes_exemplo_20260807_091735.log
```

`STEM_LOWER` **puxa sempre o nome real do ficheiro** (`Path(__file__).stem.lower()`).
Nunca hardcodar o nome do script numa string (`"scrape_quotes_exemplo"`).
Se renomear o `.py`, o nome do log acompanha sozinho.

### Constantes e paths no topo (modelo do bloco 2)

```python
# ---------------------------------------------------------------------------
# Configuracao (todas as variaveis juntas, depois dos imports)
# ---------------------------------------------------------------------------

TZ = ZoneInfo("America/Sao_Paulo")

# Identidade do script em execucao (nome do .py -> log)
_SCRIPT = Path(__file__).resolve()
STEM_LOWER = _SCRIPT.stem.lower()
BASE_DIR = _SCRIPT.parent

# Area ServerCRON (pasta relativa sob automacoes/)
_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

# Logs: sempre criar a pasta; ficheiro = STEM_LOWER + timestamp
LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

# Pastas de negocio
PASTA_ENTRADA = Path.home() / "Downloads" / "Entrada"
PASTA_SAIDA = Path.home() / "Documents" / "Automacoes" / STEM_LOWER / "saida"
PASTA_ERROS = Path.home() / "Documents" / "Automacoes" / STEM_LOWER / "erros"

# Opcoes de execucao / web
HEADLESS = False
TIMEOUT_MS = 30_000
VIEWPORT = {"width": 1920, "height": 1080}

# Identidade na planilha registro_automacoes.xlsx (ver secao 13)
PYTHON_NAME = STEM_LOWER  # = coluna python_name / nome_automacao
REGISTRO_XLSX = next(
    (
        p / "registro_automacoes.xlsx"
        for p in _SCRIPT.parents
        if (p / "registro_automacoes.xlsx").is_file()
    ),
    Path.home() / "Desktop" / "ServerCRON" / "registro_automacoes.xlsx",
)
EMAIL_DEV = "seu_email_dev@empresa.com"  # so voce recebe em retcode 1 ou 2
ENVIAR_EMAIL = True  # False para desligar notificacoes nesta automacao

# Bibliotecas de terceiros: (nome_do_import, nome_do_pacote_pip)
# O script instala sozinho o que faltar (ver garantir_dependencias).
DEPENDENCIAS: list[tuple[str, str]] = [
    ("playwright", "playwright"),
]
# Comandos extra apos pip (ex.: browsers do Playwright). Lista vazia se nao precisar.
POS_INSTALL_CMDS: list[list[str]] = [
    [sys.executable, "-m", "playwright", "install", "chrome"],
]
```

Ao iniciar a corrida:

```python
LOG_DIR.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
caminho_log = LOG_DIR / f"{STEM_LOWER}_{stamp}.log"
```

### Auto-install de bibliotecas (obrigatorio)

Todo `.py` que use pacotes fora da stdlib deve declarar `DEPENDENCIAS` no topo e
chamar `garantir_dependencias()` **antes** de importar / usar esses pacotes.

Regras:

- So instala o que **falta** (tenta `importlib.import_module`; se der `ImportError`, faz pip).
- Usar sempre `sys.executable -m pip install ...` (o mesmo Python que esta a correr o script).
- `check=True` no `subprocess.run`; se o pip falhar -> retcode `1`.
- Nao pedir ao utilizador para correr `pip install -r requirements.txt` manualmente.
- Playwright: alem do pip, na **primeira** instalacao garantir o Chrome com
  `python -m playwright install chrome` (via `POS_INSTALL_CMDS`, so quando o pip
  acabou de instalar algo).
- Nao logar tokens; pip pode ser verboso - registar `INFO:` do que esta a instalar.

```python
import importlib
import subprocess
import sys


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
```

Ordem no `__main__`:

```python
if __name__ == "__main__":
    iniciar_log_execucao()
    try:
        try:
            garantir_dependencias()
            code = main()  # main (ou funcoes) importa playwright/openpyxl so depois disto
        except Exception as exc:
            ...
        sys.exit(code)
    finally:
        fechar_log_execucao()
```

Dentro de `main` / helpers web, importar terceiros **depois** do ensure:

```python
def coletar_citacoes() -> list[dict[str, str]]:
    from playwright.sync_api import sync_playwright  # import local apos garantir_dependencias
    ...
```

### Funcoes

- Funcoes curtas; nomes que digam o que fazem (`listar_pdfs`, `enviar_relatorio`).
- `main()` so orquestra: chama funcoes, decide o retcode.
- Nao meter Playwright + Excel + email tudo numa unica funcao gigante.
- Preferir `def foo() -> int | Path | None:` com type hints simples quando ajudar.
- Evitar classes salvo se o fluxo for claramente stateful (browser session longa, etc.).

### Separadores de secao (opcional, sem emoji)

```python
# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
```

---

## 4. Padroes de codificacao Python (obrigatorio para agents)

Estas regras valem para **qualquer** `.py` que o agent construir para o utilizador.

### Estilo geral

- Python 3.10+ (salvo a empresa exigir outra versao).
- Seguir espirito PEP 8: indentacao 4 espacos, linhas ~100 caracteres (nao obsessao).
- Uma instrucao por linha; evitar one-liners densos.
- Preferir legibilidade a "cleverness".
- Nao adicionar abstracoes, factories, plugins ou configs YAML sem pedido.
- Nao deixar codigo morto, imports nao usados, nem `print` de debug esquecidos.
- Nao criar ficheiros extra (README, testes, utils) salvo o utilizador pedir.

### Nomes

| Tipo | Padrao | Exemplo |
|------|--------|---------|
| Modulo / ficheiro | `snake_case.py` | `baixar_notas_fiscais.py` |
| Funcao / variavel | `snake_case` | `pasta_entrada`, `listar_pdfs` |
| Constante | `MAIUSCULAS_COM_UNDERSCORE` | `TIMEOUT_MS`, `PASTA_SAIDA` |
| Classe (se precisar) | `PascalCase` | `ClienteEmail` |
| Privado interno | prefixo `_` | `_montar_nome_arquivo` |

- Nomes descritivos; evitar `a`, `tmp2`, `data1` (exceto indices curtos `i`, `row`).
- Booleanos com prefixo claro: `tem_anexo`, `sucesso`, `is_ativo` (escolher um estilo e manter).

### Strings e formatacao

- Preferir **f-strings**: `f"Processado: {caminho.name}"`.
- Aspas: consistencia no ficheiro; em PT-BR com apostrofos no texto, preferir aspas duplas
  por fora: `"nao encontrado"`.
- Paths: sempre `pathlib.Path`, nunca concatenar com `+ "\\" +`.
- Abrir texto com encoding explicito: `encoding="utf-8"` (ou `utf-8-sig` se vier do Excel).

```python
# Bom
texto = caminho.read_text(encoding="utf-8")
with caminho.open("w", encoding="utf-8", newline="") as f:
    f.write(texto)

# Ruim
open(str(caminho)).read()
```

### Numeros magicos

- Timeouts, retentativas, tamanhos maximos: constantes no topo com nome claro.
- `30_000` ok para milhares; comentar unidade no nome (`TIMEOUT_MS`, `MAX_TENTATIVAS`).

### Controlo de fluxo

- Preferir **early return** (sair cedo) em vez de `if/else` profundos.
- Maximo ~3 niveis de indentacao; se passar, extrair funcao.
- `for` / `while` com `break`/`continue` claros; evitar flags confusas.
- Nao usar `else` em `try`/`for` salvo deixar o fluxo mais simples.

```python
# Bom
def processar(pasta: Path) -> int:
    ficheiros = listar(pasta)
    if not ficheiros:
        print("Nada para processar.")
        return 2
    for f in ficheiros:
        tratar(f)
    return 0
```

### Funcoes e assinaturas

- Argumentos com defaults **imutaveis** apenas (`None`, `""`, `0`, `()`). Nunca `def f(xs=[])`.
- Usar `None` + criar lista dentro se precisar de default mutavel.
- Type hints simples nos parametros e retorno quando ajudam (`Path`, `int`, `list[Path]`).
- Uma funcao = uma responsabilidade. Se o nome precisa de "e" (`baixar_e_enviar_e_gravar`), dividir.

```python
# Ruim
def f(itens=[]):
    itens.append(1)

# Bom
def f(itens: list[str] | None = None) -> list[str]:
    if itens is None:
        itens = []
    return itens
```

### Imports

- So o que e usado.
- Ordem: stdlib | terceiros | locais (com linha em branco entre blocos).
- Evitar `from modulo import *`.
- Evitar imports dentro de funcoes salvo ciclo circular ou dependencia opcional pesada
  (e comentar o porque em pt-BR).

### Ficheiros, pastas e CSV/Excel

- `Path.mkdir(parents=True, exist_ok=True)` antes de gravar.
- Verificar `path.exists()` / `is_file()` / `is_dir()` quando a ausencia for erro (retcode 1)
  ou "sem dados" (retcode 2), conforme o caso.
- Ao mover/renomear: `Path.replace` / `shutil.move` com destino sob `Path.home()`.
- CSV: `csv` ou pandas se ja for dependencia; sempre UTF-8; nao assumir locale Windows.
- Excel: `openpyxl` (ou o que a empresa padronizar); nao hardcodar linhas magicas sem constante.

### Datas e horas

- Para Brasil / ServerCRON: preferir `ZoneInfo("America/Sao_Paulo")`.
- Evitar `datetime.now()` ingenuo se o horario for regra de negocio; documentar o fuso.
- Formatos de log legiveis: `%Y-%m-%d %H:%M:%S` ou ISO.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

def agora_sp() -> datetime:
    """Data/hora atual em America/Sao_Paulo."""
    return datetime.now(TZ)
```

### Excecoes (detalhe)

- Nunca `except:` nem `except Exception: pass`.
- Capturar a excecao mais especifica possivel; `Exception` so na borda do `main`.
- Ao relancar ou envolver: manter a causa (`raise NovoErro(...) from exc`) se fizer sentido.
- Mensagem de erro com contexto: o que tentava fazer + path/URL (sem segredos).

### Concorrencia e subprocessos

- Automacoes ServerCRON: em geral **sincronas** e simples (um fluxo).
- Nao abrir threads/async sem pedido.
- Se chamar outro programa: `subprocess.run(..., check=False)` e tratar returncode;
  preferir lista de args, nunca `shell=True` com input do utilizador.

### Seguranca basica

- Sem senhas no codigo-fonte.
- Ler segredos de `os.environ` ou ficheiro fora do git sob `Path.home()`.
- Nao logar cookies, tokens, corpos de resposta com PII.
- Validar paths se vierem de input externo (evitar path traversal).

### Qualidade minima antes de entregar

- Script corre (ou o agent indica o comando de teste).
- Sem `TODO` / `FIXME` silenciosos sem avisar o utilizador.
- Sem dependencia nova sem listar no `requirements.txt` ou na resposta.
- Diff minimo: so o necessario para a tarefa pedida.

---

## 5. Caminhos: sempre Path.home()

Nunca hardcodar home do utilizador. Preferir:

| Ambiente | Use |
|----------|-----|
| Python | `Path.home()`, `os.path.expanduser('~')` |
| Ficheiros do projeto | relativos ao script: `Path(__file__).resolve().parent` |
| Dados do utilizador | sob `Path.home()` (Documents, Downloads, Desktop, etc.) |

```python
from pathlib import Path

BASE = Path(__file__).resolve().parent
DOWNLOADS = Path.home() / "Downloads"
DOCS = Path.home() / "Documents"
OUT_DIR = Path.home() / "Documents" / "Automacoes" / "minha_automacao"
OUT_DIR.mkdir(parents=True, exist_ok=True)
```

Credenciais, tokens e senhas: fora do codigo (env, ficheiro local ignorado pelo git,
cofre da empresa). Nunca commitar segredos.

---

## 6. Codigos de saida (obrigatorio para o ServerCRON)

**Todo script deve terminar com `sys.exit(0)`, `sys.exit(1)` ou `sys.exit(2)`.**
Nunca sair sem retcode, nunca usar outros numeros, nunca "so imprimir" o status
sem sair com o codigo. O ServerCRON **nao le a string do print** para classificar:
ele le o **`returncode` do processo**.

### O que o server faz com o retcode

1. Corre o `.py` com `subprocess` e le `proc.returncode`.
2. Mapeia: `0` -> `success`, `2` -> `no_data`, resto -> `error`.
3. Grava nos logs + SQLite + **CSV** (`historico_execucoes.csv`).
4. O painel web, o Excel dashboard e o **Power BI** leem esse historico
   (success / error / no_data, flags, tendencias).

Se o script nao devolver 0/1/2 corretos, os graficos, o CSV e o Power BI ficam errados.

### Tabela oficial

| `sys.exit` | Status no server / CSV / dashboard / Power BI | Quando usar |
|------------|-----------------------------------------------|-------------|
| `0` | **success** | Processou com sucesso (havia material e concluiu). |
| `1` | **error** | Falha tecnica (excecao, login falhou, ficheiro corrompido, timeout, etc.). |
| `2` | **no_data** | Rodou **sem erro tecnico**, mas **nao havia nada para processar** (pasta vazia, email sem anexo, fila vazia, etc.). |

`no_data` **nao** e falha: e "nada para fazer". Nao misturar com `error`.

### Padrao obrigatorio no fim do script

```python
import sys

def main() -> int:
    """Devolve sempre 0, 1 ou 2 para o ServerCRON captar."""
    arquivos = list(pasta.glob("*.pdf"))
    if not arquivos:
        print("Nenhum ficheiro para processar.")
        return 2  # no_data -> CSV / painel / Power BI

    try:
        processar(arquivos)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1  # error

    print("OK")
    return 0  # success


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        code = 1
    if code not in (0, 1, 2):
        code = 1
    sys.exit(code)
```

Resumo: **a unica forma do server, logs, CSV, dashboard e Power BI ficarem certos
e o script sair com retcode 0, 1 ou 2.**

---

## 7. Automacao web: Playwright (obrigatorio)

Quando a tarefa for browser / site / portal:

1. Usar **Playwright** (Python).
2. Browser: **Google Chrome** via `channel="chrome"` (nao Chromium empacotado, salvo se o utilizador pedir o contrario).
3. Viewport fixo: **1920 x 1080**.
4. Preferir `sync_api` em scripts de automacao simples (um fluxo linear).

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Abre Chrome do sistema com viewport Full HD
    browser = p.chromium.launch(
        channel="chrome",
        headless=False,  # True so se o utilizador/empresa pedir headless
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="pt-BR",
    )
    page = context.new_page()
    page.goto("https://exemplo.com", wait_until="domcontentloaded")
    # ... passos da automacao ...
    context.close()
    browser.close()
```

Regras Playwright:

- Viewport **sempre** `1920x1080` em automacoes web.
- Channel **sempre** `chrome` salvo indicacao em contrario.
- Esperas: preferir `page.get_by_role` / `locator.wait_for` / `expect`, evitar `time.sleep` fixo longo.
- Seletores estaveis (role, label, text, test-id). Evitar XPath fragil quando houver alternativa.
- Fechar browser/context no `finally` ou com context managers.
- Screenshots de erro: gravar sob `Path.home()` (ex.: `Documents/Automacoes/.../erros`), nunca sob path hardcoded de outro PC.

Instalacao tipica (documentar no README da automacao se for projeto novo):

```text
pip install playwright
playwright install chrome
```

(Se a empresa so permitir `playwright install`, e o Chrome do sistema existir, `channel="chrome"` continua valido.)

---

## 8. Estrutura completa (modelo)

O modelo abaixo ja inclui retcodes, logs com `RETCODE`, traceback em erro e
ficheiro `.log` em `Path.home()/Desktop/ServerCRON/logs/<AREA>/`.
Os helpers de log completos estao na secao 9 (copiar `iniciar_log_execucao`,
`log_*`, `encerrar`, etc.).

```python
# -*- coding: utf-8 -*-
"""Baixa anexos da pasta de entrada e arquiva os processados."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

TZ = ZoneInfo("America/Sao_Paulo")

# Identidade do script: nome do .py em execucao (sem extensao, minusculas)
_SCRIPT = Path(__file__).resolve()
STEM_LOWER = _SCRIPT.stem.lower()

_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

# Pasta de logs (criar sempre) + ficheiro STEM_LOWER_timestamp.log
LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

PASTA_ENTRADA = Path.home() / "Downloads" / "Entrada"
PASTA_SAIDA = Path.home() / "Documents" / "Automacoes" / STEM_LOWER / "saida"

HEADLESS = False
TIMEOUT_MS = 30_000

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
    if code == 0 and msg:
        log_ok(msg)
    elif code == 2:
        log_no_data(msg or "Nada para processar.")
    elif code != 0 and msg:
        _emit(f"ERRO: {msg}", erro=True)
    _emit(f"RETCODE: {code}")
    return code


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------

def listar_pdfs(pasta: Path) -> list[Path]:
    """Lista PDFs na pasta de entrada (nao recursivo)."""
    if not pasta.is_dir():
        raise FileNotFoundError(f"Pasta inexistente: {pasta}")
    return sorted(pasta.glob("*.pdf"))


def processar_arquivo(caminho: Path) -> None:
    """Processa um unico PDF e move para a pasta de saida."""
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    # ... logica de negocio ...
    destino = PASTA_SAIDA / caminho.name
    caminho.replace(destino)
    log_info(f"Processado: {caminho.name}")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def main() -> int:
    """Retorna 0 success, 1 error, 2 no_data."""
    try:
        pdfs = listar_pdfs(PASTA_ENTRADA)
    except FileNotFoundError as exc:
        log_erro(f"{exc}", com_traceback=True)
        return encerrar(1)

    if not pdfs:
        return encerrar(2, "Nenhum PDF na pasta de entrada.")

    try:
        for pdf in pdfs:
            processar_arquivo(pdf)
    except Exception as exc:
        log_erro(f"Falha ao processar: {exc}", com_traceback=True)
        return encerrar(1)

    return encerrar(0, f"Concluido: {len(pdfs)} ficheiro(s).")


if __name__ == "__main__":
    iniciar_log_execucao()
    try:
        try:
            code = main()
        except Exception as exc:
            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            code = encerrar(1)
        sys.exit(code)
    finally:
        fechar_log_execucao()
```

---

## 9. Padroes de log (obrigatorio)

O ServerCRON captura o **stdout+stderr** do processo e grava no historico/CSV.
Por isso o log tem de ser legivel e, em erro, trazer **traceback completo**.

Alem disso, **cada execucao** da automacao grava o seu proprio ficheiro `.log`
em disco (ver abaixo).

### Ficheiro .log por execucao (obrigatorio)

As automacoes vivem em `automacoes/<AREA>/.../<script>.py`.
Em cada corrida devem **criar** a pasta de logs (se nao existir) e gravar:

```text
Path.home() / "Desktop" / "ServerCRON" / "logs" / <AREA_NAME> / <STEM_LOWER>_<timestamp>.log
```

`STEM_LOWER` e variavel do topo: `Path(__file__).resolve().stem.lower()`.
Ex.: ficheiro `baixar_notas.py` -> `baixar_notas_20260807_091735.log`.

Regras do caminho:

| Parte | Regra |
|-------|--------|
| Raiz | `Path.home() / "Desktop" / "ServerCRON" / "logs"` (nunca hardcodar `C:\Users\...`) |
| `AREA_NAME` | pasta(s) relativa(s) sob `automacoes/` (ex.: script em `automacoes/teste/foo.py` -> area `teste`; em `automacoes/financeiro/mensal/bar.py` -> `financeiro/mensal`) |
| Nome do ficheiro | `{STEM_LOWER}_{YYYYMMDD_HHMMSS}.log` (STEM_LOWER = `Path(__file__).stem.lower()`) |
| Criacao | `LOG_DIR.mkdir(parents=True, exist_ok=True)` **sempre** antes de escrever |
| Conteudo | as mesmas linhas do console (`INFO`/`OK`/`NO_DATA`/`ERRO`/traceback/`RETCODE`) |

Exemplo:

```text
.../Desktop/ServerCRON/logs/teste/padrao_success_20260802_173045.log
.../Desktop/ServerCRON/logs/financeiro/mensal/backup_diario_20260802_080001.log
```

Tudo o que for para stdout/stderr deve ir **tambem** para este ficheiro (tee).

### Formato das linhas

Prefixos em pt-BR, sem emoji:

| Prefixo | Uso |
|---------|-----|
| `INFO:` | Progresso normal |
| `OK:` | Conclusao com sucesso (antes do exit 0) |
| `NO_DATA:` | Sem material (antes do exit 2) |
| `ERRO:` | Falha tecnica (antes do exit 1) |
| `RETCODE:` | Sempre na **ultima linha** util: `RETCODE: 0` / `1` / `2` |

Regras:

- Progresso em **stdout**; erros e traceback em **stderr**; **ambos** no `.log`.
- Em **error (1)**: mensagem clara **e** traceback completo (`traceback.format_exc()`).
- Em **no_data (2)** e **success (0)**: nao precisa de traceback.
- Sempre registar o retcode final com `RETCODE: N` (no ficheiro e no console).
- Nao logar senhas, tokens ou PII completa.

### Helpers padrao (copiar para o script)

```python
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

# Pasta automacoes = pai(s) ate chegar a "automacoes"; area = relativo a ela
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

_log_fp = None  # ficheiro da execucao atual


def iniciar_log_execucao() -> Path:
    """Cria logs/<AREA>/{STEM_LOWER}_{timestamp}.log e devolve o path."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    nome = f"{STEM_LOWER}_{stamp}.log"
    caminho = LOG_DIR / nome
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    _escrever_ficheiro(f"INFO: Log da execucao: {caminho}")
    _escrever_ficheiro(f"INFO: Script: {_SCRIPT}")
    _escrever_ficheiro(f"INFO: STEM_LOWER: {STEM_LOWER}")
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
    """Escreve no console e no .log da execucao."""
    stream = sys.stderr if erro else sys.stdout
    print(msg, file=stream, flush=True)
    _escrever_ficheiro(msg)


def log_info(msg: str) -> None:
    """Log de progresso."""
    _emit(f"INFO: {msg}")


def log_ok(msg: str) -> None:
    """Log de sucesso."""
    _emit(f"OK: {msg}")


def log_no_data(msg: str) -> None:
    """Log de ausencia de material."""
    _emit(f"NO_DATA: {msg}")


def log_erro(msg: str, *, com_traceback: bool = True) -> None:
    """Log de erro (+ traceback completo no stderr e no .log)."""
    _emit(f"ERRO: {msg}", erro=True)
    if com_traceback:
        tb = traceback.format_exc()
        _emit(tb.rstrip("\n"), erro=True)


def encerrar(code: int, msg: str = "") -> int:
    """
    Padroniza a saida: mensagem + RETCODE + devolve o codigo para sys.exit.
    code: 0 success, 1 error, 2 no_data.
    """
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
```

### Uso no `main` / `__main__`

```python
def main() -> int:
    """Retorna 0 success, 1 error, 2 no_data."""
    try:
        ficheiros = listar_pdfs(PASTA_ENTRADA)
    except Exception as exc:
        log_erro(f"Falha ao listar pasta: {exc}", com_traceback=True)
        return encerrar(1)

    if not ficheiros:
        return encerrar(2, "Pasta de entrada vazia.")

    try:
        for f in ficheiros:
            processar_arquivo(f)
    except Exception as exc:
        log_erro(f"Falha ao processar: {exc}", com_traceback=True)
        return encerrar(1)

    return encerrar(0, f"Processados {len(ficheiros)} ficheiro(s).")


if __name__ == "__main__":
    iniciar_log_execucao()
    try:
        try:
            code = main()
        except Exception as exc:
            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            log_erro(f"Retcode invalido ({code}); a forcar 1.", com_traceback=False)
            code = encerrar(1)
        sys.exit(code)
    finally:
        fechar_log_execucao()
```

### Exemplo de saida no historico / .log (error)

```text
INFO: Log da execucao: .../logs/teste/padrao_error_20260802_173045.log
INFO: A iniciar...
ERRO: Falha ao processar: [Errno 13] Permission denied: '...'
Traceback (most recent call last):
  File "...", line 42, in main
    processar_arquivo(f)
  ...
PermissionError: [Errno 13] Permission denied: '...'
RETCODE: 1
```

### Exemplo (no_data)

```text
NO_DATA: Pasta de entrada vazia.
RETCODE: 2
```

### Exemplo (success)

```text
INFO: Encontrados 3 PDF(s).
OK: Processados 3 ficheiro(s).
RETCODE: 0
```

---

## 10. Tratamento de erros

- Capturar excecoes na borda (`main` / `if __name__`), nao engolir com `except:` vazio.
- Em falha tecnica: `log_erro(..., com_traceback=True)` + `encerrar(1)` / `sys.exit(1)`.
- Em "sem material": `encerrar(2, motivo)` (nao lancar excecao so por pasta vazia; sem traceback).
- Recursos (browser, ficheiros, ligacoes, **ficheiro .log**): fechar em `finally` ou `with`.
- O traceback completo tem de aparecer no stderr **e** no `.log` para o ServerCRON / analise.

---

## 11. Dependencias e ambiente

- **Nao depender** de o utilizador correr `pip install -r requirements.txt` a mao.
- Declarar `DEPENDENCIAS` (e `POS_INSTALL_CMDS` se preciso) nas variaveis do topo.
- Chamar `garantir_dependencias()` no arranque (antes de usar pacotes de terceiros).
- Python 3.10+ salvo requisito da empresa.
- Windows: paths com `pathlib` (funciona com `/` e `\`).
- Fuso: se a empresa for Brasil, preferir horarios em `America/Sao_Paulo` quando relevante.
- Se quiser documentar deps num `requirements.txt`, pode; mas o script **tem** de se auto-instalar na mesma.

---

## 12. Integracao ServerCRON (se aplicavel)

- Nome do ficheiro / `STEM_LOWER` / `PYTHON_NAME` = `python_name` (e `nome_automacao`)
  na planilha `registro_automacoes.xlsx` (sem a extensao `.py` na celula).
- Colocar o `.py` sob a pasta `automacoes/` (subpastas por area ok).
- `cron_schedule` e `is_active` na planilha; o script em si nao agenda.
- Retcodes 0 / 1 / 2 como na secao 6.
- Emails de resultado: secao 13 (`emails_cc` + Outlook / pythoncom).
- Log proprio de cada corrida (obrigatorio):

```text
Path.home() / "Desktop" / "ServerCRON" / "logs" / <AREA> / <STEM_LOWER>_<YYYYMMDD_HHMMSS>.log
```

  Ex.: `automacoes/teste/padrao_success.py` ->
  `Desktop/ServerCRON/logs/teste/padrao_success_20260807_091735.log`

- O historico global do server (CSV / painel / Power BI) continua em
  `Path.home() / "Documents" / "ServerCRON" / "logs" / historico_execucoes.csv`
  (isso o server grava; o `.log` por automacao e responsabilidade do script).

---

## 13. Planilha registro_automacoes.xlsx + email Outlook (obrigatorio no futuro)

Todas as automacoes devem seguir o **mesmo padrao de variaveis** para encaixar
no Excel de registro e nas notificacoes por email.

### Onde fica o Excel

```text
Path(__file__) ... / ServerCRON / registro_automacoes.xlsx
```

Na raiz do projeto ServerCRON (junto de `server.py`), nao dentro de `automacoes/`.
Modelo versionado: `registro_automacoes.example.xlsx`. Copia local (nao git):
`registro_automacoes.xlsx`.

### Colunas que o script / o ServerCRON usam

Aba principal (nome tipico: `AUTOMACOES`). Colunas relevantes para o `.py`:

| Coluna | Quem usa | Descricao |
|--------|----------|-----------|
| `python_name` | script + server | Nome do `.py` sem extensao. **Deve ser igual a `STEM_LOWER`**. Alias legado no server: `nome_automacao`. |
| `area_name` | server / gestao | Area solicitante que pediu a automacao (ex.: `financeiro`, `rh`). |
| `emails_cc` | **script** | Destinatarios do email de **success** (retcode 0). Varios emails separados por `,` ou `;`. |
| `cron_schedule` | server | Expressao cron (o script nao agenda). |
| `is_active` | server | TRUE/FALSE se o server deve agendar. |

Outras colunas podem existir para o `server.py` (painel, BI, etc.). O script
**nao precisa** ler todas; no minimo precisa de achar a linha do seu `python_name`
e ler `emails_cc`.

### Variaveis padrao no topo do `.py`

```python
PYTHON_NAME = STEM_LOWER
REGISTRO_XLSX = Path.home() / "Desktop" / "ServerCRON" / "registro_automacoes.xlsx"
# Se o projeto nao estiver no Desktop, resolver a partir de _SCRIPT:
# REGISTRO_XLSX = next(
#     (p / "registro_automacoes.xlsx" for p in _SCRIPT.parents
#      if (p / "registro_automacoes.xlsx").is_file()),
#     Path.home() / "Desktop" / "ServerCRON" / "registro_automacoes.xlsx",
# )

EMAIL_DEV = "dev@empresa.com"  # SEU email - unico destinatario em retcode 1 ou 2
ENVIAR_EMAIL = True
```

`EMAIL_DEV` e o programador / operador da maquina. Em falha ou no_data **so ele**
recebe o email (para depurar). Em success, quem recebe sao os da coluna `emails_cc`.

### Regra de destinatarios por retcode

| Retcode | Status (email) | Destinatarios do email |
|---------|----------------|------------------------|
| `0` | `SUCCESS` | Todos em `emails_cc` (virgula ou ponto-e-virgula). Se `emails_cc` vazio: so `EMAIL_DEV` (aviso no log). |
| `1` | `ERROR` | **Apenas** `EMAIL_DEV` |
| `2` | `NO DATA` | **Apenas** `EMAIL_DEV` |

### Assunto do email (obrigatorio, sempre MAIUSCULAS)

Formato fixo:

```text
MONITRACAO PYTHON - {PYTHON_NAME} - {STATUS}
```

Exemplos:

```text
MONITRACAO PYTHON - SCRAPE_QUOTES_EXEMPLO - SUCCESS
MONITRACAO PYTHON - SCRAPE_QUOTES_EXEMPLO - ERROR
MONITRACAO PYTHON - SCRAPE_QUOTES_EXEMPLO - NO DATA
```

Todo o assunto em maiusculas (incluindo o `PYTHON_NAME`).

### Corpo do email (obrigatorio, HTML)

O corpo e **HTML** (`mail.HTMLBody`), nao texto plano. Cores por status:

| Status | Cor da faixa | Hex |
|--------|--------------|-----|
| `SUCCESS` | verde | `#1B7A4E` |
| `ERROR` | vermelho | `#B42318` |
| `NO DATA` | amarelo/ambar | `#B8860B` |

Conteudo minimo (fuso `America/Sao_Paulo`), tipografia `Segoe UI` / `Calibri`:

- faixa colorida com o STATUS
- `INICIO AUTOMACAO: YYYY-MM-DD - HH:MM:SS`
- `FIM AUTOMACAO: YYYY-MM-DD - HH:MM:SS`
- `DURACAO: Xh Ym Zs`
- `RESUMO:` texto curto

Nunca enviar traceback completo no corpo para `emails_cc` (retcode 0). Em
retcode 1/2 o resumo para `EMAIL_DEV` pode ser mais detalhado; o detalhe completo
fica no `.log` anexado.

### Anexo (obrigatorio)

**Sempre** anexar o ficheiro `.log` da execucao corrente
(`{STEM_LOWER}_{YYYYMMDD_HHMMSS}.log`). Fechar o log (`fechar_log_execucao`)
**antes** de anexar, para o ficheiro ficar completo e nao bloqueado no Windows.

### Envio: Outlook Classic via pythoncom (obrigatorio)

Nao usar SMTP generico nestas automacoes. O envio e pelo **Outlook Classic**
instalado na maquina, via `pywin32` (`win32com` + `pythoncom`).

Incluir em `DEPENDENCIAS`:

```python
DEPENDENCIAS: list[tuple[str, str]] = [
    ("openpyxl", "openpyxl"),   # ler registro_automacoes.xlsx
    ("win32com", "pywin32"),    # Outlook Classic
]
```

Helpers (modelo):

```python
STATUS_POR_RETCODE = {
    0: "SUCCESS",
    1: "ERROR",
    2: "NO DATA",
}


def _partir_emails(bruto: str) -> list[str]:
    """Separa emails por virgula ou ponto-e-virgula."""
    if not bruto or not str(bruto).strip():
        return []
    partes = str(bruto).replace(";", ",").split(",")
    return [p.strip() for p in partes if p.strip()]


def ler_emails_cc_do_registro(python_name: str) -> list[str]:
    """Le a coluna emails_cc da linha cujo python_name/nome_automacao = STEM_LOWER."""
    from openpyxl import load_workbook

    if not REGISTRO_XLSX.is_file():
        raise FileNotFoundError(f"Planilha nao encontrada: {REGISTRO_XLSX}")

    wb = load_workbook(REGISTRO_XLSX, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            return []
        headers = [str(h).strip().lower() if h is not None else "" for h in header]
        # Aceitar python_name (novo) ou nome_automacao (legado ServerCRON)
        idx_nome = next(
            (i for i, h in enumerate(headers) if h in ("python_name", "nome_automacao")),
            None,
        )
        idx_cc = next((i for i, h in enumerate(headers) if h == "emails_cc"), None)
        if idx_nome is None or idx_cc is None:
            raise KeyError(
                "Planilha precisa de python_name (ou nome_automacao) e emails_cc"
            )
        alvo = python_name.strip().lower()
        for row in rows:
            if not row or idx_nome >= len(row):
                continue
            nome = row[idx_nome]
            if nome is None:
                continue
            if str(nome).strip().lower() == alvo:
                bruto = row[idx_cc] if idx_cc < len(row) else ""
                return _partir_emails(str(bruto or ""))
    finally:
        wb.close()
    return []


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


# Cores da faixa HTML por status (Outlook le estilos inline)
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
                     style="background:{cores['fundo']};border-radius:6px;
                            border:1px solid {cores['faixa']}33;">
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
    """Envia email HTML pelo Outlook Classic (pythoncom + win32com) com .log anexado."""
    import pythoncom
    import win32com.client

    if not destinatarios:
        log_info("Nenhum destinatario de email; a saltar envio.")
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
        mail.Send()
        # Depois de Send() o item some do COM; nao aceder a mail.To
        log_info(f"Email Outlook enviado para: {para}")
    finally:
        pythoncom.CoUninitialize()


def notificar_por_email(
    code: int,
    resumo: str,
    inicio: datetime,
    fim: datetime,
    caminho_log: Path | None = None,
) -> None:
    """
    Retcode 0 -> emails_cc da planilha.
    Retcode 1 ou 2 -> apenas EMAIL_DEV.
    Sempre anexa o .log da execucao (se existir).
    """
    if not ENVIAR_EMAIL:
        log_info("ENVIAR_EMAIL=False; notificacao desligada.")
        return

    if code == 0:
        try:
            destinatarios = ler_emails_cc_do_registro(PYTHON_NAME)
        except Exception as exc:
            log_info(f"Falha ao ler emails_cc; a usar EMAIL_DEV. Motivo: {exc}")
            destinatarios = [EMAIL_DEV]
        if not destinatarios:
            log_info("emails_cc vazio; a notificar so EMAIL_DEV.")
            destinatarios = [EMAIL_DEV]
    else:
        destinatarios = [EMAIL_DEV]

    assunto = montar_assunto_email(code)
    corpo_html = montar_corpo_email(code, inicio, fim, resumo)
    enviar_email_outlook(destinatarios, assunto, corpo_html, anexo_log=caminho_log)
```

### Onde chamar no `__main__`

Registar `inicio` no arranque, `fim` apos o `main`, **fechar o log** e so depois
enviar o email (para o anexo `.log` ficar completo):

```python
if __name__ == "__main__":
    inicio = datetime.now(TZ)
    caminho_log = iniciar_log_execucao()
    code = 1
    try:
        try:
            garantir_dependencias()
            code = main()
        except Exception as exc:
            log_erro(f"Falha nao tratada: {exc}", com_traceback=True)
            code = encerrar(1)
        if code not in (0, 1, 2):
            code = encerrar(1)
    finally:
        fechar_log_execucao()

    fim = datetime.now(TZ)
    try:
        notificar_por_email(
            code,
            resumo=f"RETCODE: {code}",
            inicio=inicio,
            fim=fim,
            caminho_log=caminho_log,
        )
    except Exception as exc:
        # Email falhou: nao mascara o retcode da automacao
        print(f"ERRO: Falha ao enviar email Outlook: {exc}", file=sys.stderr, flush=True)
    sys.exit(code)
```

Se o Outlook nao estiver aberto / perfil nao configurado, o envio pode falhar:
registar `ERRO:` (console / log se ainda aberto), mas **manter** o retcode
original da automacao (0/1/2).

### Requisitos na maquina

- Outlook Classic instalado e perfil de email configurado (conta que envia).
- `pywin32` e `openpyxl` (via `garantir_dependencias`).
- Preferivel Outlook ja autenticado na sessao do Windows do ServerCRON.

---

## 14. Checklist do agent (antes de entregar)

- [ ] Sem emojis em lado nenhum (codigo, logs, docs)
- [ ] Comentarios e docstrings em **pt-BR**
- [ ] Ordem: stdlib -> variaveis (`STEM_LOWER`, `DEPENDENCIAS`, `PYTHON_NAME`, `EMAIL_DEV`, ...) -> funcoes -> `main` -> email -> `sys.exit`
- [ ] `garantir_dependencias()` no arranque (inclui `openpyxl` + `pywin32` se houver email)
- [ ] Imports de terceiros so **depois** do ensure
- [ ] Pasta de logs + `{STEM_LOWER}_{timestamp}.log`
- [ ] Logs `INFO:` / `OK:` / `NO_DATA:` / `ERRO:` + `RETCODE: N`
- [ ] Em error (1): traceback completo no stderr e no `.log`
- [ ] `PYTHON_NAME` = `STEM_LOWER` alinhado a coluna `python_name` / `nome_automacao` do Excel
- [ ] Email Outlook (pythoncom): assunto `MONITRACAO PYTHON - NAME - STATUS` (maiusculas); corpo HTML com faixa verde/vermelho/amarelo + INICIO/FIM/DURACAO; sempre anexar `.log`
- [ ] Email: retcode 0 -> `emails_cc`; retcode 1 ou 2 -> so `EMAIL_DEV`
- [ ] Sem caminho `C:\Users\...` hardcoded; usa `Path.home()` / `Path(__file__)`
- [ ] **Sempre** `sys.exit(0|1|2)`
- [ ] Se for web: Playwright + `channel="chrome"` + viewport `1920x1080`
- [ ] Pasta/lista vazia -> `2`, nao `1`
- [ ] Diff minimo; sem over-engineering

---

## 15. Como o utilizador pede ao agent

Modelo de pedido:

> Segue o ficheiro `INSTRUCOES_AUTOMACAO_PYTHON.md`.
> Cria a automacao que faz: [descrever o fluxo].
> Entrada: [pasta / email / URL].
> Saida: [onde gravar].
> Area solicitante: [area_name].
> Emails success (emails_cc): [lista].
> Empresa: [regras extras se houver].

O agent implementa o `.py` obedecendo este documento.
