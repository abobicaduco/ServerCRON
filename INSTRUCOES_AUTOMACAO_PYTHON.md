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

Ordem fixa no `.py` (de cima para baixo):

1. Shebang opcional / `# -*- coding: utf-8 -*-`
2. Docstring do modulo (1 a 3 linhas: o que a automacao faz)
3. `from __future__ import annotations` (se usar type hints modernas)
4. Imports da stdlib (alfabetico por bloco)
5. Linha em branco
6. Imports de terceiros (`playwright`, `openpyxl`, etc.)
7. Linha em branco
8. Imports locais / do projeto (se houver)
9. Constantes em `MAIUSCULAS` (paths, timeouts, nomes de pastas)
10. Funcoes auxiliares (pequenas, uma responsabilidade)
11. `main() -> int` (fluxo principal; devolve 0, 1 ou 2)
12. Bloco `if __name__ == "__main__":` com `sys.exit(...)`

### Constantes e paths no topo

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PASTA_ENTRADA = Path.home() / "Downloads" / "Entrada"
PASTA_SAIDA = Path.home() / "Documents" / "Automacoes" / "minha_automacao" / "saida"
PASTA_ERROS = Path.home() / "Documents" / "Automacoes" / "minha_automacao" / "erros"
TIMEOUT_MS = 30_000
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
_SCRIPT = Path(__file__).resolve()
_AUTOMAOES_ROOT = next(
    (p for p in _SCRIPT.parents if p.name.lower() == "automacoes"),
    _SCRIPT.parent,
)
_AREA_REL = _SCRIPT.parent.relative_to(_AUTOMAOES_ROOT)
AREA_NAME = "." if str(_AREA_REL) == "." else str(_AREA_REL).replace("\\", "/")

LOG_ROOT = Path.home() / "Desktop" / "ServerCRON" / "logs"
LOG_DIR = LOG_ROOT / AREA_NAME

PASTA_ENTRADA = Path.home() / "Downloads" / "Entrada"
PASTA_SAIDA = Path.home() / "Documents" / "Automacoes" / "exemplo" / "saida"

_log_fp = None


# ---------------------------------------------------------------------------
# Log (console + ficheiro .log da execucao)
# ---------------------------------------------------------------------------

def iniciar_log_execucao() -> Path:
    """Cria logs/<AREA>/<stem_lower>_<timestamp>.log."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    caminho = LOG_DIR / f"{_SCRIPT.stem.lower()}_{stamp}.log"
    _log_fp = caminho.open("a", encoding="utf-8", newline="\n")
    log_info(f"Log da execucao: {caminho}")
    log_info(f"Script: {_SCRIPT}")
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
Em cada corrida devem criar um log em:

```text
Path.home() / "Desktop" / "ServerCRON" / "logs" / <AREA_NAME> / <stem_lower>_<timestamp>.log
```

Regras do caminho:

| Parte | Regra |
|-------|--------|
| Raiz | `Path.home() / "Desktop" / "ServerCRON" / "logs"` (nunca hardcodar `C:\Users\...`) |
| `AREA_NAME` | pasta(s) relativa(s) sob `automacoes/` (ex.: script em `automacoes/teste/foo.py` -> area `teste`; em `automacoes/financeiro/mensal/bar.py` -> `financeiro/mensal`) |
| Nome do ficheiro | `{Path(__file__).stem.lower()}_{YYYYMMDD_HHMMSS}.log` |
| Criacao | `mkdir(parents=True, exist_ok=True)` antes de escrever |
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
    """Cria logs/<AREA>/<stem_lower>_<timestamp>.log e devolve o path."""
    global _log_fp
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    nome = f"{_SCRIPT.stem.lower()}_{stamp}.log"
    caminho = LOG_DIR / nome
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

- Listar deps minimas (`requirements.txt` ou comentario no topo se for um unico script).
- Python 3.10+ salvo requisito da empresa.
- Windows: paths com `pathlib` (funciona com `/` e `\`).
- Fuso: se a empresa for Brasil, preferir horarios em `America/Sao_Paulo` quando relevante.

---

## 12. Integracao ServerCRON (se aplicavel)

- Nome do ficheiro = `nome_automacao` na planilha (sem precisar da extensao na celula).
- Colocar o `.py` sob a pasta `automacoes/` (subpastas por area ok).
- `cron_schedule` na planilha; o script em si nao agenda.
- Retcodes 0 / 1 / 2 como na secao 6.
- Log proprio de cada corrida (obrigatorio):

```text
Path.home() / "Desktop" / "ServerCRON" / "logs" / <AREA> / <stem_lower>_<YYYYMMDD_HHMMSS>.log
```

  Ex.: `automacoes/teste/padrao_success.py` ->
  `Desktop/ServerCRON/logs/teste/padrao_success_20260802_173045.log`

- O historico global do server (CSV / painel / Power BI) continua em
  `Path.home() / "Documents" / "ServerCRON" / "logs" / historico_execucoes.csv`
  (isso o server grava; o `.log` por automacao e responsabilidade do script).

---

## 13. Checklist do agent (antes de entregar)

- [ ] Sem emojis em lado nenhum (codigo, logs, docs)
- [ ] Comentarios e docstrings em **pt-BR**
- [ ] Logs com `INFO:` / `OK:` / `NO_DATA:` / `ERRO:` + linha final `RETCODE: N`
- [ ] Ficheiro `.log` em `Path.home()/Desktop/ServerCRON/logs/<AREA>/<stem_lower>_<timestamp>.log`
- [ ] Em error (1): **traceback completo** no stderr e no `.log`
- [ ] Ficheiro organizado: imports -> constantes -> helpers -> `main` -> `sys.exit`
- [ ] Padroes da secao 4 (f-strings, early return, sem `except:` vazio, pathlib, utf-8)
- [ ] Sem caminho `C:\Users\...` ou `/Users/nome` hardcoded
- [ ] Usa `Path.home()` / `Path(__file__)` onde couber
- [ ] **Sempre** `sys.exit(0|1|2)` no fim (server / CSV / dashboard / Power BI)
- [ ] Semantica correta: `0` success, `1` error, `2` no_data (sem material)
- [ ] Se for web: Playwright + `channel="chrome"` + viewport `1920x1080`
- [ ] Tratamento de "lista/pasta/email vazio" -> `2`, nao `1`
- [ ] Segredos fora do codigo; sem dependencia nova nao listada
- [ ] Diff minimo; sem over-engineering
- [ ] Script executavel de ponta a ponta (ou passos de setup documentados)

---

## 14. Como o utilizador pede ao agent

Modelo de pedido:

> Segue o ficheiro `INSTRUCOES_AUTOMACAO_PYTHON.md`.
> Cria a automacao que faz: [descrever o fluxo].
> Entrada: [pasta / email / URL].
> Saida: [onde gravar].
> Empresa: [regras extras se houver].

O agent implementa o `.py` obedecendo este documento.
