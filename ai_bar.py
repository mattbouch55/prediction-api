# Shared AI bar injected into all pages at serve time
AI_BAR_CSS  = """
    /* ── AI AGENT TOP BAR ── */
    .ai-topbar { position: fixed; top: 0; left: var(--sidebar-w); right: 0; height: 70px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; padding: 0 24px; z-index: 100; }
    .ai-topbar-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--blue); flex-shrink: 0; animation: aipulse 2s ease-in-out infinite; }
    @keyframes aipulse { 0%,100%{opacity:0.3;transform:scale(1)} 50%{opacity:1;transform:scale(1.25)} }
    .ai-topbar-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey2); white-space: nowrap; flex-shrink: 0; }
    .ai-topbar-input { flex: 1; background: var(--surface2); border: 1px solid transparent; border-radius: 10px; outline: none; font-family: "Inter", sans-serif; font-size: 13px; color: var(--text); padding: 10px 18px; transition: border-color 0.15s, box-shadow 0.15s; max-width: 680px; }
    .ai-topbar-input:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(21,101,255,0.08); background: var(--surface); }
    .ai-topbar-input::placeholder { color: var(--grey); }
    .ai-topbar-send { background: var(--blue); border: none; border-radius: 50%; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.12s; flex-shrink: 0; }
    .ai-topbar-send:hover { background: #1a6fff; }
    .ai-topbar-send:disabled { background: var(--border2); cursor: not-allowed; }
    .ai-topbar-response { flex: 1; font-size: 12px; color: var(--text2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-left: 12px; border-left: 2px solid var(--blue); display: none; max-width: 700px; line-height: 1.5; }
    .ai-topbar-response.active { display: block; }
    .ai-topbar-clear { background: none; border: none; color: var(--grey); cursor: pointer; font-size: 14px; padding: 2px; transition: color 0.12s; flex-shrink: 0; display: none; }
    .ai-topbar-clear:hover { color: var(--red); }
"""
AI_BAR_HTML = """  <!-- AI Agent Bar — injected on all pages -->
  <div class="ai-topbar" id="aiTopbar">
    <div class="ai-topbar-dot"></div>
    <span class="ai-topbar-label">Ask AI</span>
    <input class="ai-topbar-input" id="aiBarInput" type="text"
      placeholder="Ask anything... e.g. When does Trump usually tweet? What moved oil prices today?"
      maxlength="300"/>
    <button class="ai-topbar-send" id="aiBarSend" onclick="askAI()" title="Ask">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="white"><path d="M14.5 8l-13 7 3-7-3-7z"/></svg>
    </button>
    <div class="ai-topbar-response" id="aiBarResponse"></div>
    <button class="ai-topbar-clear" id="aiBarClear" onclick="clearAI()" title="Clear">&#xd7;</button>
  </div>
"""
AI_BAR_JS   = """
  <script>
  /* AI Agent Bar */
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
    resp.innerHTML = "<em style='color:var(--grey)'>Searching...</em>";
    resp.classList.add("active");
    clr.style.display = "flex";
    try {
      var res = await fetch("/ask", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ question: q })
      });
      var data = await res.json();
      resp.textContent = data.answer || "No answer found.";
    } catch(e) {
      resp.textContent = "Error: " + e.message;
    } finally {
      send.disabled = false;
    }
  }
  function clearAI() {
    document.getElementById("aiBarInput").value = "";
    document.getElementById("aiBarResponse").classList.remove("active");
    document.getElementById("aiBarResponse").textContent = "";
    document.getElementById("aiBarClear").style.display = "none";
  }
  </script>
"""

def inject(html: str) -> str:
    """Inject AI bar CSS, HTML, and JS into any page."""
    html = html.replace("  </style>", AI_BAR_CSS + "  </style>", 1)
    html = html.replace("<div class=\"app\">", AI_BAR_HTML + "\n<div class=\"app\">", 1)
    html = html.replace("</body>", AI_BAR_JS + "\n</body>", 1)
    return html
