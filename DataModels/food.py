class Food:
    def __init__(
        self,
        food_id: int,
        name: str,
        food_group_id: int,
        cost: float,
        preference: float,
        prep_time: float,
        cook_time: float,
        co2: float,
        is_vegetarian: bool,
    ):
        self.food_id = food_id
        self.name = name
        self.food_group_id = food_group_id
        self.cost = cost
        self.preference = preference
        self.prep_time = prep_time
        self.cook_time = cook_time
        self.co2 = co2
        self.is_vegetarian = is_vegetarian
        self.nutrients = {}  # e.g., {'Energy': 250.5, 'Protein': 12.0}
