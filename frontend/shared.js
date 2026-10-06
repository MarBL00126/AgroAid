/* AgroAid - utilidades compartidas de la webapp.
 * Sesion unica (access_token > guest_token), authFetch con renovacion de
 * invitado, barra de navegacion y helpers. Se carga con <script src="/static/shared.js">.
 */
(function () {
  const API = window.location.origin;
  const GUEST_KEY = "guest_token";
  const LOGIN_KEY = "access_token";

  function tokenValid(token) {
    if (!token) return false;
    try {
      const payload = JSON.parse(
        atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))
      );
      return !payload.exp || payload.exp * 1000 > Date.now() + 60000;
    } catch (_) {
      return false;
    }
  }

  function currentToken() {
    const login = localStorage.getItem(LOGIN_KEY);
    if (tokenValid(login)) return login;
    const guest = localStorage.getItem(GUEST_KEY);
    return tokenValid(guest) ? guest : null;
  }

  async function ensureAuth(force) {
    if (!force && currentToken()) return;
    localStorage.removeItem(GUEST_KEY);
    const res = await fetch(API + "/auth/guest", { method: "POST" });
    if (!res.ok) throw new Error("No se pudo iniciar la sesion (" + res.status + ")");
    const data = await res.json();
    localStorage.setItem(GUEST_KEY, data.access_token);
  }

  async function authFetch(url, options) {
    const opts = options || {};
    const send = () => {
      const headers = { ...(opts.headers || {}) };
      const tok = currentToken();
      if (tok) headers["Authorization"] = "Bearer " + tok;
      return fetch(url, { ...opts, headers });
    };
    await ensureAuth(false);
    let res = await send();
    if (res.status === 401) {
      localStorage.removeItem(LOGIN_KEY);
      await ensureAuth(true);
      res = await send();
    }
    return res;
  }

  async function errorText(res) {
    try {
      const data = await res.json();
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; ");
    } catch (_) {}
    return "Error " + res.status;
  }

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function downloadPdf(path, filename) {
    const res = await authFetch(API + path);
    if (!res.ok) throw new Error(await errorText(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  const LINKS = [
    ["chat", "/", "\u{1F4AC} Chat"],
    ["mapa", "/mapa", "\u{1F5FA}\uFE0F Mapa"],
    ["prevuelo", "/prevuelo", "\u2708\uFE0F Pre-vuelo"],
    ["recetas", "/recetas", "\u{1F4C4} Recetas"],
    ["admin", "/admin.html", "\u2699\uFE0F Admin"],
  ];

  function renderNav(active) {
    const host = document.getElementById("app-nav");
    if (!host) return;
    host.innerHTML =
      '<nav style="display:flex;gap:4px;overflow-x:auto;padding:8px 12px;' +
      'background:#14532d;-webkit-overflow-scrolling:touch">' +
      LINKS.map(([key, href, label]) => {
        const on = key === active;
        return (
          '<a href="' + href + '" style="flex:none;min-height:44px;display:flex;' +
          "align-items:center;padding:0 14px;border-radius:12px;text-decoration:none;" +
          "font:600 14px system-ui,sans-serif;color:#fff;white-space:nowrap;" +
          "background:" + (on ? "rgba(255,255,255,.22)" : "transparent") + '">' +
          label + "</a>"
        );
      }).join("") +
      "</nav>";
  }

  window.AgroAid = { API, currentToken, ensureAuth, authFetch, errorText, esc, downloadPdf, renderNav };
})();
