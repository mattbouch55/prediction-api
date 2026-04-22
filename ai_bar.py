# Shared AI bar injected into all pages at serve time

AI_BAR_CSS = """
    /* ── ONYX AI BAR ── */
    .ai-topbar { position: fixed; top: 0; left: var(--sidebar-w); right: 0; height: 107px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; z-index: 100; }

    /* Left: ask panel */
    .ai-ask-panel { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center; padding: 14px 18px; border-right: 1px solid var(--border); gap: 8px; }
    .ai-ask-brand { display: flex; align-items: center; gap: 7px; }
    .ai-ask-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--blue); animation: aipulse 2s ease-in-out infinite; flex-shrink: 0; }
    @keyframes aipulse { 0%,100%{opacity:0.3;transform:scale(1)} 50%{opacity:1;transform:scale(1.3)} }
    .ai-ask-name { font-size: 13px; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
    .ai-ask-tag { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey); }
    .ai-ask-row { display: flex; gap: 7px; align-items: center; }
    .ai-topbar-input { flex: 1; background: var(--surface2); border: 1px solid var(--border2); border-radius: 7px; outline: none; font-family: "Inter", sans-serif; font-size: 12px; color: var(--text); padding: 7px 12px; transition: border-color 0.15s, box-shadow 0.15s; }
    .ai-topbar-input:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(21,101,255,0.08); background: var(--surface); }
    .ai-topbar-input::placeholder { color: var(--grey); font-size: 11px; }
    .ai-topbar-send { background: var(--blue); border: none; border-radius: 6px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.12s; flex-shrink: 0; }
    .ai-topbar-send:hover { background: #1a6fff; }
    .ai-topbar-send:disabled { background: var(--border2); cursor: not-allowed; }

    /* Right: response panel */
    .ai-response-panel { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 14px 20px; min-width: 0; position: relative; }
    .ai-response-label { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey); margin-bottom: 6px; }
    .ai-response-text { font-size: 12px; color: var(--text2); line-height: 1.6; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
    .ai-response-empty { font-size: 12px; color: var(--grey); font-style: italic; line-height: 1.6; }
    .ai-response-thinking { color: var(--grey); font-style: italic; }
    .ai-topbar-clear { position: absolute; top: 10px; right: 14px; background: none; border: none; color: var(--grey); cursor: pointer; font-size: 14px; padding: 2px 4px; transition: color 0.12s; display: none; line-height: 1; }
    .ai-topbar-clear:hover { color: var(--red); }
"""

AI_BAR_HTML = """  <!-- Onyx AI Bar — injected on all pages -->
  <div class="ai-topbar" id="aiTopbar">

    <!-- Left: Ask panel -->
    <div class="ai-ask-panel">
      <div class="ai-ask-brand">
        <div class="ai-ask-dot"></div>
        <span class="ai-ask-name">Onyx</span>
        <span class="ai-ask-tag">AI Agent</span>
      </div>
      <div class="ai-ask-row">
        <input class="ai-topbar-input" id="aiBarInput" type="text"
          placeholder="Ask anything..." maxlength="300"/>
        <button class="ai-topbar-send" id="aiBarSend" onclick="askAI()" title="Ask Onyx">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="white"><path d="M14.5 8l-13 7 3-7-3-7z"/></svg>
        </button>
      </div>
    </div>

    <!-- Right: Response panel -->
    <div class="ai-response-panel">
      <button class="ai-topbar-clear" id="aiBarClear" onclick="clearAI()" title="Clear">&#xd7;</button>
      <div class="ai-response-label">Response</div>
      <div class="ai-response-text" id="aiBarResponse">
        <span class="ai-response-empty">Ask Onyx anything — market data, quick facts, current events...</span>
      </div>
    </div>

  </div>
"""

AI_BAR_JS = """
  <script>
  /* Onyx AI Agent Bar */
  document.getElementById("aiBarInput").addEventListener("keydown", function(e) {
    if (e.key === "Enter") askAI();
    if (e.key === "Escape") clearAI();
  });

  async function askAI() {
    var q = document.getElementById("aiBarInput").value.trim();
    if (!q) return;
    var send = document.getElementById("aiBarSend");
    var resp = document.getElementById("aiBarResponse");
    var clr  = document.getElementById("aiBarClear");
    send.disabled = true;
    resp.innerHTML = "<span class=\'ai-response-thinking\'>Searching...</span>";
    clr.style.display = "block";
    try {
      var res = await fetch("/ask", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ question: q })
      });
      var data = await res.json();
      resp.textContent = data.answer || "No answer found.";
    } catch(e) {
      resp.textContent = "Error reaching Onyx: " + e.message;
    } finally {
      send.disabled = false;
    }
  }

  function clearAI() {
    document.getElementById("aiBarInput").value = "";
    document.getElementById("aiBarResponse").innerHTML =
      "<span class=\'ai-response-empty\'>Ask Onyx anything — market data, quick facts, current events...</span>";
    document.getElementById("aiBarClear").style.display = "none";
  }
  </script>
"""

def inject(html: str) -> str:
    """Inject Onyx AI bar CSS, HTML, and JS into any page."""
    html = html.replace("  </style>", AI_BAR_CSS + "  </style>", 1)
    html = html.replace('<div class="app">', AI_BAR_HTML + '\n<div class="app">', 1)
    html = html.replace("</body>", AI_BAR_JS + "\n</body>", 1)
    return html
