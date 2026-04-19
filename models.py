from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid
from datetime import datetime


class Domain(str, Enum):
    tech = "tech"
    markets = "markets"
    geopolitics = "geopolitics"


class TimeHorizon(str, Enum):
    days = "1-7 days"
    weeks = "1-2 weeks"
    month = "3-4 weeks"


class PredictionRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200, example="AI regulation in the EU")
    domain: Domain = Field(..., example="tech")
    time_horizon: TimeHorizon = Field(default=TimeHorizon.weeks, example="1-2 weeks")

    class Config:
        use_enum_values = True


class Signal(BaseModel):
    type: str          # e.g. "policy filing", "earnings guidance", "sentiment shift"
    description: str
    source: Optional[str] = None
    strength: str      # "strong" | "moderate" | "weak"


class Prediction(BaseModel):
    statement: str                  # The specific, falsifiable prediction
    confidence: str                 # "High" | "Medium" | "Low"
    time_horizon: str
    supporting_signals: List[Signal]
    risk_factors: List[str]         # Things that could invalidate the prediction
    reasoning: str                  # Agent's chain of thought


class PredictionResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    domain: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    predictions: List[Prediction]
    news_summary: str               # Brief overview of what was found
    sources_searched: List[str]     # Queries the agent ran
    agent_notes: Optional[str] = None  # Any caveats or limitations noted


class PredictionsListResponse(BaseModel):
    predictions: List[PredictionResponse]
    total: int


class DomainSummaryResponse(BaseModel):
    tech: int
    markets: int
    geopolitics: int
    total: int
