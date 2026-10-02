from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Callable, Mapping


EARTH_RADIUS_KM = 6371.0088


class InvalidRouteLocations(ValueError):
    """Raised when saved itinerary locations cannot form a geographic graph."""


@dataclass(frozen=True)
class RouteLocation:
    id: str
    name: str
    latitude: float
    longitude: float
    day_number: int


@dataclass(frozen=True)
class AStarResult:
    path: list[str]
    cost: float
    expanded_nodes: list[dict[str, float | str]]


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Return the great-circle distance between two coordinates in kilometers."""
    latitude_a, longitude_a, latitude_b, longitude_b = map(
        math.radians, (latitude_a, longitude_a, latitude_b, longitude_b)
    )
    latitude_delta = latitude_b - latitude_a
    longitude_delta = longitude_b - longitude_a
    value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_a) * math.cos(latitude_b) * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, value)))


def astar_search(
    graph: Mapping[str, Mapping[str, float]],
    start: str,
    goal: str,
    heuristic: Callable[[str], float],
) -> AStarResult | None:
    """Find a least-cost path with f(n) = g(n) + h(n); return None if unreachable."""
    if start not in graph or goal not in graph:
        raise ValueError("Start and goal must be nodes in the graph.")

    start_h = float(heuristic(start))
    if not math.isfinite(start_h) or start_h < 0:
        raise ValueError("Heuristic values must be finite and non-negative.")

    open_nodes: list[tuple[float, float, str]] = [(start_h, start_h, start)]
    came_from: dict[str, str] = {}
    g_score = {start: 0.0}
    expanded_nodes: list[dict[str, float | str]] = []

    while open_nodes:
        current_f, current_h, current = heapq.heappop(open_nodes)
        current_g = g_score.get(current)
        if current_g is None or not math.isclose(current_f, current_g + current_h):
            continue

        expanded_nodes.append({"location_id": current, "g": current_g, "h": current_h, "f": current_f})
        if current == goal:
            path = [goal]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            path.reverse()
            return AStarResult(path=path, cost=current_g, expanded_nodes=expanded_nodes)

        for neighbor, raw_cost in sorted(graph[current].items()):
            edge_cost = float(raw_cost)
            if neighbor not in graph or not math.isfinite(edge_cost) or edge_cost < 0:
                raise ValueError("Graph edges must lead to known nodes and have finite non-negative costs.")
            tentative_g = current_g + edge_cost
            if tentative_g >= g_score.get(neighbor, math.inf):
                continue
            neighbor_h = float(heuristic(neighbor))
            if not math.isfinite(neighbor_h) or neighbor_h < 0:
                raise ValueError("Heuristic values must be finite and non-negative.")
            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            heapq.heappush(open_nodes, (tentative_g + neighbor_h, neighbor_h, neighbor))

    return None


def extract_itinerary_locations(itinerary: object) -> list[RouteLocation]:
    """Read only saved attraction coordinates; locations without coordinates are omitted."""
    if not isinstance(itinerary, list):
        raise InvalidRouteLocations("The saved itinerary must be a list.")

    locations: list[RouteLocation] = []
    for day_index, day in enumerate(itinerary, start=1):
        if not isinstance(day, dict):
            raise InvalidRouteLocations("Each itinerary day must be an object.")
        attractions = day.get("attractions", [])
        if not isinstance(attractions, list):
            raise InvalidRouteLocations("Attractions for each itinerary day must be a list.")
        raw_day_number = day.get("day_number", day_index)
        if isinstance(raw_day_number, bool) or not isinstance(raw_day_number, int) or raw_day_number < 1:
            raise InvalidRouteLocations("Itinerary day numbers must be positive integers.")

        for attraction_index, attraction in enumerate(attractions, start=1):
            if not isinstance(attraction, dict):
                raise InvalidRouteLocations("Each itinerary attraction must be an object.")
            place = attraction.get("place")
            if not isinstance(place, dict):
                raise InvalidRouteLocations("Each itinerary attraction must include a place object.")
            name = place.get("name")
            if not isinstance(name, str) or not name.strip():
                raise InvalidRouteLocations("Each itinerary place must have a non-empty name.")

            latitude = place.get("latitude", place.get("lat"))
            longitude = place.get("longitude", place.get("lon", place.get("lng")))
            if latitude is None and longitude is None:
                continue
            if latitude is None or longitude is None:
                raise InvalidRouteLocations(f"Coordinates for {name.strip()} must include latitude and longitude.")
            if isinstance(latitude, bool) or isinstance(longitude, bool):
                raise InvalidRouteLocations(f"Coordinates for {name.strip()} must be numeric.")
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                raise InvalidRouteLocations(f"Coordinates for {name.strip()} must be numeric.") from None
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise InvalidRouteLocations(f"Coordinates for {name.strip()} are outside valid geographic ranges.")
            locations.append(
                RouteLocation(
                    id=f"day-{raw_day_number}-attraction-{attraction_index}",
                    name=name.strip(),
                    latitude=latitude,
                    longitude=longitude,
                    day_number=raw_day_number,
                )
            )
    return locations


def build_location_graph(
    locations: list[RouteLocation], neighbors_per_location: int = 2
) -> dict[str, dict[str, float]]:
    """Connect each location to its nearest geographic neighbors with great-circle costs."""
    graph = {location.id: {} for location in locations}
    if neighbors_per_location < 1:
        raise ValueError("Each location must have at least one graph neighbor.")

    for location in locations:
        nearest = sorted(
            (
                (haversine_km(location.latitude, location.longitude, other.latitude, other.longitude), other.id)
                for other in locations
                if other.id != location.id
            ),
            key=lambda item: (item[0], item[1]),
        )[:neighbors_per_location]
        for distance, neighbor_id in nearest:
            graph[location.id][neighbor_id] = distance
            graph[neighbor_id][location.id] = distance
    return graph


def geographic_heuristic(locations: list[RouteLocation], goal: str) -> Callable[[str], float]:
    by_id = {location.id: location for location in locations}
    if goal not in by_id:
        raise ValueError("Goal must be a known itinerary location.")
    target = by_id[goal]

    def estimate(location_id: str) -> float:
        location = by_id.get(location_id)
        if location is None:
            raise ValueError("Heuristic requested for an unknown itinerary location.")
        return haversine_km(location.latitude, location.longitude, target.latitude, target.longitude)

    return estimate