import anthropic
import json
import os
import asyncio
from typing import List
from models import PredictionResponse, Prediction, Signal


DOMAIN_PROMPTS = {
    "tech": """
You are a senior technology intelligence analyst specializing in short-term forecasting.
Focus on: AI/ML developments, Big Tech moves, regulation (EU AI Act, US bills), 
semiconductor supply chains, startup funding signals, product launches, and layoff/hiring trends.

High-value signal types to prioritize:
- Patent filings and R&D announcements
- Regulatory body communications (FTC, EU DG CONNECT)
- Earnings call language from major tech companies
- GitHub activity and open-source releases
- VC funding rounds (Series B+ indicate market conviction)
""",

    "markets": """
You are a quantitative market intelligence analyst specializing in 1-4 week forward signals.
Focus on: equity markets, interest rate expectations, inflation data, earnings calendars, 
commodities, crypto, and macro economic indicators.

High-value signal types to prioritize:
- Central bank language (Fed minutes, ECB statements, BoJ decisions)
- Options market positioning (put/call ratios)
- Earnings guidance revisions
- PMI and consumer confidence prints
- Institutional fund flow data
- Credit spread movements
""",

    "geopolitics": """
You are a geopolitical risk analyst specializing in near-term event forecasting.
Focus on: diplomatic meetings, election cycles, military posturing, sanctions, 
trade negotiations, energy supply routes, and international organization decisions.

High-value signal types to prioritize:
- Official diplomatic communiqués and press releases
- UN Security Council agenda items
- Treaty negotiations and breakdowns
- Troop/naval movements reported by credible outlets
- Economic sanctions announcements
- Election polling trajectory changes
"""
}

STRUCTURED_OUTPUT_SCHEMA = """
Return your analysis as a single valid JSON object. No markdown, no explanation outside the JSON.

{
  "news_summary": "2-3 sentence overview of what you found",
  "sources_searched": ["search query 1", "search query 2", "..."],
  "agent_notes": "Any caveats, data gaps, or confidence limitations",
  "predictions": [
    {
      "statement": "Specific, falsifiable prediction statement",
      "confidence": "High | Medium | Low",
      "time_horizon": "e.g. 1-2 weeks",
      "reasoning": "Chain of thought explaining why you believe this",
      "supporting_signals": [
        {
          "type": "signal category (e.g. policy filing, earnings guidance)",
          "description": "What the signal is and what it indicates",
          "source": "Publication or outlet name",
          "strength": "strong | moderate | weak"
        }
      ],
      "risk_factors": [
        "Factor that could invalidate this prediction",
        "Another invalidation risk"
      ]
    }
  ]
}

Generate 2-4 predictions. Be specific and falsifiable — avoid vague statements like 'markets may be volatile'.
"""


class PredictionAgent:
    def __init__(self):
        {
    "detail": "'NoneType' object has no attribute 'strip'"
}
        self.model = "claude-sonnet-4-5"
        self.tools = [{"type": "web_search_20250305", "name": "web_search"}]

    async def run(self, topic: str, domain: str, time_horizon: str) -> PredictionResponse:
        """Run the agentic prediction loop and return a structured PredictionResponse."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, topic, domain, time_horizon)
        return result

    def _run_sync(self, topic: str, domain: str, time_horizon: str) -> PredictionResponse:
        domain_context = DOMAIN_PROMPTS.get(domain, "")

        system_prompt = f"""
{domain_context}

Your task is to research the given topic and produce STRUCTURED SHORT-TERM PREDICTIONS.

RESEARCH PROCESS:
1. Run 3-5 targeted web searches covering different angles of the topic
2. Look for leading indicators — not just what happened, but what it signals
3. Cross-reference conflicting signals and weigh them
4. Identify the 2-4 most defensible predictions for the {time_horizon} time horizon
5. Assign honest confidence levels based on signal strength and consensus

{STRUCTURED_OUTPUT_SCHEMA}
"""

        messages = [
            {
                "role": "user",
                "content": f"Research topic: {topic}\nTime horizon: {time_horizon}\n\nBegin your research and return predictions as structured JSON."
            }
        ]

        # Agentic loop — agent searches until it reaches end_turn
        max_iterations = 8
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=self.tools,
                messages=messages
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract the JSON prediction from the final text block
                for block in response.content:
                    if hasattr(block, "text"):
                        return self._parse_response(block.text, topic, domain)

            elif response.stop_reason == "tool_use":
                # Feed tool results back for the next iteration
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Search completed. Analyze results and continue."
                        })

                messages.append({"role": "user", "content": tool_results})

        raise RuntimeError("Agent did not complete within the maximum number of iterations.")

    def _parse_response(self, text: str, topic: str, domain: str) -> PredictionResponse:
        """Parse the agent's JSON output into a PredictionResponse."""
        # Strip any accidental markdown fences
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("```").strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            # Fallback: extract JSON object from the text
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(clean[start:end])
            else:
                raise ValueError(f"Could not parse JSON from agent response: {clean[:200]}")

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
