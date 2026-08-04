(function () {
  const TITLES = {
    dashboard: ["Dashboard", "Estado do agendador e tendencia"],
    relatorio: ["Relatório", "Totais, comparativos e histórico por período"],
    scripts: ["Automacoes", "Lidas de registro_automacoes.xlsx"],
    queue: ["Fila", "Pendentes, proximas e a rodar agora"],
    history: ["Historico", "Ultimas execucoes"],
    users: ["Usuarios", "Quem pode acessar o painel (login por email)"],
    paths: ["Caminhos", "Pastas, planilha e leitura do disco"],
  };

  let scriptsCache = [];
  let runningCache = [];
  let pollTimer = null;
  let clockTimer = null;
  const inFlightActions = new Set();
  const TZ_BR = "America/Sao_Paulo";

  function $(id) {
    return document.getElementById(id);
  }

  function showToast(message, type) {
    const stack = $("toast-stack");
    if (!stack) return;
    const el = document.createElement("div");
    el.className = "toast" + (type ? " " + type : "");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add("leaving");
      setTimeout(() => el.remove(), 200);
    }, 4200);
  }

  function debounce(fn, wait) {
    let timer = null;
    return function debounced(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** ISO / Date -> "15:28:25 - 02/08/2026" (pt-BR). */
  function formatDateBr(value, withSeconds) {
    if (value == null || value === "") return "-";
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    if (withSeconds === false) {
      return hh + ":" + mi + " - " + dd + "/" + mm + "/" + yyyy;
    }
    return hh + ":" + mi + ":" + ss + " - " + dd + "/" + mm + "/" + yyyy;
  }

  function partsInTz(date, timeZone) {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: timeZone,
      weekday: "short",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      hourCycle: "h23",
    }).formatToParts(date);
    const map = {};
    parts.forEach((p) => {
      if (p.type !== "literal") map[p.type] = p.value;
    });
    return map;
  }

  let lastWeekKey = "";
  let weatherCache = null;
  let weatherTimer = null;
  let weatherSelectedIdx = 0;
  let weatherResetTimer = null;

  const WEATHER_ICONS = {
    clear:
      '<svg stroke="#ffffff" fill="#ffffff" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path d="M512 704a192 192 0 1 0 0-384 192 192 0 0 0 0 384zm0 64a256 256 0 1 1 0-512 256 256 0 0 1 0 512zm0-704a32 32 0 0 1 32 32v64a32 32 0 0 1-64 0V96a32 32 0 0 1 32-32zm0 768a32 32 0 0 1 32 32v64a32 32 0 1 1-64 0v-64a32 32 0 0 1 32-32zM195.2 195.2a32 32 0 0 1 45.248 0l45.248 45.248a32 32 0 1 1-45.248 45.248L195.2 240.448a32 32 0 0 1 0-45.248zm543.104 543.104a32 32 0 0 1 45.248 0l45.248 45.248a32 32 0 0 1-45.248 45.248l-45.248-45.248a32 32 0 0 1 0-45.248zM64 512a32 32 0 0 1 32-32h64a32 32 0 0 1 0 64H96a32 32 0 0 1-32-32zm768 0a32 32 0 0 1 32-32h64a32 32 0 1 1 0 64h-64a32 32 0 0 1-32-32zM195.2 828.8a32 32 0 0 1 0-45.248l45.248-45.248a32 32 0 0 1 45.248 45.248L240.448 828.8a32 32 0 0 1-45.248 0zm543.104-543.104a32 32 0 0 1 0-45.248l45.248-45.248a32 32 0 0 1 45.248 45.248l-45.248 45.248a32 32 0 0 1-45.248 0z" fill="#ffffff"></path></svg>',
    cloudy:
      '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 15C4.23858 15 2 12.7614 2 10C2 7.23858 4.23858 5 7 5C7.03315 5 7.06622 5.00032 7.09922 5.00097C8.0094 3.2196 9.86227 2 12 2C14.5192 2 16.6429 3.69375 17.2943 6.00462C17.3625 6.00155 17.4311 6 17.5 6C19.9853 6 22 8.01472 22 10.5C22 12.9853 19.9853 15 17.5 15C13.7434 15 11.2352 15 7 15Z" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
    rain:
      '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 18.5L15 21M8 18.5L7 21M12 18.5L11 21M7 15C4.23858 15 2 12.7614 2 10C2 7.23858 4.23858 5 7 5C7.03315 5 7.06622 5.00032 7.09922 5.00097C8.0094 3.2196 9.86227 2 12 2C14.5192 2 16.6429 3.69375 17.2943 6.00462C17.3625 6.00155 17.4311 6 17.5 6C19.9853 6 22 8.01472 22 10.5C22 12.9853 19.9853 15 17.5 15C13.7434 15 11.2352 15 7 15Z" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
    storm:
      '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 18.5L15 21M8 18.5L7 21M12 18.5L11 21M7 15C4.23858 15 2 12.7614 2 10C2 7.23858 4.23858 5 7 5C7.03315 5 7.06622 5.00032 7.09922 5.00097C8.0094 3.2196 9.86227 2 12 2C14.5192 2 16.6429 3.69375 17.2943 6.00462C17.3625 6.00155 17.4311 6 17.5 6C19.9853 6 22 8.01472 22 10.5C22 12.9853 19.9853 15 17.5 15C13.7434 15 11.2352 15 7 15Z" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M13 11L10 15H14L11 19" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
    snow:
      '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3V21M5 7L19 17M19 7L5 17" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/></svg>',
    fog:
      '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 8H20M2 12H22M6 16H18" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/></svg>',
  };

  function weatherIcon(kind) {
    return WEATHER_ICONS[kind] || WEATHER_ICONS.cloudy;
  }

  function fmtTemp(v) {
    if (v == null || Number.isNaN(Number(v))) return "--";
    return String(Math.round(Number(v)));
  }

  function weekdayShortPt(isoDate) {
    if (!isoDate) return "-";
    const d = new Date(isoDate + "T12:00:00");
    return new Intl.DateTimeFormat("pt-BR", { weekday: "short" })
      .format(d)
      .replace(".", "")
      .toUpperCase();
  }

  function dateShortPt(isoDate) {
    if (!isoDate) return "-";
    const d = new Date(isoDate + "T12:00:00");
    const shortDay = weekdayShortPt(isoDate);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return shortDay + " " + mm + "-" + dd;
  }

  function showWeatherDay(idx) {
    if (!weatherCache) return;
    const days = weatherCache.days || [];
    const day = days[idx];
    if (!day) return;
    weatherSelectedIdx = idx;

    const cond = $("clock-condition");
    const temp = $("clock-temp");
    const range = $("clock-range");
    const icon = $("clock-weather-icon");
    const dateEl = $("clock-date");
    const city = $("clock-city");

    const isToday = !!day.is_today || idx === 0;
    if (cond) cond.textContent = day.label || weatherCache.label || "São Paulo";
    if (icon) icon.innerHTML = weatherIcon(day.icon || "cloudy");
    if (range) {
      range.textContent = fmtTemp(day.temp_max) + "°/" + fmtTemp(day.temp_min) + "°";
    }
    if (temp) {
      const t =
        day.temperature != null
          ? day.temperature
          : isToday
            ? weatherCache.temperature
            : day.temp_max;
      temp.textContent = fmtTemp(t) + "°";
    }
    if (dateEl && day.date) dateEl.textContent = dateShortPt(day.date);
    if (city) {
      city.textContent =
        (weatherCache.city || "São Paulo") + (isToday ? "" : " · previsao");
    }

    const weekEl = $("clock-weekdays");
    if (weekEl) {
      weekEl.querySelectorAll(".day-btn").forEach((btn, i) => {
        btn.classList.toggle("is-active", i === idx);
      });
    }
  }

  function resetWeatherToToday() {
    weatherSelectedIdx = 0;
    if (weatherCache) showWeatherDay(0);
  }

  function scheduleWeatherReset() {
    clearTimeout(weatherResetTimer);
    weatherResetTimer = setTimeout(() => {
      resetWeatherToToday();
    }, 3000);
  }

  function cancelWeatherReset() {
    clearTimeout(weatherResetTimer);
    weatherResetTimer = null;
  }

  function bindWeatherCardInteractions() {
    const card = $("status-clock");
    if (!card || card.dataset.weatherBound === "1") return;
    card.dataset.weatherBound = "1";
    card.addEventListener("mouseenter", cancelWeatherReset);
    card.addEventListener("mouseleave", () => {
      if (weatherSelectedIdx !== 0) scheduleWeatherReset();
    });
    card.addEventListener("click", (e) => {
      const btn = e.target.closest(".day-btn");
      if (!btn || !card.contains(btn)) return;
      const idx = Number(btn.dataset.dayIndex);
      if (Number.isNaN(idx)) return;
      cancelWeatherReset();
      showWeatherDay(idx);
    });
  }

  function applyWeather(data) {
    if (!data || data.ok === false) return;
    weatherCache = data;
    const days = data.days || [];
    const weekEl = $("clock-weekdays");
    if (weekEl && days.length) {
      const labels = days.slice(0, 7).map((day, idx) => {
        const short = weekdayShortPt(day.date);
        let dayNum = "";
        if (day.date && /^\d{4}-\d{2}-\d{2}$/.test(day.date)) {
          dayNum = String(Number(day.date.slice(8, 10)));
        }
        return (
          '<button type="button" class="day-btn' +
          (idx === weatherSelectedIdx ? " is-active" : "") +
          '" data-day-index="' +
          idx +
          '" title="' +
          esc(day.label || "") +
          (day.date ? " · " + day.date : "") +
          '">' +
          '<span class="day">' +
          esc(short) +
          "</span>" +
          '<span class="day-num">' +
          esc(dayNum) +
          "</span>" +
          '<span class="icon-weather-day">' +
          weatherIcon(day.icon || "cloudy") +
          "</span>" +
          "</button>"
        );
      });
      weekEl.innerHTML = labels.join("");
      lastWeekKey = "weather";
    }
    bindWeatherCardInteractions();
    const keep = Math.min(weatherSelectedIdx, Math.max(0, days.length - 1));
    showWeatherDay(keep);
  }

  async function refreshWeather() {
    try {
      const data = await api("/api/weather?force=1");
      applyWeather(data);
    } catch (err) {
      console.warn("clima:", err);
      const cond = $("clock-condition");
      if (cond && !weatherCache) cond.textContent = "clima indisponível";
    }
  }

  function updateCloudClock(isoOptional) {
    const dateEl = $("clock-date");
    const hourEl = $("clock-hour");
    const weekEl = $("clock-weekdays");
    if (!dateEl || !hourEl) return;

    let d;
    if (isoOptional) {
      d = new Date(isoOptional);
      if (Number.isNaN(d.getTime())) d = new Date();
    } else {
      d = new Date();
    }

    const p = partsInTz(d, TZ_BR);

    // Relogio sempre ao vivo; a data so muda se estiver no dia "hoje" selecionado
    hourEl.textContent =
      String(p.hour).padStart(2, "0") + ":" + String(p.minute).padStart(2, "0");
    if (!weatherCache || weatherSelectedIdx === 0) {
      const shortDay = new Intl.DateTimeFormat("pt-BR", {
        timeZone: TZ_BR,
        weekday: "short",
      })
        .format(d)
        .replace(".", "")
        .toUpperCase();
      dateEl.textContent =
        shortDay +
        " " +
        String(p.month).padStart(2, "0") +
        "-" +
        String(p.day).padStart(2, "0");
    }

    if (weekEl && !weatherCache) {
      const weekKey = p.year + "-" + p.month + "-" + p.day;
      if (weekKey !== lastWeekKey) {
        lastWeekKey = weekKey;
        const baseY = Number(p.year);
        const baseM = Number(p.month) - 1;
        const baseD = Number(p.day);
        const labels = [];
        for (let i = 0; i < 7; i++) {
          const nd = new Date(Date.UTC(baseY, baseM, baseD + i, 15, 0, 0));
          const label = new Intl.DateTimeFormat("pt-BR", {
            timeZone: TZ_BR,
            weekday: "short",
          })
            .format(nd)
            .replace(".", "")
            .toUpperCase();
          const dayNum = String(nd.getUTCDate());
          labels.push(
            '<button type="button" class="day-btn" data-day-index="' +
              i +
              '" tabindex="-1">' +
              '<span class="day">' +
              esc(label) +
              "</span>" +
              '<span class="day-num">' +
              esc(dayNum) +
              "</span>" +
              '<span class="icon-weather-day">' +
              weatherIcon("clear") +
              "</span>" +
              "</button>"
          );
        }
        weekEl.innerHTML = labels.join("");
      }
    }
  }

  const TOKEN_KEY = "servercron_token";

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch (_) {
      return "";
    }
  }

  function setToken(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (_) {}
  }

  let loginMode = "email";
  let isAdmin = false;

  function applyAdminUI() {
    const usersNav = document.querySelector('.nav-btn[data-tab="users"]');
    if (usersNav) usersNav.hidden = !isAdmin;
    const activeTab = document.querySelector(".tab.active");
    if (!isAdmin && activeTab && activeTab.id === "tab-users") {
      switchTab("dashboard");
    }
  }

  // A tela de login vive fora do painel (static/login.html) — nao ha mais dialog
  // aqui. Sessao invalida/ausente redireciona para /login (evita mostrar a
  // interface do painel a quem nao esta autenticado).
  function goToLogin() {
    setToken("");
    location.replace("/login");
  }

  async function api(path, opts) {
    const headers = { Accept: "application/json", "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers["X-ServerCRON-Token"] = token;
    const res = await fetch(path, { headers, ...opts });
    if (res.status === 401) {
      goToLogin();
      return new Promise(() => {}); // navegando embora; nunca resolve
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || res.statusText || "erro");
    }
    return data;
  }

  function switchTab(name) {
    if (name === "users" && !isAdmin) name = "dashboard";
    document.querySelectorAll(".nav-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === name);
    });
    document.querySelectorAll(".tab").forEach((el) => {
      el.classList.toggle("active", el.id === "tab-" + name);
    });
    const meta = TITLES[name] || TITLES.dashboard;
    $("page-title").textContent = meta[0];
    $("page-sub").textContent = meta[1];
    if (name === "dashboard" && window.__statsLast) {
      requestAnimationFrame(() => renderStatsDashboard(window.__statsLast));
    }
    if (name === "relatorio") {
      if (window.__reportLast) {
        requestAnimationFrame(() => renderReport(window.__reportLast));
      } else {
        loadReport();
      }
    }
    if (name === "users" && isAdmin) {
      loadUsers();
    }
  }

  let usersCache = [];

  async function loadUsers() {
    const body = $("users-body");
    try {
      const data = await api("/api/users");
      usersCache = data.users || [];
      renderUsers();
    } catch (err) {
      if (body) body.innerHTML = `<tr><td colspan="4" class="muted">Erro: ${esc(err.message)}</td></tr>`;
    }
  }

  function renderUsers() {
    const body = $("users-body");
    if (!body) return;
    if (!usersCache.length) {
      body.innerHTML = '<tr><td colspan="4" class="muted">Nenhum email cadastrado ainda.</td></tr>';
      return;
    }
    body.innerHTML = usersCache
      .map((u) => {
        const active = u.is_active
          ? '<span class="badge on">TRUE</span>'
          : '<span class="badge off">FALSE</span>';
        return `<tr>
          <td><code>${esc(u.email)}</code></td>
          <td>${esc(u.nome || "-")}</td>
          <td>${active}</td>
          <td class="actions">
            <button type="button" class="btn sm" data-toggle-user="${esc(u.email)}">${u.is_active ? "Desativar" : "Ativar"}</button>
            <button type="button" class="btn sm danger" data-delete-user="${esc(u.email)}">Remover</button>
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderScripts(filter) {
    const q = (filter || "").trim().toLowerCase();
    const rows = scriptsCache.filter((s) => !q || s.nome_automacao.toLowerCase().includes(q) || (s.area || "").toLowerCase().includes(q));
    const body = $("scripts-body");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7" class="muted">Nenhuma automacao.</td></tr>';
      return;
    }
    body.innerHTML = rows
      .map((s) => {
        const isLive = runningCache.some(
          (r) => String(r.nome_automacao).toLowerCase() === String(s.nome_automacao).toLowerCase()
        );
        const active = s.is_active
          ? '<span class="badge on">TRUE</span>'
          : '<span class="badge off">FALSE</span>';
        const file = s.available_locally
          ? '<span class="badge ok">OK</span>'
          : '<span class="badge err">em falta</span>';
        const liveBadge = isLive ? ' <span class="badge run">ao vivo</span>' : "";
        const cronClass = s.is_valid_cron ? "" : "badge err";
        return `<tr>
          <td><strong>${esc(s.nome_automacao)}</strong>${liveBadge}</td>
          <td>${esc(s.area || "-")}</td>
          <td class="${cronClass}"><code>${esc(s.cron_schedule || "-")}</code></td>
          <td>${active}</td>
          <td>${file}</td>
          <td><code>${esc(formatDateBr(s.next_run))}</code></td>
          <td class="actions">
            <button type="button" class="btn sm primary" data-run="${esc(s.nome_automacao)}" ${
              s.available_locally && !isLive ? "" : "disabled"
            }>${isLive ? "A rodar" : "Rodar"}</button>
            ${
              isLive
                ? `<button type="button" class="btn sm danger" data-kill="${esc(s.nome_automacao)}">Parar</button>`
                : ""
            }
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderLive(running, maxConcurrent) {
    runningCache = running || [];
    const box = $("live-list");
    const cap = $("live-capacity");
    if (cap) {
      cap.textContent =
        runningCache.length +
        " de " +
        (maxConcurrent || 5) +
        " vagas";
    }
    if (!box) return;
    if (!runningCache.length) {
      box.innerHTML = '<p class="muted">Nenhuma automacao em execucao.</p>';
      return;
    }
    box.innerHTML = runningCache
      .map(
        (r) => `<div class="live-item">
          <div>
            <strong>${esc(r.nome_automacao)}</strong>
            <span>
              início ${esc(formatDateBr(r.started, true))}<br>
              ${esc(r.reason || "-")} · pid ${esc(r.pid || "-")}
            </span>
          </div>
          <button type="button" class="btn sm danger" data-kill="${esc(r.nome_automacao)}">Parar</button>
        </div>`
      )
      .join("");
  }

  function renderPending(pending, queueCount) {
    const box = $("pending-list");
    if (!box) return;
    const rows = pending || [];
    if (!rows.length) {
      box.innerHTML =
        '<p class="muted">Nenhuma atrasada. Catch-up em dia' +
        (queueCount ? " · fila total: " + queueCount : "") +
        ".</p>";
      return;
    }
    box.innerHTML = rows
      .map(
        (p) => `<div class="pending-item">
          <div>
            <strong>${esc(p.nome_automacao)}</strong>
            <div class="meta">
              <div>Área: ${esc(p.area || "-")}</div>
              <div>Cron: <code>${esc(p.cron_schedule || "")}</code></div>
              <div>Previsto: ${esc(formatDateBr(p.scheduled_for, true))}</div>
            </div>
          </div>
          <div class="late">atrasada ${esc(p.overdue_human || "")}</div>
        </div>`
      )
      .join("");
  }

  function renderQueue(queue) {
    const box = $("queue-list");
    if (!box) return;
    const rows = (queue || []).filter((j) => !j.due).slice(0, 30);
    if (!rows.length) {
      box.innerHTML = '<p class="muted">Nenhum horario futuro na fila ainda.</p>';
      return;
    }
    box.innerHTML = rows
      .map(
        (j) => `<div class="pending-item">
          <div>
            <strong>${esc(j.nome_automacao)}</strong>
            <div class="meta">
              <div>${esc(j.reason || "scheduled")} · área ${esc(j.area || "-")}</div>
              <div>Agendado: ${esc(formatDateBr(j.scheduled_for, true))}</div>
            </div>
          </div>
          <div class="late" style="color:var(--muted)">em ${esc(
            j.wait_sec != null ? (j.wait_sec < 60 ? j.wait_sec + "s" : Math.floor(j.wait_sec / 60) + " min") : "-"
          )}</div>
        </div>`
      )
      .join("");
  }

  function renderHistory(rows) {
    const body = $("history-body");
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6" class="muted">Sem historico.</td></tr>';
      return;
    }
    body.innerHTML = rows
      .map((h) => {
        const st =
          h.status === "success"
            ? "ok"
            : h.status === "no_data"
              ? "nodata"
              : h.status === "running"
                ? "run"
                : "err";
        const label =
          h.status === "success"
            ? "success (0)"
            : h.status === "no_data"
              ? "no_data (2) nada para processar"
              : h.status === "running"
                ? "a rodar"
                : h.status === "error"
                  ? "error (1)"
                  : esc(h.status);
        return `<tr>
          <td><code>${esc(formatDateBr(h.start_time, true))}</code></td>
          <td>${esc(h.nome_automacao)}</td>
          <td>${esc(h.trigger_reason)}</td>
          <td><span class="badge ${st}">${label}</span></td>
          <td>${h.duration_sec != null ? esc(h.duration_sec) + "s" : "-"}</td>
          <td>
            <button type="button" class="btn sm ghost" data-out="${esc(h.id)}">${
              h.exit_code != null ? esc(h.exit_code) : "-"
            }</button>
          </td>
        </tr>`;
      })
      .join("");
    body._history = rows;
  }

  function inventoryLines(inv, dir) {
    if (!inv) return ["Sem dados de leitura."];
    const pasta = dir || inv.automacoes_dir || "pasta das automacoes";
    return [
      "Pasta: " + pasta,
      "Automacoes .py na pasta: " + (inv.py_on_disk ?? 0),
      "Áreas encontradas: " + (inv.areas_count ?? 0),
      "Na planilha: " + (inv.sheet_total ?? 0) +
        " (" + (inv.sheet_active ?? 0) + " ativas, " +
        (inv.sheet_inactive ?? 0) + " desativadas)",
      "Localizadas: " + (inv.sheet_located ?? 0),
      "Em falta: " + (inv.sheet_missing ?? 0),
      inv.registro_exists
        ? "Planilha registro_automacoes.xlsx: encontrada"
        : "Planilha registro_automacoes.xlsx: não encontrada",
    ];
  }

  function applyInventory(status, flashMsg) {
    const inv = status.inventory || {
      py_on_disk: status.py_on_disk,
      sheet_total: status.total_scripts,
      sheet_active: status.active_scripts,
      sheet_inactive: status.inactive_scripts,
      sheet_located: status.located_scripts,
      sheet_missing: status.missing_scripts,
      areas_count: status.areas_count,
      registro_exists: status.registro_exists,
      automacoes_dir: status.automacoes_dir,
    };
    $("stat-py-disk").textContent = inv.py_on_disk ?? status.py_on_disk ?? "-";
    $("stat-total").textContent = inv.sheet_total ?? status.total_scripts ?? "-";
    $("stat-active").textContent = inv.sheet_active ?? status.active_scripts ?? "-";
    $("stat-inactive").textContent = inv.sheet_inactive ?? status.inactive_scripts ?? "-";
    $("stat-running").textContent =
      (status.running_count != null ? status.running_count : (status.running || []).length) +
      "/" +
      (status.max_concurrent || 5);
    if ($("stat-queue")) {
      $("stat-queue").textContent = status.queue_count ?? (status.queue || []).length ?? 0;
    }
    if ($("stat-pending")) {
      $("stat-pending").textContent = status.pending_count ?? (status.pending || []).length ?? "-";
    }
    if ($("max-concurrent-label")) {
      $("max-concurrent-label").textContent = String(status.max_concurrent || 5);
    }
    const summary = $("scan-summary");
    if (summary) {
      summary.innerHTML = inventoryLines(inv, status.automacoes_dir)
        .map((line) => "<li>" + esc(line) + "</li>")
        .join("");
    }
    const flash = $("config-flash");
    if (flash && flashMsg) {
      flash.hidden = false;
      flash.innerHTML = String(flashMsg)
        .split(/\n+/)
        .filter(Boolean)
        .map((line) => "<span>" + esc(line.trim()) + "</span>")
        .join("");
    }
  }

  function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function ensureChartTooltip(canvas) {
    const wrap = canvas.parentElement;
    if (!wrap) return null;
    let tip = wrap.querySelector(".chart-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "chart-tooltip";
      tip.setAttribute("role", "tooltip");
      wrap.appendChild(tip);
    }
    return tip;
  }

  function tooltipBreakdownHtml(title, success, error, noData) {
    const total = (success || 0) + (error || 0) + (noData || 0);
    return (
      '<div class="tt-title">' +
      esc(title) +
      "</div>" +
      '<div class="tt-row"><span class="st-ok">success</span><span>' +
      esc(success || 0) +
      "</span></div>" +
      '<div class="tt-row"><span class="st-err">error</span><span>' +
      esc(error || 0) +
      "</span></div>" +
      '<div class="tt-row"><span class="st-nodata">no_data</span><span>' +
      esc(noData || 0) +
      "</span></div>" +
      '<div class="tt-total">total ' +
      esc(total) +
      "</div>"
    );
  }

  function showChartTooltip(canvas, html, clientX, clientY) {
    const tip = ensureChartTooltip(canvas);
    const wrap = canvas.parentElement;
    if (!tip || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    tip.innerHTML = html;
    tip.classList.add("is-visible");
    let left = clientX - rect.left;
    let top = clientY - rect.top;
    const tipW = tip.offsetWidth || 160;
    left = Math.max(tipW / 2 + 4, Math.min(rect.width - tipW / 2 - 4, left));
    top = Math.max(8, top);
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  function hideChartTooltip(canvas) {
    const tip = canvas && canvas.parentElement && canvas.parentElement.querySelector(".chart-tooltip");
    if (tip) tip.classList.remove("is-visible");
  }

  function bindChartHover(canvas, kind) {
    if (!canvas || canvas._hoverBound) return;
    canvas._hoverBound = true;
    canvas.style.cursor = "default";

    canvas.addEventListener("mousemove", (ev) => {
      const hit = canvas._hit;
      if (!hit) return;
      const rect = canvas.getBoundingClientRect();
      const x = ((ev.clientX - rect.left) / rect.width) * (hit.cssW || rect.width);
      const y = ((ev.clientY - rect.top) / rect.height) * (hit.cssH || rect.height);

      if (kind === "bars" && hit.bars) {
        const bar = hit.bars.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
        if (!bar) {
          canvas.style.cursor = "default";
          hideChartTooltip(canvas);
          if (canvas._hoverIndex != null) {
            canvas._hoverIndex = null;
            drawStackedTrend(canvas, hit.series, null);
          }
          return;
        }
        canvas.style.cursor = "pointer";
        if (canvas._hoverIndex !== bar.i) {
          canvas._hoverIndex = bar.i;
          drawStackedTrend(canvas, hit.series, bar.i);
        }
        const row = hit.series[bar.i] || {};
        const rawDay = String(row.day || "");
        // hit.series.day pode ser data ISO (grafico do Dashboard) ou rotulo ja
        // formatado tipo "23/07"/"jan" (grafico do Relatorio) — so reformatar no 1o caso.
        const title = /^\d{4}-\d{2}-\d{2}$/.test(rawDay)
          ? formatDateBr(rawDay + "T12:00:00", false).split(" - ").pop()
          : rawDay || "-";
        showChartTooltip(
          canvas,
          tooltipBreakdownHtml(title, row.success, row.error, row.no_data),
          ev.clientX,
          ev.clientY
        );
        return;
      }

      if (kind === "pie" && hit.slices) {
        const dx = x - hit.cx;
        const dy = y - hit.cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < hit.innerR || dist > hit.r) {
          canvas.style.cursor = "default";
          hideChartTooltip(canvas);
          return;
        }
        let ang = Math.atan2(dy, dx);
        // canvas arcs start at -PI/2 in our draw; atan2 is from +x
        // our slices stored with same absolute angles as drawn
        const slice = hit.slices.find((s) => {
          let a0 = s.start;
          let a1 = s.end;
          // normalize ang into [a0, a1] spanning possibly across
          let a = ang;
          while (a < a0) a += Math.PI * 2;
          while (a > a0 + Math.PI * 2) a -= Math.PI * 2;
          return a >= a0 && a < a1;
        });
        if (!slice) {
          canvas.style.cursor = "default";
          hideChartTooltip(canvas);
          return;
        }
        canvas.style.cursor = "pointer";
        const t = hit.totals || {};
        showChartTooltip(
          canvas,
          tooltipBreakdownHtml(
            slice.label + " · " + slice.n + " (" + slice.pct + "%)",
            t.success,
            t.error,
            t.no_data
          ),
          ev.clientX,
          ev.clientY
        );
      }
    });

    canvas.addEventListener("mouseleave", () => {
      canvas.style.cursor = "default";
      hideChartTooltip(canvas);
      if (kind === "bars" && canvas._hoverIndex != null) {
        canvas._hoverIndex = null;
        const hit = canvas._hit;
        if (hit && hit.series) drawStackedTrend(canvas, hit.series, null);
      }
    });
  }

  function drawStackedTrend(canvas, series, hoverIndex) {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 640;
    const cssH = 250;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    // t=40 (nao 24): a barra mais alta encosta exatamente no topo do grafico
    // (topY = pad.t), entao precisa desse respiro pra caber o numero do total
    // + o ponto da linha de tendencia por cima dela sem colidir.
    const pad = { t: 40, r: 14, b: 48, l: 42 };
    const w = cssW - pad.l - pad.r;
    const h = cssH - pad.t - pad.b;
    const rows = (series || []).map((r) => {
      const success = Number(r.success || 0);
      const error = Number(r.error || 0);
      const no_data = Number(r.no_data || 0);
      return {
        day: r.day,
        success: success,
        error: error,
        no_data: no_data,
        total: success + error + no_data,
      };
    });
    const maxY = Math.max(1, ...rows.map((r) => r.total || 0));
    const n = Math.max(1, rows.length);
    const gap = Math.max(6, Math.floor(w / n / 8));
    const barW = Math.max(12, (w - gap * (n - 1)) / n);

    const colOk = cssVar("--ok", "#22c55e");
    const colErr = cssVar("--err", "#ef4444");
    const colNd = cssVar("--warn", "#eab308");
    const grid = cssVar("--border", "#2a2a2a");
    const muted = cssVar("--muted", "#9a9a9a");
    const text = cssVar("--text", "#f2f2f2");

    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.l, pad.t);
    ctx.lineTo(pad.l, pad.t + h);
    ctx.lineTo(pad.l + w, pad.t + h);
    ctx.stroke();

    ctx.fillStyle = muted;
    ctx.font = "600 12px Sora, Segoe UI, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const val = Math.round((maxY * i) / 4);
      const y = pad.t + h - (h * i) / 4;
      ctx.fillText(String(val), pad.l - 8, y);
      ctx.strokeStyle = grid;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + w, y);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Rotulos (dia embaixo, total em cima) sao "selective direct labels": com poucas
    // barras cabem todos, mas com muitas (ex.: 30 dias) o texto de cada barra colide
    // com o vizinho — em vez de desenhar em todas, so desenha em barras espacadas o
    // suficiente pra nao sobrepor (a barra em si continua sendo desenhada sempre).
    const dayLabels = rows.map((row) => {
      const rawDay = String(row.day || "");
      if (/^\d{4}-\d{2}-\d{2}$/.test(rawDay)) {
        return rawDay.slice(8, 10) + "/" + rawDay.slice(5, 7);
      }
      if (/^\d{4}-\d{2}$/.test(rawDay)) {
        return rawDay.slice(5, 7) + "/" + rawDay.slice(2, 4);
      }
      return rawDay || "-";
    });

    ctx.font = "700 15px Sora, Segoe UI, sans-serif";
    const maxDayLabelW = dayLabels.reduce((m, l) => Math.max(m, ctx.measureText(l).width), 0);
    ctx.font = "700 14px Sora, Segoe UI, sans-serif";
    const maxTotalLabelW = rows.reduce((m, r) => Math.max(m, ctx.measureText(String(r.total)).width), 0);

    const slot = barW + gap;
    const dayStep = Math.max(1, Math.ceil((maxDayLabelW + 10) / slot));
    const totalStep = Math.max(1, Math.ceil((maxTotalLabelW + 8) / slot));
    const lastIdx = n - 1;

    // O ultimo rotulo e sempre forcado (mostra o dia mais recente), mas se o rotulo
    // "regular" logo antes dele estiver perto demais, os dois colidem (ex.: "03/08"
    // grudado em "04/08") — suprime esse regular vizinho nesse caso.
    const suppressNearEnd = (step, requiredW) => {
      if (lastIdx <= 0) return -1;
      let idx = Math.floor(lastIdx / step) * step;
      if (idx === lastIdx) idx -= step;
      if (idx < 0) return -1;
      return (lastIdx - idx) * slot < requiredW ? idx : -1;
    };
    const daySuppressIdx = suppressNearEnd(dayStep, maxDayLabelW + 10);
    const totalSuppressIdx = suppressNearEnd(totalStep, maxTotalLabelW + 8);

    const bars = [];
    rows.forEach((row, i) => {
      const x = pad.l + i * (barW + gap);
      let y = pad.t + h;
      const parts = [
        ["success", colOk],
        ["error", colErr],
        ["no_data", colNd],
      ];
      const dim = hoverIndex != null && hoverIndex !== i;
      const total = row.total;
      parts.forEach(([key, color]) => {
        const v = Number(row[key] || 0);
        if (!v) return;
        const bh = (v / maxY) * h;
        y -= bh;
        ctx.globalAlpha = dim ? 0.35 : 1;
        ctx.fillStyle = color;
        ctx.fillRect(x, y, barW, Math.max(bh, 0.5));
        ctx.globalAlpha = 1;
      });
      bars.push({ i: i, x: x, y: pad.t, w: barW, h: h });
      if (hoverIndex === i) {
        ctx.strokeStyle = text;
        ctx.globalAlpha = 0.4;
        ctx.strokeRect(x + 0.5, pad.t + 0.5, barW - 1, h - 1);
        ctx.globalAlpha = 1;
      }
      const showTotal =
        total > 0 &&
        ((i % totalStep === 0 && i !== totalSuppressIdx) || i === lastIdx || i === hoverIndex);
      if (showTotal) {
        const topY = pad.t + h - (total / maxY) * h;
        ctx.fillStyle = dim ? muted : text;
        ctx.font = "700 14px Sora, Segoe UI, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        // -11 (nao -4) pra sobrar espaco do ponto da linha de tendencia, que fica
        // exatamente no topo da barra (mesmo Y usado pelo total). O piso e so pra
        // nao cortar o texto no topo do canvas, nao precisa mais depender de pad.t
        // (esse respiro ja foi reservado no valor de pad.t acima).
        ctx.fillText(String(total), x + barW / 2, Math.max(16, topY - 11));
      }
      const showDay = (i % dayStep === 0 && i !== daySuppressIdx) || i === lastIdx || i === hoverIndex;
      if (showDay) {
        ctx.fillStyle = dim ? muted : text;
        ctx.font = "700 15px Sora, Segoe UI, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(dayLabels[i] || "-", x + barW / 2, pad.t + h + 12);
      }
    });

    // Linha de tendencia: liga o topo de cada barra (total do dia) pra mostrar
    // se a serie esta subindo ou descendo, sem depender so da altura isolada
    // de cada barra. Halo na cor do fundo por baixo pra nao sumir quando passa
    // por cima de um segmento colorido da barra.
    if (rows.some((r) => r.total > 0) && n > 1) {
      const accent = cssVar("--accent", "#8a6a15");
      const surface = cssVar("--bg-elev", "#ffffff");
      const points = rows.map((row, i) => ({
        x: pad.l + i * (barW + gap) + barW / 2,
        y: pad.t + h - (row.total / maxY) * h,
      }));

      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.strokeStyle = surface;
      ctx.lineWidth = 4.5;
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      ctx.stroke();
      ctx.globalAlpha = 1;

      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      ctx.stroke();

      points.forEach((p, i) => {
        const isHover = hoverIndex === i;
        const r = isHover ? 5 : 3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + 1.5, 0, Math.PI * 2);
        ctx.fillStyle = surface;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fillStyle = accent;
        ctx.fill();
      });
    }

    if (!rows.some((r) => r.total > 0)) {
      ctx.fillStyle = muted;
      ctx.font = "14px Sora, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("Sem execucoes neste periodo", pad.l + w / 2, pad.t + h / 2);
    }

    canvas._hit = { kind: "bars", cssW: cssW, cssH: cssH, bars: bars, series: rows };
    bindChartHover(canvas, "bars");
  }

  function drawPie(canvas, totals) {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 280;
    const cssH = 220;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const slicesMeta = [
      { key: "success", label: "success", color: cssVar("--ok", "#22c55e"), n: Number(totals.success || 0) },
      { key: "error", label: "error", color: cssVar("--err", "#ef4444"), n: Number(totals.error || 0) },
      { key: "no_data", label: "no_data", color: cssVar("--warn", "#eab308"), n: Number(totals.no_data || 0) },
    ];
    const total = slicesMeta.reduce((a, s) => a + s.n, 0);
    const cx = cssW * 0.38;
    const cy = cssH / 2;
    const r = Math.min(cssW, cssH) * 0.32;
    const innerR = r * 0.55;
    const muted = cssVar("--muted", "#9a9a9a");
    const text = cssVar("--text", "#f2f2f2");
    const hitSlices = [];

    if (!total) {
      ctx.strokeStyle = cssVar("--border", "#2a2a2a");
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = muted;
      ctx.font = "13px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("Sem dados", cx, cy);
      canvas._hit = { kind: "pie", cssW: cssW, cssH: cssH, slices: [], totals: totals, cx: cx, cy: cy, r: r, innerR: innerR };
      bindChartHover(canvas, "pie");
      return;
    }

    let angle = -Math.PI / 2;
    slicesMeta.forEach((s) => {
      if (!s.n) return;
      const sweep = (s.n / total) * Math.PI * 2;
      const start = angle;
      const end = angle + sweep;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, end);
      ctx.closePath();
      ctx.fillStyle = s.color;
      ctx.fill();
      hitSlices.push({
        key: s.key,
        label: s.label,
        n: s.n,
        pct: Math.round((100 * s.n) / total),
        start: start,
        end: end,
        color: s.color,
      });
      angle = end;
    });

    // donut hole
    ctx.beginPath();
    ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
    ctx.fillStyle = cssVar("--bg-soft", "#1a1a1a");
    ctx.fill();
    ctx.fillStyle = text;
    ctx.font = "bold 16px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(total), cx, cy - 6);
    ctx.fillStyle = muted;
    ctx.font = "11px sans-serif";
    ctx.fillText("total", cx, cy + 12);

    let ly = cy - 40;
    slicesMeta.forEach((s) => {
      const pct = total ? Math.round((100 * s.n) / total) : 0;
      ctx.fillStyle = s.color;
      ctx.fillRect(cssW * 0.68, ly, 10, 10);
      ctx.fillStyle = text;
      ctx.font = "12px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(s.label + " " + s.n + " (" + pct + "%)", cssW * 0.68 + 16, ly + 5);
      ly += 28;
    });

    canvas._hit = {
      kind: "pie",
      cssW: cssW,
      cssH: cssH,
      slices: hitSlices,
      totals: totals,
      cx: cx,
      cy: cy,
      r: r,
      innerR: innerR,
    };
    bindChartHover(canvas, "pie");
  }

  function renderStatsDashboard(data) {
    if (!data) return;
    // Recalcula a partir da series do grafico para os numeros baterem 100%
    const series = (data.series || []).map((r) => {
      const success = Number(r.success || 0);
      const error = Number(r.error || 0);
      const no_data = Number(r.no_data || 0);
      return {
        day: r.day,
        success: success,
        error: error,
        no_data: no_data,
        total: success + error + no_data,
      };
    });
    const totals = series.reduce(
      (acc, r) => {
        acc.success += r.success;
        acc.error += r.error;
        acc.no_data += r.no_data;
        acc.total += r.total;
        return acc;
      },
      { success: 0, error: 0, no_data: 0, total: 0 }
    );
    const todayKey = (data.until || "").slice(0, 10);
    const todayRow = series.find((r) => r.day === todayKey) || series[series.length - 1] || {};
    const today = {
      success: todayRow.success || 0,
      error: todayRow.error || 0,
      no_data: todayRow.no_data || 0,
      total: todayRow.total || 0,
    };
    const pct = (n) => (totals.total ? Math.round((1000 * n) / totals.total) / 10 : null);
    const successRate = pct(totals.success);
    const errorRate = pct(totals.error);
    const noDataRate = pct(totals.no_data);

    if ($("stats-today-total")) $("stats-today-total").textContent = today.total ?? 0;
    if ($("stats-today-break")) {
      $("stats-today-break").innerHTML =
        '<span class="st-ok">' +
        today.success +
        " ok</span> · " +
        '<span class="st-err">' +
        today.error +
        " err</span> · " +
        '<span class="st-nodata">' +
        today.no_data +
        " sem dados</span>";
    }
    if ($("stats-period-total")) $("stats-period-total").textContent = totals.total ?? 0;
    if ($("stats-period-break")) {
      $("stats-period-break").innerHTML =
        '<span class="st-ok">' +
        totals.success +
        " ok</span> · " +
        '<span class="st-err">' +
        totals.error +
        " err</span> · " +
        '<span class="st-nodata">' +
        totals.no_data +
        " sem dados</span>";
    }
    if ($("stats-period-range")) {
      const since = String(data.since || "").slice(0, 10);
      const until = String(data.until || "").slice(0, 10);
      const fmt = (iso) => {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso || "-";
        return iso.slice(8, 10) + "/" + iso.slice(5, 7);
      };
      const nDays = Number(data.days || series.length || 7);
      $("stats-period-range").textContent =
        nDays + " dias: " + fmt(since) + " -> " + fmt(until);
    }
    if ($("stats-success-rate")) {
      $("stats-success-rate").textContent =
        successRate == null ? "-" : successRate + "%";
    }
    if ($("stats-error-rate")) {
      $("stats-error-rate").textContent =
        errorRate == null ? "-" : errorRate + "%";
    }
    if ($("stats-nodata-rate")) {
      $("stats-nodata-rate").textContent =
        noDataRate == null ? "-" : noDataRate + "%";
    }

    drawStackedTrend($("chart-trend"), series);
    drawPie($("chart-pie"), totals);


    const body = $("stats-top-body");
    if (body) {
      const rows = data.top_scripts || [];
      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="8" class="muted">Sem dados ainda.</td></tr>';
      } else {
        body.innerHTML = rows
          .map((r) => {
            const pct = (v) => (v == null ? "-" : v + "%");
            return (
              "<tr>" +
              "<td>" +
              esc(r.nome_automacao) +
              "</td>" +
              "<td>" +
              esc(r.total) +
              "</td>" +
              '<td class="st-ok">' +
              esc(r.success) +
              "</td>" +
              '<td class="st-ok">' +
              esc(pct(r.success_pct)) +
              "</td>" +
              '<td class="st-err">' +
              esc(r.error) +
              "</td>" +
              '<td class="st-err">' +
              esc(pct(r.error_pct)) +
              "</td>" +
              '<td class="st-nodata">' +
              esc(r.no_data) +
              "</td>" +
              '<td class="st-nodata">' +
              esc(pct(r.no_data_pct)) +
              "</td>" +
              "</tr>"
            );
          })
          .join("");
      }
    }
  }

  // ---------------------------------------------------------------------
  // Aba Relatorio: totais desde o inicio, comparativo semana/mes (fixo) e
  // drill-down por ano/mes/dia. Fonte: /api/report (CSV, exclui catchup).
  // ---------------------------------------------------------------------

  let reportToken = 0;
  const reportFilters = { year: "", month: "" };

  function reportQuery() {
    const params = [];
    if (reportFilters.year) params.push("year=" + encodeURIComponent(reportFilters.year));
    if (reportFilters.month) params.push("month=" + encodeURIComponent(reportFilters.month));
    return params.length ? "?" + params.join("&") : "";
  }

  function fillSelect(select, values, currentValue, allLabel) {
    const prevValue = currentValue || "";
    select.innerHTML = '<option value="">' + allLabel + "</option>";
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = String(v);
      opt.textContent = typeof v === "number" && v < 10 ? "0" + v : String(v);
      select.appendChild(opt);
    });
    select.value = values.map(String).includes(prevValue) ? prevValue : "";
  }

  async function loadReport() {
    const token = ++reportToken;
    const wrap = $("tab-relatorio");
    if (wrap) wrap.setAttribute("aria-busy", "true");
    try {
      const data = await api("/api/report" + reportQuery());
      if (token !== reportToken) return;
      window.__reportLast = data;
      renderReport(data);
    } catch (err) {
      console.error("report:", err);
      const title = $("report-period-title");
      if (title) title.textContent = "Falha ao carregar: " + (err.message || err);
    } finally {
      if (wrap) wrap.removeAttribute("aria-busy");
    }
  }

  function renderReport(data) {
    if (!data) return;

    const yearSel = $("report-year");
    const monthSel = $("report-month");
    if (yearSel && document.activeElement !== yearSel) {
      fillSelect(yearSel, data.available.years || [], reportFilters.year, "Todos");
    }
    monthSel.disabled = !reportFilters.year;
    if (monthSel && document.activeElement !== monthSel) {
      fillSelect(monthSel, data.available.months || [], reportFilters.month, "Todos");
    }

    const title = $("report-period-title");
    if (title) title.textContent = "Período: " + data.period_label;

    const trendTitle = $("report-trend-title");
    if (trendTitle) {
      const gLabel = { day: "por dia", month: "por mês", none: "" }[data.trend_granularity] || "";
      trendTitle.textContent = data.trend.length
        ? "Execuções " + gLabel
        : "Sem série para este período (dia único selecionado)";
    }

    const p = data.period;
    const tilesRoot = $("report-tiles");
    if (tilesRoot) {
      const tiles = [
        ["Execuções", p.total, ""],
        ["% success", p.taxa_sucesso + "%", "st-ok"],
        ["% error", p.taxa_erro + "%", "st-err"],
        ["% no_data", p.taxa_sem_dados + "%", "st-nodata"],
        ["Automações distintas", p.automacoes_distintas, ""],
        ["Mais executada", p.top_automacao + " (" + p.top_count + "x)", ""],
      ];
      tilesRoot.innerHTML = tiles
        .map(
          ([label, value, cls]) =>
            '<article class="card"><p class="card-label">' +
            esc(label) +
            '</p><p class="card-value ' +
            cls +
            '">' +
            esc(value) +
            "</p></article>"
        )
        .join("");
    }

    const chartWrap = document.getElementById("report-trend-chart")
      ? document.getElementById("report-trend-chart").parentElement
      : null;
    if (data.trend.length) {
      if (chartWrap) chartWrap.hidden = false;
      const series = data.trend.map((r) => ({
        day: r.label,
        success: r.success,
        error: r.error,
        no_data: r.no_data,
      }));
      drawStackedTrend($("report-trend-chart"), series);
    } else if (chartWrap) {
      chartWrap.hidden = true;
    }

    renderCompareCard("report-compare", [
      { title: "Semana atual vs. semana passada", block: data.week },
      { title: "Mês atual vs. mês anterior", block: data.month_cmp },
    ]);
  }

  function deltaCls(value, higherIsBetter) {
    if (value == null || value === 0) return "flat";
    const up = value > 0;
    const good = higherIsBetter ? up : !up;
    return (up ? "up" : "down") + "-" + (good ? "good" : "bad");
  }
  function deltaArrow(value) {
    if (value == null || value === 0) return "→";
    return value > 0 ? "↑" : "↓";
  }
  function fmtDeltaPct(v) {
    if (v == null) return "–";
    const sign = v > 0 ? "+" : v < 0 ? "-" : "";
    return sign + Math.abs(v).toLocaleString("pt-BR") + "%";
  }
  // Numeros grandes com separador de milhar pt-BR (1586 -> "1.586").
  function fmtNum(v) {
    return Number(v || 0).toLocaleString("pt-BR");
  }
  // Delta em pontos percentuais (nao confundir com variacao relativa %).
  function fmtPts(v) {
    const n = Math.round(Math.abs(v || 0) * 10) / 10;
    const sign = v > 0 ? "+" : v < 0 ? "-" : "";
    return sign + n.toLocaleString("pt-BR") + " pts";
  }

  // Veredito resumido do periodo: combina variacao de sucesso/erro/sem_dados
  // (em pontos percentuais) numa unica palavra + cor, pro leigo bater o olho.
  function buildVerdict(block) {
    const dSucc = block.delta_taxa_sucesso || 0;
    const dErr = block.delta_taxa_erro || 0;
    const dNod = block.delta_taxa_sem_dados || 0;
    const score = dSucc - dErr - 0.5 * dNod;
    if (score > 1.5) return { cls: "good", label: "Melhorou", icon: "↑" };
    if (score < -1.5) return { cls: "bad", label: "Piorou", icon: "↓" };
    return { cls: "flat", label: "Estável", icon: "→" };
  }

  // Frase em portugues simples explicando o comparativo, sem exigir que o
  // usuario interprete numeros/percentuais sozinho.
  function buildSummary(block) {
    const c = block.curr;
    const dTotalPct = block.delta_pct_total;
    const dSucc = block.delta_taxa_sucesso || 0;
    const dErr = block.delta_taxa_erro || 0;

    let execPhrase;
    if (dTotalPct == null) {
      execPhrase = "sem execuções no período anterior para comparar";
    } else if (dTotalPct > 0) {
      execPhrase = "<strong>" + fmtNum(dTotalPct) + "% a mais</strong> que no período anterior";
    } else if (dTotalPct < 0) {
      execPhrase = "<strong>" + fmtNum(Math.abs(dTotalPct)) + "% a menos</strong> que no período anterior";
    } else {
      execPhrase = "igual ao período anterior";
    }

    const succPhrase =
      dSucc > 0
        ? 'sucesso <strong class="good">subiu ' + fmtPts(dSucc).replace("+", "") + "</strong>"
        : dSucc < 0
        ? 'sucesso <strong class="bad">caiu ' + fmtPts(dSucc).replace("-", "") + "</strong>"
        : "sucesso ficou igual";

    const errPhrase =
      dErr > 0
        ? 'erro <strong class="bad">subiu ' + fmtPts(dErr).replace("+", "") + "</strong>"
        : dErr < 0
        ? 'erro <strong class="good">caiu ' + fmtPts(dErr).replace("-", "") + "</strong>"
        : "erro ficou igual";

    return (
      "<strong>" +
      fmtNum(c.total) +
      "</strong> execuções neste período, " +
      execPhrase +
      ". A taxa de " +
      succPhrase +
      " e a de " +
      errPhrase +
      "."
    );
  }

  function renderCompareCard(rootId, cards) {
    const root = $(rootId);
    if (!root) return;
    root.innerHTML = "";
    cards.forEach(({ title, block }) => {
      const verdict = buildVerdict(block);
      const rows = [
        {
          label: "Execuções",
          curr: block.curr.total,
          prev: block.prev.total,
          delta: block.delta_pct_total,
          deltaText: fmtDeltaPct(block.delta_pct_total),
          higherIsBetter: true,
          percent: false,
        },
        {
          label: "Taxa de sucesso",
          curr: block.curr.taxa_sucesso,
          prev: block.prev.taxa_sucesso,
          delta: block.delta_taxa_sucesso,
          deltaText: fmtPts(block.delta_taxa_sucesso),
          higherIsBetter: true,
          percent: true,
        },
        {
          label: "Taxa de erro",
          curr: block.curr.taxa_erro,
          prev: block.prev.taxa_erro,
          delta: block.delta_taxa_erro,
          deltaText: fmtPts(block.delta_taxa_erro),
          higherIsBetter: false,
          percent: true,
        },
        {
          label: "Taxa sem dados",
          curr: block.curr.taxa_sem_dados,
          prev: block.prev.taxa_sem_dados,
          delta: block.delta_taxa_sem_dados,
          deltaText: fmtPts(block.delta_taxa_sem_dados),
          higherIsBetter: false,
          percent: true,
        },
      ];

      const card = document.createElement("div");
      card.className = "compare-card";
      card.innerHTML =
        "<h4>" +
        esc(title) +
        '</h4><p class="muted small">Atual ' +
        esc(block.curr_label) +
        " · Anterior " +
        esc(block.prev_label) +
        '</p><span class="cr-verdict ' +
        verdict.cls +
        '"><span class="cr-verdict-icon"></span><span class="cr-verdict-label"></span></span>' +
        '<p class="cr-summary"></p>' +
        '<div class="cr-scores"></div>';
      card.querySelector(".cr-verdict-icon").textContent = verdict.icon;
      card.querySelector(".cr-verdict-label").textContent = verdict.label;
      card.querySelector(".cr-summary").innerHTML = buildSummary(block);

      const scoresRoot = card.querySelector(".cr-scores");
      rows.forEach((r) => {
        const cls = deltaCls(r.delta, r.higherIsBetter);
        const unit = r.percent ? "%" : "";

        const tile = document.createElement("div");
        tile.className = "cr-score";
        tile.innerHTML =
          '<p class="cr-score-label"></p>' +
          '<p class="cr-score-value"></p>' +
          '<p class="cr-score-delta ' +
          cls +
          '"></p>' +
          '<p class="cr-score-prev"></p>';
        tile.querySelector(".cr-score-label").textContent = r.label;
        tile.querySelector(".cr-score-value").textContent = fmtNum(r.curr) + unit;
        tile.querySelector(".cr-score-delta").textContent = deltaArrow(r.delta) + " " + r.deltaText;
        tile.querySelector(".cr-score-prev").textContent = "Antes: " + fmtNum(r.prev) + unit;
        scoresRoot.appendChild(tile);
      });

      root.appendChild(card);
    });
  }

  let statsToken = 0;

  async function refreshStats() {
    const token = ++statsToken;
    const data = await api("/api/stats?days=7");
    if (token !== statsToken) return; // resposta antiga: uma chamada mais nova ja esta em curso
    window.__statsLast = data;
    renderStatsDashboard(data);
  }

  // Uso em polling automatico (refresh() a cada 5s): falha fica so no console,
  // sem incomodar o utilizador com um alerta a cada ciclo.
  function refreshStatsQuiet() {
    return refreshStats().catch((err) => console.warn("stats:", err));
  }

  async function rebuildExcelDashboard() {
    try {
      const data = await api("/api/dashboard/rebuild", { method: "POST" });
      showToast(
        (data && data.hint) ||
          "Excel atualizado a partir do CSV (o CSV nao foi alterado).",
        "ok"
      );
    } catch (err) {
      showToast("Falha ao regenerar Excel: " + (err.message || err), "error");
    }
  }

  let refreshToken = 0;

  async function refresh(flashMsg) {
    const token = ++refreshToken;
    const clock = $("status-clock");
    try {
      const [status, scripts, history] = await Promise.all([
        api("/api/status"),
        api("/api/scripts"),
        api("/api/history?limit=80"),
      ]);
      if (token !== refreshToken) return; // uma chamada mais nova ja resolveu antes desta
      if (clock) clock.classList.remove("is-offline");
      updateCloudClock(status.now);

      applyInventory(status, flashMsg);
      refreshStatsQuiet();

      $("path-home").textContent = status.home || "-";
      $("path-data").textContent = status.data_root || "-";
      $("path-config").textContent = status.config_path || "-";
      $("path-areas").textContent = (status.areas && status.areas.length)
        ? status.areas.join(", ")
        : "(nenhuma area ainda)";
      $("path-xlsx").textContent = status.registro_xlsx;
      $("path-dir").textContent = status.automacoes_dir;
      $("path-sqlite").textContent = status.sqlite_path || "-";
      $("path-csv").textContent = status.history_csv || status.logs_dir || "-";
      $("path-tz").textContent = status.tz_label
        || (status.tz === "America/Sao_Paulo"
          ? "Horário de Brasília (São Paulo)"
          : (status.tz || "-"));
      $("path-reload").textContent = "a cada " + status.reload_minutes + " minuto(s)";
      const lastReload = status.last_reload_at
        ? formatDateBr(status.last_reload_at, true)
        : "-";
      const nextReload = status.next_reload_at
        ? formatDateBr(status.next_reload_at, true)
        : "-";
      $("path-reload-last").textContent = lastReload;
      $("path-reload-next").textContent = nextReload;
      const setReloadEls = (lastId, nextId, cdId) => {
        if ($(lastId)) $(lastId).textContent = lastReload;
        if ($(nextId)) $(nextId).textContent = nextReload;
        const cd = $(cdId);
        if (!cd) return;
        const sec = status.seconds_until_reload;
        if (sec == null) {
          cd.textContent = "";
        } else if (sec <= 0) {
          cd.textContent = "(a atualizar…)";
        } else {
          const m = Math.floor(sec / 60);
          const s = sec % 60;
          cd.textContent =
            "(em " + (m > 0 ? m + "m " : "") + s + "s)";
        }
      };
      setReloadEls("reload-last-top", "reload-next-top", "reload-countdown-top");

      const dirInput = $("input-automacoes-dir");
      if (dirInput && document.activeElement !== dirInput) {
        dirInput.value = status.automacoes_dir || "";
        dirInput.disabled = !!status.automacoes_locked_by_env;
        $("btn-save-dir").disabled = !!status.automacoes_locked_by_env;
        if (status.automacoes_locked_by_env) {
          $("config-msg").textContent =
            "Bloqueado por SERVERCRON_AUTOMAOES_DIR no ambiente.";
        }
      }

      scriptsCache = scripts.scripts || [];
      renderLive(status.running || [], status.max_concurrent);
      renderPending(status.pending || [], status.queue_count || 0);
      renderQueue(status.queue || []);
      renderScripts($("script-search").value);
      renderHistory(history.history || []);
    } catch (err) {
      if (token !== refreshToken) return;
      if (clock) clock.classList.add("is-offline");
      console.error(err);
    }
  }

  function bind() {
    document.querySelectorAll(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    const btnStats = $("btn-refresh-stats");
    if (btnStats) {
      const btnStatsLabel = btnStats.textContent;
      btnStats.addEventListener("click", async () => {
        btnStats.disabled = true;
        btnStats.textContent = "Atualizando…";
        try {
          await refreshStats();
          btnStats.textContent = "Atualizado!";
        } catch (err) {
          console.error("stats:", err);
          btnStats.textContent = "Falha ao atualizar";
        } finally {
          setTimeout(() => {
            btnStats.textContent = btnStatsLabel;
            btnStats.disabled = false;
          }, 1400);
        }
      });
    }

    const reportYearSel = $("report-year");
    const reportMonthSel = $("report-month");
    if (reportYearSel) {
      reportYearSel.addEventListener("change", () => {
        reportFilters.year = reportYearSel.value;
        reportFilters.month = "";
        loadReport();
      });
    }
    if (reportMonthSel) {
      reportMonthSel.addEventListener("change", () => {
        reportFilters.month = reportMonthSel.value;
        loadReport();
      });
    }
    const btnReportClear = $("btn-report-clear");
    if (btnReportClear) {
      btnReportClear.addEventListener("click", () => {
        reportFilters.year = "";
        reportFilters.month = "";
        loadReport();
      });
    }

    const btnExcel = $("btn-rebuild-excel");
    if (btnExcel) {
      btnExcel.addEventListener("click", async () => {
        btnExcel.disabled = true;
        const msg = $("excel-rebuild-msg");
        if (msg) msg.textContent = "A regenerar Excel a partir do CSV…";
        try {
          const data = await api("/api/dashboard/rebuild", { method: "POST" });
          if (msg) {
            msg.textContent =
              (data && data.hint) ||
              "Excel atualizado. Reabra o .xlsx (CSV nao foi alterado).";
          }
        } catch (err) {
          if (msg) msg.textContent = "Falha: " + (err.message || err);
        } finally {
          btnExcel.disabled = false;
        }
      });
    }

    const btnCatchup = $("btn-catchup");
    if (btnCatchup) btnCatchup.addEventListener("click", async () => {
      const btn = $("btn-catchup");
      if (!btn || btn.disabled || btn.classList.contains("is-loading")) return;

      const labelOriginal = "Atualizar fila do dia";
      const t0 = performance.now();
      let tickTimer = null;
      let finishedOk = false;

      const setLoadingLabel = () => {
        const sec = ((performance.now() - t0) / 1000).toFixed(1);
        btn.textContent = "A atualizar… " + sec + "s";
      };

      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.classList.add("is-loading");
      setLoadingLabel();
      tickTimer = setInterval(setLoadingLabel, 100);

      try {
        const [res] = await Promise.all([
          api("/api/catchup", { method: "POST", body: "{}" }),
          new Promise((r) => setTimeout(r, 450)),
        ]);
        const elapsedMid = ((performance.now() - t0) / 1000).toFixed(1);
        btn.textContent = "A refletir… " + elapsedMid + "s";
        const msg =
          "Fila do dia atualizada\n" +
          (res.pending_count ?? 0) +
          " atrasada(s) · " +
          (res.upcoming_count ?? 0) +
          " próxima(s)\n" +
          "Fila: " +
          (res.queue_due ?? 0) +
          " prontas / " +
          (res.queue_waiting ?? 0) +
          " a aguardar hora";
        await refresh(msg);
        const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
        finishedOk = true;
        btn.textContent = "Atualizado (" + elapsed + "s)";
        setTimeout(() => {
          if (!btn.classList.contains("is-loading")) {
            btn.textContent = labelOriginal;
          }
        }, 2200);
      } catch (e) {
        const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
        showToast("Falha ao atualizar fila apos " + elapsed + "s: " + e.message, "error");
        btn.textContent = labelOriginal;
      } finally {
        if (tickTimer) clearInterval(tickTimer);
        btn.classList.remove("is-loading");
        btn.removeAttribute("aria-busy");
        btn.disabled = false;
        if (!finishedOk) {
          btn.textContent = labelOriginal;
        } else if (
          btn.textContent.startsWith("A atualizar") ||
          btn.textContent.startsWith("A refletir")
        ) {
          btn.textContent = labelOriginal;
        }
      }
    });

    $("form-automacoes-dir").addEventListener("submit", async (e) => {
      e.preventDefault();
      const msgEl = $("config-msg");
      const raw = ($("input-automacoes-dir").value || "").trim();
      if (!raw) {
        msgEl.textContent = "Indique um caminho.";
        return;
      }
      try {
        const res = await api("/api/config", {
          method: "POST",
          body: JSON.stringify({ automacoes_dir: raw }),
        });
        const inv = res.inventory || {};
        const flash =
          "Pasta alterada\n" +
          (inv.py_on_disk ?? 0) +
          " .py · planilha " +
          (inv.sheet_total ?? 0) +
          " (" +
          (inv.sheet_active ?? 0) +
          " ativas / " +
          (inv.sheet_inactive ?? 0) +
          " desativadas)\n" +
          "Localizadas: " +
          (inv.sheet_located ?? 0) +
          " · Em falta: " +
          (inv.sheet_missing ?? 0);
        msgEl.textContent = flash.replace(/\n/g, " · ");
        await refresh(flash);
      } catch (err) {
        msgEl.textContent = "Erro: " + err.message;
      }
    });

    $("script-search").addEventListener(
      "input",
      debounce((e) => renderScripts(e.target.value), 150)
    );

    const userAddForm = $("user-add-form");
    if (userAddForm) {
      userAddForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const emailEl = $("user-add-email");
        const nomeEl = $("user-add-nome");
        const errEl = $("user-add-error");
        const email = emailEl.value.trim();
        const submitBtn = userAddForm.querySelector('button[type="submit"]');
        errEl.hidden = true;
        if (submitBtn) submitBtn.disabled = true;
        try {
          await api("/api/users", {
            method: "POST",
            body: JSON.stringify({ email, nome: nomeEl.value.trim() }),
          });
          emailEl.value = "";
          nomeEl.value = "";
          await loadUsers();
          showToast("Email adicionado: " + email, "ok");
        } catch (err) {
          errEl.textContent = err.message;
          errEl.hidden = false;
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    const changeTokenBtn = $("btn-change-token");
    if (changeTokenBtn) {
      changeTokenBtn.addEventListener("click", async () => {
        try {
          await api("/api/logout", { method: "POST" });
        } catch (_) {}
        goToLogin();
      });
    }

    window.addEventListener(
      "resize",
      debounce(() => {
        if (window.__statsLast) renderStatsDashboard(window.__statsLast);
        if (window.__reportLast) renderReport(window.__reportLast);
      }, 150)
    );

    document.body.addEventListener("click", async (e) => {
      const runBtn = e.target.closest("[data-run]");
      if (runBtn) {
        const nome = runBtn.getAttribute("data-run");
        const key = "run:" + nome;
        if (runBtn.disabled || inFlightActions.has(key)) return;
        inFlightActions.add(key);
        const prevLabel = runBtn.textContent;
        runBtn.disabled = true;
        runBtn.textContent = "A iniciar...";
        try {
          await api("/api/run", {
            method: "POST",
            body: JSON.stringify({ nome_automacao: nome }),
          });
          await refresh();
        } catch (err) {
          showToast(err.message, "error");
          runBtn.disabled = false;
          runBtn.textContent = prevLabel;
        } finally {
          inFlightActions.delete(key);
        }
        return;
      }
      const killBtn = e.target.closest("[data-kill]");
      if (killBtn) {
        const nome = killBtn.getAttribute("data-kill");
        const key = "kill:" + nome;
        if (killBtn.disabled || inFlightActions.has(key)) return;
        inFlightActions.add(key);
        const prevLabel = killBtn.textContent;
        killBtn.disabled = true;
        killBtn.textContent = "A parar...";
        try {
          await api("/api/kill", {
            method: "POST",
            body: JSON.stringify({ nome_automacao: nome }),
          });
          await refresh();
        } catch (err) {
          showToast(err.message, "error");
          killBtn.disabled = false;
          killBtn.textContent = prevLabel;
        } finally {
          inFlightActions.delete(key);
        }
        return;
      }
      const outBtn = e.target.closest("[data-out]");
      if (outBtn) {
        const id = Number(outBtn.getAttribute("data-out"));
        const rows = $("history-body")._history || [];
        const row = rows.find((r) => r.id === id);
        $("dialog-title").textContent = row ? row.nome_automacao : "Saida";
        $("dialog-output").textContent = (row && row.output) || "(sem saida)";
        $("output-dialog").showModal();
        return;
      }
      const toggleUserBtn = e.target.closest("[data-toggle-user]");
      if (toggleUserBtn) {
        const email = toggleUserBtn.getAttribute("data-toggle-user");
        const key = "toggle-user:" + email;
        if (toggleUserBtn.disabled || inFlightActions.has(key)) return;
        inFlightActions.add(key);
        toggleUserBtn.disabled = true;
        try {
          await api("/api/users/" + encodeURIComponent(email) + "/toggle", { method: "POST" });
          await loadUsers();
        } catch (err) {
          showToast(err.message, "error");
        } finally {
          inFlightActions.delete(key);
          toggleUserBtn.disabled = false;
        }
        return;
      }
      const deleteUserBtn = e.target.closest("[data-delete-user]");
      if (deleteUserBtn) {
        const email = deleteUserBtn.getAttribute("data-delete-user");
        const key = "delete-user:" + email;
        if (deleteUserBtn.disabled || inFlightActions.has(key)) return;
        inFlightActions.add(key);
        deleteUserBtn.disabled = true;
        try {
          await api("/api/users/" + encodeURIComponent(email), { method: "DELETE" });
          await loadUsers();
          showToast("Email removido: " + email, "ok");
        } catch (err) {
          showToast(err.message, "error");
        } finally {
          inFlightActions.delete(key);
          deleteUserBtn.disabled = false;
        }
        return;
      }
    });
  }

  async function checkAuthStatus() {
    const el = $("auth-status");
    try {
      const token = getToken();
      const headers = { Accept: "application/json" };
      if (token) headers["X-ServerCRON-Token"] = token;
      const res = await fetch("/api/auth", { headers });
      const data = await res.json().catch(() => ({}));
      loginMode = data.login_mode === "token" ? "token" : "email";
      isAdmin = !!data.is_admin;
      applyAdminUI();
      if (!el) return data;
      if (!data.auth_required) {
        el.textContent = "Painel aberto (nenhum email cadastrado nem token definido — ok para uso local).";
      } else if (data.authenticated && data.email) {
        el.textContent = "Logado como " + data.email + ".";
      } else if (data.authenticated) {
        el.textContent = "Protegido por token — sessao atual autenticada.";
      } else if (loginMode === "email") {
        el.textContent = "Protegido por login de email — nenhuma sessao ativa.";
      } else {
        el.textContent = "Protegido por token — token em falta ou invalido.";
      }
      return data;
    } catch (_) {
      if (el) el.textContent = "Nao foi possivel verificar (servidor offline?).";
      return null;
    }
  }

  async function ensureAuthenticated() {
    const data = await checkAuthStatus();
    if (data && data.auth_required && !data.authenticated) {
      goToLogin();
      return new Promise(() => {}); // navegando embora
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      localStorage.removeItem("servercron_theme");
    } catch (_) {}
    bind();
    await ensureAuthenticated();
    updateCloudClock();
    clockTimer = setInterval(() => updateCloudClock(), 1000);
    refreshWeather();
    weatherTimer = setInterval(refreshWeather, 15 * 60 * 1000);
    refresh();
    pollTimer = setInterval(refresh, 5000);
    // refresh() ja chama refreshStats() a cada ciclo — nao duplicar com outro
    // timer independente (duas chamadas concorrentes podiam responder fora
    // de ordem e pisar o grafico com dados antigos).
  });
})();
