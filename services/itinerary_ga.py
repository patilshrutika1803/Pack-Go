from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any

from services.itinerary_csp import parse_time_range, solve_csp

MAX_ITINERARY_EVENTS = 200
MAX_TRIP_DAYS = 60
MAX_POPULATION_SIZE = 100
MAX_GENERATIONS = 100


@dataclass(frozen=True)
class ItineraryEvent:
    event_id: str
    name: str
    kind: str
    current_day: int
    payload: Any
    interval: tuple[int, int] | None


Chromosome = tuple[int, ...]


def create_chromosome(events: list[ItineraryEvent]) -> Chromosome:
    """Encode one day assignment per stable itinerary event."""
    return tuple(event.current_day for event in events)


def chromosome_is_valid(chromosome: Chromosome, event_count: int, duration: int) -> bool:
    return (
        len(chromosome) == event_count
        and all(isinstance(day, int) and not isinstance(day, bool) and 1 <= day <= duration for day in chromosome)
    )


def calculate_fitness(
    chromosome: Chromosome,
    events: list[ItineraryEvent],
    duration: int,
    conflict_pairs: list[tuple[int, int]],
) -> float:
    """Higher is better; penalties use only saved assignments, timings, and day counts."""
    invalid_days = sum(not 1 <= day <= duration for day in chromosome)
    overlaps = sum(
        chromosome[left] == chromosome[right]
        for left, right in conflict_pairs
        if left < len(chromosome) and right < len(chromosome)
    )
    loads = [sum(day == day_number for day in chromosome) for day_number in range(1, duration + 1)]
    target_load = len(chromosome) / duration
    imbalance = sum(abs(load - target_load) for load in loads)
    moved = sum(
        day != event.current_day
        for day, event in zip(chromosome, events)
    )
    return -(1000 * invalid_days + 100 * overlaps + imbalance + 0.25 * moved)


def tournament_selection(
    population: list[Chromosome],
    fitnesses: list[float],
    rng: random.Random,
    tournament_size: int = 3,
) -> Chromosome:
    if not population or len(population) != len(fitnesses):
        raise ValueError("Population and fitness values must have matching non-empty lengths.")
    candidates = rng.sample(range(len(population)), min(tournament_size, len(population)))
    winner = max(candidates, key=lambda index: fitnesses[index])
    return population[winner]


def uniform_assignment_crossover(
    first: Chromosome,
    second: Chromosome,
    rng: random.Random,
) -> tuple[Chromosome, Chromosome]:
    """Inherit each fixed event's day from one parent; event identity/order cannot change."""
    if len(first) != len(second):
        raise ValueError("Parent chromosomes must have the same number of genes.")
    child_one = []
    child_two = []
    for first_day, second_day in zip(first, second):
        if rng.random() < 0.5:
            child_one.append(first_day)
            child_two.append(second_day)
        else:
            child_one.append(second_day)
            child_two.append(first_day)
    return tuple(child_one), tuple(child_two)


def mutate_chromosome(
    chromosome: Chromosome,
    duration: int,
    mutation_rate: float,
    rng: random.Random,
) -> Chromosome:
    """Move each gene to another in-trip day with the configured per-gene probability."""
    if not 0 <= mutation_rate <= 1:
        raise ValueError("Mutation rate must be between 0 and 1.")
    if not chromosome_is_valid(chromosome, len(chromosome), duration):
        raise ValueError("Cannot mutate an invalid chromosome.")
    mutated = list(chromosome)
    if duration < 2:
        return chromosome
    for index, day in enumerate(mutated):
        if rng.random() < mutation_rate:
            alternatives = [candidate for candidate in range(1, duration + 1) if candidate != day]
            mutated[index] = rng.choice(alternatives)
    return tuple(mutated)


def _extract_itinerary_events(
    duration: Any,
    itinerary: Any,
) -> tuple[list[ItineraryEvent], dict[int, dict[str, Any]], str | None]:
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
        return [], {}, "A positive trip duration is required to create itinerary day assignments."
    if duration > MAX_TRIP_DAYS:
        return [], {}, f"The trip exceeds the supported {MAX_TRIP_DAYS}-day optimization limit."
    if not isinstance(itinerary, list):
        return [], {}, "The saved itinerary is not a list of day plans."

    events: list[ItineraryEvent] = []
    day_templates: dict[int, dict[str, Any]] = {}
    for day_index, day in enumerate(itinerary):
        if not isinstance(day, dict):
            return [], {}, f"Itinerary day entry {day_index + 1} is malformed."
        day_number = day.get("day_number")
        if (
            isinstance(day_number, bool)
            or not isinstance(day_number, int)
            or day_number < 1
            or day_number > duration
            or day_number in day_templates
        ):
            return [], {}, f"Itinerary day entry {day_index + 1} has an invalid, out-of-range, or duplicate day number."
        activities = day.get("activities", [])
        attractions = day.get("attractions", [])
        if not isinstance(activities, list) or not isinstance(attractions, list):
            return [], {}, f"Itinerary day {day_number} must store activities and attractions as lists."

        day_templates[day_number] = copy.deepcopy(day)
        for activity_index, activity in enumerate(activities):
            if not isinstance(activity, str) or not activity.strip():
                return [], {}, f"An activity on day {day_number} is malformed."
            if len(events) >= MAX_ITINERARY_EVENTS:
                return [], {}, f"The itinerary has more than the supported {MAX_ITINERARY_EVENTS} optimizable items."
            events.append(ItineraryEvent(
                event_id=f"activity-{day_number}-{activity_index}",
                name=activity.strip(),
                kind="activity",
                current_day=day_number,
                payload=copy.deepcopy(activity),
                interval=None,
            ))

        for attraction_index, attraction in enumerate(attractions):
            if not isinstance(attraction, dict) or not isinstance(attraction.get("place"), dict):
                return [], {}, f"An attraction on day {day_number} is malformed."
            name = attraction["place"].get("name")
            timing = attraction.get("timing")
            if not isinstance(name, str) or not name.strip():
                return [], {}, f"An attraction on day {day_number} has no usable place name."
            if timing is not None and not isinstance(timing, str):
                return [], {}, f"Attraction timing on day {day_number} must be text."
            if len(events) >= MAX_ITINERARY_EVENTS:
                return [], {}, f"The itinerary has more than the supported {MAX_ITINERARY_EVENTS} optimizable items."
            events.append(ItineraryEvent(
                event_id=f"attraction-{day_number}-{attraction_index}",
                name=name.strip(),
                kind="attraction",
                current_day=day_number,
                payload=copy.deepcopy(attraction),
                interval=parse_time_range(timing),
            ))

    if not events:
        return [], {}, "No saved activities or attractions are available to optimize."
    return events, day_templates, None


def _get_conflicts(events: list[ItineraryEvent]) -> list[tuple[int, int]]:
    conflicts = []
    for left in range(len(events)):
        if events[left].interval is None:
            continue
        for right in range(left + 1, len(events)):
            if events[right].interval is None:
                continue
            left_start, left_end = events[left].interval
            right_start, right_end = events[right].interval
            if left_start < right_end and right_start < left_end:
                conflicts.append((left, right))
    return conflicts


def generate_initial_population(
    events: list[ItineraryEvent],
    duration: int,
    conflict_pairs: list[tuple[int, int]],
    population_size: int,
    rng: random.Random,
) -> list[Chromosome]:
    """Seed from saved days and bounded CSP runs; duplicate feasible seeds if needed."""
    baseline = create_chromosome(events)
    domains = {event.event_id: list(range(1, duration + 1)) for event in events}
    constraints = {
        (events[left].event_id, events[right].event_id)
        for left, right in conflict_pairs
    }
    candidates = [baseline]
    feasible: list[Chromosome] = []
    for _ in range(min(8, max(1, population_size - 1))):
        preferences = {event.event_id: rng.randint(1, duration) for event in events}
        solution = solve_csp(domains, constraints, preferences).assignment
        if solution is not None:
            chromosome = tuple(solution[event.event_id] for event in events)
            if chromosome not in feasible:
                feasible.append(chromosome)
                if chromosome not in candidates:
                    candidates.append(chromosome)

    if feasible:
        while len(candidates) < population_size:
            candidates.append(feasible[rng.randrange(len(feasible))])
        return candidates[:population_size]

    # If CSP proves the constraints infeasible, vary the saved schedule by legal day moves.
    while len(candidates) < population_size:
        source = candidates[rng.randrange(len(candidates))]
        varied = mutate_chromosome(source, duration, 1 / max(1, len(events)), rng)
        candidates.append(varied)
    return candidates


def _build_result_itinerary(
    events: list[ItineraryEvent],
    day_templates: dict[int, dict[str, Any]],
    chromosome: Chromosome,
    duration: int,
) -> list[dict[str, Any]]:
    days = {}
    for day_number in range(1, duration + 1):
        day = copy.deepcopy(day_templates.get(day_number, {"day_number": day_number}))
        day["activities"] = []
        day["attractions"] = []
        days[day_number] = day
    for event, day_number in zip(events, chromosome):
        days[day_number]["activities" if event.kind == "activity" else "attractions"].append(copy.deepcopy(event.payload))
    return [days[day_number] for day_number in range(1, duration + 1)]


def build_itinerary_ga_result(
    duration: Any,
    itinerary: Any,
    population_size: int = 20,
    generations: int = 20,
    mutation_rate: float = 0.1,
    seed: int | None = None,
) -> dict[str, Any]:
    events, day_templates, error = _extract_itinerary_events(duration, itinerary)
    if error:
        return {
            "status": "insufficient_data",
            "algorithm": "Genetic Algorithm",
            "message": error,
            "optimized_itinerary": None,
            "unavailable_constraints": [error],
        }
    if not 4 <= population_size <= MAX_POPULATION_SIZE or not 1 <= generations <= MAX_GENERATIONS:
        raise ValueError("Population size or generation count is outside the supported bounds.")
    if not 0 <= mutation_rate <= 1:
        raise ValueError("Mutation rate must be between 0 and 1.")

    rng = random.Random(seed)
    conflicts = _get_conflicts(events)
    population = generate_initial_population(events, duration, conflicts, population_size, rng)
    baseline = create_chromosome(events)
    fitnesses = [calculate_fitness(chromosome, events, duration, conflicts) for chromosome in population]
    initial_best_fitness = max(fitnesses)

    for _ in range(generations):
        elite = population[max(range(len(population)), key=lambda index: fitnesses[index])]
        next_population = [elite]
        while len(next_population) < population_size:
            parent_one = tournament_selection(population, fitnesses, rng)
            parent_two = tournament_selection(population, fitnesses, rng)
            children = uniform_assignment_crossover(parent_one, parent_two, rng)
            for child in children:
                next_population.append(mutate_chromosome(child, duration, mutation_rate, rng))
                if len(next_population) == population_size:
                    break
        population = next_population
        fitnesses = [calculate_fitness(chromosome, events, duration, conflicts) for chromosome in population]

    best_index = max(range(len(population)), key=lambda index: fitnesses[index])
    best = population[best_index]
    parsed_timings = sum(event.interval is not None for event in events)
    unavailable = [
        "Entry fees are not consistently numeric across itinerary items, so budget fit cannot be scored reliably.",
        "Trip interests and things to avoid are not associated with individual activities or attractions, so preference matching is unavailable.",
        "Travel durations, opening hours, coordinates, and popularity are not consistently stored per item and are not inferred.",
    ]
    if parsed_timings < sum(event.kind == "attraction" for event in events):
        unavailable.append("Overlap checking is unavailable for items without a parseable attraction timing range.")

    applied_criteria = [
        "Penalize same-day overlaps between attractions with parsed timing ranges (100 points per conflicting pair).",
        "Prefer an even distribution of saved activities and attractions across trip days (sum of absolute daily-load deviations).",
        "Prefer to preserve each item's saved day when other fitness criteria are equal (0.25 points per moved item).",
    ]
    return {
        "status": "optimized",
        "algorithm": "Genetic Algorithm",
        "message": "The Genetic Algorithm searches a population of candidate itineraries for a higher-fitness solution; it does not guarantee a global optimum.",
        "optimized_itinerary": _build_result_itinerary(events, day_templates, best, duration),
        "fitness_score": round(fitnesses[best_index], 4),
        "baseline_fitness": round(calculate_fitness(baseline, events, duration, conflicts), 4),
        "initial_population_best_fitness": round(initial_best_fitness, 4),
        "final_fitness": round(fitnesses[best_index], 4),
        "generations_executed": generations,
        "population_size": population_size,
        "mutation_rate": mutation_rate,
        "fitness_formula": "-(1000 * invalid_day_assignments + 100 * same_day_timing_conflicts + daily_load_deviation + 0.25 * moved_items)",
        "applied_criteria": applied_criteria,
        "unavailable_constraints": unavailable,
    }