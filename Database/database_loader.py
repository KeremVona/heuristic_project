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
        foods_dict = {}
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Updated to use fn.quantity and exact column names
            query = """
                SELECT f.id, f.name, f.foodGroupId, f.cost, f.preference, 
                       f.preparingTime, f.cookingTime, f.co2, 
                       n.name AS nutrient_name, fn.quantity AS nutrient_value
                FROM foods f
                LEFT JOIN food_nutrients fn ON f.id = fn.foodId
                LEFT JOIN nutrients n ON fn.nutrientId = n.id;
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                food_id = row['id']
                
                if food_id not in foods_dict:
                    group_id = int(row['foodGroupId']) if row['foodGroupId'] else 0
                    
                    # NOTE: Check Database if IDs are correct

                    meat_groups = [2, 3, 15, 23] 
                    is_veg = group_id not in meat_groups

                    foods_dict[food_id] = Food(
                        food_id=food_id,
                        name=row['name'],
                        food_group_id=group_id,
                        cost=float(row['cost']),
                        preference=float(row['preference']),
                        prep_time=float(row['preparingTime']),
                        cook_time=float(row['cookingTime']),
                        co2=float(row['co2']),
                        is_vegetarian=is_veg
                    )
                
                if row['nutrient_name'] and row['nutrient_value'] is not None:
                    foods_dict[food_id].nutrients[row['nutrient_name']] = float(row['nutrient_value'])

        finally:
            cursor.close()
            conn.close()

        return foods_dict

    def load_user(self, user_id: int) -> User:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Fetch User Demographics
            user_query = "SELECT age, gender FROM user WHERE id = %s"
            cursor.execute(user_query, (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                raise ValueError(f"User with ID {user_id} not found in database.")
                
            age = user_data['age']
            gender = user_data['gender']
            
            # User 1 is Non-vegetarian, User 2 is Vegetarian
            is_veg = True if user_id == 2 else False
            user = User(user_id=user_id, is_vegetarian=is_veg)

            # 2. Fetch DRI bounds using Demographics
            dri_query = """
                SELECT n.name AS nutrient_name, d.RLL, d.RUL
                FROM dri d
                JOIN nutrients n ON d.nutrient_id = n.id
                WHERE d.low_age <= %s AND d.up_age >= %s AND d.gender = %s;
            """
            cursor.execute(dri_query, (age, age, gender))
            for row in cursor.fetchall():
                user.dri_limits[row['nutrient_name']] = [float(row['RLL']), float(row['RUL'])]

            # 3. Fetch User-specific food preferences
            pref_query = """
                SELECT foodId, preference
                FROM user_foods
                WHERE userId = %s;
            """
            cursor.execute(pref_query, (user_id,))
            for row in cursor.fetchall():
                user.food_preferences[row['foodId']] = float(row['preference'])

        finally:
            cursor.close()
            conn.close()

        return user
