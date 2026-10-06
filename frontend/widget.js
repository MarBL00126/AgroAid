class AgroAidWidget extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  connectedCallback() {
    const apiKey = this.getAttribute("api-key") || "";
    const baseUrl =
      this.getAttribute("base-url") || window.location.origin;
    const guestKey = "agroaid_widget_guest_token";
    const hasApiKey = apiKey && !apiKey.includes("aqui");

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

    async function authHeaders() {
      if (hasApiKey) return { "X-API-Key": apiKey };

      let token = localStorage.getItem(guestKey);
      if (!tokenValid(token)) {
        const res = await fetch(`${baseUrl}/auth/guest`, { method: "POST" });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem(guestKey, token);
      }

      return { Authorization: `Bearer ${token}` };
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          max-width: 420px;
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          color: #0f172a;
        }
        .widget {
          border: 1px solid #bbf7d0;
          border-radius: 8px;
          background: #f8fafc;
          padding: 14px;
          box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
        }
        .title {
          margin: 0 0 8px;
          font-size: 16px;
          font-weight: 800;
          color: #14532d;
        }
        textarea {
          width: 100%;
          min-height: 96px;
          resize: vertical;
          box-sizing: border-box;
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          padding: 9px;
          font: inherit;
        }
        button {
          margin-top: 10px;
          width: 100%;
          border: 0;
          border-radius: 6px;
          background: #16a34a;
          color: white;
          padding: 10px 12px;
          font-weight: 800;
          cursor: pointer;
        }
        button:disabled {
          cursor: wait;
          opacity: 0.7;
        }
        .resultado {
          margin-top: 10px;
          padding: 10px;
          border-radius: 6px;
          background: white;
          border: 1px solid #e2e8f0;
          line-height: 1.4;
          min-height: 24px;
          }
      </style>
      <div class="widget">
        <p class="title">AgroAid Risk Score</p>
        <textarea id="q" placeholder="Consulta sobre seguridad agricola"></textarea>
        <button id="btn">Evaluar riesgo</button>
        <div id="resultado" class="resultado"></div>
      </div>
    `;
    const btn = this.shadowRoot.getElementById("btn");
    const qInput = this.shadowRoot.getElementById("q");
    const resultado = this.shadowRoot.getElementById("resultado");
    btn.addEventListener("click", async () => {
      const q = qInput.value.trim();
      if (!q) return;
      btn.disabled = true;
      resultado.textContent = "Evaluando...";
      try {
        const res = await fetch(
          `${baseUrl}/api/risk-score?q=${encodeURIComponent(q)}`,
          { headers: await authHeaders() }
        );
        if (!res.ok) {
          throw new Error(await res.text());
        }
        const data = await res.json();
        resultado.innerHTML = `
          <strong>${data.nivel_riesgo || "SIN NIVEL"}</strong><br>
          ${data.justificacion || "Sin justificacion disponible"}
        `;
      } catch (error) {
        resultado.textContent = "No se pudo evaluar la consulta.";
        console.error(error);
      } finally {
        btn.disabled = false;
      }
    });
  }
}
customElements.define("agroaid-widget", AgroAidWidget);
