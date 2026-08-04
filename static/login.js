(function () {
  const TOKEN_KEY = "servercron_token";
  const $ = (id) => document.getElementById(id);

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (_) { return ""; }
  }
  function setToken(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (_) {}
  }

  let loginMode = "otp"; // "otp" (email + codigo por email) ou "token" (legado)
  let otpStep = "email"; // "email" -> pede o codigo | "code" -> confirma o codigo

  function el() {
    return {
      email: $("login-email"),
      token: $("login-token"),
      code: $("login-code"),
      note: $("login-otp-note"),
      hint: $("login-hint"),
      err: $("login-error"),
      submit: $("login-submit"),
      resend: $("login-resend"),
    };
  }

  function render() {
    const e = el();
    e.err.hidden = true;

    if (loginMode === "token") {
      e.email.hidden = true;
      e.code.hidden = true;
      e.note.hidden = true;
      e.resend.hidden = true;
      e.token.hidden = false;
      e.hint.textContent = "Este servidor exige um token para chamar a API. Cole o valor de SERVERCRON_API_TOKEN.";
      e.submit.textContent = "Entrar";
      return;
    }

    e.token.hidden = true;
    if (otpStep === "email") {
      e.email.hidden = false;
      e.code.hidden = true;
      e.note.hidden = true;
      e.resend.hidden = true;
      e.hint.textContent = "Informe o seu email cadastrado. Vamos enviar um codigo de acesso.";
      e.submit.textContent = "Enviar codigo";
    } else {
      e.email.hidden = true;
      e.code.hidden = false;
      e.note.hidden = false;
      e.resend.hidden = false;
      e.hint.textContent = "Confira seu email (" + e.email.value.trim() + ") e cole o codigo recebido.";
      e.submit.textContent = "Confirmar codigo";
    }
  }

  async function checkAlreadyLoggedIn() {
    const token = getToken();
    const headers = { Accept: "application/json" };
    if (token) headers["X-ServerCRON-Token"] = token;
    try {
      const res = await fetch("/api/auth", { headers });
      const data = await res.json().catch(() => ({}));
      loginMode = data.login_mode === "token" ? "token" : "otp";
      render();
      if (data.authenticated) {
        location.replace("/");
      }
    } catch (_) {
      render();
    }
  }

  async function requestCode(email) {
    const res = await fetch("/api/login/request", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || "falha ao enviar o codigo");
    }
    const e = el();
    const ttlMin = Math.max(1, Math.round((data.ttl_sec || 120) / 60));
    e.note.textContent = "Codigo valido por " + ttlMin + " minuto(s). Nao recebeu? Confira spam ou peca de novo.";
    otpStep = "code";
    render();
    e.code.focus();
  }

  async function verifyCode(email, code) {
    const res = await fetch("/api/login/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email, code }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || "codigo invalido ou expirado");
    }
    setToken(data.token);
    location.replace("/");
  }

  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const els = el();
    els.err.hidden = true;

    if (loginMode === "token") {
      const value = els.token.value.trim();
      if (!value) return;
      setToken(value);
      location.replace("/");
      return;
    }

    els.submit.disabled = true;
    try {
      if (otpStep === "email") {
        const email = els.email.value.trim();
        if (!email) return;
        await requestCode(email);
      } else {
        const email = els.email.value.trim();
        const code = els.code.value.trim();
        if (!code) return;
        await verifyCode(email, code);
      }
    } catch (err) {
      els.err.textContent = err.message;
      els.err.hidden = false;
    } finally {
      els.submit.disabled = false;
    }
  });

  $("login-resend").addEventListener("click", () => {
    otpStep = "email";
    $("login-code").value = "";
    render();
    $("login-email").focus();
  });

  checkAlreadyLoggedIn();
})();
