import os
import json
import time
import asyncio
import requests
import anthropic

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from models import PredictionRequest, InvestmentRequest
from agent import PredictionAgent, InvestmentAgent
from database import Database
from ai_bar import inject as inject_ai_bar

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="Onyx AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db = Database()
db.initialize()
predict_agent = PredictionAgent()
invest_agent  = InvestmentAgent()

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FINNHUB_KEY   = os.environ.get("FINNHUB_API_KEY", "")
HEADERS       = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Pages ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/markets")

@app.get("/search", response_class=HTMLResponse)
def research():
    return inject_ai_bar(open("search.html").read())

@app.get("/markets", response_class=HTMLResponse)
def markets():
    return inject_ai_bar(open("markets.html").read())

# ── Prices ─────────────────────────────────────────────────────
@app.get("/prices")
def get_prices(tickers: str):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    result = {}
    for ticker in ticker_list:
        price, prev = None, None

        # Finnhub (primary)
        if FINNHUB_KEY:
            try:
                r = requests.get(
                    f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}",
                    timeout=5, headers=HEADERS
                )
                if r.status_code == 200:
                    d = r.json()
                    c, pc = d.get("c", 0), d.get("pc", 0)
                    best = c if (c and float(c) > 0) else pc
                    if best and float(best) > 0:
                        price = round(float(best), 2)
                        prev  = round(float(pc), 2) if pc else price
            except Exception:
                pass

        # Yahoo Finance v8 (fallback)
        if not price:
            try:
                r = requests.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d",
                    timeout=5, headers=HEADERS
                )
                if r.status_code == 200:
                    res = r.json().get("chart", {}).get("result", [])
                    if res:
                        meta = res[0].get("meta", {})
                        p  = meta.get("regularMarketPrice") or meta.get("previousClose")
                        pc = meta.get("previousClose") or p
                        if p and float(p) > 0:
                            price = round(float(p), 2)
                            prev  = round(float(pc), 2) if pc else price
            except Exception:
                pass

        if price:
            chg = round(((price - prev) / prev) * 100, 2) if prev and prev > 0 else 0
            result[ticker] = {"price": price, "prev_close": prev, "change_pct": chg}
        else:
            result[ticker] = {"price": None, "change_pct": None, "error": "No data"}

    return result

# ── Chart ──────────────────────────────────────────────────────
@app.get("/chart")
def get_chart(ticker: str, from_ts: int = None, to_ts: int = None, resolution: str = "5"):
    now = int(time.time())
    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/stock/candle"
            f"?symbol={ticker}&resolution={resolution}"
            f"&from={from_ts or now-86400}&to={to_ts or now}&token={FINNHUB_KEY}",
            timeout=8
        )
        d = r.json()
        if d.get("s") == "ok":
            return {"ticker": ticker, "prices": [{"t": t, "p": c} for t, c in zip(d["t"], d["c"])]}
    except Exception:
        pass
    return {"ticker": ticker, "prices": []}

# ── AI: Predict ────────────────────────────────────────────────
@app.post("/predict")
async def predict(request: PredictionRequest):
    result = await predict_agent.run(
        topic=request.topic,
        domain=request.domain,
        time_horizon=request.time_horizon,
        custom_source=getattr(request, "custom_source", None)
    )
    try:
        db.save_prediction(result)
    except Exception:
        pass
    return result

# ── AI: Invest ─────────────────────────────────────────────────
@app.post("/invest")
async def invest(request: InvestmentRequest):
    return await invest_agent.run(
        ticker=request.ticker,
        asset_type=request.asset_type,
        custom_source=getattr(request, "custom_source", None)
    )

# ── AI: Stock Effect ───────────────────────────────────────────
@app.post("/stock-effect")
async def stock_effect(request: dict):
    prediction = (request.get("prediction") or "").strip()
    ticker     = (request.get("ticker") or "").upper().strip()
    confidence = request.get("confidence") or ""
    topic      = request.get("topic") or prediction

    if not prediction or not ticker:
        return {"error": "prediction and ticker required"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    prompt = f"""You are a senior equity analyst.

TOPIC: {topic}
PREDICTION: {prediction}
CONFIDENCE: {confidence}

Analyse how this prediction affects {ticker}. Search the web for current data.

Return ONLY valid JSON:
{{
  "ticker": "{ticker}",
  "company_name": "Full name",
  "impact": "High|Medium|Low|Minimal",
  "direction": "Bullish|Bearish|Neutral|Mixed",
  "impact_score": 0,
  "summary": "2-3 sentence explanation",
  "bull_scenario": "If prediction correct",
  "bull_price_direction": "Increase|Decrease",
  "bull_price_magnitude": "+5-10%",
  "bear_scenario": "If prediction wrong",
  "bear_price_direction": "Increase|Decrease",
  "bear_price_magnitude": "-3-7%",
  "key_factors": ["factor1","factor2","factor3"],
  "time_horizon": "2-4 weeks",
  "confidence": "High|Medium|Low"
}}"""

    defaults = {
        "ticker": ticker, "company_name": ticker, "impact": "Medium",
        "direction": "Neutral", "impact_score": 0,
        "summary": "Analysis unavailable.", "bull_scenario": "N/A",
        "bull_price_direction": "Increase", "bull_price_magnitude": "Unknown",
        "bear_scenario": "N/A", "bear_price_direction": "Decrease",
        "bear_price_magnitude": "Unknown", "key_factors": [],
        "time_horizon": "Unknown", "confidence": "Low"
    }

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=800,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            result = json.loads(text[s:e])
            for k, v in defaults.items():
                if result.get(k) is None:
                    result[k] = v
            return result
    except Exception as ex:
        return {"error": str(ex)}

    return {"error": "Could not parse response"}

# ── AI: Ask ────────────────────────────────────────────────────
@app.post("/ask")
async def ask(request: dict):
    question = (request.get("question") or "").strip()
    context  = request.get("context") or {}
    if not question:
        return {"answer": "Please ask a question.", "action": None}

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    system = """You are Onyx, an AI agent embedded in a stock investment dashboard.
You can answer questions AND control the dashboard by returning actions.

If the user wants to:
- Add a stock to watchlist: action={"type":"addTicker","ticker":"TSLA"}
- Buy a stock: action={"type":"buy","ticker":"TSLA","shares":5}
- Sell a stock: action={"type":"sell","ticker":"TSLA","shares":5}
- Scan/analyse a stock: action={"type":"scan","ticker":"TSLA"}
- Go to research page: action={"type":"navigate","page":"research"}
- Go to dashboard: action={"type":"navigate","page":"dashboard"}
- Search a topic: action={"type":"research","topic":"Federal Reserve rates"}
- No action needed: action=null

Always respond with JSON:
{"answer": "your 1-3 sentence response", "action": null or action object}

Be conversational and helpful. If buying/selling, confirm what you did."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=400,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            system=system,
            messages=[{"role": "user", "content":
                f"User context: {json.dumps(context)}\n\nQuestion/Command: {question}"}]
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
        # Try to parse JSON response
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            try:
                parsed = json.loads(text[s:e])
                return {
                    "answer": parsed.get("answer", text.strip()),
                    "action": parsed.get("action", None)
                }
            except Exception:
                pass
        return {"answer": text.strip() or "No answer found.", "action": None}
    except Exception as ex:
        return {"answer": f"Error: {str(ex)}", "action": None}

@app.post("/suggest")
async def suggest(request: dict):
    """Generate smart next-step suggestions based on user context."""
    context = request.get("context") or {}
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": f"""You are Onyx, an AI investment assistant.

Based on this user's current dashboard state, suggest 4 specific, actionable next steps to help them trade smarter.

User context: {json.dumps(context)}

Return ONLY a JSON array of 4 suggestions:
[
  {{"title": "Short action title", "description": "One sentence explaining why", "action": {{"type": "scan", "ticker": "AAPL"}} or null}},
  ...
]

Make suggestions specific to their actual watchlist/portfolio. Search for relevant market info if needed."""}]
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
        s, e = text.find("["), text.rfind("]") + 1
        if s >= 0 and e > s:
            return {"suggestions": json.loads(text[s:e])}
    except Exception as ex:
        pass
    return {"suggestions": [
        {"title": "Scan your watchlist", "description": "Get AI signals on all your tracked stocks.", "action": {"type": "scanAll"}},
        {"title": "Research market trends", "description": "Ask Onyx about current macro conditions.", "action": {"type": "navigate", "page": "research"}},
        {"title": "Review your portfolio", "description": "Check P&L and consider rebalancing.", "action": None},
        {"title": "Add a new position", "description": "Diversify by adding a new ticker.", "action": None}
    ]}

# ── History ────────────────────────────────────────────────────
@app.get("/predictions")
def get_predictions(limit: int = 10):
    try:
        return db.get_predictions(limit=limit)
    except Exception:
        return []


@app.get("/kalshi-market")
async def get_kalshi_market(url: str = "", ticker: str = ""):
    """Fetch live Kalshi market data via AI web search."""
    # Extract ticker from URL
    if url and not ticker:
        parts = url.rstrip("/").split("/")
        ticker = parts[-1]

    if not ticker and not url:
        return {"error": "No URL provided"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    prompt = (
        f"Search the web for this Kalshi prediction market: {url or ticker}\n\n"
        "Find and return the current YES price in cents (1-99), NO price, the full market question, "
        "close/expiry date, and trading volume. "
        "Return ONLY a valid JSON object, no markdown, no explanation:\n"
        '{"title": "...", "yes": 62, "no": 38, "close": "Jun 18 2025", "volume": "$1.2M", "category": "finance"}'
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
        # Find JSON in response
        s = text.find("{")
        e = text.rfind("}") + 1
        if s >= 0 and e > s:
            result = json.loads(text[s:e])
            result["url"] = url or f"https://kalshi.com/markets/{ticker}"
            result["ticker"] = ticker
            if result.get("yes") and not result.get("no"):
                result["no"] = 100 - int(result["yes"])
            if result.get("no") and not result.get("yes"):
                result["yes"] = 100 - int(result["no"])
            return result
        # If no JSON found, return what we got for debugging
        return {"error": f"AI could not parse market. Raw: {text[:200]}"}
    except Exception as ex:
        return {"error": str(ex)}


@app.post("/analyse-market")
async def analyse_market(request: dict):
    question = (request.get("question") or "").strip()
    if not question:
        return {"error": "No question provided"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=600,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": question}]
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e])
            except Exception:
                pass
        return {"error": "Could not parse response", "raw": text[:300]}
    except Exception as ex:
        return {"error": str(ex)}

@app.get("/health")
def health():
    return {"status": "ok"}
