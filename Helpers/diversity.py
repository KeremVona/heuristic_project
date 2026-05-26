from typing import Any, Dict, Iterable, List


def calculate_diversity_score(menu_ids: Iterable[int], foods_dict: Dict[int, Any]) -> int:
    """Return the number of distinct foodGroupId values in a decoded menu."""
    groups = set()
    for food_id in menu_ids:
        food = foods_dict.get(food_id)
        if food is not None:
            groups.add(food.food_group_id)
    return len(groups)


def diversity_constraint_value(
    menu_ids: Iterable[int],
    foods_dict: Dict[int, Any],
    use_diversity: bool = True,
    min_groups: int = 4,
) -> float:
    """Pymoo-compatible constraint: values <= 0 are feasible."""
    if not use_diversity:
        return 0.0
    return float(min_groups - calculate_diversity_score(menu_ids, foods_dict))


def diversity_penalty(
    menu_ids: Iterable[int],
    foods_dict: Dict[int, Any],
    use_diversity: bool = True,
    min_groups: int = 4,
    weight: float = 5.0,
) -> float:
    """Penalty used by the experiment runner when diversity is enabled."""
    if not use_diversity:
        return 0.0

    score = calculate_diversity_score(menu_ids, foods_dict)
    if score >= min_groups:
        return 0.0

    return float(min_groups - score) * weight


def menu_group_ids(menu_ids: Iterable[int], foods_dict: Dict[int, Any]) -> List[int]:
    """Return group ids for reporting and debugging experiment output."""
    group_ids = []
    for food_id in menu_ids:
        food = foods_dict.get(food_id)
        if food is not None:
            group_ids.append(food.food_group_id)
    return group_ids
