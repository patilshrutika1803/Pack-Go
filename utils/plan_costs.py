import re
from collections.abc import Iterable

from models.schemas import BudgetBreakdown, CategoryCost, DayPlan


def parse_cost(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value or ""))
    return float(match.group(0).replace(",", "")) if match else 0.0


def reconcile_budget(budget: BudgetBreakdown, itinerary: Iterable[DayPlan], budget_limit: float) -> BudgetBreakdown:
    accommodation = 0.0
    food = 0.0
    activities = 0.0
    transport = 0.0

    for day in itinerary:
        accommodation += parse_cost(day.hotel.price_per_night)
        food += sum(parse_cost(meal.estimated_cost) for meal in day.meals)
        activities += sum(parse_cost(attraction.place.entry_fee) for attraction in day.attractions)
        transport += parse_cost(day.transport.estimated_cost)

    categories = [
        CategoryCost(name="Accommodation", amount=accommodation),
        CategoryCost(name="Food", amount=food),
        CategoryCost(name="Transport", amount=transport),
        CategoryCost(name="Activities", amount=activities),
    ]
    total = sum(category.amount for category in categories)
    return budget.model_copy(
        update={
            "total_estimated": total,
            "categories": categories,
            "is_within_budget": total <= budget_limit,
        }
    )