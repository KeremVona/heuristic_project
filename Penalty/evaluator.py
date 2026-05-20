from typing import Dict, List

class Evaluator:
    def __init__(self, lambda_weight: float = 1.0):
        # Start with lambda = 1.0 as suggested by the handout
        self.lambda_weight = lambda_weight

    def calculate_penalty(self, totals: Dict[str, float], dri_limits: Dict[str, List[float]]) -> float:
        """
        Calculates the penalty R for a given menu based on DRI violations.
        """
        total_R = 0.0

        for nutrient, (rll, rul) in dri_limits.items():
            # v_j is the total amount of this nutrient in the generated menu
            v_j = totals.get(nutrient, 0.0)

            # Denominator: RUL_j - RLL_j
            range_diff = rul - rll
            
            # Safety check to prevent division by zero
            if range_diff <= 0:
                continue

            # 1. Calculate violations
            # viol_low_j = max(0, (RLL_j - v_j) / (RUL_j - RLL_j))
            viol_low_j = max(0.0, (rll - v_j) / range_diff)

            # viol_high_j = max(0, (v_j - RUL_j) / (RUL_j - RLL_j))
            viol_high_j = max(0.0, (v_j - rul) / range_diff)

            # 2. Calculate proportional penalty for this nutrient
            # R = 0.7 * viol_low_j + 0.3 * viol_high_j
            nutrient_R = (0.7 * viol_low_j) + (0.3 * viol_high_j)

            # 3. Sum up the penalties for all 5 nutrients
            total_R += nutrient_R

        return total_R