class User:
    def __init__(self, user_id: int, is_vegetarian: bool):
        self.user_id = user_id
        self.is_vegetarian = is_vegetarian
        self.dri_limits = {}  # e.g., {'Energy': [RLL, RUL], 'Protein': [RLL, RUL]}
        self.food_preferences = {}  # Overrides default food preferences
