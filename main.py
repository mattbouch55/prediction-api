from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import os

from models import PredictionRequest, PredictionResponse, PredictionsListResponse, DomainSummaryResponse
from agent import PredictionAgent
from database import Database

db = Database()
agent = PredictionAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield


app = FastAPI(
    title="AI Prediction Intelligence API",
    description="Scans the internet for news signals and generates predictions for Tech, Markets, and Geopolitics.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your Figma Make domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    """Serve the Onyx AI frontend."""
    return FileResponse("index.html")


@app.get("/health")
def health_check():
    """Check API is running."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/predict", response_model=PredictionResponse)
async def run_prediction(request: PredictionRequest):
    """
    Run a prediction scan for a given topic and domain.
    The agent searches the internet across multiple angles and returns
    structured predictions with confidence levels and signals.
    """
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


@app.get("/predictions", response_model=PredictionsListResponse)
def get_all_predictions(limit: int = 50, offset: int = 0):
    """Return all stored predictions, newest first."""
    predictions = db.get_predictions(limit=limit, offset=offset)
    total = db.count_predictions()
    return PredictionsListResponse(predictions=predictions, total=total)


@app.get("/predictions/{domain}", response_model=PredictionsListResponse)
def get_predictions_by_domain(domain: str, limit: int = 20):
    """Return predictions filtered by domain: tech | markets | geopolitics"""
    if domain not in ("tech", "markets", "geopolitics"):
        raise HTTPException(status_code=400, detail="domain must be one of: tech, markets, geopolitics")
    predictions = db.get_predictions_by_domain(domain=domain, limit=limit)
    total = db.count_predictions(domain=domain)
    return PredictionsListResponse(predictions=predictions, total=total)


@app.get("/summary", response_model=DomainSummaryResponse)
def get_domain_summary():
    """Return a high-level count summary across all three domains."""
    return DomainSummaryResponse(
        tech=db.count_predictions("tech"),
        markets=db.count_predictions("markets"),
        geopolitics=db.count_predictions("geopolitics"),
        total=db.count_predictions()
    )


@app.delete("/predictions/{prediction_id}")
def delete_prediction(prediction_id: str):
    """Delete a specific prediction by ID."""
    deleted = db.delete_prediction(prediction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {"message": "Deleted successfully"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
