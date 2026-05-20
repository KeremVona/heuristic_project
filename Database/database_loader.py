import mysql.connector
from typing import Dict
from DataModels.food import Food
import os
from dotenv import load_dotenv

load_dotenv()


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
            # TODO: Write SQL query to fetch from `foods` table
            # TODO: Write SQL query to join `food_nutrients` and `nutrients` tables
            pass
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
            # TODO: Write SQL query to fetch from `user_dri` for RLL/RUL bounds
            # TODO: Write SQL query to fetch from `user_foods` for specific preferences
            pass
        finally:
            cursor.close()
            conn.close()

        return user
