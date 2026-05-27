from typing import List, Tuple, Dict, Any

class DietDecoder:
    """Converts genes (IDs) in a chromosome into a real menu according to rules.
    
    Takes permutation sequences (breakfast and lunch/dinner) and assigns 
    foods to meals while satisfying constraints (vegetarianism, daily limits, 
    breakfast targets).
    """
    
    BREAKFAST_SPLIT = 0.35  # Estimated share of breakfast in daily calories
    TOLERANCE_UPPER = 1.15  # Upper limit tolerance
    TOLERANCE_LOWER = 0.90  # Lower target tolerance
    
    @classmethod
    def decode(cls, chromosome, user, foods_dict: Dict[int, Any]) -> Tuple[List[int], List[int], Dict[str, float]]:
        """Decodes the chromosome and creates a menu split into meals."""
        breakfast_menu = []
        lunch_dinner_menu = []
        
        # Dictionary to keep track of current nutrient value totals
        totals = {n: 0.0 for n in user.dri_limits.keys()}
        
        # --- LIMIT CALCULATIONS ---
        # Minimum targets to reach for breakfast (only for Energy and Protein)
        targets_b = {n: user.dri_limits[n][0] * cls.BREAKFAST_SPLIT * cls.TOLERANCE_LOWER 
                     for n in ['Energy', 'Protein'] if n in user.dri_limits}
        
        # Special upper limit for Energy and Protein during breakfast menu creation
        limits_b = {n: user.dri_limits[n][1] * cls.BREAKFAST_SPLIT * cls.TOLERANCE_UPPER 
                    for n in ['Energy', 'Protein'] if n in user.dri_limits}

        # Absolute daily upper limits that must not be exceeded (for all nutrients)
        limits_daily = {n: user.dri_limits[n][1] * cls.TOLERANCE_UPPER for n in totals}
        
        # Minimum daily targets to reach (for all nutrients)
        targets_daily = {n: user.dri_limits[n][0] * cls.TOLERANCE_LOWER for n in totals}

        # --- PHASE 1: BREAKFAST ---
        for f_id in chromosome.breakfast_part:
            food = foods_dict.get(f_id)
            if not food: continue
            
            # Vegetarian constraint
            if user.is_vegetarian and not food.is_vegetarian: 
                continue
            
            can_add = True
            
            # 1.a) Breakfast-specific upper limit check (prevent overfilling Energy and Protein)
            for n in ['Energy', 'Protein']:
                if n in food.nutrients and n in limits_b:
                    if totals.get(n, 0) + food.nutrients[n] > limits_b[n]:
                        can_add = False
                        break
            
            # 1.b) DAILY upper limit check (e.g., to not exceed daily sodium limit at breakfast)
            if can_add:
                for n, limit_val in limits_daily.items():
                    if n in food.nutrients:
                        if totals.get(n, 0) + food.nutrients[n] > limit_val:
                            can_add = False
                            break
            
            # If all limits are satisfied, add to menu and update totals
            if can_add:
                breakfast_menu.append(f_id)
                for n, val in food.nutrients.items():
                    if n in totals: 
                        totals[n] += val
                        
            # Stop breakfast selection if targets (Energy/Protein 35%) are reached
            if targets_b and all(totals.get(n, 0) >= targets_b[n] for n in targets_b): 
                break

        # --- PHASE 2: LUNCH + DINNER ---
        for f_id in chromosome.lunch_dinner_part:
            food = foods_dict.get(f_id)
            if not food: continue
            
            if user.is_vegetarian and not food.is_vegetarian: 
                continue
            
            can_add = True
            
            # Daily overall upper limit check
            for n, limit_val in limits_daily.items():
                if n in food.nutrients:
                    if totals.get(n, 0) + food.nutrients[n] > limit_val:
                        can_add = False
                        break
            
            if can_add:
                lunch_dinner_menu.append(f_id)
                for n, val in food.nutrients.items():
                    if n in totals: 
                        totals[n] += val
                        
            # Stop adding to menu if all daily targets are reached
            if targets_daily and all(totals.get(n, 0) >= targets_daily[n] for n in targets_daily): 
                break
                
        # Safety: Return at least some info in case of an empty menu
        if not breakfast_menu and not lunch_dinner_menu:
            # Menu could not be created — all nutrients are zero
            pass  # Totals are already zero, penalty will be high
            
        return breakfast_menu, lunch_dinner_menu, totals
