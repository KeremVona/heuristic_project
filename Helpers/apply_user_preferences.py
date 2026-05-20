import copy
from typing import Dict
from DataModels.food import Food
from DataModels.user import User

def apply_user_preferences(master_foods_dict: Dict[int, Food], user: User) -> Dict[int, Food]:
    """
    Makes a user-specific copy of the foods dictionary and overwrites 
    the default preferences with the user's specific preferences.
    """
    # 1. Make a deep copy so we don't mutate the original dictionary
    user_foods_dict = copy.deepcopy(master_foods_dict)
    
    # 2. Iterate through the user's custom preferences
    for food_id, custom_pref in user.food_preferences.items():
        # 3. If the food exists in our dictionary, update its preference
        if food_id in user_foods_dict:
            user_foods_dict[food_id].preference = custom_pref
            
    return user_foods_dict