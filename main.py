from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import os

from models import PredictionRequest, PredictionResponse, PredictionsListResponse, DomainSummaryResponse, InvestmentRequest, InvestmentResponse
from agent import PredictionAgent, InvestmentAgent
from database import Database

db = Database()
agent = PredictionAgent()
invest_agent = InvestmentAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield


app = FastAPI(
    title="Onyx AI API",
    description="AI-powered prediction and investment signal intelligence.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Frontend routes ──────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    return FileResponse("index.html")


@app.get("/invest")
def serve_invest():
    return FileResponse("invest.html")


@app.get("/watchlist")
def serve_watchlist():
    return FileResponse("watchlist.html")


# ── API routes ───────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/prices")
def get_prices(tickers: str):
    """Get current prices using direct Yahoo Finance API calls."""
    import requests as req
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    result = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://finance.yahoo.com/",
    }
    for ticker in ticker_list:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
            r = req.get(url, headers=headers, timeout=10)
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = round(float(meta["regularMarketPrice"]), 2)
            prev = round(float(meta.get("chartPreviousClose", meta["regularMarketPrice"])), 2)
            change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0
            result[ticker] = {"price": price, "prev_close": prev, "change_pct": change_pct}
        except Exception as e:
            result[ticker] = {"price": None, "change_pct": None, "error": str(e)}
    return result


@app.post("/predict", response_model=PredictionResponse)
async def run_prediction(request: PredictionRequest):
    try:
        result = await agent.run(
            topic=request.topic,
            domain=request.domain,
            time_horizon=request.time_horizon
        )
        db.save_prediction(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invest", response_model=InvestmentResponse)
async def run_investment(request: InvestmentRequest):
    try:
        result = await invest_agent.run(
            ticker=request.ticker,
            asset_type=request.asset_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions", response_model=PredictionsListResponse)
def get_all_predictions(limit: int = 50, offset: int = 0):
    predictions = db.get_predictions(limit=limit, offset=offset)
    total = db.count_predictions()
    return PredictionsListResponse(predictions=predictions, total=total)


@app.get("/predictions/{domain}", response_model=PredictionsListResponse)
def get_predictions_by_domain(domain: str, limit: int = 20):
    if domain not in ("tech", "markets", "geopolitics"):
        raise HTTPException(status_code=400, detail="domain must be one of: tech, markets, geopolitics")
    predictions = db.get_predictions_by_domain(domain=domain, limit=limit)
    total = db.count_predictions(domain=domain)
    return PredictionsListResponse(predictions=predictions, total=total)


@app.get("/summary", response_model=DomainSummaryResponse)
def get_domain_summary():
    return DomainSummaryResponse(
        tech=db.count_predictions("tech"),
        markets=db.count_predictions("markets"),
        geopolitics=db.count_predictions("geopolitics"),
        total=db.count_predictions()
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
