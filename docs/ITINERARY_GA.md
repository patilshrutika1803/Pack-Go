# Itinerary Genetic Algorithm

## Data Audit

The existing trip model stores `duration`, `total_budget`, `budget_currency`, `interests`, `things_to_avoid`, and an itinerary JSON list. Saved day entries use `day_number`, `activities` (strings), and `attractions` (objects containing a `place` object and optional `timing`). Attraction/place objects can contain additional fields, which the preview preserves without interpreting them.

The optimizer moves saved activity and attraction items between numbered trip days. It preserves each item payload and other day-level JSON fields. Missing days are represented with the existing `day_number`, `activities`, and `attractions` structure. It does not add or remove itinerary items.

Entry-fee values are not consistently numeric, and itinerary items have no reliable association to trip interests or things to avoid. Consequently budget fit and preference matching are unavailable. The optimizer does not invent prices, coordinates, travel times, popularity, or opening hours. It only parses attraction timing ranges using the parser shared with the CSP scheduler.

## Genetic Algorithm

- **Chromosome:** A tuple of day numbers aligned to the fixed, extracted list of saved itinerary items.
- **Gene:** The trip day assigned to one specific event. Event identity and item order are fixed, so every chromosome contains every activity and attraction exactly once.
- **Initial population:** Includes the saved day assignment and up to eight CSP-generated assignments satisfying parsed same-day timing-conflict constraints. The CSP solver remains responsible for constraint-satisfying assignments; when the constraints are infeasible, the GA seeds from the saved schedule and legal day mutations. Small feasible sets are repeated to meet the requested population size.
- **Fitness:** Higher is better. `-(1000 * invalid_day_assignments + 100 * same_day_timing_conflicts + daily_load_deviation + 0.25 * moved_items)`. Daily load deviation is the sum, over trip days, of the absolute difference between that day's item count and the mean item count. Invalid day assignments are defensively scored, although chromosome operators restrict genes to valid trip days. The weights express optimization priorities; they are not attraction ratings or inferred travel data.
- **Selection:** Tournament selection samples up to three population members and chooses the highest-fitness candidate. It is simple, stochastic, and reproducible with a seed.
- **Crossover:** Uniform assignment crossover independently inherits each fixed item's day gene from one parent (with complementary inheritance in the paired child). Since genes are assignments rather than a visit-order permutation, this preserves item identity and cannot create duplicates or omissions. Visit order is not optimized because reliable travel-time/order data is unavailable.
- **Mutation:** Each gene mutates independently at the configured mutation rate by moving that item to a different valid trip day.
- **Generations:** Elitist evolution retains the current best candidate, then fills the next generation through tournament selection, crossover, and mutation. Defaults are population 20, generations 20, and mutation rate 0.1. Population and generation counts are bounded at 100.

The preview returns baseline fitness, initial-population best fitness, final fitness, actual criteria, and unavailable data. It never writes the candidate to the trip. A Genetic Algorithm searches a population of candidate itineraries for a higher-fitness solution; it does not guarantee a global optimum.

## API

`POST /api/v1/trips/{trip_id}/itinerary/ga-optimize`

The endpoint requires authentication and uses `TripAccessService`, allowing the trip owner and active group members while hiding inaccessible trips. Optional configuration is bounded: population size 4-100, generations 1-100, mutation rate 0-1, and an optional deterministic random seed. Missing or malformed itinerary data returns an `insufficient_data` result rather than modifying saved trip data.