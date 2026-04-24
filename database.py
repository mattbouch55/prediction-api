import sqlite3
import json
import os
from typing import List, Optional
from models import PredictionResponse, Prediction, Signal

DB_PATH = os.environ.get("DB_PATH", "predictions.db")


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    news_summary TEXT,
                    sources_searched TEXT,   -- JSON array
                    agent_notes TEXT,
                    predictions TEXT NOT NULL -- JSON array of prediction objects
                )
            """)
            conn.commit()

    def save_prediction(self, response: PredictionResponse):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO predictions
                    (id, topic, domain, created_at, news_summary, sources_searched, agent_notes, predictions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.id,
                    response.topic,
                    response.domain,
                    response.created_at,
                    response.news_summary,
                    json.dumps(response.sources_searched),
                    response.agent_notes,
                    json.dumps([p.model_dump() for p in response.predictions])
                )
            )
            conn.commit()

    def get_predictions(self, limit: int = 50, offset: int = 0) -> List[PredictionResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM predictions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [self._row_to_response(r) for r in rows]

    def get_predictions_by_domain(self, domain: str, limit: int = 20) -> List[PredictionResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM predictions WHERE domain = ? ORDER BY created_at DESC LIMIT ?",
                (domain, limit)
            ).fetchall()
        return [self._row_to_response(r) for r in rows]

    def count_predictions(self, domain: Optional[str] = None) -> int:
        with self._connect() as conn:
            if domain:
                row = conn.execute(
                    "SELECT COUNT(*) FROM predictions WHERE domain = ?", (domain,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()
        return row[0]

    def delete_prediction(self, prediction_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM predictions WHERE id = ?", (prediction_id,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def _row_to_response(self, row: sqlite3.Row) -> PredictionResponse:
        raw_predictions = json.loads(row["predictions"])
        predictions = []
        for p in raw_predictions:
            signals = [Signal(**s) for s in p.get("supporting_signals", [])]
            predictions.append(Prediction(
                statement=p["statement"],
                confidence=p["confidence"],
                time_horizon=p["time_horizon"],
                reasoning=p["reasoning"],
                supporting_signals=signals,
                risk_factors=p.get("risk_factors", [])
            ))

        return PredictionResponse(
            id=row["id"],
            topic=row["topic"],
            domain=row["domain"],
            created_at=row["created_at"],
            news_summary=row["news_summary"] or "",
            sources_searched=json.loads(row["sources_searched"] or "[]"),
            agent_notes=row["agent_notes"],
            predictions=predictions
        )
