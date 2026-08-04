// Bloqueante (nao "defer"): evita flash da interface antes de confirmar login.
// A validacao real do token acontece no servidor (app.js); isto so evita
// mostrar a casca do painel a quem nunca fez login neste navegador.
(function () {
  var authRequired = true;
  try {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/auth", false);
    xhr.send(null);
    if (xhr.status === 200) {
      authRequired = !!JSON.parse(xhr.responseText).auth_required;
    }
  } catch (e) {
    // servidor inacessivel: mantem o comportamento seguro (exige login)
  }
  if (authRequired && !localStorage.getItem("servercron_token")) {
    location.replace("/login");
  }
})();
