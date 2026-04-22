# Shared Onyx AI bar — injected on all pages via main.py

AI_BAR_CSS = """
    /* ── ONYX AI BAR ── */
    .ai-topbar { position: fixed; top: 0; left: var(--sidebar-w); right: 0; height: 107px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; z-index: 100; }

    /* Left: ask panel */
    .ai-ask-panel { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center; padding: 12px 16px; border-right: 1px solid var(--border); gap: 8px; }
    .ai-ask-brand { display: flex; align-items: center; gap: 7px; }
    .ai-ask-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--blue); animation: aipulse 2s ease-in-out infinite; flex-shrink: 0; }
    @keyframes aipulse { 0%,100%{opacity:0.3;transform:scale(1)} 50%{opacity:1;transform:scale(1.3)} }
    .ai-ask-name { font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
    .ai-ask-tag { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey); margin-left: 2px; }
    .ai-ask-row { display: flex; gap: 6px; align-items: center; }
    .ai-topbar-input { flex: 1; background: var(--surface2); border: 1px solid var(--border2); border-radius: 7px; outline: none; font-family: "Inter", sans-serif; font-size: 12px; color: var(--text); padding: 7px 12px; transition: border-color 0.15s, box-shadow 0.15s; }
    .ai-topbar-input:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(21,101,255,0.08); background: var(--surface); }
    .ai-topbar-input::placeholder { color: var(--grey); font-size: 11px; }
    .ai-topbar-send { background: var(--blue); border: none; border-radius: 6px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.12s; flex-shrink: 0; }
    .ai-topbar-send:hover { background: #1a6fff; }
    .ai-topbar-send:disabled { background: var(--border2); cursor: not-allowed; }

    /* Middle: response panel */
    .ai-response-panel { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 12px 18px; min-width: 0; border-right: 1px solid var(--border); }
    .ai-response-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .ai-response-label { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey); }
    .ai-topbar-clear { background: none; border: none; color: var(--grey); cursor: pointer; font-size: 13px; padding: 0; transition: color 0.12s; display: none; line-height: 1; }
    .ai-topbar-clear:hover { color: var(--red); }
    .ai-response-text { font-size: 12px; color: var(--text2); line-height: 1.6; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
    .ai-response-empty { font-size: 11.5px; color: var(--grey); font-style: italic; }
    .ai-response-thinking { color: var(--grey); font-style: italic; }
    .ai-action-bar { margin-top: 6px; display: none; }
    .ai-action-bar.active { display: flex; gap: 6px; flex-wrap: wrap; }
    .ai-action-chip { font-size: 10px; font-weight: 600; padding: 3px 10px; border-radius: 10px; border: 1px solid var(--blue); color: var(--blue); background: var(--blue-soft); cursor: pointer; transition: all 0.12s; white-space: nowrap; }
    .ai-action-chip:hover { background: var(--blue); color: white; }

    /* Right: suggestions panel */
    .ai-suggest-panel { width: 200px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center; padding: 12px 14px; gap: 6px; }
    .ai-suggest-btn { width: 100%; background: var(--text); color: var(--surface); border: none; font-family: "Inter", sans-serif; font-size: 11px; font-weight: 600; padding: 7px 12px; border-radius: 6px; cursor: pointer; transition: opacity 0.12s; display: flex; align-items: center; justify-content: center; gap: 6px; }
    .ai-suggest-btn:hover { opacity: 0.85; }
    .ai-suggest-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .ai-suggest-label { font-size: 9px; color: var(--grey); text-align: center; line-height: 1.4; }

    /* Suggestions dropdown */
    .ai-suggest-dropdown { position: fixed; top: 107px; right: 0; width: 320px; background: var(--surface); border: 1px solid var(--border); border-top: none; border-radius: 0 0 10px 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); z-index: 99; display: none; }
    .ai-suggest-dropdown.open { display: block; }
    .ai-suggest-header { padding: 12px 16px 8px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--grey); border-bottom: 1px solid var(--border); }
    .ai-suggest-list { padding: 6px 0; }
    .ai-suggest-item { padding: 10px 16px; cursor: pointer; transition: background 0.1s; border-bottom: 1px solid var(--border); }
    .ai-suggest-item:last-child { border-bottom: none; }
    .ai-suggest-item:hover { background: var(--surface2); }
    .ai-suggest-item-title { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 2px; }
    .ai-suggest-item-desc { font-size: 11px; color: var(--grey2); line-height: 1.4; }
    .ai-suggest-loading { padding: 20px 16px; text-align: center; font-size: 12px; color: var(--grey); font-style: italic; }
"""

AI_BAR_HTML = """  <!-- Onyx AI Bar — injected on all pages -->
  <div class="ai-topbar" id="aiTopbar">

    <!-- Left: Ask -->
    <div class="ai-ask-panel">
      <div class="ai-ask-brand">
        <div class="ai-ask-dot"></div>
        <span class="ai-ask-name">Onyx</span>
        <span class="ai-ask-tag">AI Agent</span>
      </div>
      <div class="ai-ask-row">
        <input class="ai-topbar-input" id="aiBarInput" type="text"
          placeholder='Ask or command... "Buy 5 TSLA" "Add NVDA" "Scan AAPL"'
          maxlength="300"/>
        <button class="ai-topbar-send" id="aiBarSend" onclick="askOnyx()" title="Ask Onyx">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="white"><path d="M14.5 8l-13 7 3-7-3-7z"/></svg>
        </button>
      </div>
    </div>

    <!-- Middle: Response -->
    <div class="ai-response-panel">
      <div class="ai-response-top">
        <span class="ai-response-label">Onyx Response</span>
        <button class="ai-topbar-clear" id="aiBarClear" onclick="clearOnyx()" title="Clear">&#xd7;</button>
      </div>
      <div class="ai-response-text" id="aiBarResponse">
        <span class="ai-response-empty">Ask anything or give a command — Onyx can answer questions and control the dashboard.</span>
      </div>
      <div class="ai-action-bar" id="aiActionBar"></div>
    </div>

    <!-- Right: Suggestions -->
    <div class="ai-suggest-panel">
      <button class="ai-suggest-btn" id="aiSuggestBtn" onclick="toggleSuggestions()">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2a1 1 0 110 2 1 1 0 010-2zm1 9H7v-5h2v5z"/></svg>
        Suggest Next Steps
      </button>
      <div class="ai-suggest-label">AI-powered trading suggestions based on your portfolio</div>
    </div>
  </div>

  <!-- Suggestions dropdown -->
  <div class="ai-suggest-dropdown" id="aiSuggestDropdown">
    <div class="ai-suggest-header">Onyx Suggestions</div>
    <div class="ai-suggest-list" id="aiSuggestList">
      <div class="ai-suggest-loading">Loading suggestions...</div>
    </div>
  </div>
"""

AI_BAR_JS = r"""
  <script>
  /* ── Onyx AI Agent ── */

  // Gather page context for Onyx
  function getOnyxContext() {
    try {
      var wl  = JSON.parse(localStorage.getItem('onyx_wl_v3') || '[]');
      var port = JSON.parse(localStorage.getItem('onyx_portfolio') || '[]');
      return {
        page: window.location.pathname === '/' ? 'dashboard' : 'research',
        watchlist: wl.map(function(w) { return { ticker: w.ticker, signal: w.signal, score: w.score }; }),
        portfolio: port.map(function(p) { return { ticker: p.ticker, shares: p.shares }; })
      };
    } catch(e) { return {}; }
  }

  // Execute action returned by Onyx
  function executeOnyxAction(action) {
    if (!action) return;
    var type = action.type;
    var ticker = (action.ticker || '').toUpperCase();

    if (type === 'addTicker' && ticker) {
      if (typeof addTicker === 'function') {
        var inp = document.getElementById('tickerInput');
        if (inp) { inp.value = ticker; addTicker(); }
        return '✓ Added ' + ticker + ' to watchlist';
      }
    }
    if (type === 'buy' && ticker) {
      if (typeof buyFromPanel === 'function') {
        selectStock(ticker);
        setTimeout(function() {
          var bi = document.getElementById('buyInput-' + ticker);
          if (bi) { bi.value = action.shares || 1; buyFromPanel(ticker); }
        }, 300);
        return '✓ Buying ' + (action.shares || 1) + ' shares of ' + ticker;
      }
    }
    if (type === 'sell' && ticker) {
      if (typeof sellFromPanel === 'function') {
        selectStock(ticker);
        setTimeout(function() {
          var si = document.getElementById('sellInput-' + ticker);
          if (si) { si.value = action.shares || 1; sellFromPanel(ticker); }
        }, 300);
        return '✓ Selling ' + (action.shares || 1) + ' shares of ' + ticker;
      }
    }
    if (type === 'scan' && ticker) {
      if (typeof scanTicker === 'function') { scanTicker(ticker); return '✓ Scanning ' + ticker; }
    }
    if (type === 'scanAll') {
      if (typeof scanAll === 'function') { scanAll(); return '✓ Scanning all stocks'; }
    }
    if (type === 'navigate') {
      if (action.page === 'research') window.location.href = '/search';
      if (action.page === 'dashboard') window.location.href = '/';
    }
    if (type === 'research' && action.topic) {
      if (window.location.pathname !== '/search') {
        window.location.href = '/search';
      } else if (typeof runResearch === 'function') {
        document.getElementById('topicInput').value = action.topic;
        runResearch();
      }
    }
    return null;
  }

  document.getElementById('aiBarInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') askOnyx();
    if (e.key === 'Escape') clearOnyx();
  });

  async function askOnyx() {
    var q = document.getElementById('aiBarInput').value.trim();
    if (!q) return;
    var send = document.getElementById('aiBarSend');
    var resp = document.getElementById('aiBarResponse');
    var clr  = document.getElementById('aiBarClear');
    var ab   = document.getElementById('aiActionBar');
    send.disabled = true;
    resp.innerHTML = '<span class="ai-response-thinking">Onyx is thinking...</span>';
    ab.classList.remove('active');
    clr.style.display = 'block';
    try {
      var res = await fetch('/ask', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question: q, context: getOnyxContext() })
      });
      var data = await res.json();
      resp.textContent = data.answer || 'No answer found.';
      // Execute action if any
      if (data.action) {
        var confirmation = executeOnyxAction(data.action);
        if (confirmation) {
          ab.innerHTML = '<span class="ai-action-chip">' + confirmation + '</span>';
          ab.classList.add('active');
        }
      }
    } catch(e) {
      resp.textContent = 'Error reaching Onyx: ' + e.message;
    } finally {
      send.disabled = false;
    }
  }

  function clearOnyx() {
    document.getElementById('aiBarInput').value = '';
    document.getElementById('aiBarResponse').innerHTML =
      '<span class="ai-response-empty">Ask anything or give a command — Onyx can answer questions and control the dashboard.</span>';
    document.getElementById('aiBarClear').style.display = 'none';
    document.getElementById('aiActionBar').classList.remove('active');
  }

  // ── Suggestions ──
  var suggestionsLoaded = false;
  function toggleSuggestions() {
    var dd = document.getElementById('aiSuggestDropdown');
    dd.classList.toggle('open');
    if (dd.classList.contains('open') && !suggestionsLoaded) loadSuggestions();
  }
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#aiSuggestDropdown') && !e.target.closest('#aiSuggestBtn')) {
      document.getElementById('aiSuggestDropdown').classList.remove('open');
    }
  });
  async function loadSuggestions() {
    var list = document.getElementById('aiSuggestList');
    list.innerHTML = '<div class="ai-suggest-loading">Onyx is analysing your portfolio...</div>';
    suggestionsLoaded = true;
    try {
      var res = await fetch('/suggest', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ context: getOnyxContext() })
      });
      var data = await res.json();
      list.innerHTML = (data.suggestions || []).map(function(s) {
        return '<div class="ai-suggest-item" onclick="applySuggestion(' + JSON.stringify(s).replace(/"/g, "&quot;") + ')">' +
          '<div class="ai-suggest-item-title">' + s.title + '</div>' +
          '<div class="ai-suggest-item-desc">' + s.description + '</div>' +
        '</div>';
      }).join('');
    } catch(e) {
      list.innerHTML = '<div class="ai-suggest-loading">Could not load suggestions.</div>';
    }
  }
  function applySuggestion(s) {
    document.getElementById('aiSuggestDropdown').classList.remove('open');
    if (s.action) executeOnyxAction(s.action);
    // Show suggestion in response panel
    document.getElementById('aiBarResponse').textContent = s.title + ' — ' + s.description;
    document.getElementById('aiBarClear').style.display = 'block';
  }
  function refreshSuggestions() {
    suggestionsLoaded = false;
    loadSuggestions();
  }
  </script>
"""

def inject(html: str) -> str:
    # Inject CSS — handle any whitespace before </style>
    for style_end in ["  </style>", "</style>"]:
        if style_end in html:
            html = html.replace(style_end, AI_BAR_CSS + style_end, 1)
            break
    # Inject HTML before main wrapper
    for wrapper in ['<div class="app">', '<div class="layout">']:
        if wrapper in html:
            html = html.replace(wrapper, AI_BAR_HTML + "\n" + wrapper, 1)
            break
    html = html.replace("</body>", AI_BAR_JS + "\n</body>", 1)
    return html
