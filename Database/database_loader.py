import mysql.connector
from typing import Dict
from DataModels.food import Food
from DataModels.user import User
import os


class DatabaseLoader:
    def __init__(self):
        self.db_config = {
            "host": os.getenv("DB_HOST"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME"),
        }

    def _get_connection(self):
        return mysql.connector.connect(**self.db_config)

    def load_foods(self) -> Dict[int, Food]:
        """
        Connects to the DB, fetches all 405 foods, and populates their nutrients.
        Returns the foods_dict expected by your mate's DietDecoder.
        """
        foods_dict = {}
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Join foods with their nutrients
            query = """
                SELECT f.id, f.name, f.cost, f.preference, 
                       f.preparingTime, f.cookingTime, f.co2, 
                       n.name AS nutrient_name, fn.value AS nutrient_value
                FROM foods f
                LEFT JOIN food_nutrients fn ON f.id = fn.foodid
                LEFT JOIN nutrients n ON fn.nutrientid = n.id;
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                food_id = row['id']
                
                # If we haven't seen this food yet, make it
                if food_id not in foods_dict:
                    # Note: We may need to adjust the is_vegetarian logic based on how 
                    # our specific DB schema flags meat vs. non-meat groups.
                    foods_dict[food_id] = Food(
                        food_id=food_id,
                        name=row['name'],
                        cost=float(row['cost']),
                        preference=float(row['preference']),
                        prep_time=float(row['preparingTime']),
                        cook_time=float(row['cookingTime']),
                        co2=float(row['co2']),
                        is_vegetarian=True # Update this based on our food_group logic!
                    )
                
                # Add the nutrient to the food's dictionary
                if row['nutrient_name']:
                    foods_dict[food_id].nutrients[row['nutrient_name']] = float(row['nutrient_value'])

        finally:
            cursor.close()
            conn.close()

        return foods_dict

    def load_user(self, user_id: int) -> User:
        """
        Connects to the DB, fetches user details, DRI limits, and specific preferences.
        Returns the User object expected by your mate's DietDecoder.
        """
        # User 1 is Non-vegetarian, User 2 is Vegetarian
        is_veg = True if user_id == 2 else False
        user = User(user_id=user_id, is_vegetarian=is_veg)

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # 1. Fetch DRI bounds and map nutrient names directly
            dri_query = """
                SELECT n.name AS nutrient_name, d.RLL, d.RUL
                FROM dri d
                JOIN nutrients n ON d.nutrientId = n.id
                WHERE d.userId = %s;
            """
            cursor.execute(dri_query, (user_id,))
            for row in cursor.fetchall():
                # Store as [Lower Limit, Upper Limit] as expected by DietDecoder
                user.dri_limits[row['nutrient_name']] = [float(row['RLL']), float(row['RUL'])]

            # 2. Fetch User-specific food preferences
            pref_query = """
                SELECT foodid, preference
                FROM user_foods
                WHERE userId = %s;
            """
            cursor.execute(pref_query, (user_id,))
            for row in cursor.fetchall():
                user.food_preferences[row['foodid']] = float(row['preference'])

        finally:
            cursor.close()
            conn.close()

        return user
