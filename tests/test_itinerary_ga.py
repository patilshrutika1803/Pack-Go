import random

from services.itinerary_ga import (
    ItineraryEvent,
    calculate_fitness,
    chromosome_is_valid,
    create_chromosome,
    generate_initial_population,
    mutate_chromosome,
    tournament_selection,
    uniform_assignment_crossover,
    build_itinerary_ga_result,
)


def _events():
    return [
        ItineraryEvent("museum", "Museum", "attraction", 1, {"place": {"name": "Museum"}}, (600, 720)),
        ItineraryEvent("gallery", "Gallery", "attraction", 1, {"place": {"name": "Gallery"}}, (660, 780)),
        ItineraryEvent("walk", "Walk", "activity", 2, "Walk", None),
    ]


def test_chromosome_creation_and_validity_preserve_one_day_gene_per_event():
    events = _events()
    chromosome = create_chromosome(events)

    assert chromosome == (1, 1, 2)
    assert chromosome_is_valid(chromosome, len(events), 2)
    assert not chromosome_is_valid((1, 3, 2), len(events), 2)
    assert not chromosome_is_valid((1, 2), len(events), 2)


def test_fitness_penalizes_real_overlapping_attraction_timings():
    events = _events()
    conflicts = [(0, 1)]

    assert calculate_fitness((1, 2, 2), events, 2, conflicts) > calculate_fitness((1, 1, 2), events, 2, conflicts)
    assert calculate_fitness((1, 1, 2), events, 2, conflicts) == -101.0


def test_population_uses_csp_feasible_seeds_and_preserves_event_count():
    events = _events()
    population = generate_initial_population(events, 2, [(0, 1)], 8, random.Random(7))

    assert len(population) == 8
    assert all(chromosome_is_valid(chromosome, len(events), 2) for chromosome in population)
    assert any(chromosome[0] != chromosome[1] for chromosome in population)


def test_tournament_selection_returns_a_fitter_competitor_with_tied_seeded_sampling():
    population = [(1,), (2,), (3,)]
    first = tournament_selection(population, [-3, -2, -1], random.Random(13), tournament_size=3)
    second = tournament_selection(population, [-3, -2, -1], random.Random(13), tournament_size=3)

    assert first == (3,)
    assert second == first


def test_uniform_assignment_crossover_cannot_duplicate_or_drop_genes():
    first = (1, 1, 2, 2)
    second = (2, 2, 1, 1)
    child_one, child_two = uniform_assignment_crossover(first, second, random.Random(5))

    assert len(child_one) == len(first)
    assert len(child_two) == len(second)
    assert all(day in {1, 2} for day in child_one + child_two)
    assert all((a, b) in {(1, 2), (2, 1)} for a, b in zip(child_one, child_two))


def test_mutation_moves_only_selected_genes_to_valid_days():
    mutated = mutate_chromosome((1, 1, 2), 2, 1, random.Random(3))

    assert mutated == (2, 2, 1)
    assert chromosome_is_valid(mutated, 3, 2)
    assert mutate_chromosome((1, 1), 1, 1, random.Random(3)) == (1, 1)


def test_seeded_ga_improves_known_overlapping_baseline_and_is_repeatable():
    itinerary = [{
        "day_number": 1,
        "activities": ["Walk"],
        "attractions": [
            {"place": {"name": "Museum"}, "timing": "10:00 AM - 12:00 PM"},
            {"place": {"name": "Gallery"}, "timing": "11:00 AM - 1:00 PM"},
        ],
    }]

    first = build_itinerary_ga_result(2, itinerary, population_size=8, generations=5, seed=42)
    second = build_itinerary_ga_result(2, itinerary, population_size=8, generations=5, seed=42)

    assert first == second
    assert first["final_fitness"] > first["baseline_fitness"]
    assert first["optimized_itinerary"][0]["attractions"] != itinerary[0]["attractions"]
    assert first["generations_executed"] == 5


def test_insufficient_and_malformed_itineraries_are_reported():
    assert build_itinerary_ga_result(2, [])["status"] == "insufficient_data"
    malformed = build_itinerary_ga_result(2, [{"day_number": 1, "activities": [7]}])
    assert malformed["status"] == "insufficient_data"
    assert "malformed" in malformed["message"]
    assert build_itinerary_ga_result(61, [{"day_number": 1, "activities": ["Walk"]}])["status"] == "insufficient_data"