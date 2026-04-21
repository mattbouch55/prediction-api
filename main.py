import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from models import PredictionRequest, InvestmentRequest
from agent import PredictionAgent, InvestmentAgent
from database import Database
import requests as req

app = FastAPI(title="Onyx AI Prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()
db.initialize()

predict_agent = PredictionAgent()
invest_agent  = InvestmentAgent()


# ── PAGES ─────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/search", response_class=HTMLResponse)
def search_page():
    with open("search.html", "r") as f:
        return f.read()


# ── PRICES ────────────────────────────────────────────────────

@app.get("/prices")
def get_prices(tickers: str):
    """Get real-time stock prices. Tries Finnhub first, then Yahoo Finance."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    api_key = os.environ.get("FINNHUB_API_KEY", "")
    result = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    for ticker in ticker_list:
        price = None
        prev  = None

        # 1. Finnhub (primary)
        if api_key:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
                r = req.get(url, timeout=6, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    c  = data.get("c", 0)
                    pc = data.get("pc", 0)
                    # Use current price if available, else previous close (market closed)
                    best = c if (c and float(c) > 0) else pc
                    if best and float(best) > 0:
                        price = round(float(best), 2)
                        prev  = round(float(pc), 2) if pc else price
            except Exception:
                pass

        # 2. Yahoo Finance v8 (fallback)
        if not price:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
                r = req.get(url, timeout=6, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("chart", {}).get("result", [])
                    if results:
                        meta = results[0].get("meta", {})
                        p  = meta.get("regularMarketPrice") or meta.get("previousClose")
                        pc = meta.get("previousClose") or p
                        if p and float(p) > 0:
                            price = round(float(p), 2)
                            prev  = round(float(pc), 2) if pc else price
            except Exception:
                pass

        # 3. Yahoo Finance v7 (second fallback)
        if not price:
            try:
                url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
                r = req.get(url, timeout=6, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    quotes = data.get("quoteResponse", {}).get("result", [])
                    if quotes:
                        q  = quotes[0]
                        p  = q.get("regularMarketPrice")
                        pc = q.get("regularMarketPreviousClose") or p
                        if p and float(p) > 0:
                            price = round(float(p), 2)
                            prev  = round(float(pc), 2) if pc else price
            except Exception:
                pass

        if price:
            chg = round(((price - prev) / prev) * 100, 2) if prev and prev > 0 else 0
            result[ticker] = {"price": price, "prev_close": prev, "change_pct": chg}
        else:
            result[ticker] = {"price": None, "change_pct": None, "error": "No price data"}

    return result


# ── CHART ─────────────────────────────────────────────────────

@app.get("/chart")
def get_chart_data(ticker: str, from_ts: int = None, to_ts: int = None, resolution: str = "5"):
    import time
    api_key = os.environ.get("FINNHUB_API_KEY", "")
    now     = int(time.time())
    from_ts = from_ts or (now - 86400)
    to_ts   = to_ts   or now
    try:
        url  = f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution={resolution}&from={from_ts}&to={to_ts}&token={api_key}"
        r    = req.get(url, timeout=10)
        data = r.json()
        if data.get("s") == "ok":
            prices = [{"t": t, "p": c} for t, c in zip(data["t"], data["c"])]
            return {"ticker": ticker, "prices": prices}
        return {"ticker": ticker, "prices": []}
    except Exception as e:
        return {"ticker": ticker, "prices": [], "error": str(e)}


# ── AI ────────────────────────────────────────────────────────

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

@app.post("/invest")
async def invest(request: InvestmentRequest):
    result = await invest_agent.run(
        ticker=request.ticker,
        asset_type=request.asset_type,
        custom_source=getattr(request, "custom_source", None)
    )
    return result

@app.get("/predictions")
def get_predictions(limit: int = 10):
    try:
        return db.get_predictions(limit=limit)
    except Exception:
        return []


@app.post("/stock-effect")
async def stock_effect(request: dict):
    """Analyse how a macro prediction affects a specific stock."""
    import anthropic as ant
    client = ant.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prediction = request.get("prediction", "")
    ticker     = request.get("ticker", "").upper().strip()
    confidence = request.get("confidence", "")
    topic      = request.get("topic", "")

    prediction = prediction or ""
    topic = topic or ""
    confidence = confidence or ""

    prompt = f"""You are a senior equity analyst. A macro/thematic research prediction has been made:

TOPIC: {topic}
PREDICTION: {prediction}
PREDICTION CONFIDENCE: {confidence}

Analyse how this specific prediction would affect the stock: {ticker}

Search the web for current information about {ticker} and its relationship to the prediction topic.

Return ONLY a valid JSON object (no markdown, no extra text):
{{
  "ticker": "{ticker}",
  "company_name": "Full company name",
  "impact": "High",
  "direction": "Bullish",
  "impact_score": 5,
  "summary": "2-3 sentence explanation",
  "bull_scenario": "What happens if prediction is correct",
  "bear_scenario": "What happens if prediction is wrong",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "time_horizon": "2-4 weeks",
  "confidence": "Medium"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                text += block.text
        # Extract JSON
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            # Ensure no None values that would cause concat errors
            defaults = {
                "ticker": ticker, "company_name": ticker,
                "impact": "Medium", "direction": "Neutral",
                "impact_score": 0, "summary": "Analysis unavailable.",
                "bull_scenario": "N/A", "bear_scenario": "N/A",
                "key_factors": [], "time_horizon": "Unknown",
                "confidence": "Low"
            }
            for k, v in defaults.items():
                if result.get(k) is None:
                    result[k] = v
            return result
        return {"error": "Could not parse AI response"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}
