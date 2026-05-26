#  ------- NSGA-II (Multi-Objective) Genetic Algorithm ------------

import random

from decoder import DietDecoder                                     
from Helpers.apply_user_preferences import apply_user_preferences  
from Penalty.evaluator import Evaluator                             
from genetic import DietChromosome, GeneticOperators               

#  MENU SCORE CALCULATOR
def calculate_menu_scores(chromosome, user, user_foods, evaluator):
    # create menu from chromosome
    breakfast_menu, lunch_dinner_menu, totals = DietDecoder.decode(chromosome, user, user_foods)
    all_selected_foods = breakfast_menu + lunch_dinner_menu
    
    total_preference = 0.0
    total_price = 0.0
    total_time = 0.0  
    unique_groups = set()  # to make unique
    
    # Calculate simple total price and taste
    for food_id in all_selected_foods:
        if food_id in user_foods:
            food = user_foods[food_id]
            total_price += food.cost
            total_preference += food.preference
            
            total_time += (food.prep_time + food.cook_time)
            
            # add the id of food to see diversity
            unique_groups.add(food.food_group_id)

    # Calculate rule mistakes using the Evaluator class
    mistake_points = evaluator.calculate_penalty(totals, user.dri_limits)
    
    # Diversity Punishment (Option B) If the diversity is low, Punishment will be high
    group_count = len(unique_groups)
    if group_count > 0:
        diversity_penalty = 1.0 / group_count
    else:
        diversity_penalty = 1.0

    alpha = 5.0  # diversity penalty coefficient
    mistake_points += (diversity_penalty * alpha)
    
    return total_preference, total_price, total_time, mistake_points  


def assign_quality_groups(menu_pool):
    #  RESET EVERYONE
    #  Reset beaten status.
    for menu in menu_pool:
        menu.quality_group = 0
        menu.is_beaten = False

    group_number = 1
    
    while True:
        #  FIND MENUS WAITING FOR A GROUP
        waiting_menus = []
        for menu in menu_pool:
            if menu.quality_group == 0:
                waiting_menus.append(menu)

        if len(waiting_menus) == 0:
            break

        # Start to take a menu for compare
        for menu1 in waiting_menus:
            menu1.is_beaten = False  # New round, clean the record.
            
            for menu2 in waiting_menus:
                if menu1 == menu2: continue
                
                
                    
                if menu2.mistake_points < menu1.mistake_points: # delete menu that is not healthy
                    menu1.is_beaten = True 
                    break 
                elif menu2.mistake_points > menu1.mistake_points: 
                    continue 
                else: # if mistake points are same , compare these for preference,price and  cooking time. 
                    # COMPARE CHECK RULES FOR FINDING THE BEST MENU
                    # IF THE MENU IS NOT WORSE THAN FROM THE OTHER ONE IN EVERY AREA
    
                    better_or_equal_pref = (menu2.preference_score >= menu1.preference_score)
                    better_or_equal_price = (menu2.price_score <= menu1.price_score)
                    better_or_equal_time = (menu2.time_score <= menu1.time_score)
    
                    
                    # IF THIS MENU IS BETTER THAN THE OTHER ONE AT LEAST IN ONE AREA
                    
                    strictly_better_pref = (menu2.preference_score > menu1.preference_score)
                    strictly_better_price = (menu2.price_score < menu1.price_score)
                    strictly_better_time = (menu2.time_score < menu1.time_score)
                    
                    if (better_or_equal_pref and better_or_equal_price and better_or_equal_time):
                        if (strictly_better_pref or strictly_better_price or strictly_better_time):
                            menu1.is_beaten = True
                            break 

       # END OF THE LOOP, IF THERE IS A MENU THAT IS NOT LOSER GIVE IT A GROUP NUMBER 
        any_group_assigned = False
        for menu in waiting_menus:
            if menu.is_beaten == False:
                menu.quality_group = group_number
                any_group_assigned = True # AT LEAST A MENU ASSIGNED
                
        #  Prevent infinite loop if no menu wins.
        if any_group_assigned == False:
            for menu in waiting_menus:
                menu.quality_group = group_number
            break
            
        group_number += 1



# NSGA-II CROWDING DISTANCE CALCULATOR


def calculate_crowding_distance(front_menus):
    # If there are only 1 or 2 menus in the group there is no need to crowding.
    if len(front_menus) <= 2:
        for menu in front_menus:
            menu.crowding_distance = 999999.0    # the max num 
        return

    # Reset crowding distance 
    for menu in front_menus:
        menu.crowding_distance = 0.0

    
    #  CROWDING CALCULATION FOR PREFERENCE
   
    front_menus.sort(key=lambda x: x.preference_score) # Sort by preference score
    
    front_menus[0].crowding_distance = 999999.0  # to take the worst  menu give it the max num 
    front_menus[-1].crowding_distance = 999999.0 # to take the best menu give it the max num 
    
    # find taste range that is the extract between the best and the worst menu for preference score

    taste_range = front_menus[-1].preference_score - front_menus[0].preference_score
    if taste_range == 0: taste_range = 0.0001  # if the extract is 0 , give it this for making calculation
    
    #  make for between in second menu and the menu that is before the  last menu  

    for i in range(1, len(front_menus) - 1):
        neighbor_gap = front_menus[i+1].preference_score - front_menus[i-1].preference_score # subtract between in left and right menu
        front_menus[i].crowding_distance += (neighbor_gap / taste_range)  # update crowding distance to this menu for preference 

    
    #  CROWDING CALCULATION FOR  PRICE SCORE
    
    front_menus.sort(key=lambda x: x.price_score) # Sort by price scor
    
    front_menus[0].crowding_distance = 999999.0    #to take the worst  menu give it the max num 
    front_menus[-1].crowding_distance = 999999.0    # to take the best menu give it the max num
    # find price range that is the extract between the best and the worst menu for price score

    price_range = front_menus[-1].price_score - front_menus[0].price_score
    if price_range == 0: price_range = 0.0001  # if the extract is 0 , give it this for making calculation
      
      #  make for between in second menu and the menu that is before the  last menu  

    for i in range(1, len(front_menus) - 1):
        neighbor_gap = front_menus[i+1].price_score - front_menus[i-1].price_score   # subtract between in left and right menu
        front_menus[i].crowding_distance += (neighbor_gap / price_range)        # update crowding distance to this menu for price 

   
    #  CROWDING CALCULATION FOR  COOK TIME
   
    front_menus.sort(key=lambda x: x.time_score) # Sort by time score
    
    front_menus[0].crowding_distance = 999999.0     #to take the worst  menu give it the max num 
    front_menus[-1].crowding_distance = 999999.0    # to take the best menu give it the max num
    
     # find time range that is the extract between the best and the worst menu for time score

    time_range = front_menus[-1].time_score - front_menus[0].time_score
    if time_range == 0: time_range = 0.0001    # if the extract is 0 , give it this for making calculation
    
     #  make for between in second menu and the menu that is before the  last menu 

    for i in range(1, len(front_menus) - 1):
        neighbor_gap = front_menus[i+1].time_score - front_menus[i-1].time_score    # subtract between in left and right menu
        front_menus[i].crowding_distance += (neighbor_gap / time_range)       # update crowding distance to this menu for time 


# BINARY TOURNAMENT SELECTION
def tournament_selection(population):
    # Pick two random menus from the population to compare
    menu1 = random.choice(population)
    menu2 = random.choice(population)
    
    #  The one with the smaller quality group wins
    if menu1.quality_group < menu2.quality_group:
        return menu1
    elif menu2.quality_group < menu1.quality_group:
        return menu2
    # Rule 2: If quality point is the same, the one with higher crowding distance wins
    else:
        # Use getattr because if the crowding distance is not still calculated the value will be zero just for compare parents   
        dist1 = getattr(menu1, 'crowding_distance', 0.0)
        dist2 = getattr(menu2, 'crowding_distance', 0.0)
        
        if dist1 > dist2:
            return menu1
        else:
            return menu2


#  MAIN ALGORITHM (NSGA-II)
def nsga2_algorithm(breakfast_ids, lunch_dinner_ids, user, user_foods, num_generations=100, population_size=100):
    evaluator = Evaluator(lambda_weight=1.0)
    score_record = [] # save the num of winner for each generation (the first value is the num of winner for first generation)
    
    current_menus = []
    for _ in range(population_size):
        new_menu = DietChromosome(breakfast_ids, lunch_dinner_ids, randomize=True) # creat new menu with randomize 
        current_menus.append(new_menu)  # add this new menu
        
    for generation in range(num_generations):
        new_children_menus = []
        while len(new_children_menus) < population_size:
            # Apply tournament selectıon for choosing parents
            mom = tournament_selection(current_menus)
            dad = tournament_selection(current_menus)
            
            child1, child2 = GeneticOperators.evolve(mom, dad, p_c=0.9)
            new_children_menus.append(child1)
            if len(new_children_menus) < population_size:
                new_children_menus.append(child2)
                
        combined_menus = current_menus + new_children_menus   # connect old menus and new menus 
        
        for menu in combined_menus:
            preference_val, price_val, time_val, mistake_val = calculate_menu_scores(menu, user, user_foods, evaluator) # calculate all scores for all menus
            menu.preference_score = preference_val
            menu.price_score = price_val
            menu.time_score = time_val
            menu.mistake_points = mistake_val

        #  SORTING 
        assign_quality_groups(combined_menus)
        
        #  APPLY CROWDING DISTANCE 
        
        #  Find the maximum quality group number in the combined menus
        max_group_num = 0
        for menu in combined_menus:
            if menu.quality_group > max_group_num:
                max_group_num = menu.quality_group   # update the max_group_num for finding the total num of group in combined menus 
        
        #  Group menus by their quality group and calculate crowding distance
        current_group_num = 1
        while current_group_num <= max_group_num:   # visit all group by orderly
            current_front = [] # Empty array for this specific group
            
            # Visit all menus, if they belong to the current group, put them in the array
            for menu in combined_menus:
                if menu.quality_group == current_group_num:
                    current_front.append(menu)
            
            # Calculate crowding distance only for the menus in same group
            if len(current_front) > 0:
                calculate_crowding_distance(current_front)
            
            # Move to the next group
            current_group_num += 1
            
        #  SORT ACCORDING TO 2 RULES
        # Rule 1: quality_group (smaller is better thats why we make order from smallest to largest)
        # Rule 2: crowding_distance (larger is better, so we use minus sign to make order from largest to smallest)
        combined_menus.sort(key=lambda x: (x.quality_group, -x.crowding_distance)) 
       
        
        current_menus = combined_menus[:population_size]

        winner_num = 0  
        
       
        for menu in current_menus:
            # find the number of   menu in the best group for each generation 
            if menu.quality_group == 1:
                winner_num += 1  

        score_record.append(winner_num) # SAVE THE BEST MENU FOR VISUALIZATION
        
    return current_menus[0], current_menus, score_record