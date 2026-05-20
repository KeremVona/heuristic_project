import os
from dotenv import load_dotenv
from Database.database_loader import DatabaseLoader
from Helpers.apply_user_preferences import apply_user_preferences

# Load environment variables from .env file
load_dotenv()

# Initialize the DB loader
db = DatabaseLoader()

# 1. Load the master list of foods ONCE
master_foods = db.load_foods()

# 2. Process User 1
user1 = db.load_user(user_id=1)
user1_foods = apply_user_preferences(master_foods, user1)
# -> Now you pass user1_foods and user1 into the DietDecoder and MOEA!

# 3. Process User 2
user2 = db.load_user(user_id=2)
user2_foods = apply_user_preferences(master_foods, user2)
# -> Now you pass user2_foods and user2 into the DietDecoder and MOEA!