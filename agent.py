import anthropic
import json
import os
import asyncio
from models import PredictionResponse, Prediction, Signal, InvestmentResponse, InvestmentSignal


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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, topic, domain, time_horizon)
        return result

    def _run_sync(self, topic: str, domain: str, time_horizon: str) -> PredictionResponse:
        domain_context = DOMAIN_PROMPTS.get(domain, "You are an intelligence analyst.")

        custom_source_note = ""
        if custom_source:
            custom_source_note = f"\n\nIMPORTANT: The user has provided this specific source URL for you to consider in your analysis: {custom_source}\nFetch and read this URL as part of your research and factor its content into your predictions."

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
          "url": "exact URL from search results or null",
          "strength": "strong"
        }}
      ],
      "risk_factors": ["thing that could invalidate this prediction"]
    }}
  ]
}}

Generate 2-3 predictions. Return ONLY the JSON object.{custom_source_note}
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                full_text += block.text

        if not full_text:
            raise ValueError("No text response from agent")

        return self._parse_response(full_text, topic, domain)

    def _parse_response(self, text: str, topic: str, domain: str) -> PredictionResponse:
        clean = text.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if part.startswith("json"):
                    clean = part[4:].strip()
                    break
                elif part.strip().startswith("{"):
                    clean = part.strip()
                    break

        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse JSON: {e}")

        predictions = []
        for p in data.get("predictions", []):
            signals = [
                Signal(
                    type=s.get("type", "unknown"),
                    description=s.get("description", ""),
                    source=s.get("source"),
                    url=s.get("url"),
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


class InvestmentAgent:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"

    async def run(self, ticker: str, asset_type: str, custom_source: str = None) -> InvestmentResponse:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, ticker, asset_type, custom_source)
        return result

    def _run_sync(self, ticker: str, asset_type: str, custom_source: str = None) -> InvestmentResponse:
        asset_label = "stock" if asset_type == "stock" else "cryptocurrency"

        prompt = f"""
You are a senior investment analyst. Analyse the {asset_label} with ticker: {ticker}

Search for:
1. Latest news about {ticker} in the past 1-2 weeks
2. Recent earnings, product launches, or major announcements
3. Analyst price targets and ratings
4. Market sentiment and momentum
5. Key risks and headwinds

Based on your research, return ONLY a valid JSON object (no markdown) in this exact format:

{{
  "asset_name": "Full company or asset name",
  "signal": "BUY or WATCH or HOLD",
  "confidence": "High or Medium or Low",
  "time_horizon": "1-4 weeks",
  "summary": "2-3 sentence overview of the investment case",
  "catalysts": [
    "Specific positive catalyst that could drive price up",
    "Another upside catalyst"
  ],
  "risks": [
    "Specific risk that could drive price down",
    "Another downside risk"
  ],
  "supporting_signals": [
    {{
      "type": "signal type e.g. Earnings, Analyst Rating, News",
      "description": "What this signal means for the investment",
      "source": "Source name e.g. Reuters, Bloomberg",
      "url": "exact URL from search results or null",
      "strength": "strong or moderate or weak"
    }}
  ]
}}

Signal definitions:
- BUY: Strong positive catalysts, good risk/reward, positive momentum
- WATCH: Interesting but wait for better entry or more clarity  
- HOLD: No clear directional catalyst, roughly balanced risks
- SELL: Strong negative catalysts, price expected to decline, risks significantly outweigh upside

Return ONLY the JSON object.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        full_text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                full_text += block.text

        if not full_text:
            raise ValueError("No response from investment agent")

        clean = full_text.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if part.startswith("json"):
                    clean = part[4:].strip()
                    break
                elif part.strip().startswith("{"):
                    clean = part.strip()
                    break

        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]

        data = json.loads(clean)

        signals = [
            InvestmentSignal(
                type=s.get("type", "unknown"),
                description=s.get("description", ""),
                source=s.get("source"),
                url=s.get("url"),
                strength=s.get("strength", "moderate")
            )
            for s in data.get("supporting_signals", [])
        ]

        return InvestmentResponse(
            ticker=ticker,
            asset_name=data.get("asset_name"),
            asset_type=asset_type,
            signal=data.get("signal", "WATCH"),
            confidence=data.get("confidence", "Medium"),
            time_horizon=data.get("time_horizon", "1-4 weeks"),
            summary=data.get("summary", ""),
            catalysts=data.get("catalysts", []),
            risks=data.get("risks", []),
            supporting_signals=signals
        )
