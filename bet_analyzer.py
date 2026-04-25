"""
Onyx Bet Analyzer
─────────────────
Multi-step research agent for Kalshi prediction markets.

How it works:
  1. Caller passes structured bet data (question, odds, description, variations,
     past outcomes, user notes).
  2. We build a calibration-focused prompt that frames the task as finding edge
     vs. the market, NOT just "predict the outcome".
  3. We give Claude web_search tool access and let it run multiple search turns
     until it has what it needs (Claude decides when to stop).
  4. We parse a structured JSON verdict back, including market-implied probability,
     Onyx's own probability, the edge gap, and a BET_YES / BET_NO / PASS recommendation
     based on whether the edge clears a minimum threshold.
"""

import json
import anthropic
from typing import Optional, List, Dict, Any

# Edge threshold: if Onyx's probability is within this many points of the market,
# we recommend PASS — there's no real edge.
MIN_EDGE_PCT = 4

# Max search turns Claude can take. Each turn = one round of web_search calls
# plus reasoning. Claude usually finishes in 2-4 turns.
MAX_AGENT_TURNS = 8

MODEL = "claude-sonnet-4-5-20250929"


def _format_variations(variations: List[Dict[str, Any]], focus_idx: Optional[int]) -> str:
    """Render the variation list as context. The focused variation (if any) is marked."""
    if not variations:
        return ""
    lines = ["Related variations of this market (from the user's research):"]
    for i, v in enumerate(variations):
        marker = " ← ANALYZING THIS ONE" if i == focus_idx else ""
        yes = f"{v['yes']}¢" if v.get("yes") is not None else "no price"
        no = f"{v['no']}¢" if v.get("no") is not None else "no price"
        lines.append(f"  • \"{v.get('q', '')}\" — YES {yes} / NO {no}{marker}")
    return "\n".join(lines)


def _format_past_outcomes(past_outcomes: List[Dict[str, Any]]) -> str:
    """Render Onyx's track record on similar bets so the model can self-correct."""
    if not past_outcomes:
        return ""
    lines = ["Onyx's recent track record on similar markets:"]
    for o in past_outcomes[:5]:  # cap to avoid prompt bloat
        outcome = o.get("outcome", "pending")
        lines.append(
            f"  • \"{o.get('q', '')}\" — predicted {o.get('verdict', '?')} "
            f"({o.get('confidence', '?')} conf), actual: {outcome}"
        )
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return f"""You are Onyx, an expert prediction-market analyst. Your job is to find EDGE vs. the market — not just guess outcomes.

CORE FRAMING:
The market price IS a probability. If YES costs 67¢, the market thinks there's a 67% chance YES resolves true.
Your job is to determine whether the market is OVERPRICING or UNDERPRICING that probability.

  • If you think the true probability is HIGHER than the YES price → buy YES (edge)
  • If you think the true probability is LOWER than the YES price → buy NO (edge)
  • If your probability is within {MIN_EDGE_PCT} points of the market → PASS (no real edge)

RESEARCH PROCESS:
You have web_search available. Use it MULTIPLE times if needed. Search for:
  1. The most recent news / data relevant to this market resolving
  2. Base rates — how often things like this have happened historically
  3. Specific entities, dates, or numbers mentioned in the resolution criteria
Don't settle for one search. Drill down. Cross-check.

CALIBRATION:
Most retail bettors are overconfident. If you don't have strong evidence, say "Medium" or "Low" confidence and recommend PASS. PASS is a valid, often correct answer. Don't manufacture conviction.

Consider variation relationships: if multiple variations of the same parent market exist, their prices should be internally consistent. Inconsistencies = signal.

Consider the user's notes: they may have insider knowledge or have already done research. Read them seriously.

OUTPUT FORMAT:
After all your research, return ONLY valid JSON in this exact schema:
{{
  "verdict": "YES" | "NO",
  "onyx_probability": 0-100,           // your estimated probability of YES resolving true
  "market_implied_probability": 0-100, // the YES price as a number (passed in to you)
  "edge_pct": number,                  // onyx_probability - market_implied_probability (signed)
  "recommendation": "BET_YES" | "BET_NO" | "PASS",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "2-4 sentence explanation of WHY the market is mispriced (or why it's fairly priced)",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "uncertainties": ["thing that would change my mind 1", "thing 2"],
  "sources": ["url 1", "url 2", "url 3"]
}}

Recommendation rule:
  • If onyx_probability − market_implied_probability ≥ {MIN_EDGE_PCT}  → BET_YES
  • If market_implied_probability − onyx_probability ≥ {MIN_EDGE_PCT}  → BET_NO
  • Otherwise                                                          → PASS

Return ONLY the JSON object. No prose before or after."""


def _build_user_prompt(bet: Dict[str, Any], variation_idx: Optional[int],
                       past_outcomes: List[Dict[str, Any]]) -> str:
    """Build the user-turn prompt that describes the specific bet."""

    # Pick the focus: parent bet, or one variation
    if variation_idx is not None and bet.get("variations") and variation_idx < len(bet["variations"]):
        v = bet["variations"][variation_idx]
        focus_q = v.get("q", "")
        focus_yes = v.get("yes")
        focus_no = v.get("no")
        focus_desc = v.get("desc") or bet.get("desc", "")
        focus_notes = v.get("notes", "")
        parent_context = f"\nParent market: \"{bet.get('q', '')}\""
    else:
        focus_q = bet.get("q", "")
        focus_yes = bet.get("yes")
        focus_no = bet.get("no")
        focus_desc = bet.get("desc", "")
        focus_notes = ""  # parent notes passed separately if needed
        parent_context = ""

    # Build the core lines
    parts = [
        f"MARKET TO ANALYZE: \"{focus_q}\"{parent_context}",
        f"Category: {bet.get('cat', 'unknown')}",
        f"Closes: {bet.get('close', 'unknown')}",
    ]

    # Odds
    if focus_yes is not None and focus_no is not None:
        parts.append(
            f"Current market odds: YES {focus_yes}¢ ({focus_yes}% implied), "
            f"NO {focus_no}¢ ({focus_no}% implied)"
        )
        parts.append(f"Market-implied probability of YES: {focus_yes}%")
    elif focus_yes is not None:
        parts.append(f"YES price: {focus_yes}¢ ({focus_yes}% implied)")
        parts.append(f"Market-implied probability of YES: {focus_yes}%")
    else:
        parts.append("Market odds: not provided. Estimate fair value from scratch.")

    # Resolution criteria
    if focus_desc:
        parts.append(f"\nResolution criteria:\n{focus_desc}")

    # Variations context (full set, with focus marker)
    variations = bet.get("variations") or []
    if variations:
        parts.append("\n" + _format_variations(variations, variation_idx))

    # User research notes
    user_notes = focus_notes or bet.get("notes", "")
    if user_notes:
        parts.append(f"\nThe user's research notes (treat as serious context, not noise):\n{user_notes}")

    # Past outcomes for self-correction
    if past_outcomes:
        parts.append("\n" + _format_past_outcomes(past_outcomes))

    parts.append(
        "\nResearch this market thoroughly using web_search (multiple times if needed), "
        "then return your verdict in the JSON schema specified."
    )

    return "\n".join(parts)


def _coerce_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def _post_process(result: Dict[str, Any], market_implied: Optional[int]) -> Dict[str, Any]:
    """Clean up and validate the model's JSON output."""

    # Always overwrite market_implied_probability with the truth (don't let the model hallucinate)
    if market_implied is not None:
        result["market_implied_probability"] = market_implied

    onyx_p = _coerce_int(result.get("onyx_probability"))
    market_p = _coerce_int(result.get("market_implied_probability"))

    # Clamp probabilities to 0-100
    if onyx_p is not None:
        onyx_p = max(0, min(100, onyx_p))
        result["onyx_probability"] = onyx_p

    # Recompute edge from clean numbers (don't trust model arithmetic)
    if onyx_p is not None and market_p is not None:
        edge = onyx_p - market_p
        result["edge_pct"] = edge

        # Recompute recommendation from edge — single source of truth
        if edge >= MIN_EDGE_PCT:
            result["recommendation"] = "BET_YES"
        elif edge <= -MIN_EDGE_PCT:
            result["recommendation"] = "BET_NO"
        else:
            result["recommendation"] = "PASS"

        # Verdict tracks recommendation direction (or what the model picked if PASS)
        if result["recommendation"] == "BET_YES":
            result["verdict"] = "YES"
        elif result["recommendation"] == "BET_NO":
            result["verdict"] = "NO"
        # If PASS, leave verdict as model chose (or "YES"/"NO" by majority)

    # Ensure list fields are lists
    for k in ("key_factors", "uncertainties", "sources"):
        if k not in result or not isinstance(result[k], list):
            result[k] = []

    # Ensure required fields exist
    result.setdefault("verdict", "YES")
    result.setdefault("confidence", "Medium")
    result.setdefault("reasoning", "Analysis incomplete.")
    result.setdefault("recommendation", "PASS")

    return result


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Find and parse the JSON object in the model's response."""
    if not text:
        return None
    s = text.find("{")
    e = text.rfind("}") + 1
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(text[s:e])
    except json.JSONDecodeError:
        return None


def analyse_bet(bet: Dict[str, Any], variation_idx: Optional[int] = None,
                past_outcomes: Optional[List[Dict[str, Any]]] = None,
                api_key: str = "") -> Dict[str, Any]:
    """
    Run the multi-step research agent on a single bet (or one of its variations).

    Returns the structured verdict dict, or {"error": "..."} on failure.
    """
    if not api_key:
        return {"error": "No API key configured"}

    if not bet or not bet.get("q"):
        return {"error": "Bet question is required"}

    # Compute market-implied probability for the focused thing
    if variation_idx is not None and bet.get("variations") and variation_idx < len(bet["variations"]):
        market_implied = bet["variations"][variation_idx].get("yes")
    else:
        market_implied = bet.get("yes")
    market_implied = _coerce_int(market_implied)

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(bet, variation_idx, past_outcomes or [])

    client = anthropic.Anthropic(api_key=api_key)

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as ex:
        return {"error": f"Anthropic API error: {str(ex)}"}

    # Combine all text blocks from the response. With server-side web_search,
    # Claude makes multiple search calls internally and returns one combined message
    # with text + tool_use blocks. We just want the final text.
    text = "".join(
        b.text for b in resp.content
        if hasattr(b, "text") and b.text
    )

    parsed = _extract_json(text)
    if parsed is None:
        return {
            "error": "Could not parse JSON verdict from model response",
            "raw": text[:500],
        }

    return _post_process(parsed, market_implied)
