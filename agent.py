import anthropic
import json
import os
from models import PredictionResponse, Prediction, Signal


DOMAIN_PROMPTS = {
    "tech": "You are a senior technology intelligence analyst. Focus on AI/ML, Big Tech, regulation, semiconductors, and startup funding.",
    "markets": "You are a quantitative market analyst. Focus on equity markets, interest rates, inflation, earnings, commodities, and crypto.",
    "geopolitics": "You are a geopolitical risk analyst. Focus on diplomacy, elections, military movements, sanctions, and trade negotiations."
}

class PredictionAgent:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"

    async def run(self, topic: str, domain: str, time_horizon: str) -> PredictionResponse:
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, topic, domain, time_horizon)
        return result

    def _run_sync(self, topic: str, domain: str, time_horizon: str) -> PredictionResponse:
        domain_context = DOMAIN_PROMPTS.get(domain, "You are an intelligence analyst.")

        prompt = f"""
{domain_context}

Search the web for the latest news about: {topic}

Then return ONLY a valid JSON object (no markdown, no explanation) in this exact format:

{{
  "news_summary": "2-3 sentence overview of what you found",
  "sources_searched": ["query 1", "query 2", "query 3"],
  "agent_notes": "Any caveats or limitations",
  "predictions": [
    {{
      "statement": "Specific falsifiable prediction for the next {time_horizon}",
      "confidence": "High",
      "time_horizon": "{time_horizon}",
      "reasoning": "Why you believe this based on the news",
      "supporting_signals": [
        {{
          "type": "signal type",
          "description": "what this signal means",
          "source": "source name",
          "strength": "strong"
        }}
      ],
      "risk_factors": ["thing that could invalidate this prediction"]
    }}
  ]
}}

Generate 2-3 predictions. Return ONLY the JSON object.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                full_text += block.text

        if not full_text:
            raise ValueError("No text response from agent")

        return self._parse_response(full_text, topic, domain)

    def _parse_response(self, text: str, topic: str, domain: str) -> PredictionResponse:
        clean = text.strip()

        # Strip markdown code fences if present
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if part.startswith("json"):
                    clean = part[4:].strip()
                    break
                elif part.strip().startswith("{"):
                    clean = part.strip()
                    break

        # Find JSON object
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse JSON: {e}. Text was: {clean[:300]}")

        predictions = []
        for p in data.get("predictions", []):
            signals = [
                Signal(
                    type=s.get("type", "unknown"),
                    description=s.get("description", ""),
                    source=s.get("source"),
                    strength=s.get("strength", "moderate")
                )
                for s in p.get("supporting_signals", [])
            ]
            predictions.append(Prediction(
                statement=p.get("statement", ""),
                confidence=p.get("confidence", "Medium"),
                time_horizon=p.get("time_horizon", "1-2 weeks"),
                reasoning=p.get("reasoning", ""),
                supporting_signals=signals,
                risk_factors=p.get("risk_factors", [])
            ))

        return PredictionResponse(
            topic=topic,
            domain=domain,
            predictions=predictions,
            news_summary=data.get("news_summary", ""),
            sources_searched=data.get("sources_searched", []),
            agent_notes=data.get("agent_notes")
        )
