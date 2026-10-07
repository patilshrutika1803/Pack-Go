from __future__ import annotations

import math
import re
from typing import Literal
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database

from api.v1.dependencies import CurrentUser, get_current_user
from database.mongodb import get_database
from models.api_schemas import ItineraryCSPRequest, ItineraryGARequest, RouteOptimizationRequest
from services.collaboration_service import AccessDenied, TripAccessService
from services.route_optimization import (
    InvalidRouteLocations,
    astar_search,
    build_location_graph,
    extract_itinerary_locations,
    geographic_heuristic,
)
from services.travel_utility_service import build_packing_list, extract_map_locations
from services.itinerary_csp import build_itinerary_csp_result
from services.itinerary_ga import build_itinerary_ga_result
from tools.currency_conversion_tool import CurrencyConverterTool
from tools.place_search_tool import PlaceSearchTool
from tools.weather_info_tool import WeatherInfoTool

router = APIRouter(prefix="/api/v1", tags=["Travel utilities"])


@router.get("/utilities/weather")
def get_weather(location: str = Query(min_length=1, max_length=255)):
    location = location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Location is required.")
    try:
        return WeatherInfoTool().get_current_weather_info(location).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Weather provider is temporarily unavailable.") from exc


@router.get("/utilities/currency")
def convert_currency(
    amount: float = Query(gt=0),
    from_currency: str = Query(min_length=3, max_length=3),
    to_currency: str = Query(min_length=3, max_length=3),
):
    if not math.isfinite(amount) or amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be a finite value greater than zero.")
    source = from_currency.upper()
    target = to_currency.upper()
    if not re.fullmatch(r"[A-Z]{3}", source) or not re.fullmatch(r"[A-Z]{3}", target):
        raise HTTPException(status_code=422, detail="Currency codes must be three letters.")
    try:
        converted = CurrencyConverterTool().currency_service.convert(amount, source, target)
        converted = float(converted)
        if not math.isfinite(converted) or converted <= 0:
            raise ValueError("Provider returned an invalid conversion amount.")
        return {
            "amount": amount,
            "from_currency": source,
            "to_currency": target,
            "rate": converted / amount,
            "converted_amount": converted,
            "source": "ExchangeRate-API",
            "status": "success",
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Currency provider is temporarily unavailable.") from exc


@router.get("/utilities/places")
def search_places(
    location: str = Query(min_length=1, max_length=255),
    category: Literal["attractions", "restaurants", "activities", "transportation"] = "attractions",
):
    location = location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Location is required.")
    method_name = {
        "attractions": "tavily_search_attractions",
        "restaurants": "tavily_search_restaurants",
        "activities": "tavily_search_activity",
        "transportation": "tavily_search_transportation",
    }[category]
    try:
        search = PlaceSearchTool().tavily_search
        result = getattr(search, method_name)(location.strip())
        return {"location": location, "category": category, "results": result, "status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Place provider is temporarily unavailable.") from exc


@router.get("/trips/{trip_id}/utilities/packing")
def get_packing_list(trip_id: str, db: Database = Depends(get_database), user: CurrentUser = Depends(get_current_user)):
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None
    return build_packing_list(trip)


@router.get("/trips/{trip_id}/utilities/map")
def get_trip_map(trip_id: str, db: Database = Depends(get_database), user: CurrentUser = Depends(get_current_user)):
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None
    locations = extract_map_locations(trip)
    return {
        "trip_id": trip["id"],
        "locations": [
            {**location, "search_url": f"https://www.openstreetmap.org/search?query={quote_plus(location['name'] + ', ' + trip['destination'])}"}
            for location in locations
        ],
    }


def _route_locations(trip) -> list:
    try:
        return extract_itinerary_locations(trip.get("itinerary"))
    except InvalidRouteLocations as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _route_location_payload(location) -> dict:
    return {
        "id": location.id,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "day_number": location.day_number,
    }


@router.get("/trips/{trip_id}/route/locations")
def get_route_locations(trip_id: str, db: Database = Depends(get_database), user: CurrentUser = Depends(get_current_user)):
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None

    locations = _route_locations(trip)
    available = len(locations) >= 2
    return {
        "available": available,
        "status": "ready" if available else "insufficient_locations",
        "message": None if available else "At least two itinerary attractions with valid coordinates are required.",
        "locations": [_route_location_payload(location) for location in locations],
    }


@router.post("/trips/{trip_id}/route/optimize")
def optimize_trip_route(
    trip_id: str,
    payload: RouteOptimizationRequest,
    db: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None

    locations = _route_locations(trip)
    public_locations = [_route_location_payload(location) for location in locations]
    base_response = {"algorithm": "A*", "locations": public_locations}
    if len(locations) < 2:
        return {
            **base_response,
            "available": False,
            "status": "insufficient_locations",
            "message": "At least two itinerary attractions with valid coordinates are required.",
            "route": None,
        }
    if payload.start_location_id is None:
        return {
            **base_response,
            "available": True,
            "status": "needs_selection",
            "message": "Choose a start location and destination to find the shortest path.",
            "route": None,
        }

    location_ids = {location.id for location in locations}
    if payload.start_location_id not in location_ids or payload.goal_location_id not in location_ids:
        raise HTTPException(status_code=422, detail="Start and destination must be itinerary locations with coordinates.")

    graph = build_location_graph(locations)
    result = astar_search(
        graph,
        payload.start_location_id,
        payload.goal_location_id,
        geographic_heuristic(locations, payload.goal_location_id),
    )
    if result is None:
        return {
            **base_response,
            "available": True,
            "status": "unreachable",
            "message": "No connected path exists between those itinerary locations.",
            "route": None,
        }

    by_id = {location.id: location for location in locations}
    return {
        **base_response,
        "available": True,
        "status": "optimized",
        "message": None,
        "route": {
            "ordered_locations": [_route_location_payload(by_id[location_id]) for location_id in result.path],
            "total_distance_km": result.cost,
            "search_stats": {
                "expanded_count": len(result.expanded_nodes),
                "expanded_nodes": result.expanded_nodes,
            },
        },
    }


@router.post("/trips/{trip_id}/itinerary/csp-optimize")
def optimize_trip_itinerary_csp(
    trip_id: str,
    payload: ItineraryCSPRequest,
    db: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _ = payload
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None
    return build_itinerary_csp_result(trip["duration"], trip["itinerary"])


@router.post("/trips/{trip_id}/itinerary/ga-optimize")
def optimize_trip_itinerary_ga(
    trip_id: str,
    payload: ItineraryGARequest,
    db: Database = Depends(get_database),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        trip = TripAccessService(db).get_trip_for_member(trip_id, user.id)
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Trip not found.") from None
    return build_itinerary_ga_result(
        trip["duration"],
        trip["itinerary"],
        population_size=payload.population_size,
        generations=payload.generations,
        mutation_rate=payload.mutation_rate,
        seed=payload.random_seed,
    )