import pytest

from services.route_optimization import (
    InvalidRouteLocations,
    astar_search,
    extract_itinerary_locations,
    haversine_km,
)


def test_astar_finds_known_shortest_path_and_reports_f_equals_g_plus_h():
    graph = {
        "start": {"museum": 1.0, "market": 2.0},
        "museum": {"start": 1.0, "goal": 1.0},
        "market": {"start": 2.0, "goal": 1.0},
        "goal": {"museum": 1.0, "market": 1.0},
    }
    estimates = {"start": 2.0, "museum": 1.0, "market": 1.0, "goal": 0.0}

    result = astar_search(graph, "start", "goal", estimates.__getitem__)

    assert result is not None
    assert result.path == ["start", "museum", "goal"]
    assert result.cost == 2.0
    museum_score = next(entry for entry in result.expanded_nodes if entry["location_id"] == "museum")
    assert museum_score["g"] == 1.0
    assert museum_score["h"] == 1.0
    assert museum_score["f"] == museum_score["g"] + museum_score["h"]


def test_astar_returns_none_for_unreachable_goal():
    result = astar_search({"start": {}, "goal": {}}, "start", "goal", lambda _node: 0.0)

    assert result is None


@pytest.mark.parametrize(
    "place",
    [
        {"name": "Missing longitude", "latitude": 19.0},
        {"name": "Invalid latitude", "latitude": 91, "longitude": 72},
        {"name": "Non-numeric", "latitude": "north", "longitude": 72},
    ],
)
def test_invalid_itinerary_coordinates_are_rejected(place):
    itinerary = [{"day_number": 1, "attractions": [{"place": place}]}]

    with pytest.raises(InvalidRouteLocations):
        extract_itinerary_locations(itinerary)


def test_geographic_heuristic_is_real_symmetric_distance():
    distance = haversine_km(19.0760, 72.8777, 18.5204, 73.8567)

    assert 100 < distance < 200
    assert haversine_km(19.0760, 72.8777, 19.0760, 72.8777) == 0
    assert distance == haversine_km(18.5204, 73.8567, 19.0760, 72.8777)


def test_astar_result_is_deterministic_for_same_graph_and_input():
    graph = {
        "start": {"b": 1.0, "a": 1.0},
        "a": {"start": 1.0, "goal": 1.0},
        "b": {"start": 1.0, "goal": 1.0},
        "goal": {"a": 1.0, "b": 1.0},
    }
    run = lambda: astar_search(graph, "start", "goal", lambda _node: 0.0)

    assert run() == run()