# Itinerary Constraint Satisfaction

PACK & GO's CSP endpoint checks a saved itinerary without replacing the LLM itinerary generator or writing changes to the trip. It returns proposed day assignments for review.

## Model

- **Variables:** Each non-empty saved activity string and each saved attraction visit.
- **Domains:** Integer trip days from `1` through `Trip.duration`.
- **Initial value order:** The item's existing `day_number` is tried first when it is within the trip duration; remaining days are tried in ascending order.
- **Implemented constraints:** Every item receives one in-range trip day. Two attraction visits whose saved `timing` strings parse as clock ranges and overlap must be assigned to different days. Backtracking search uses minimum remaining values, degree tie-breaking, forward checking, and conflict-directed backjumping.

The solver does not claim global optimality. It finds a satisfying assignment if one exists under these constraints. Reassignments are returned as a preview; the persisted itinerary is not modified.

## Unavailable Constraints

The current itinerary contract does not provide reliable opening hours, a per-day capacity, item-level cost data, structured travel dates, activity-to-preference links, or travel durations. These are reported as unavailable and are not inferred. Unparseable attraction timing and activity timings cannot participate in overlap checks. Coordinates and A* distance estimates are unrelated to this scheduling CSP.

Endpoint: `POST /api/v1/trips/{trip_id}/itinerary/csp-optimize` with an empty JSON object. Access requires authentication and the same private-trip owner or active group-member authorization used by trip utilities.