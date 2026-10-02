from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

MAX_CSP_EVENTS = 200
MAX_CSP_TRIP_DAYS = 60


@dataclass
class CSPSolution:
    assignment: dict[str, int] | None
    backtracks: int
    backjumps: int
    constraint_checks: int
    values_pruned: int


def solve_csp(
    domains: dict[str, list[int]],
    different_day_constraints: set[tuple[str, str]],
    preferred_values: dict[str, int] | None = None,
) -> CSPSolution:
    """Solve binary different-day constraints with backtracking and forward checking."""
    preferences = preferred_values or {}
    neighbors = {variable: set() for variable in domains}
    for left, right in different_day_constraints:
        neighbors[left].add(right)
        neighbors[right].add(left)

    stats = {"backtracks": 0, "backjumps": 0, "constraint_checks": 0, "values_pruned": 0}

    def search(
        assignment: dict[str, int],
        remaining_domains: dict[str, list[int]],
    ) -> tuple[dict[str, int] | None, set[str]]:
        if len(assignment) == len(domains):
            return dict(assignment), set()

        unassigned = [variable for variable in domains if variable not in assignment]
        variable = min(
            unassigned,
            key=lambda item: (
                len(remaining_domains[item]),
                -len(neighbors[item].intersection(unassigned)),
                item,
            ),
        )
        ordered_values = sorted(
            remaining_domains[variable],
            key=lambda value: (value != preferences.get(variable), value),
        )
        conflicts: set[str] = set()

        for value in ordered_values:
            blocked_by = set()
            for neighbor, assigned_value in assignment.items():
                if neighbor in neighbors[variable]:
                    stats["constraint_checks"] += 1
                    if value == assigned_value:
                        blocked_by.add(neighbor)
            if blocked_by:
                stats["backtracks"] += 1
                conflicts.update(blocked_by)
                continue

            next_domains = {key: list(values) for key, values in remaining_domains.items()}
            next_domains[variable] = [value]
            wiped_out = None
            for neighbor in sorted(neighbors[variable]):
                if neighbor in assignment:
                    continue
                filtered = [candidate for candidate in next_domains[neighbor] if candidate != value]
                stats["constraint_checks"] += len(next_domains[neighbor])
                stats["values_pruned"] += len(next_domains[neighbor]) - len(filtered)
                next_domains[neighbor] = filtered
                if not filtered:
                    wiped_out = neighbor
                    break

            if wiped_out is not None:
                stats["backtracks"] += 1
                conflicts.add(variable)
                continue

            next_assignment = {**assignment, variable: value}
            solution, child_conflicts = search(next_assignment, next_domains)
            if solution is not None:
                return solution, set()
            if variable not in child_conflicts:
                stats["backjumps"] += 1
                return None, child_conflicts
            child_conflicts.discard(variable)
            conflicts.update(child_conflicts)
            stats["backtracks"] += 1

        return None, conflicts

    if any(not domain for domain in domains.values()):
        return CSPSolution(None, 0, 0, 0, 0)

    assignment, _ = search({}, {key: list(values) for key, values in domains.items()})
    return CSPSolution(assignment, **stats)


def parse_time_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*", value, re.IGNORECASE)
    if not match:
        return None

    parsed = []
    for part in match.groups():
        cleaned = " ".join(part.upper().split())
        pattern = "%I:%M %p" if cleaned.endswith(("AM", "PM")) else "%H:%M"
        try:
            moment = datetime.strptime(cleaned, pattern)
        except ValueError:
            return None
        parsed.append(moment.hour * 60 + moment.minute)
    return (parsed[0], parsed[1]) if parsed[1] > parsed[0] else None


def build_itinerary_csp_result(duration: Any, itinerary: Any) -> dict[str, Any]:
    """Build and solve a day-assignment CSP from saved itinerary fields only."""
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
        return _insufficient("A positive trip duration is required to create day domains.")
    if duration > MAX_CSP_TRIP_DAYS:
        return _insufficient(f"The trip exceeds the supported {MAX_CSP_TRIP_DAYS}-day CSP scheduling limit.")
    if not isinstance(itinerary, list):
        return _insufficient("The saved itinerary is not a list of day plans.")

    events: list[dict[str, Any]] = []
    seen_days = set()
    for index, day in enumerate(itinerary, start=1):
        if not isinstance(day, dict):
            return _insufficient(f"Itinerary day entry {index} is malformed.")
        day_number = day.get("day_number")
        if isinstance(day_number, bool) or not isinstance(day_number, int) or day_number < 1 or day_number in seen_days:
            return _insufficient(f"Itinerary day entry {index} has an invalid or duplicate day number.")
        seen_days.add(day_number)

        activities = day.get("activities", [])
        attractions = day.get("attractions", [])
        if not isinstance(activities, list) or not isinstance(attractions, list):
            return _insufficient(f"Itinerary day {day_number} must store activities and attractions as lists.")

        for activity_index, activity in enumerate(activities):
            if not isinstance(activity, str):
                return _insufficient(f"An activity on day {day_number} is malformed.")
            if activity.strip():
                if len(events) >= MAX_CSP_EVENTS:
                    return _insufficient(f"The itinerary has more than the supported {MAX_CSP_EVENTS} schedulable items.")
                events.append({
                    "id": f"activity-day-{day_number}-{activity_index}",
                    "name": activity.strip(),
                    "type": "activity",
                    "current_day_number": day_number,
                    "timing": None,
                    "interval": None,
                })

        for attraction_index, attraction in enumerate(attractions):
            if not isinstance(attraction, dict) or not isinstance(attraction.get("place"), dict):
                return _insufficient(f"An attraction on day {day_number} is malformed.")
            place = attraction["place"]
            name = place.get("name")
            if not isinstance(name, str) or not name.strip():
                return _insufficient(f"An attraction on day {day_number} has no usable place name.")
            timing = attraction.get("timing")
            if timing is not None and not isinstance(timing, str):
                return _insufficient(f"Attraction timing on day {day_number} must be text.")
            if len(events) >= MAX_CSP_EVENTS:
                return _insufficient(f"The itinerary has more than the supported {MAX_CSP_EVENTS} schedulable items.")
            events.append({
                "id": f"attraction-day-{day_number}-{attraction_index}",
                "name": name.strip(),
                "type": "attraction",
                "current_day_number": day_number,
                "timing": timing,
                    "interval": parse_time_range(timing),
            })

    if not events:
        return _insufficient("No saved activities or attractions are available to schedule.")

    day_domain = list(range(1, duration + 1))
    domains = {event["id"]: list(day_domain) for event in events}
    preferred = {
        event["id"]: event["current_day_number"]
        for event in events
        if event["current_day_number"] in day_domain
    }
    constraints = set()
    conflict_pairs = []
    unresolved_timing = False
    for index, event in enumerate(events):
        if event["type"] == "activity" or event["interval"] is None:
            unresolved_timing = True
        for other in events[index + 1:]:
            if event["interval"] is None or other["interval"] is None:
                continue
            start, end = event["interval"]
            other_start, other_end = other["interval"]
            if start < other_end and other_start < end:
                pair = tuple(sorted((event["id"], other["id"])))
                constraints.add(pair)
                conflict_pairs.append({
                    "activities": [event["name"], other["name"]],
                    "timing": [event["timing"], other["timing"]],
                    "reason": "Overlapping attraction timings cannot be assigned to the same day.",
                })

    solution = solve_csp(domains, constraints, preferred)
    applied_constraints = [f"Each activity and attraction is assigned to a trip day from 1 to {duration}."]
    if constraints:
        applied_constraints.append("Attractions with parsed overlapping timing ranges must be assigned to different days.")
    else:
        applied_constraints.append("No overlapping parsed attraction timing ranges were found.")

    unavailable_constraints = [
        "Opening hours are unavailable because the itinerary has no opening-hours field.",
        "A maximum activities-per-day limit is unavailable because no capacity is stored.",
        "Item costs cannot be compared reliably with the trip budget; activity-level prices are not consistently available.",
        "Travel dates are free-form text and cannot be validated as calendar dates.",
        "Trip-wide interests and things to avoid are not linked to individual activities, so they cannot be enforced as hard constraints.",
        "Travel-time constraints are unavailable; CSP does not infer travel durations or use the separate A* route calculation.",
    ]
    if unresolved_timing:
        unavailable_constraints.append("Overlap checks are unavailable for activities or attractions without parseable timing ranges.")

    if solution.assignment is None:
        return {
            "status": "conflicts",
            "valid": False,
            "algorithm": "CSP / Backtracking",
            "assignments": [],
            "applied_constraints": applied_constraints,
            "unavailable_constraints": unavailable_constraints,
            "conflicts": conflict_pairs,
            "solver_info": _solver_info(solution, len(events)),
            "message": "No schedule satisfies the available day and overlapping-attraction constraints.",
        }

    assignments = [
        {
            "id": event["id"],
            "name": event["name"],
            "type": event["type"],
            "current_day_number": event["current_day_number"],
            "day_number": solution.assignment[event["id"]],
            "timing": event["timing"],
        }
        for event in events
    ]
    return {
        "status": "valid",
        "valid": True,
        "algorithm": "CSP / Backtracking",
        "assignments": assignments,
        "applied_constraints": applied_constraints,
        "unavailable_constraints": unavailable_constraints,
        "conflicts": [],
        "solver_info": _solver_info(solution, len(events)),
        "message": "A schedule satisfying the available constraints was found; this is not a global optimum claim.",
    }


def _solver_info(solution: CSPSolution, variable_count: int) -> dict[str, int]:
    return {
        "variable_count": variable_count,
        "backtracks": solution.backtracks,
        "backjumps": solution.backjumps,
        "constraint_checks": solution.constraint_checks,
        "values_pruned": solution.values_pruned,
    }


def _insufficient(message: str) -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "valid": None,
        "algorithm": "CSP / Backtracking",
        "assignments": [],
        "applied_constraints": [],
        "unavailable_constraints": [message],
        "conflicts": [],
        "solver_info": {"variable_count": 0, "backtracks": 0, "backjumps": 0, "constraint_checks": 0, "values_pruned": 0},
        "message": message,
    }