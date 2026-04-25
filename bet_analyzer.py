"""
Onyx Bet Analyzer (v2)
──────────────────────
Multi-step research agent for Kalshi prediction markets.

Pipeline:
  1. Caller passes structured bet data + the user's past outcomes (correct/wrong marks).
  2. We filter past outcomes to ones in the same category (relevant context only).
  3. We build a calibration-focused system prompt that frames the task as finding
     edge vs. the market — not just "predict the outcome".
  4. We give Claude server-side web_search and let it run multiple search turns.
  5. Parse the JSON verdict back. If parsing fails, retry once with a stricter reminder.
  6. Post-process: clamp probabilities, recompute edge from clean numbers,
     force PASS on Low confidence (no edge claim without strong evidence),
     warn if no sources cited.
"""

import json
import re
import time
import anthropic
from typing import Optional, List, Dict, Any, Tuple

# ── Tunable knobs ─────────────────────────────────────────────────────────────
# Edge threshold: if Onyx's probability is within this many points of the market,
# we recommend PASS — there's no real edge.
MIN_EDGE_PCT = 4

# Force PASS when confidence is "Low" — Onyx shouldn't claim edge without evidence.
FORCE_PASS_ON_LOW_CONFIDENCE = True

# Cap how many past outcomes we send. Too many = prompt bloat, no help.
MAX_PAST_OUTCOMES_IN_PROMPT = 5

# How many retries on bad JSON before giving up.
MAX_PARSE_RETRIES = 1

# How long to wait for the API before giving up (seconds). Web search runs add latency.
ANTHROPIC_TIMEOUT_S = 180.0

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 2000


# ── Past-outcome filtering ────────────────────────────────────────────────────

def _filter_relevant_outcomes(
    past_outcomes: List[Dict[str, Any]],
    target_category: str,
) -> List[Dict[str, Any]]:
    """Keep finished outcomes (correct/wrong only) from the same category as the
    target bet. If we don't have enough same-category, mix in others."""
    target_cat = (target_category or "").strip().lower()
    finished = [
        o for o in past_outcomes
        if (o.get("outcome") or "").lower() in ("correct", "wrong")
    ]
    if not finished:
        return []

    if target_cat:
        same_cat = [o for o in finished if (o.get("cat") or "").strip().lower() == target_cat]
        if len(same_cat) >= 2:
            return same_cat[:MAX_PAST_OUTCOMES_IN_PROMPT]
        # Mix: prefer same-cat, fill with others
        others = [o for o in finished if o not in same_cat]
        return (same_cat + others)[:MAX_PAST_OUTCOMES_IN_PROMPT]

    return finished[:MAX_PAST_OUTCOMES_IN_PROMPT]


def _format_variations(variations: List[Dict[str, Any]], focus_idx: Optional[int]) -> str:
    """Render the variation list as context. The focused variation (if any) is marked."""
    if not variations:
        return ""
    lines = ["RELATED VARIATIONS of this market (use these to cross-check internal consistency):"]
    for i, v in enumerate(variations):
        marker = "  ← THIS IS THE ONE TO ANALYZE" if i == focus_idx else ""
        yes = f"{v['yes']}\u00a2" if v.get("yes") is not None else "no price"
        no = f"{v['no']}\u00a2" if v.get("no") is not None else "no price"
        lines.append(f"  - \"{v.get('q', '')}\" — YES {yes} / NO {no}{marker}")
    return "\n".join(lines)


def _format_past_outcomes(past_outcomes: List[Dict[str, Any]]) -> str:
    """Render Onyx's past predictions + actual outcomes for self-correction."""
    if not past_outcomes:
        return ""
    lines = [
        "ONYX'S PAST TRACK RECORD on similar markets (LEARN from past mistakes):"
    ]
    for o in past_outcomes:
        outcome = (o.get("outcome") or "?").upper()
        verdict = o.get("verdict") or o.get("recommendation") or "?"
        symbol = "✓" if outcome == "CORRECT" else "✗"
        lines.append(
            f"  {symbol} \"{o.get('q', '')}\" — Onyx said {verdict} "
            f"({o.get('confidence', '?')} conf), actual: {outcome}"
        )
    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    return f"""You are Onyx, an expert prediction-market analyst. Your job is to find EDGE vs. the market — not just guess outcomes.

CORE FRAMING — THE MARKET PRICE IS A PROBABILITY:
If YES costs 67¢, the market is saying "67% chance YES resolves true". Your job is NOT to guess YES or NO. Your job is to determine whether that 67% is too HIGH or too LOW.

  • You think true probability is HIGHER than the YES price → BET_YES (edge)
  • You think true probability is LOWER than the YES price → BET_NO (edge)
  • Your probability is within {MIN_EDGE_PCT} points of the market → PASS (no real edge)

PASS IS A VALID, OFTEN CORRECT ANSWER. Most markets are roughly fair. If your research doesn't reveal a clear mispricing, recommend PASS. Don't manufacture conviction.

RESEARCH PROCESS:
You have web_search. USE IT MULTIPLE TIMES. Do NOT settle for one search. Drill down:
  1. Find the most recent news / data relevant to resolution
  2. Look up base rates — how often does this kind of thing happen historically
  3. Look up specific entities, dates, or numbers in the resolution criteria
  4. Cross-check sources. If two reliable sources disagree, note it as uncertainty.

CALIBRATION RULES (these are firm):
  • If your research is THIN (1-2 weak sources, no concrete data) → confidence = "Low" → recommend PASS
  • If you can find ONE clear data point or recent event that points one way → "Medium"
  • If you have multiple independent sources confirming + a clear thesis → "High"
  Most retail bettors are overconfident. Be more skeptical than feels comfortable.

CONSIDER VARIATION RELATIONSHIPS:
If the user provided multiple variations of the same parent market (e.g. temperature thresholds), their YES prices should form a consistent curve. A spike or drop between adjacent thresholds is a SIGNAL, not noise.

USER'S RESEARCH NOTES:
The user has put real thought into these markets. If they've left notes, READ THEM CAREFULLY and weigh them. They may have insider knowledge or have already done research you can't reproduce.

LEARN FROM PAST MISTAKES:
If past outcomes show Onyx was WRONG on similar bets, ask why and adjust. Pattern of errors → systematic miscalibration → correct it.

OUTPUT — RETURN ONLY VALID JSON, NO PROSE BEFORE OR AFTER:
{{
  "verdict": "YES" | "NO",
  "onyx_probability": integer 0-100,
  "market_implied_probability": integer 0-100,
  "edge_pct": signed integer (onyx_probability - market_implied_probability),
  "recommendation": "BET_YES" | "BET_NO" | "PASS",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "2-4 sentence explanation focused on WHY the market is mispriced (or fairly priced)",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "uncertainties": ["thing that would change my mind 1", "thing 2"],
  "sources": ["full url 1", "full url 2", "full url 3"]
}}

Recommendation rule (the server will recompute and override if you get this wrong):
  • edge ≥ {MIN_EDGE_PCT}    → BET_YES
  • edge ≤ -{MIN_EDGE_PCT}   → BET_NO
  • else                      → PASS
  • Low confidence            → PASS (regardless of edge)"""


def _build_user_prompt(bet: Dict[str, Any], variation_idx: Optional[int],
                       past_outcomes: List[Dict[str, Any]]) -> str:
    # Pick the focus: parent bet, or one variation
    if variation_idx is not None and bet.get("variations") and 0 <= variation_idx < len(bet["variations"]):
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
        focus_notes = ""
        parent_context = ""

    parts = [
        f"MARKET TO ANALYZE: \"{focus_q}\"{parent_context}",
        f"Category: {bet.get('cat', 'unknown')}",
        f"Closes: {bet.get('close', 'unknown')}",
    ]

    if focus_yes is not None and focus_no is not None:
        parts.append(f"Current market odds: YES {focus_yes}\u00a2, NO {focus_no}\u00a2")
        parts.append(f"-> Market-implied probability of YES = {focus_yes}%")
    elif focus_yes is not None:
        parts.append(f"YES price: {focus_yes}\u00a2 -> market-implied probability of YES = {focus_yes}%")
    else:
        parts.append("No market price provided. Estimate fair value from scratch.")

    if focus_desc:
        parts.append(f"\nRESOLUTION CRITERIA:\n{focus_desc}")

    variations = bet.get("variations") or []
    if variations:
        parts.append("\n" + _format_variations(variations, variation_idx))

    user_notes = focus_notes or bet.get("notes", "")
    if user_notes:
        parts.append(f"\nUSER'S RESEARCH NOTES (real signal — read carefully):\n{user_notes}")

    if past_outcomes:
        parts.append("\n" + _format_past_outcomes(past_outcomes))

    parts.append(
        "\nNow: research thoroughly using web_search (multiple searches if needed), "
        "then return your JSON verdict. Remember: PASS is a valid answer if you don't find clear edge."
    )

    return "\n".join(parts)


# ── Output validation / cleanup ───────────────────────────────────────────────

def _coerce_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Find and parse the largest JSON object in the model's response."""
    if not text:
        return None
    s = text.find("{")
    e = text.rfind("}") + 1
    if s < 0 or e <= s:
        return None
    raw = text[s:e]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Common LLM mistake: trailing commas. Strip and retry.
        try:
            cleaned = re.sub(r',\s*([}\]])', r'\1', raw)
            return json.loads(cleaned)
        except Exception:
            return None


def _post_process(result: Dict[str, Any], market_implied: Optional[int]) -> Dict[str, Any]:
    """Clean up, validate, and normalize the model's JSON output.

    The server is the source of truth for derived fields:
      • market_implied_probability (we know the price, model can't fudge it)
      • edge_pct (recomputed from clean ints)
      • recommendation (recomputed from edge + confidence rule)
    """
    # Lock down market-implied prob
    if market_implied is not None:
        result["market_implied_probability"] = market_implied

    onyx_p = _coerce_int(result.get("onyx_probability"))
    market_p = _coerce_int(result.get("market_implied_probability"))

    # Clamp 0-100
    if onyx_p is not None:
        onyx_p = max(0, min(100, onyx_p))
        result["onyx_probability"] = onyx_p
    if market_p is not None:
        market_p = max(0, min(100, market_p))
        result["market_implied_probability"] = market_p

    # Confidence sanity
    conf = (result.get("confidence") or "").strip()
    if conf not in ("High", "Medium", "Low"):
        cl = conf.lower()
        if "high" in cl:
            conf = "High"
        elif "low" in cl:
            conf = "Low"
        else:
            conf = "Medium"
    result["confidence"] = conf

    # Recompute edge + recommendation from clean numbers (single source of truth)
    if onyx_p is not None and market_p is not None:
        edge = onyx_p - market_p
        result["edge_pct"] = edge

        if FORCE_PASS_ON_LOW_CONFIDENCE and conf == "Low":
            result["recommendation"] = "PASS"
        elif edge >= MIN_EDGE_PCT:
            result["recommendation"] = "BET_YES"
        elif edge <= -MIN_EDGE_PCT:
            result["recommendation"] = "BET_NO"
        else:
            result["recommendation"] = "PASS"

        # Verdict tracks recommendation for clarity (PASS preserves model's lean)
        if result["recommendation"] == "BET_YES":
            result["verdict"] = "YES"
        elif result["recommendation"] == "BET_NO":
            result["verdict"] = "NO"
    else:
        # No probability info — fall back to model's stated recommendation, or PASS
        rec = result.get("recommendation") or "PASS"
        if rec not in ("BET_YES", "BET_NO", "PASS"):
            rec = "PASS"
        result["recommendation"] = rec

    # Lists must be clean lists of trimmed strings
    for k in ("key_factors", "uncertainties", "sources"):
        v = result.get(k)
        if not isinstance(v, list):
            result[k] = []
        else:
            result[k] = [str(x).strip() for x in v if str(x) and str(x).strip()]

    # Trim sources to plausible URLs
    result["sources"] = [
        u for u in result["sources"]
        if u.startswith("http://") or u.startswith("https://")
    ][:8]

    # Add a flag if sources are missing — UI can warn the user
    result["sources_warning"] = (
        "Onyx didn't cite any web sources. Treat this analysis as low-confidence."
        if not result["sources"] else None
    )

    # Defaults
    result.setdefault("verdict", "YES")
    result.setdefault("reasoning", "Analysis incomplete.")

    return result


# ── Anthropic call wrapper ────────────────────────────────────────────────────

def _call_model(client: "anthropic.Anthropic", system_prompt: str,
                user_prompt: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (text, error). Exactly one is non-None on success/failure."""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APITimeoutError as ex:
        return None, f"Anthropic API timed out: {ex}"
    except anthropic.APIError as ex:
        return None, f"Anthropic API error: {ex}"
    except Exception as ex:
        return None, f"Unexpected error: {ex}"

    text = "".join(
        b.text for b in resp.content
        if hasattr(b, "text") and b.text
    )
    return text, None


# ── Public entry point ────────────────────────────────────────────────────────

def analyse_bet(bet: Dict[str, Any], variation_idx: Optional[int] = None,
                past_outcomes: Optional[List[Dict[str, Any]]] = None,
                api_key: str = "") -> Dict[str, Any]:
    """
    Run the multi-step research agent on a single bet (or one of its variations).

    Returns a result dict with verdict / probability / edge / recommendation /
    reasoning / key_factors / uncertainties / sources, plus a meta block with
    timing info. On failure returns {"error": "..."}.
    """
    started = time.time()

    if not api_key:
        return {"error": "No API key configured on server"}

    if not bet or not bet.get("q"):
        return {"error": "Bet question is required"}

    # Compute market-implied probability for the focused thing (so we can recompute
    # edge from a known-good number, not whatever the model echoes back).
    if variation_idx is not None and bet.get("variations") and 0 <= variation_idx < len(bet["variations"]):
        market_implied = bet["variations"][variation_idx].get("yes")
    else:
        market_implied = bet.get("yes")
    market_implied = _coerce_int(market_implied)

    # Filter past outcomes to the relevant category before sending
    relevant_past = _filter_relevant_outcomes(past_outcomes or [], bet.get("cat", ""))

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(bet, variation_idx, relevant_past)

    client = anthropic.Anthropic(api_key=api_key, timeout=ANTHROPIC_TIMEOUT_S)

    # First call
    text, err = _call_model(client, system_prompt, user_prompt)
    if err:
        return {"error": err, "meta": {"duration_s": round(time.time() - started, 1)}}

    parsed = _extract_json(text)

    # Retry once with a stricter reminder if JSON didn't parse
    retries = 0
    while parsed is None and retries < MAX_PARSE_RETRIES:
        retries += 1
        retry_prompt = (
            user_prompt
            + "\n\nIMPORTANT: Your previous response did not return valid JSON. "
              "This time, return ONLY the JSON object — no prose before, no prose after, "
              "no markdown code fences. Just the raw JSON. Do your research and return the JSON."
        )
        text, err = _call_model(client, system_prompt, retry_prompt)
        if err:
            return {"error": err, "meta": {"duration_s": round(time.time() - started, 1)}}
        parsed = _extract_json(text)

    if parsed is None:
        return {
            "error": "Could not parse JSON verdict from model response",
            "raw": (text or "")[:500],
            "meta": {"duration_s": round(time.time() - started, 1), "retries": retries},
        }

    # Server-side normalization & validation
    result = _post_process(parsed, market_implied)

    # Telemetry block (helps debug bad analyses later)
    result["meta"] = {
        "duration_s": round(time.time() - started, 1),
        "retries": retries,
        "past_outcomes_used": len(relevant_past),
        "variation_idx": variation_idx,
    }

    return result
