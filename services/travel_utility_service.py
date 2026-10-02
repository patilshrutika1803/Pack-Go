from __future__ import annotations

from typing import Any


def build_packing_list(trip: Any) -> dict[str, Any]:
    """Build a deterministic preparation list from saved trip data."""
    categories = {
        "clothing": [],
        "essentials": ["Phone charger and power bank", "Basic toiletries and personal medication"],
        "documents": ["Government ID and travel documents"],
        "weather": [],
        "destination": [],
    }
    weather = trip.weather if isinstance(trip.weather, dict) else {}
    conditions = str(weather.get("conditions", "")).lower()
    suggestions = weather.get("packing_suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []
    for suggestion in suggestions:
        if not suggestion:
            continue
        item = str(suggestion)
        category = "clothing" if any(term in item.lower() for term in ("clothing", "jacket", "sweater", "layers", "shoes", "footwear")) else "weather"
        categories[category].append(item)
    if any(term in conditions for term in ("rain", "storm", "shower")):
        categories["weather"].append("Umbrella or raincoat")
    if any(term in conditions for term in ("snow", "cold", "freezing")):
        categories["clothing"].append("Warm layers")
    interests = {str(value).lower() for value in (trip.interests or []) if value}
    if interests.intersection({"beach", "swimming", "water"}):
        categories["destination"].append("Swimwear and sun protection")
    if interests.intersection({"adventure", "hiking", "nature"}):
        categories["clothing"].append("Comfortable walking shoes")
    categories = {name: list(dict.fromkeys(items)) for name, items in categories.items()}
    items = list(dict.fromkeys(item for category_items in categories.values() for item in category_items))
    preparation = [
        f"Confirm accommodation and transport for {trip.destination}",
        "Check travel dates, identification, and required entry documents",
        "Review the weather forecast shortly before departure",
    ]
    return {
        "trip_id": trip.id,
        "destination": trip.destination,
        "travel_dates": trip.travel_dates,
        "categories": categories,
        "items": list(dict.fromkeys(items)),
        "preparation": preparation,
        "weather_used": bool(weather),
    }


def extract_map_locations(trip: Any) -> list[dict[str, str]]:
    locations: list[dict[str, str]] = [{"name": trip.destination, "type": "destination"}]
    for day in trip.itinerary or []:
        if not isinstance(day, dict):
            continue
        for attraction in day.get("attractions", []):
            place = attraction.get("place", {}) if isinstance(attraction, dict) else {}
            name = place.get("name") if isinstance(place, dict) else None
            if name:
                locations.append({"name": str(name), "type": "attraction"})
        hotel = day.get("hotel", {})
        if isinstance(hotel, dict) and hotel.get("name"):
            locations.append({"name": str(hotel["name"]), "type": "hotel"})
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for location in locations:
        unique[(location["name"].lower(), location["type"])] = location
    return list(unique.values())