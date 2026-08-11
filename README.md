# ServerCRON

Servidor e gerenciador de automações de tarefas agendadas (Cron Jobs) em Python.

---

## O problema

1. **O que é:** O **ServerCRON** é uma plataforma de gerenciamento e agendamento de scripts de automação.
2. **Qual necessidade ataca:** Garante que scripts de manutenção, relatórios e backups sejam executados pontualmente nos horários programados.
3. **Por que existe:** O agendador de tarefas nativo do sistema por vezes falha de forma silenciosa e não gera relatórios amigáveis.
4. **Qual o objetivo:** Oferecer um ambiente centralizado em Python para gerenciar e registrar tarefas automáticas.

---

## Recursos

- ✅ **Agendamento Flexível:** Agende rotinas com sintaxe cron padrão ou intervalos de tempo.
- ✅ **Registro de Execuções:** Histórico completo de logs das automações executadas.
- ✅ **Instalador de Dependências:** Script `install_deps.bat` para configuração rápida em ambientes Windows.

---

## Instalação

### Pré-requisitos
- Python 3.10 ou superior

### Instalação
```bash
git clone https://github.com/caducosilva/ServerCRON.git
cd ServerCRON
install_deps.bat
```

---

## Como usar

Configure suas rotinas na pasta `automacoes` e inicie o gerenciador:
```bash
python automacoes/main.py
```

---

## Configuração

Copie `.env.example` para `.env` e configure as chaves necessárias.

| Variável | Descrição |
|---|---|
| `CRON_INTERVAL` | Intervalo padrão de checagem |

---

## Detalhes técnicos relevantes

- **Linguagem:** Python 3.10+.
- **Logs:** Registrados em formato de planilha e arquivo `.log`.

---

## Testes

```bash
python -m unittest discover automacoes
```

---

## Problemas comuns

| Mensagem de erro | Causa provável | Solução |
|---|---|---|
| `ModuleNotFoundError` | Dependências não instaladas | Execute `install_deps.bat` para atualizar os pacotes Python |

---

## Apoie o projeto

Se este projeto te ajudou, considere fazer uma doação via PIX:

```
f74458dc-2a36-49bd-9250-1cef4365ebb8
```

---

## Licença

[MIT](LICENSE) — Carlos Eduardo
