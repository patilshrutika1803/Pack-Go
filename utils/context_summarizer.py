"""
Context summarizer utility.
Reduces inter-agent data to the minimum tokens ItineraryAgent actually needs.
"""
from typing import Dict, Any, Optional


def summarize_for_itinerary(
    research: Optional[Dict[str, Any]],
    weather,  # WeatherInfo pydantic model or None
    budget,   # BudgetBreakdown pydantic model or None
) -> str:
    """
    Returns a compact, token-efficient summary string for the ItineraryAgent prompt.
    
    Instead of dumping full JSON objects, we extract only:
    - Top 5 place names + entry fees
    - Top 3 restaurant names + cuisine
    - Weather: one-line summary + conditions
    - Budget: total and currency only
    """
    lines = []

    # ── Places (top 5) ────────────────────────────────────────────────────────
    if research:
        places = research.get("places", [])[:5]
        if places:
            lines.append("TOP PLACES:")
            for p in places:
                name = p.get("name", "Unknown")
                fee = p.get("entry_fee", "Free")
                duration = p.get("recommended_duration_hours", "")
                duration_str = f", {duration}h" if duration else ""
                lines.append(f"  - {name} (entry: {fee}{duration_str})")

        restaurants = research.get("restaurants", [])[:3]
        if restaurants:
            lines.append("TOP RESTAURANTS:")
            for r in restaurants:
                name = r.get("name", "Unknown")
                cuisine = r.get("cuisine", "")
                cost = r.get("average_cost", "")
                lines.append(f"  - {name} ({cuisine}, avg: {cost})")

    # ── Weather (one line) ────────────────────────────────────────────────────
    if weather:
        summary = getattr(weather, "summary", "")
        conditions = getattr(weather, "conditions", "")
        temp = getattr(weather, "temperature_range", "")
        warnings = getattr(weather, "travel_warnings", [])
        weather_line = f"WEATHER: {temp}, {conditions}."
        if summary:
            weather_line += f" {summary}"
        lines.append(weather_line)
        if warnings:
            lines.append(f"WEATHER WARNINGS: {'; '.join(warnings[:2])}")

    # ── Budget (totals only) ──────────────────────────────────────────────────
    if budget:
        total = getattr(budget, "total_estimated", 0)
        currency = getattr(budget, "currency", "")
        within = getattr(budget, "is_within_budget", True)
        lines.append(f"BUDGET LIMIT: {total} {currency} ({'within budget' if within else 'OVER BUDGET'}).")
        if not within:
            suggestions = getattr(budget, "adjustment_suggestions", [])[:2]
            if suggestions:
                lines.append(f"COST CUTS: {'; '.join(suggestions)}")

    return "\n".join(lines) if lines else "No context available."
