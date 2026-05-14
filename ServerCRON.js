/* --- Server: Cron SPA (/cron/) + Uploaders Jinja (/) --- */
(function () {
    /** Cron JSON APIs under /cron in unified mode; same helper para ambos os portais. */
    function getApiBase() {
        const path = window.location.pathname || "/";
        const pv =
            (typeof document !== "undefined" &&
                document.body &&
                document.body.getAttribute("data-portal-view")) ||
            "";
        if (path === "/cron" || path.startsWith("/cron/") || pv === "cron") {
            return window.location.origin + "/cron";
        }
        return window.location.origin;
    }

    /**
     * Página Uploaders (data-portal-view=uploaders): login é form POST — runCronPanel() não corre.
     * Isto garante logs no Console e confirma que o clique/submit disparou.
     */
    function initUploadersPortal() {
        const pv = document.body && document.body.getAttribute("data-portal-view");
        console.log("[Server] portal=uploaders", {
            pathname: window.location.pathname,
            dataPortalView: pv || "(vazio)",
            dica: "Sem mais logs aqui é normal; o envio é POST ao ServerUploaders. Veja também o log Python [AUTH] request_token.",
        });
        const formRt = document.querySelector('form[action*="request_token"]');
        if (formRt) {
            formRt.addEventListener("submit", function () {
                const inp = formRt.querySelector('input[name="username"]');
                const u = inp ? String(inp.value || "").trim() : "";
                console.log("[login] Uploaders → POST request_token", formRt.action, "| usuário:", u);
            });
            console.log("[login] listener OK: formulário request_token (Uploaders)");
        } else {
            console.log("[login] nenhum form request_token (ex.: já logado ou outra página).");
        }
        const formV = document.querySelector('form[action*="verify_token"]');
        if (formV) {
            formV.addEventListener("submit", function () {
                console.log("[login] Uploaders → POST verify_token", formV.action);
            });
        }
    }

    function runCronPanel() {
        const TAB_TITLES = {
            dashboard: 'Dashboard',
            upload: 'Uploaders',
            scripts: 'Scripts',
            live: 'Ao vivo',
            pending: 'Pendentes',
            history: 'Histórico',
            jobs: 'Agendados',
        };
        let currentTab = 'dashboard';
        let statusData = null;
        let _liveHighlightName = '';
        /** @type {Array<{name: string, count: number}> | null} */
        let areasSummaryCache = null;
        /** @type {string | null} */
        let selectedAreaName = null;
        /** @type {object[] | null} */
        let currentAreaScripts = null;
        let serverOnline = true;
        let _pollTimer = null;
        let isAdmin = false;
        let currentUser = null;
        let _scriptSearchTimer = null;
        let _uploadersEmbedReady = false;

        const THEME_KEY = 'server_cron_theme';

        function escapeHtml(s) {
            if (s == null || s === undefined) return '';
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }
        try {
            const __t0 = localStorage.getItem(THEME_KEY);
            if (__t0 === 'light' || __t0 === 'dark') document.documentElement.setAttribute('data-theme', __t0);
        } catch (e) {}

        function applyRoleUi() {
            document.querySelectorAll('.adm-only').forEach((el) => {
                el.classList.toggle('hidden', !isAdmin);
                el.setAttribute('aria-hidden', isAdmin ? 'false' : 'true');
            });
        }

        function applyTheme(theme) {
            const t = theme === 'light' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', t);
            try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
            const btn = document.getElementById('theme-toggle-btn');
            if (btn) btn.textContent = t === 'light' ? 'Modo escuro' : 'Modo claro';
        }

        function toggleTheme() {
            const cur = document.documentElement.getAttribute('data-theme') || 'dark';
            applyTheme(cur === 'dark' ? 'light' : 'dark');
        }

        function showLoginUi() {
            document.getElementById('login-overlay')?.classList.remove('hidden');
            document.getElementById('app-shell')?.classList.add('hidden');
        }

        function hideLoginUi() {
            document.getElementById('login-overlay')?.classList.add('hidden');
            document.getElementById('app-shell')?.classList.remove('hidden');
        }

        async function refreshAuthStatus() {
            try {
                const r = await fetch(getApiBase() + '/api/auth/status', { credentials: 'same-origin' });
                const d = await r.json();
                if (d.logged_in) {
                    currentUser = d.username;
                    isAdmin = d.role === 'admin';
                    const su = document.getElementById('session-user');
                    const sr = document.getElementById('session-role');
                    if (su) su.textContent = d.username || '—';
                    if (sr) sr.textContent = isAdmin ? 'Administrador' : 'Somente visualização';
                    applyRoleUi();
                    return true;
                }
            } catch (e) { console.error(e); }
            currentUser = null;
            isAdmin = false;
            applyRoleUi();
            return false;
        }

        async function doLogout() {
            clearTimeout(_pollTimer);
            _pollTimer = null;
            _dashboardBooted = false;
            _uploadersEmbedReady = false;
            const _upFr = document.getElementById('uploaders-embed-frame');
            if (_upFr) _upFr.src = 'about:blank';
            await fetch(getApiBase() + '/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
            showLoginUi();
            document.getElementById('login-step-token')?.classList.add('hidden');
            document.getElementById('login-msg').textContent = '';
        }

        function closeSidebar() {
            document.getElementById('sidebar')?.classList.remove('sidebar-open');
            document.getElementById('sidebar-backdrop')?.classList.remove('is-open');
        }
        function openSidebar() {
            document.getElementById('sidebar')?.classList.add('sidebar-open');
            document.getElementById('sidebar-backdrop')?.classList.add('is-open');
        }

        // --- UI Logic ---
        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            document.getElementById('tab-' + tab).classList.add('active');
            const navItem = document.querySelector(`.nav-item[data-tab="${tab}"]`);
            if (navItem) navItem.classList.add('active');
            
            currentTab = tab;
            const title = TAB_TITLES[tab] || tab;
            const pt = document.getElementById('page-title');
            const ptm = document.getElementById('page-title-mobile');
            if (pt) pt.textContent = title;
            if (ptm) ptm.textContent = title;
            closeSidebar();
            
            // Initial loads for specific tabs
            if (tab === 'dashboard') masterPoll();
            if (tab === 'scripts') loadScriptsTab();
            if (tab === 'history') loadHistory();
            if (tab === 'jobs') loadJobs();
            if (tab === 'pending') loadPending();
            if (tab === 'upload') setupUploadersEmbed();
            if (tab !== 'live') _liveHighlightName = '';
            if (tab === 'live' && statusData) renderLive(statusData);
        }

        function goToLiveForPython(name) {
            _liveHighlightName = String(name || '').trim().toLowerCase();
            switchTab('live');
        }

        function toast(msg, type = 'info') {
            const container = document.getElementById('toasts');
            const d = document.createElement('div');
            
            const colors = {
                success: 'bg-green-500 border-green-400',
                error: 'bg-red-500 border-red-400',
                info: 'bg-blue-500 border-blue-400',
                warning: 'bg-orange-500 border-orange-400'
            };
            
            d.className = `px-6 py-3 rounded-xl shadow-2xl border-l-4 text-white text-sm font-bold flex items-center space-x-3 animate-bounce-in ${colors[type] || colors.info}`;
            d.innerHTML = `
                <span>${msg}</span>
            `;
            
            container.appendChild(d);
            setTimeout(() => {
                d.style.opacity = '0';
                d.style.transform = 'translateX(20px)';
                setTimeout(() => d.remove(), 300);
            }, 4000);
        }

        // --- API Helpers ---
        async function api(path, opts = {}) {
            try {
                const fetchOpts = { credentials: 'same-origin', ...opts };
                const r = await fetch(getApiBase() + path, fetchOpts);
                if (r.status === 401) {
                    showLoginUi();
                    toast('Sessão expirada — faça login novamente.', 'warning');
                    return null;
                }
                if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
                const ct = (r.headers.get('content-type') || '').toLowerCase();
                const raw = await r.text();
                if (ct.includes('application/json') || /^\s*[\[{]/.test(raw)) {
                    try {
                        return JSON.parse(raw);
                    } catch (e) {
                        console.error(`API JSON parse (${path}):`, e);
                        return null;
                    }
                }
                return raw;
            } catch (e) {
                console.error(`API Error (${path}):`, e);
                return null;
            }
        }

        function _uploadersEmbedFallbackSrc() {
            const u = new URL('/', window.location.origin);
            u.searchParams.set('cron_embed', '1');
            return u.toString();
        }

        async function setupUploadersEmbed() {
            if (_uploadersEmbedReady) return;
            const frame = document.getElementById('uploaders-embed-frame');
            const hint = document.getElementById('uploaders-duo-hint');
            if (!frame) return;
            try {
                const info = await api('/api/server/info');
                const duoFlag = info.servercron_duo_ports;
                const duo = !!(info && (duoFlag === true || String(duoFlag).toLowerCase() === 'true' || duoFlag === 1));
                const rawBase = info && info.uploaders_base_url != null ? String(info.uploaders_base_url).trim() : '';
                const base = rawBase || window.location.origin;
                if (hint) hint.classList.toggle('hidden', !duo);
                const url = new URL('/', base);
                url.searchParams.set('cron_embed', '1');
                frame.src = url.toString();
            } catch (e) {
                console.error(e);
                frame.src = _uploadersEmbedFallbackSrc();
            }
            _uploadersEmbedReady = true;
        }

        // --- Formatters ---
        function fmtTime(s) {
            s = Math.floor(s);
            if (s < 60) return s + 's';
            if (s < 3600) { 
                const m = Math.floor(s / 60); 
                return m + 'm' + String(s % 60).padStart(2, '0') + 's'; 
            }
            const h = Math.floor(s / 3600); 
            const m = Math.floor((s % 3600) / 60); 
            return h + 'h' + String(m).padStart(2, '0') + 'm';
        }

        function fmtDate(iso) { 
            if (!iso) return '--'; 
            const d = new Date(iso); 
            return d.toLocaleString('pt-BR', { 
                day: '2-digit', month: '2-digit', 
                hour: '2-digit', minute: '2-digit', second: '2-digit' 
            }); 
        }

        function countdown(iso) { 
            if (!iso) return '--'; 
            const diff = Math.max(0, Math.floor((new Date(iso) - Date.now()) / 1000)); 
            if (diff === 0) return 'agora'; 
            return fmtTime(diff); 
        }

        function getPriorityBadge(prio) {
            const colors = {
                1: 'bg-red-500/20 text-red-500 border-red-500/30',
                2: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
                3: 'bg-blue-500/20 text-blue-500 border-blue-500/30'
            };
            return `<span class="px-2 py-0.5 rounded text-[10px] font-black border ${colors[prio] || colors[2]}">P${prio}</span>`;
        }

        function getLoadColorClass(percent) {
            const p = Number(percent) || 0;
            if (p < 60) return 'text-green-500';
            if (p < 85) return 'text-yellow-500';
            return 'text-red-500';
        }

        // --- Rendering Logic ---

        /** Same card shell as CPU/RAM/Executando/Na Fila (icon 5×5, 2xl value). */
        function metricCardHtml(label, value, sub, colorClass, iconPath) {
            return `
                <div class="bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-xl sm:rounded-2xl hover:bg-white/[0.04] transition-all group">
                    <div class="flex justify-between items-start mb-3 sm:mb-4 gap-2">
                        <div class="p-2 bg-white/5 rounded-lg group-hover:bg-white/10 transition-colors shrink-0">
                            <svg class="w-5 h-5 text-gray-400 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"></path></svg>
                        </div>
                        <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest text-right leading-tight">${label}</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-black ${colorClass} tracking-tighter mb-1 tabular-nums">${value}</div>
                    <div class="text-[10px] text-gray-500 font-medium uppercase truncate">${sub}</div>
                </div>`;
        }

        const _HIST_ICONS = {
            success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
            error: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
        };

        function renderHistoryMetricCards(containerEl, block) {
            if (!containerEl) return;
            if (!block || !block.total) {
                containerEl.innerHTML = `
                    <div class="sm:col-span-3 bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-xl sm:rounded-2xl">
                        <p class="text-sm text-gray-500 text-center">Nenhuma execução neste período.</p>
                    </div>`;
                return;
            }
            const c = block.counts || {};
            const p = block.percent || {};
            const rows = [
                { key: 'success', label: 'Sucesso', color: 'text-green-500', icon: _HIST_ICONS.success },
                { key: 'error', label: 'Erro', color: 'text-red-500', icon: _HIST_ICONS.error },
            ];
            containerEl.innerHTML = rows.map(({ key, label, color, icon }) => {
                const pct = p[key] != null ? p[key] : 0;
                const cnt = c[key] != null ? c[key] : 0;
                return metricCardHtml(label, pct + '%', cnt + ' run' + (cnt === 1 ? '' : 's'), color, icon);
            }).join('');
        }

        function _renderByScriptTable(byScript) {
            const tb = document.getElementById('dash-stats-by-script');
            if (!tb) return;
            const rows = Object.entries(byScript || {})
                .sort((a, b) => (b[1].total || 0) - (a[1].total || 0))
                .slice(0, 25);
            if (!rows.length) {
                tb.innerHTML = '<tr><td colspan="5" class="px-3 py-6 text-center text-gray-600">Sem dados no período de 7 dias.</td></tr>';
                return;
            }
            tb.innerHTML = rows.map(([name, o]) => `
                <tr class="hover:bg-white/[0.02]">
                    <td class="px-3 py-2 font-medium text-white max-w-[220px] min-[1920px]:max-w-[320px] truncate" title="${escapeHtml(name)}">${escapeHtml(name)}</td>
                    <td class="px-3 py-2 text-right text-green-400 font-mono">${o.success ?? 0}</td>
                    <td class="px-3 py-2 text-right text-red-400 font-mono">${o.error ?? 0}</td>
                    <td class="px-3 py-2 text-right text-gray-400 font-mono">${o.total ?? 0}</td>
                </tr>
            `).join('');
        }

        function _ymdDiffDays(a, b) {
            const pa = a.split('-').map(Number);
            const pb = b.split('-').map(Number);
            const ta = Date.UTC(pa[0], pa[1] - 1, pa[2]);
            const tb = Date.UTC(pb[0], pb[1] - 1, pb[2]);
            return Math.round((tb - ta) / 86400000);
        }

        function _spTodayYmd() {
            return new Intl.DateTimeFormat('en-CA', {
                timeZone: 'America/Sao_Paulo',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
            }).format(new Date());
        }

        function _aggregateHistoryEntries(entries) {
            const counts = { success: 0, error: 0 };
            const by_script = {};
            for (const e of entries) {
                const st = (e.status || '').toLowerCase();
                if (st === 'killed') continue;
                const pn = e.python_name || '?';
                if (!by_script[pn]) {
                    by_script[pn] = { success: 0, error: 0, total: 0 };
                }
                by_script[pn].total++;
                if (st === 'success') {
                    counts.success++;
                    by_script[pn].success++;
                } else if (st === 'error') {
                    counts.error++;
                    by_script[pn].error++;
                }
            }
            const total = counts.success + counts.error;
            const pct = {
                success: total ? Math.round(1000 * counts.success / total) / 10 : 0,
                error: total ? Math.round(1000 * counts.error / total) / 10 : 0,
            };
            return { total, counts, percent: pct, by_script };
        }

        /** Fallback se GET /api/history/stats não existir (Server antigo) ou falhar. */
        async function buildHistoryStatsFromHistoryList(scriptFilter) {
            let url = '/api/history?limit=1000';
            if (scriptFilter) url += '&script=' + encodeURIComponent(scriptFilter);
            const pack = await api(url);
            if (!pack || !Array.isArray(pack.history)) return null;
            const todayYmd = _spTodayYmd();
            const todayList = [];
            const weekList = [];
            for (const h of pack.history) {
                const ymd = (h.start_time && h.start_time.length >= 10) ? h.start_time.slice(0, 10) : null;
                if (!ymd) continue;
                if (ymd === todayYmd) todayList.push(h);
                const diff = _ymdDiffDays(ymd, todayYmd);
                if (diff >= -6 && diff <= 0) weekList.push(h);
            }
            return {
                today: _aggregateHistoryEntries(todayList),
                last_7_days: _aggregateHistoryEntries(weekList),
                max_stored: pack.max_stored ?? '—',
            };
        }

        async function loadDashboardHistoryStats() {
            const elT = document.getElementById('dash-history-today-cards');
            const elW = document.getElementById('dash-history-week-cards');
            if (!elT || !elW) return;
            const q = (document.getElementById('dash-stats-script-filter')?.value || '').trim();
            let path = '/api/history/stats';
            if (q) path += '?script=' + encodeURIComponent(q);
            let d = await api(path);
            if (!d || typeof d !== 'object' || !('today' in d)) {
                d = await buildHistoryStatsFromHistoryList(q);
            }
            const mx = document.getElementById('dash-stats-max');
            if (mx) mx.textContent = String(d?.max_stored ?? '—');
            const td = document.getElementById('dash-stats-today-date');
            if (td) td.textContent = '(' + new Date().toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' }) + ')';
            if (!d) {
                elT.innerHTML = elW.innerHTML = '<div class="sm:col-span-3 text-center text-red-400 text-sm py-4">Falha ao carregar estatísticas.</div>';
                return;
            }
            renderHistoryMetricCards(elT, d.today);
            renderHistoryMetricCards(elW, d.last_7_days);
            _renderByScriptTable(d.last_7_days?.by_script);
        }

        function renderStats(d) {
            const s = d.server_metrics;
            const container = document.getElementById('stats-grid');
            const cpuColor = getLoadColorClass(s.cpu_percent);
            const ramColor = getLoadColorClass(s.ram_percent);
            
            const stats = [
                { label: 'CPU', value: s.cpu_percent + '%', sub: 'Processamento', color: cpuColor, icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
                { label: 'RAM', value: s.ram_percent + '%', sub: `${s.ram_used_gb}GB / ${s.ram_total_gb}GB`, color: ramColor, icon: 'M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z' },
                { label: 'Executando', value: d.running_count, sub: `de ${d.max_concurrent} slots`, color: 'text-green-500', icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
                { label: 'Na Fila', value: d.queued_count, sub: 'Ordem por prioridade e horário (cron)', color: 'text-orange-500', icon: 'M13 5l7 7-7 7M6 5l7 7-7 7' }
            ];

            container.innerHTML = stats.map(st => `
                <div class="bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-xl sm:rounded-2xl hover:bg-white/[0.04] transition-all group">
                    <div class="flex justify-between items-start mb-3 sm:mb-4 gap-2">
                        <div class="p-2 bg-white/5 rounded-lg group-hover:bg-white/10 transition-colors shrink-0">
                            <svg class="w-5 h-5 text-gray-400 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${st.icon}"></path></svg>
                        </div>
                        <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest text-right leading-tight">${st.label}</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-black ${st.color} tracking-tighter mb-1 tabular-nums">${st.value}</div>
                    <div class="text-[10px] text-gray-500 font-medium uppercase truncate">${st.sub}</div>
                </div>
            `).join('');
        }

        function renderDashRunning(procs) {
            const container = document.getElementById('dash-running');
            document.getElementById('running-count-label').textContent = `${procs.length} ativos`;
            
            if (!procs.length) { 
                container.innerHTML = '<div class="py-12 text-center text-gray-500 text-xs uppercase tracking-widest">Silêncio no ServerCron...</div>'; 
                return; 
            }

            container.innerHTML = `
                <table class="w-full min-w-[520px] text-left border-collapse">
                    <thead>
                        <tr class="text-[10px] uppercase tracking-widest text-gray-500 border-b border-white/5">
                            <th class="px-4 sm:px-6 py-3">Script</th>
                            <th class="px-4 sm:px-6 py-3">Tempo</th>
                            <th class="px-4 sm:px-6 py-3">RAM</th>
                            <th class="px-4 sm:px-6 py-3 text-right">Ação</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                        ${procs.map(p => `
                            <tr class="hover:bg-white/[0.02] transition-colors">
                                <td class="px-6 py-4">
                                    <div class="text-sm font-bold text-white">${p.python_name}</div>
                                    <div class="text-[10px] text-gray-500 uppercase">${p.area_name}</div>
                                </td>
                                <td class="px-6 py-4 font-mono text-xs text-yellow-500">${fmtTime(p.running_time_seconds)}</td>
                                <td class="px-6 py-4 font-mono text-xs text-gray-400">${p.rss_mb}MB</td>
                                <td class="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                                    <button type="button" data-py="${escapeHtml(p.python_name)}" onclick="goToLiveForPython(this.getAttribute('data-py'))" class="text-[10px] font-bold uppercase tracking-tighter rounded-lg border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-sky-300 hover:bg-sky-500/20 hover:text-sky-100">Ao vivo</button>
                                    <button type="button" onclick="killPid(${p.pid})" class="adm-only text-[10px] font-black text-red-500 hover:text-red-400 uppercase tracking-tighter">Encerrar</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderDashQueued(q) {
            const container = document.getElementById('dash-queued');
            if (!q.length) { 
                container.innerHTML = '<div class="py-8 text-center text-gray-600 text-[10px] uppercase tracking-widest">Fila vazia</div>'; 
                return; 
            }

            container.innerHTML = q.map(p => `
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-white/5 rounded-xl border border-white/5 group hover:border-yellow-500/30 transition-all">
                    <div class="flex items-start sm:items-center gap-3 min-w-0">
                        <div class="text-sm font-black text-gray-500 shrink-0">#${p.position}</div>
                        <div class="min-w-0">
                            <div class="text-sm sm:text-base font-bold text-white truncate">${p.python_name}</div>
                            <div class="text-[10px] text-gray-500 uppercase truncate">${p.area_name}</div>
                        </div>
                    </div>
                    <div class="flex items-center justify-between sm:justify-end gap-3 pl-8 sm:pl-0">
                        ${getPriorityBadge(p.priority)}
                        <span class="text-sm font-mono text-orange-500 font-bold tabular-nums">${fmtTime(p.waiting_seconds)}</span>
                    </div>
                </div>
            `).join('');
        }

        function updateReloadCountdown(iso) {
            const t = countdown(iso);
            const el = document.getElementById('bq-countdown');
            const elm = document.getElementById('bq-countdown-mobile');
            if (el) el.textContent = t;
            if (elm) elm.textContent = t;
        }

        // --- Master Polling ---
        async function masterPoll() {
            const d = await api('/api/status');
            if (!d) { 
                setOnlineStatus(false); 
                return; 
            }
            setOnlineStatus(true);
            statusData = d;
            
            // Badge Live
            const badgeLiveDot = document.getElementById('badge-live-dot');
            if (d.running_count > 0) badgeLiveDot.classList.remove('hidden');
            else badgeLiveDot.classList.add('hidden');

            const lastSyncTime = new Date().toLocaleTimeString('pt-BR');
            const lr = document.getElementById('last-refresh');
            const lrm = document.getElementById('last-refresh-mobile');
            if (lr) lr.textContent = lastSyncTime;
            if (lrm) lrm.textContent = lastSyncTime;

            if (d.next_hot_reload_iso) {
                updateReloadCountdown(d.next_hot_reload_iso);
            }

            if (currentTab === 'dashboard') { 
                renderStats(d); 
                renderDashRunning(d.running_processes); 
                renderDashQueued(d.queued_processes); 
                loadDashboardHistoryStats();
            }
            if (currentTab === 'live') renderLive(d);
        }

        function pollLoop() {
            masterPoll().finally(() => {
                const interval = document.hidden ? 10000 : 2000;
                _pollTimer = setTimeout(pollLoop, interval);
            });
        }

        function setOnlineStatus(online) {
            serverOnline = online;
            const dot = document.getElementById('status-dot');
            const lbl = document.getElementById('status-label');
            if (online) { 
                dot.className = 'w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]'; 
                lbl.textContent = 'Sistema Online'; 
            } else { 
                dot.className = 'w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'; 
                lbl.textContent = 'Server offline'; 
            }
        }

        // --- Live Tab ---
        function renderLive(d) {
            const tb = document.getElementById('live-tbody');
            if (!d.running_processes.length) { 
                tb.innerHTML = '<tr><td colspan="7" class="py-20 text-center text-gray-500 text-xs uppercase tracking-widest">Nenhum processo ativo no momento</td></tr>'; 
                return; 
            }
            const want = (_liveHighlightName || '').toLowerCase();
            tb.innerHTML = d.running_processes.map(p => `
                <tr data-live-python="${escapeHtml(p.python_name)}" class="hover:bg-white/[0.02] transition-colors text-xs ${want && (p.python_name || '').toLowerCase() === want ? 'ring-2 ring-inset ring-yellow-500/50 bg-yellow-500/[0.08]' : ''}">
                    <td class="px-6 py-4 font-bold text-white">${p.python_name}</td>
                    <td class="px-6 py-4 uppercase text-[10px] text-gray-400">${p.area_name}</td>
                    <td class="px-6 py-4 font-mono text-gray-500">${p.pid}</td>
                    <td class="px-6 py-4">${getPriorityBadge(p.priority)}</td>
                    <td class="px-6 py-4 font-mono text-yellow-500">${fmtTime(p.running_time_seconds)}</td>
                    <td class="px-6 py-4 font-mono text-gray-400">
                        <div class="flex flex-col">
                            <span>RAM: ${p.rss_mb}MB</span>
                            <span class="text-[9px] text-gray-600">CPU: ${p.cpu_percent}%</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                        <button type="button" data-py="${escapeHtml(p.python_name)}" onclick="goToLiveForPython(this.getAttribute('data-py'))" class="rounded-lg border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[10px] font-bold uppercase tracking-tighter text-sky-300 hover:bg-sky-500/20 hover:text-sky-100">Ao vivo</button>
                        <button type="button" onclick="killPid(${p.pid})" class="adm-only px-3 py-1 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 rounded-lg text-[10px] font-bold transition-all">Kill</button>
                    </td>
                </tr>
            `).join('');
            if (want) {
                requestAnimationFrame(() => {
                    for (const tr of tb.querySelectorAll('tr[data-live-python]')) {
                        if ((tr.getAttribute('data-live-python') || '').toLowerCase() === want) {
                            tr.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                            break;
                        }
                    }
                });
            }
        }

        // --- Scripts Tab (summary + one area at a time) ---
        async function loadScriptsTab() {
            await loadAreasSummary();
            if (!areasSummaryCache || !areasSummaryCache.length) {
                document.getElementById('area-chips').innerHTML = '';
                document.getElementById('areas-container').innerHTML = '<div class="py-20 text-center text-gray-500 uppercase tracking-widest">Nenhuma área no cadastro</div>';
                document.getElementById('badge-scripts').textContent = '0';
                return;
            }
            if (!selectedAreaName || !areasSummaryCache.some((a) => a.name === selectedAreaName)) {
                selectedAreaName = areasSummaryCache[0].name;
            }
            renderAreaChips();
            const q = (document.getElementById('script-search')?.value || '').trim().toLowerCase();
            if (q) {
                onScriptSearchInput();
            } else {
                await loadAreaScripts(selectedAreaName);
            }
        }

        async function loadAreasSummary() {
            const d = await api('/api/areas/summary');
            if (!d || !d.areas) return;
            areasSummaryCache = d.areas;
            const total = areasSummaryCache.reduce((acc, a) => acc + (a.count || 0), 0);
            document.getElementById('badge-scripts').textContent = String(total);
        }

        function renderAreaChips() {
            const el = document.getElementById('area-chips');
            if (!areasSummaryCache) return;
            el.innerHTML = areasSummaryCache.map((a) => {
                const active = a.name === selectedAreaName;
                return `
                    <button type="button" data-area="${encodeURIComponent(a.name)}"
                        class="area-chip shrink-0 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${active ? 'border-yellow-500 bg-yellow-500/15 text-yellow-400' : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20'}">
                        ${a.name} <span class="opacity-60">(${a.count})</span>
                    </button>`;
            }).join('');
            el.querySelectorAll('.area-chip').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const name = decodeURIComponent(btn.getAttribute('data-area') || '');
                    if (name && name !== selectedAreaName) {
                        selectedAreaName = name;
                        const searchEl = document.getElementById('script-search');
                        if (searchEl) searchEl.value = '';
                        document.getElementById('script-search-hint')?.classList.add('hidden');
                        renderAreaChips();
                        loadAreaScripts(name);
                    }
                });
            });
        }

        async function loadAreaScripts(areaName) {
            const loading = document.getElementById('area-scripts-loading');
            const box = document.getElementById('areas-container');
            loading.classList.remove('hidden');
            box.innerHTML = '';
            const q = encodeURIComponent(areaName);
            const scripts = await api('/api/scripts/by-area?area=' + q);
            loading.classList.add('hidden');
            if (!scripts || !scripts.length) {
                currentAreaScripts = [];
                box.innerHTML = '<div class="py-16 text-center text-gray-500 text-xs uppercase tracking-widest">Nenhum script nesta área</div>';
                return;
            }
            currentAreaScripts = scripts;
            renderScriptCards(scripts, { globalMode: false });
        }

        function onScriptSearchInput() {
            clearTimeout(_scriptSearchTimer);
            _scriptSearchTimer = setTimeout(async () => {
                const el = document.getElementById('script-search');
                const hint = document.getElementById('script-search-hint');
                const q = (el?.value || '').trim().toLowerCase();
                if (!q) {
                    hint?.classList.add('hidden');
                    if (selectedAreaName) await loadAreaScripts(selectedAreaName);
                    return;
                }
                hint?.classList.remove('hidden');
                hint.textContent = 'Buscando em todas as áreas…';
                const scripts = await api('/api/scripts/search?q=' + encodeURIComponent(q));
                if (!scripts || !Array.isArray(scripts)) return;
                currentAreaScripts = scripts;
                hint.textContent = `Busca global: ${scripts.length} resultado(s)`;
                renderScriptCards(scripts, { globalMode: true });
            }, 300);
        }

        function renderScriptCards(scripts, opts) {
            opts = opts || {};
            const globalMode = !!opts.globalMode;
            const list = scripts;
            const runCls = isAdmin
                ? 'px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black text-[10px] font-black rounded-lg transition-all'
                : 'hidden';
            const killCls = isAdmin
                ? 'touch-target sm:min-h-0 sm:min-w-0 p-2 text-red-500 hover:bg-red-500/10 rounded-lg transition-colors'
                : 'hidden';

            const html = list.map((s) => {
                let statusHtml = '';
                if (s.is_running) statusHtml = '<span class="flex items-center space-x-1.5 text-[10px] font-black text-green-500 uppercase"><span class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span><span>Rodando</span></span>';
                else if (s.is_queued) statusHtml = '<span class="text-[10px] font-black text-orange-500 uppercase">Na Fila</span>';
                else if (!s.available_locally) statusHtml = '<span class="text-[10px] font-black text-red-500 uppercase">Sem Arquivo</span>';
                else if (s.is_active) statusHtml = '<span class="text-[10px] font-black text-blue-500 uppercase">Ativo</span>';
                else statusHtml = '<span class="text-[10px] font-black text-gray-600 uppercase">Inativo</span>';

                const cronSourceBadge = s.cron_source === 'cobranca_xlsx'
                    ? '<span class="text-[8px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 ml-1 align-middle whitespace-nowrap">CRON planilha cobrança</span>'
                    : '';

                const escName = String(s.python_name).replace(/'/g, "\\'");
                const areaLine = globalMode
                    ? `<div class="text-[10px] font-bold uppercase tracking-wider text-amber-400/95 mb-1">${escapeHtml(s.area_name)}</div>`
                    : '';

                return `
                    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 bg-white/[0.02] border border-white/5 rounded-xl hover:border-white/20 transition-all group">
                        <div class="flex items-start gap-3 flex-1 min-w-0">
                            ${getPriorityBadge(s.priority)}
                            <div class="min-w-0 flex-1">
                                ${areaLine}
                                <div class="text-sm font-bold text-white truncate" title="${escapeHtml(s.objetivo || '')}">${escapeHtml(s.python_name)}</div>
                                <div class="text-[10px] font-mono text-gray-500 flex flex-wrap items-center gap-x-1 gap-y-1">${escapeHtml(s.cron_raw || 'ON DEMAND')}${cronSourceBadge}</div>
                            </div>
                        </div>
                        <div class="flex flex-wrap items-center justify-between sm:justify-end gap-2 sm:gap-4">
                            ${statusHtml}
                            <div class="flex items-center gap-2 min-w-0">
                                ${s.is_running ? `<button type="button" onclick="killByName('${escName}')" class="${killCls}"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>` : ''}
                                ${s.available_locally ? `<button type="button" onclick="runScript('${escName}')" class="${runCls}">Executar</button>` : ''}
                            </div>
                        </div>
                    </div>`;
            }).join('');

            document.getElementById('areas-container').innerHTML = html || '<div class="py-12 text-center text-gray-500 text-xs">Nenhum script encontrado</div>';
        }

        // --- Pending Tab ---
        async function loadPending() {
            const d = await api('/api/pending'); 
            if (!d) return;
            
            const badge = document.getElementById('badge-pending');
            if (d.total > 0) {
                badge.textContent = d.total;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }

            document.getElementById('pending-date').textContent = d.date;
            const tb = document.getElementById('pending-tbody');
            
            if (!d.pending.length) { 
                tb.innerHTML = '<tr><td colspan="6" class="py-20 text-center text-gray-500 text-xs uppercase tracking-widest">Tudo em dia por aqui!</td></tr>'; 
                return; 
            }

            tb.innerHTML = d.pending.map(p => `
                <tr class="hover:bg-white/[0.02] transition-colors text-xs">
                    <td class="px-6 py-4 font-bold text-white">${p.python_name}</td>
                    <td class="px-6 py-4 uppercase text-[10px] text-gray-400">${p.area_name}</td>
                    <td class="px-6 py-4 font-mono text-gray-500">${p.cron_raw}</td>
                    <td class="px-6 py-4 font-bold text-orange-500">${p.expected_time}</td>
                    <td class="px-6 py-4">${getPriorityBadge(p.priority)}</td>
                    <td class="px-6 py-4 text-right">
                        ${p.available_locally && isAdmin ? `<button onclick="runScript('${p.python_name}')" class="px-4 py-1.5 bg-yellow-500 hover:bg-yellow-400 text-black text-[10px] font-black rounded-lg transition-all">Executar</button>` : p.available_locally ? '<span class="text-[10px] text-gray-500">Somente admin</span>' : '<span class="text-gray-600">Sem arquivo</span>'}
                    </td>
                </tr>
            `).join('');
        }

        // --- History Tab ---
        async function loadHistory() {
            const script = document.getElementById('hist-script').value;
            const status = document.getElementById('hist-status').value;
            let url = '/api/history?limit=100';
            if (script) url += '&script=' + encodeURIComponent(script);
            if (status) url += '&status=' + status;
            
            const d = await api(url); 
            if (!d) return;
            
            const tb = document.getElementById('hist-tbody');
            if (!d.history.length) { 
                tb.innerHTML = '<tr><td colspan="6" class="py-20 text-center text-gray-500 uppercase tracking-widest">Histórico vazio</td></tr>'; 
                return; 
            }

            tb.innerHTML = d.history.map(h => {
                const displayStatus = (h.status || '').toLowerCase();
                const statusColors = {
                    success: 'text-green-500 bg-green-500/10 border-green-500/20',
                    error: 'text-red-500 bg-red-500/10 border-red-500/20',
                    killed: 'text-orange-500 bg-orange-500/10 border-orange-500/20',
                    no_data: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
                };
                return `
                    <tr class="hover:bg-white/[0.02] transition-colors">
                        <td class="px-6 py-4">
                            <div class="font-bold text-white">${h.python_name}</div>
                            <div class="text-[9px] text-gray-500 uppercase">${h.area_name}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-0.5 rounded text-[9px] font-black border ${statusColors[displayStatus] || 'text-gray-500 border-gray-500/20'} uppercase">${displayStatus}</span>
                        </td>
                        <td class="px-6 py-4 text-gray-400 font-mono">${fmtDate(h.start_time)}</td>
                        <td class="px-6 py-4 text-gray-300 font-mono">${h.duration_label}</td>
                        <td class="px-6 py-4">
                            <span class="text-[10px] text-gray-500 uppercase font-bold">${h.trigger_reason}</span>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        // --- Jobs Tab ---
        async function loadJobs() {
            const d = await api('/api/jobs'); 
            if (!d) return;
            
            const bqJob = d.find(j => j.id === 'hot_reload_job');
            if (bqJob) updateReloadCountdown(bqJob.next_run_br);

            const tb = document.getElementById('jobs-tbody');
            
            if (!d.length) { 
                tb.innerHTML = '<tr><td colspan="3" class="py-20 text-center text-gray-500 uppercase tracking-widest">Nenhum agendamento ativo</td></tr>'; 
                return; 
            }

            tb.innerHTML = d.map(j => {
                const stemLower = j.id.replace('_cron', '').toLowerCase();

                return `
                    <tr class="hover:bg-white/[0.02] transition-colors">
                        <td class="px-6 py-4">
                            <div class="text-base font-bold text-white">${stemLower}</div>
                        </td>
                        <td class="px-6 py-4 text-gray-400 font-mono text-sm">${fmtDate(j.next_run_br)}</td>
                        <td class="px-6 py-4 text-right font-black text-yellow-500 font-mono text-lg">${countdown(j.next_run_br)}</td>
                    </tr>
                `;
            }).join('');
        }

        // --- Actions ---
        async function runScript(name) {
            const d = await api('/api/run/' + encodeURIComponent(name), { method: 'POST' });
            if (d) { 
                toast(d.message, d.status === 'success' ? 'success' : 'error'); 
                masterPoll(); 
            }
        }

        async function killPid(pid) {
            if (!confirm(`Encerrar processo PID ${pid}?`)) return;
            const d = await api('/api/kill/' + pid, { method: 'POST' });
            if (d) { 
                toast(d.message, d.status === 'success' ? 'success' : 'error'); 
                masterPoll(); 
            }
        }

        async function killByName(name) {
            if (!confirm(`Encerrar todas as instâncias de "${name}"?`)) return;
            const d = await api('/api/kill/by-name/' + encodeURIComponent(name), { method: 'POST' });
            if (d) { 
                toast(d.message, d.status === 'success' ? 'success' : 'error'); 
                masterPoll(); 
            }
        }

        async function killAll() {
            if (!confirm('Encerrar TODOS os processos regulares em execução?')) return;
            const pids = statusData?.running_processes?.map(p => p.pid) || [];
            for (const pid of pids) await api('/api/kill/' + pid, { method: 'POST' });
            toast('Comando de encerramento em massa enviado', 'warning'); 
            masterPoll();
        }

        const RELOAD_COOLDOWN_MS = 3 * 60 * 1000;
        let _reloadSyncInFlight = false;
        let _reloadAllowedAfter = 0;

        function _setReloadSyncUiLoading(loading) {
            document.querySelectorAll('.reload-sync-btn').forEach((btn) => {
                /* Do not set button.disabled — disabled controls do not fire click, so users
                   get no toast when clicking again during sync or cooldown. */
                btn.setAttribute('aria-busy', loading ? 'true' : 'false');
                btn.setAttribute('aria-disabled', loading ? 'true' : 'false');
                btn.classList.toggle('opacity-50', loading);
                btn.classList.toggle('cursor-wait', loading);
            });
            document.querySelectorAll('.reload-sync-icon').forEach((ic) => {
                ic.classList.toggle('animate-spin', loading);
            });
        }

        function _fmtReloadWait(sec) {
            const s = Math.max(0, Math.ceil(sec));
            const mm = Math.floor(s / 60);
            const ss = s % 60;
            return `${mm}m ${String(ss).padStart(2, '0')}s`;
        }

        async function forceReload() {
            if (_reloadSyncInFlight) {
                toast('Sincronização em andamento. Aguarde terminar.', 'warning');
                return;
            }
            const now = Date.now();
            if (now < _reloadAllowedAfter) {
                const waitSec = (_reloadAllowedAfter - now) / 1000;
                toast(`Intervalo mínimo de 3 minutos entre sincronizações. Aguarde ${_fmtReloadWait(waitSec)}.`, 'warning');
                return;
            }

            _reloadSyncInFlight = true;
            _setReloadSyncUiLoading(true);
            try {
                const r = await fetch(getApiBase() + '/api/reload', { method: 'POST', credentials: 'same-origin' });
                let d = {};
                try {
                    const raw = await r.text();
                    if (raw) d = JSON.parse(raw);
                } catch (e) {
                    d = {};
                }

                if (r.status === 401) {
                    showLoginUi();
                    toast('Sessão expirada — faça login novamente.', 'warning');
                    return;
                }
                if (r.status === 429 && d.status === 'cooldown') {
                    const ws = Number(d.wait_seconds);
                    const sec = Number.isFinite(ws) && ws > 0 ? ws : 180;
                    _reloadAllowedAfter = Date.now() + sec * 1000;
                    toast(`Limite do Server: aguarde ${_fmtReloadWait(sec)} para sincronizar de novo.`, 'warning');
                    return;
                }
                if (!r.ok) {
                    toast((d && d.message) || `Erro ao sincronizar (HTTP ${r.status}).`, 'error');
                    return;
                }
                if (d.status === 'success') {
                    toast(`Sincronização concluída: ${d.script_count} scripts carregados`, 'success');
                    _reloadAllowedAfter = Date.now() + RELOAD_COOLDOWN_MS;
                    if (d.next_hot_reload_iso) {
                        updateReloadCountdown(d.next_hot_reload_iso);
                    }
                    masterPoll();
                    if (currentTab === 'scripts') loadScriptsTab();
                } else {
                    toast((d && d.message) || 'Resposta inesperada do Server ao sincronizar.', 'error');
                }
            } catch (e) {
                console.error('forceReload:', e);
                toast('Falha de rede ao sincronizar.', 'error');
            } finally {
                _reloadSyncInFlight = false;
                _setReloadSyncUiLoading(false);
            }
        }

        async function updateUptime() {
            const d = await api('/api/health'); 
            if (d) document.getElementById('sidebar-uptime').textContent = fmtTime(d.uptime_seconds);
            const info = await api('/api/server/info');
            if (info && info.version) document.getElementById('server-version').textContent = 'v' + info.version;
        }

        // --- Initialization ---
        let _dashboardBooted = false;
        function bootDashboard() {
            if (_dashboardBooted) return;
            _dashboardBooted = true;
            try {
                const saved = localStorage.getItem(THEME_KEY);
                if (saved === 'light' || saved === 'dark') applyTheme(saved);
                else applyTheme('dark');
            } catch (e) { applyTheme('dark'); }

            document.getElementById('sidebar-open-btn')?.addEventListener('click', openSidebar);
            document.getElementById('sidebar-close-btn')?.addEventListener('click', closeSidebar);
            document.getElementById('sidebar-backdrop')?.addEventListener('click', closeSidebar);
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSidebar(); });
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) masterPoll();
            });
            document.getElementById('theme-toggle-btn')?.addEventListener('click', toggleTheme);
            document.getElementById('logout-btn')?.addEventListener('click', () => doLogout());
            // Defensive wiring for navigation buttons (works even if inline onclick is blocked).
            document.querySelectorAll('.nav-item[data-tab]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const tab = btn.getAttribute('data-tab');
                    if (tab) switchTab(tab);
                });
            });
            document.getElementById('share-outlook-btn')?.addEventListener('click', async () => {
                const d = await api('/api/share_outlook', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: '{}',
                });
                if (d && d.status === 'success') {
                    toast((d.message || 'Outlook aberto.') + (d.shared_url ? ' ' + d.shared_url : ''), 'success');
                } else if (d && d.message) {
                    toast(d.message, 'error');
                }
            });

            document.getElementById('script-search')?.addEventListener('input', onScriptSearchInput);
            document.getElementById('dash-stats-apply')?.addEventListener('click', () => loadDashboardHistoryStats());
            document.getElementById('dash-stats-script-filter')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); loadDashboardHistoryStats(); }
            });

            switchTab('dashboard');
            clearTimeout(_pollTimer);
            pollLoop();
            setInterval(updateUptime, 10000);
            updateUptime();
            loadPending();
        }

        async function bootstrapAuth() {
            const ok = await refreshAuthStatus();
            if (ok) {
                hideLoginUi();
                bootDashboard();
            } else {
                showLoginUi();
            }
        }

        async function requestLoginToken() {
            const msgEl = document.getElementById('login-msg');
            const btn = document.getElementById('login-request-btn');
            const u = (document.getElementById('login-username')?.value || '').trim().toLowerCase();
            if (msgEl) msgEl.textContent = '';
            if (!u) {
                if (msgEl) msgEl.textContent = 'Informe o usuário.';
                return;
            }
            const prevLabel = btn ? btn.textContent : '';
            const url = getApiBase() + '/api/auth/request-token';
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Enviando…';
            }
            console.log('[login] request-token →', url, '| usuário:', u, '| API base:', getApiBase());
            try {
                const r = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: u }),
                });
                const rawText = await r.text();
                let d = {};
                try {
                    d = rawText ? JSON.parse(rawText) : {};
                } catch (parseErr) {
                    console.error('[login] request-token: corpo não é JSON | HTTP', r.status, parseErr);
                    console.error('[login] primeiros 600 chars:', (rawText || '').slice(0, 600));
                    console.log('[login] request-token resultado: falha parse JSON | HTTP', r.status);
                    if (msgEl) {
                        msgEl.textContent =
                            'Erro HTTP ' +
                            r.status +
                            ': resposta não-JSON (provável 404 na rota). Abra F12 → Console e rede.';
                    }
                    return;
                }
                console.log('[login] request-token resultado HTTP', r.status, '| JSON:', d);
                if (r.ok && d.status === 'success') {
                    console.log('[login] request-token OK —', d.message || 'sem mensagem');
                    if (msgEl) msgEl.textContent = d.message || 'Token enviado.';
                    document.getElementById('login-step-token')?.classList.remove('hidden');
                    document.getElementById('login-token')?.focus();
                } else {
                    console.warn('[login] request-token recusado | HTTP', r.status, '| payload:', d);
                    console.log('[login] request-token resultado: recusado', d);
                    const hint =
                        (d && d.message) ||
                        ('Erro HTTP ' + r.status + (d && d.error ? ' — ' + d.error : '') + '. Veja Console (F12).');
                    if (msgEl) msgEl.textContent = hint;
                }
            } catch (e) {
                console.error('[login] request-token exceção:', e);
                console.log('[login] request-token resultado: exceção', e && e.message ? e.message : e);
                if (e && e.stack) console.error(e.stack);
                if (msgEl) {
                    msgEl.textContent =
                        'Falha de rede ou bloqueio: ' +
                        (e && e.message ? e.message : String(e)) +
                        ' — detalhe completo no Console (F12).';
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = prevLabel || 'Enviar token por e-mail';
                }
            }
        }

        async function verifyLoginToken() {
            const msgEl = document.getElementById('login-msg');
            const u = (document.getElementById('login-username')?.value || '').trim().toLowerCase();
            const token = (document.getElementById('login-token')?.value || '').trim();
            if (msgEl) msgEl.textContent = '';
            if (!token) {
                if (msgEl) msgEl.textContent = 'Informe o código.';
                return;
            }
            const url = getApiBase() + '/api/auth/verify';
            console.log('[login] verify →', url, '| usuário:', u);
            try {
                const r = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: u, token }),
                });
                const rawText = await r.text();
                let d = {};
                try {
                    d = rawText ? JSON.parse(rawText) : {};
                } catch (parseErr) {
                    console.error('[login] verify: corpo não é JSON | HTTP', r.status, parseErr);
                    console.error('[login] primeiros 600 chars:', (rawText || '').slice(0, 600));
                    console.log('[login] verify resultado: falha parse JSON | HTTP', r.status);
                    if (msgEl) {
                        msgEl.textContent =
                            'Erro HTTP ' + r.status + ': resposta inválida. Veja Console (F12).';
                    }
                    return;
                }
                console.log('[login] verify resultado HTTP', r.status, '| JSON:', d);
                if (r.ok && d.status === 'success') {
                    console.log('[login] verify OK — sessão iniciada');
                    await refreshAuthStatus();
                    hideLoginUi();
                    bootDashboard();
                } else {
                    console.warn('[login] verify recusado | HTTP', r.status, '| payload:', d);
                    console.log('[login] verify resultado: recusado', d);
                    if (msgEl) {
                        msgEl.textContent =
                            (d && d.message) ||
                            'Token inválido ou sessão (HTTP ' + r.status + '). Veja Console (F12).';
                    }
                }
            } catch (e) {
                console.error('[login] verify exceção:', e);
                console.log('[login] verify resultado: exceção', e && e.message ? e.message : e);
                if (e && e.stack) console.error(e.stack);
                if (msgEl) {
                    msgEl.textContent =
                        'Falha de rede: ' + (e && e.message ? e.message : String(e)) + ' — ver Console (F12).';
                }
            }
        }

        // Expose handlers used by inline onclick attributes in ServerCRON.html
        window.switchTab = switchTab;
        window.goToLiveForPython = goToLiveForPython;
        window.runScript = runScript;
        window.killPid = killPid;
        window.killByName = killByName;
        window.killAll = killAll;
        window.forceReload = forceReload;

        function wireLoginForm() {
            const msgEl = document.getElementById('login-msg');
            const pv = document.body && document.body.getAttribute('data-portal-view');
            console.log('[login] wireLoginForm | data-portal-view=', pv, '| pathname=', window.location.pathname, '| getApiBase()=', getApiBase());
            if (!document.getElementById('login-request-btn')) {
                console.warn('[login] #login-request-btn não encontrado — enviar token não será ligado.');
            }
            document.getElementById('login-request-btn')?.addEventListener('click', async () => { await requestLoginToken(); });
            document.getElementById('login-verify-btn')?.addEventListener('click', async () => { await verifyLoginToken(); });
            document.getElementById('login-username')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    requestLoginToken();
                }
            });
            document.getElementById('login-token')?.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    verifyLoginToken();
                }
            });
            document.getElementById('login-back-btn')?.addEventListener('click', () => {
                document.getElementById('login-step-token')?.classList.add('hidden');
                if (msgEl) msgEl.textContent = '';
            });
        }

        wireLoginForm();
        bootstrapAuth();
  }
    function boot() {
        const b = document.body;
        const pv = (b && b.getAttribute("data-portal-view")) || "";
        console.log("[Server] boot", {
            dataPortalView: pv || "(vazio)",
            pathname: window.location.pathname,
            getApiBase: getApiBase(),
        });
        if (pv === "cron") runCronPanel();
        else initUploadersPortal();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
    else boot();
})();
