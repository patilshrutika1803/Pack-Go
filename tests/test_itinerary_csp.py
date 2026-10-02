from services.itinerary_csp import build_itinerary_csp_result, solve_csp


def test_known_csp_assigns_conflicting_variables_deterministically():
    domains = {"A": [1, 2], "B": [1, 2], "C": [1, 2]}
    constraints = {("A", "B")}
    preferred = {"A": 1, "B": 1, "C": 1}

    first = solve_csp(domains, constraints, preferred)
    second = solve_csp(domains, constraints, preferred)

    assert first.assignment == {"A": 1, "B": 2, "C": 1}
    assert second.assignment == first.assignment
    assert first.constraint_checks > 0
    assert first.values_pruned == 1


def test_backtracking_reports_no_solution_for_two_value_triangle():
    domains = {variable: [1, 2] for variable in ("A", "B", "C")}
    constraints = {("A", "B"), ("A", "C"), ("B", "C")}

    result = solve_csp(domains, constraints, {"A": 1, "B": 1, "C": 1})

    assert result.assignment is None
    assert result.backtracks > 0
    assert result.constraint_checks > 0


def test_overlapping_attractions_are_moved_to_another_trip_day():
    itinerary = [
        {
            "day_number": 1,
            "activities": ["Walk around town"],
            "attractions": [
                {"place": {"name": "Museum"}, "timing": "10:00 AM - 12:00 PM"},
                {"place": {"name": "Gallery"}, "timing": "11:00 AM - 1:00 PM"},
            ],
        }
    ]

    result = build_itinerary_csp_result(2, itinerary)

    assert result["status"] == "valid"
    assert [(item["name"], item["day_number"]) for item in result["assignments"]] == [
        ("Walk around town", 1),
        ("Museum", 1),
        ("Gallery", 2),
    ]
    assert result["solver_info"]["values_pruned"] == 1
    assert result["unavailable_constraints"]


def test_one_day_with_overlapping_attractions_has_no_solution():
    itinerary = [{
        "day_number": 1,
        "attractions": [
            {"place": {"name": "Museum"}, "timing": "10:00 - 12:00"},
            {"place": {"name": "Gallery"}, "timing": "11:00 - 13:00"},
        ],
    }]

    result = build_itinerary_csp_result(1, itinerary)

    assert result["status"] == "conflicts"
    assert result["valid"] is False
    assert result["conflicts"][0]["activities"] == ["Museum", "Gallery"]


def test_missing_or_malformed_itinerary_data_is_reported_as_insufficient():
    assert build_itinerary_csp_result(3, [])["status"] == "insufficient_data"
    malformed = build_itinerary_csp_result(3, [{"day_number": 1, "activities": [17]}])
    assert malformed["status"] == "insufficient_data"
    assert "malformed" in malformed["message"]


def test_csp_rejects_oversized_trip_domains_and_itineraries():
    oversized_duration = build_itinerary_csp_result(61, [{"day_number": 1, "activities": ["Walk"]}])
    oversized_itinerary = build_itinerary_csp_result(
        2,
        [{"day_number": 1, "activities": [f"Activity {index}" for index in range(201)]}],
    )

    assert oversized_duration["status"] == "insufficient_data"
    assert "60-day" in oversized_duration["message"]
    assert oversized_itinerary["status"] == "insufficient_data"
    assert "200 schedulable items" in oversized_itinerary["message"]