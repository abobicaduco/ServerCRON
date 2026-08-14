# -*- coding: utf-8 -*-
"""Interface web local: cola HTML da vaga e recebe JS para o console do Chrome."""
from __future__ import annotations

import json
import queue
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, stream_with_context

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from gerar_fill_formulario import (  # noqa: E402
    MODELO_PADRAO,
    SAIDA_JS,
    gerar_js_de_html,
    iniciar_log_execucao,
    log_erro,
    log_info,
    log_ok,
)

HOST = "127.0.0.1"
PORT = 8765

app = Flask(__name__)

PAGINA = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Preencher vaga - JS console</title>
  <style>
    :root {
      --bg: #12141a;
      --panel: #1a1d26;
      --line: #2c3140;
      --text: #e8e6e1;
      --muted: #9a958c;
      --accent: #3d9a7a;
      --accent-dim: #2a6b55;
      --danger: #c45c5c;
      --warn: #c9a227;
      --mono: "Cascadia Code", "Consolas", "SF Mono", monospace;
      --sans: "Segoe UI", "IBM Plex Sans", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(1200px 500px at 10% -10%, #1e2433 0%, transparent 55%),
        var(--bg);
      color: var(--text);
      font-family: var(--sans);
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }
    header h1 {
      margin: 0 0 6px;
      font-size: 1.45rem;
      font-weight: 650;
      letter-spacing: -0.02em;
    }
    header p {
      margin: 0 0 22px;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.45;
      max-width: 52rem;
    }
    .grid { display: grid; gap: 16px; }
    @media (min-width: 900px) {
      .grid-2 { grid-template-columns: 1fr 1fr; }
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      min-height: 360px;
    }
    label {
      display: block;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 8px;
    }
    textarea {
      flex: 1;
      width: 100%;
      min-height: 280px;
      resize: vertical;
      background: #0e1015;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font-family: var(--mono);
      font-size: 0.82rem;
      line-height: 1.4;
    }
    textarea:focus {
      outline: 2px solid var(--accent-dim);
      border-color: var(--accent);
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin: 14px 0;
      padding: 12px 14px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
    }
    .controls select {
      background: #0e1015;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font-family: var(--sans);
    }
    .chk {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.9rem;
      text-transform: none;
      letter-spacing: 0;
    }
    button {
      border: 0;
      border-radius: 8px;
      padding: 10px 16px;
      font-weight: 600;
      cursor: pointer;
      font-family: var(--sans);
    }
    button.primary { background: var(--accent); color: #04140f; }
    button.primary:disabled { opacity: 0.55; cursor: wait; }
    button.ghost {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--line);
    }
    .status {
      min-height: 1.3em;
      color: var(--muted);
      font-size: 0.9rem;
    }
    .status.erro { color: var(--danger); }
    .status.ok { color: var(--accent); }
    .hint {
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.85rem;
      line-height: 1.5;
    }
    code { font-family: var(--mono); font-size: 0.85em; }

    .console-panel {
      margin-top: 16px;
      background: #0a0c10;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
    }
    .console-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      background: #141820;
    }
    .console-head strong {
      font-size: 0.8rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }
    .console-head .pulse {
      display: none;
      align-items: center;
      gap: 8px;
      color: var(--warn);
      font-size: 0.82rem;
      font-family: var(--mono);
    }
    .console-head .pulse.on { display: flex; }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--warn);
      animation: blink 1s infinite;
    }
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.25; }
    }
    #consoleLog {
      margin: 0;
      padding: 12px 14px;
      min-height: 160px;
      max-height: 280px;
      overflow-y: auto;
      font-family: var(--mono);
      font-size: 0.78rem;
      line-height: 1.45;
      color: #b8c0cc;
      white-space: pre-wrap;
      word-break: break-word;
    }
    #consoleLog .line-erro { color: var(--danger); }
    #consoleLog .line-ok { color: var(--accent); }
    #consoleLog .line-ia { color: #7eb8ff; }
    #consoleLog .ts { color: #5c6575; margin-right: 8px; }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Preencher vaga</h1>
      <p>
        Cole o HTML da pagina (Gupy, InfoJobs, etc.). A IA le o seu perfil e devolve
        um JavaScript para colar no console do Chrome (F12).
      </p>
    </header>

    <div class="controls">
      <div>
        <label for="tipo">Contrato</label>
        <select id="tipo">
          <option value="clt" selected>CLT (pretensao R$ 2.500)</option>
          <option value="estagio">Estagio (pretensao R$ 2.000)</option>
        </select>
      </div>
      <label class="chk">
        <input type="checkbox" id="submit" />
        Clicar em Salvar/Continuar no JS
      </label>
      <div style="flex:1"></div>
      <button class="ghost" type="button" id="btnLimpar">Limpar</button>
      <button class="primary" type="button" id="btnGerar">Gerar JavaScript</button>
    </div>

    <div class="grid grid-2">
      <div class="panel">
        <label for="html">HTML da pagina</label>
        <textarea id="html" placeholder="Cole aqui o body/main do formulario..."></textarea>
      </div>
      <div class="panel">
        <label for="js">JavaScript (console)</label>
        <textarea id="js" readonly placeholder="O IIFE aparece aqui..."></textarea>
      </div>
    </div>

    <div class="console-panel">
      <div class="console-head">
        <strong>Console da IA</strong>
        <span class="pulse" id="pulse"><span class="dot"></span> processando...</span>
        <button class="ghost" type="button" id="btnLimparLog" style="padding:6px 10px;font-size:0.8rem">Limpar log</button>
      </div>
      <pre id="consoleLog">Aguardando... cole o HTML e clique em Gerar.</pre>
    </div>

    <div class="controls" style="margin-top:14px">
      <button class="ghost" type="button" id="btnCopiar" disabled>Copiar JS</button>
      <div class="status" id="status"></div>
    </div>

    <p class="hint">
      Fluxo: na vaga, F12 &rarr; Elements &rarr; copia o <code>&lt;main&gt;</code> ou o
      <code>&lt;body&gt;</code> &rarr; cola aqui &rarr; Gerar &rarr; acompanha o console &rarr;
      copia o JS &rarr; Console da mesma aba &rarr; Enter.
    </p>
  </div>

  <script>
    const elHtml = document.getElementById('html');
    const elJs = document.getElementById('js');
    const elTipo = document.getElementById('tipo');
    const elSubmit = document.getElementById('submit');
    const elStatus = document.getElementById('status');
    const elLog = document.getElementById('consoleLog');
    const elPulse = document.getElementById('pulse');
    const btnGerar = document.getElementById('btnGerar');
    const btnCopiar = document.getElementById('btnCopiar');
    const btnLimpar = document.getElementById('btnLimpar');
    const btnLimparLog = document.getElementById('btnLimparLog');

    let logBoot = true;

    function setStatus(msg, cls) {
      elStatus.textContent = msg || '';
      elStatus.className = 'status' + (cls ? ' ' + cls : '');
    }

    function agora() {
      const d = new Date();
      return d.toLocaleTimeString('pt-BR', { hour12: false });
    }

    function appendLog(msg, kind) {
      if (logBoot) {
        elLog.textContent = '';
        logBoot = false;
      }
      const line = document.createElement('div');
      if (kind === 'erro') line.className = 'line-erro';
      else if (kind === 'ok') line.className = 'line-ok';
      else if (kind === 'ia' || String(msg).includes('[IA]')) line.className = 'line-ia';

      const ts = document.createElement('span');
      ts.className = 'ts';
      ts.textContent = agora();
      line.appendChild(ts);
      line.appendChild(document.createTextNode(msg));
      elLog.appendChild(line);
      elLog.scrollTop = elLog.scrollHeight;
    }

    function setBusy(on) {
      btnGerar.disabled = on;
      elPulse.classList.toggle('on', on);
    }

    btnLimparLog.addEventListener('click', () => {
      elLog.textContent = '';
      logBoot = false;
      appendLog('Log limpo.');
    });

    btnLimpar.addEventListener('click', () => {
      elHtml.value = '';
      elJs.value = '';
      btnCopiar.disabled = true;
      setStatus('');
    });

    btnCopiar.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(elJs.value);
        setStatus('JS copiado. Cole no console do Chrome.', 'ok');
        appendLog('JS copiado para a area de transferencia.', 'ok');
      } catch (e) {
        setStatus('Nao foi possivel copiar. Selecione o JS e copie manualmente.', 'erro');
      }
    });

    async function lerStreamSSE(resp) {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const partes = buf.split(/\n\n/);
        buf = partes.pop() || '';
        for (const bloco of partes) {
          const linhas = bloco.split(/\n/);
          for (const ln of linhas) {
            if (!ln.startsWith('data:')) continue;
            const raw = ln.slice(5).trim();
            if (!raw) continue;
            let ev;
            try { ev = JSON.parse(raw); } catch (_) { continue; }
            if (ev.tipo === 'log') {
              appendLog(ev.msg || '');
            } else if (ev.tipo === 'js') {
              elJs.value = ev.js || '';
              btnCopiar.disabled = !elJs.value;
              appendLog('JS pronto para injecao no console.', 'ok');
              setStatus('Pronto. Copie o JS e cole no console da aba da vaga.', 'ok');
            } else if (ev.tipo === 'erro') {
              appendLog('ERRO: ' + (ev.erro || 'falha'), 'erro');
              setStatus(ev.erro || 'Falha ao gerar.', 'erro');
            }
          }
        }
      }
    }

    btnGerar.addEventListener('click', async () => {
      const html = elHtml.value.trim();
      if (!html) {
        setStatus('Cole o HTML da pagina primeiro.', 'erro');
        appendLog('HTML vazio: nada para enviar.', 'erro');
        return;
      }
      elJs.value = '';
      btnCopiar.disabled = true;
      setBusy(true);
      setStatus('Gerando com a IA... veja o console abaixo.');
      appendLog('--- nova geracao ---');
      appendLog('Enviando HTML (' + html.length + ' chars) para a IA...');

      try {
        const resp = await fetch('/api/gerar-stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            html,
            tipo: elTipo.value,
            submit: elSubmit.checked,
          }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.erro || ('HTTP ' + resp.status));
        }
        await lerStreamSSE(resp);
      } catch (e) {
        const msg = String(e.message || e);
        appendLog('ERRO: ' + msg, 'erro');
        setStatus(msg, 'erro');
      } finally {
        setBusy(false);
      }
    });
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    """Pagina principal da interface."""
    return render_template_string(PAGINA)


@app.post("/api/gerar")
def api_gerar():
    """Recebe HTML e devolve o IIFE (sem streaming; fallback)."""
    payload = request.get_json(silent=True) or {}
    html = (payload.get("html") or "").strip()
    tipo = (payload.get("tipo") or "clt").strip().lower()
    submit = bool(payload.get("submit"))
    modelo = (payload.get("modelo") or MODELO_PADRAO).strip()

    if not html:
        return jsonify({"ok": False, "erro": "HTML vazio."}), 400
    if tipo not in ("estagio", "clt"):
        return jsonify({"ok": False, "erro": "tipo invalido (use estagio ou clt)."}), 400

    try:
        log_info("Pedido via interface web (json).")
        iife = gerar_js_de_html(html, tipo=tipo, submit=submit, modelo=modelo)
        SAIDA_JS.write_text(iife + "\n", encoding="utf-8")
        log_ok(f"JS gerado via UI ({len(iife)} chars).")
        return jsonify({"ok": True, "js": iife})
    except Exception as exc:
        log_erro(f"Falha na API /api/gerar: {exc}")
        return jsonify({"ok": False, "erro": str(exc)}), 500


@app.post("/api/gerar-stream")
def api_gerar_stream():
    """Gera JS e envia logs em tempo real via SSE."""
    payload = request.get_json(silent=True) or {}
    html = (payload.get("html") or "").strip()
    tipo = (payload.get("tipo") or "clt").strip().lower()
    submit = bool(payload.get("submit"))
    modelo = (payload.get("modelo") or MODELO_PADRAO).strip()

    if not html:
        return jsonify({"ok": False, "erro": "HTML vazio."}), 400
    if tipo not in ("estagio", "clt"):
        return jsonify({"ok": False, "erro": "tipo invalido (use estagio ou clt)."}), 400

    log_q: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def on_log(msg: str) -> None:
        log_q.put(("log", msg))

    resultado: dict[str, str | None] = {"js": None, "erro": None}

    def worker() -> None:
        try:
            log_info("Pedido via interface web (stream).")
            iife = gerar_js_de_html(
                html,
                tipo=tipo,
                submit=submit,
                modelo=modelo,
                on_log=on_log,
            )
            SAIDA_JS.write_text(iife + "\n", encoding="utf-8")
            resultado["js"] = iife
            log_ok(f"JS gerado via UI stream ({len(iife)} chars).")
        except Exception as exc:
            resultado["erro"] = str(exc)
            log_erro(f"Falha na API /api/gerar-stream: {exc}")
        finally:
            log_q.put(("done", None))

    threading.Thread(target=worker, daemon=True).start()

    @stream_with_context
    def event_stream():
        yield f"data: {json.dumps({'tipo': 'log', 'msg': 'Stream iniciado.'}, ensure_ascii=False)}\n\n"
        while True:
            kind, data = log_q.get()
            if kind == "log":
                yield f"data: {json.dumps({'tipo': 'log', 'msg': data}, ensure_ascii=False)}\n\n"
            elif kind == "done":
                if resultado["erro"]:
                    yield f"data: {json.dumps({'tipo': 'erro', 'erro': resultado['erro']}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'tipo': 'js', 'js': resultado['js']}, ensure_ascii=False)}\n\n"
                break

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> int:
    """Sobe o servidor local e abre o browser."""
    iniciar_log_execucao()
    url = f"http://{HOST}:{PORT}/"
    log_info(f"Interface em {url}")

    def _abrir() -> None:
        webbrowser.open(url)

    threading.Timer(1.0, _abrir).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nINFO: Interface encerrada.")
        raise SystemExit(0)
