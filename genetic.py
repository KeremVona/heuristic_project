import random
from typing import List, Tuple

class DietChromosome:
    """Represents a candidate solution (chromosome) for the genetic algorithm.
    
    Uses a permutation-based representation. Holds separate orderings of 
    food IDs for Breakfast and Lunch/Dinner meals.
    """
    def __init__(self, breakfast_ids: List[int], lunch_dinner_ids: List[int], randomize: bool = True):
        # Copy lists to prevent reference errors
        self.breakfast_part = list(breakfast_ids)
        self.lunch_dinner_part = list(lunch_dinner_ids)
        
        if randomize:
            random.shuffle(self.breakfast_part)
            random.shuffle(self.lunch_dinner_part)

    def __repr__(self) -> str:
        return f"<DietChromosome (Breakfast Genes: {len(self.breakfast_part)}, Lunch/Dinner Genes: {len(self.lunch_dinner_part)})>"


class GeneticOperators:
    """Manages Crossover and Mutation operations for permutation-based chromosomes."""
    
    @staticmethod
    def ordered_crossover(p1_list: List[int], p2_list: List[int]) -> Tuple[List[int], List[int]]:
        """Ordered Crossover (OX) operator. Performs crossover without breaking permutation structure."""
        size = len(p1_list)
        if size < 2:
            return p1_list[:], p2_list[:]
            
        a, b = sorted(random.sample(range(size), 2))
        
        def fill_child(parent_main, parent_donor):
            child = [None] * size
            # 1. Copy the selected range from the main parent
            child[a:b] = parent_main[a:b]
            existing = set(parent_main[a:b])
            
            # 2. Fill in missing genes from the donor parent in order
            donor_part = parent_donor[b:] + parent_donor[:b]
            pos = b
            for item in donor_part:
                if item not in existing:
                    child[pos % size] = item
                    existing.add(item)
                    pos += 1
            return child
            
        return fill_child(p1_list, p2_list), fill_child(p2_list, p1_list)

    @staticmethod
    def swap_mutation(individual_list: List[int], p_m: float) -> List[int]:
        """Swap Mutation: Swaps two genes based on a given probability."""
        if len(individual_list) >= 2 and random.random() < p_m:
            idx1, idx2 = random.sample(range(len(individual_list)), 2)
            individual_list[idx1], individual_list[idx2] = individual_list[idx2], individual_list[idx1]
        return individual_list

    @classmethod
    def evolve(cls, parent1: DietChromosome, parent2: DietChromosome, p_c: float = 0.9) -> Tuple[DietChromosome, DietChromosome]:
        """Crosses two parents and applies mutation to produce two new child chromosomes."""
        # 1. Crossover Operation (Breakfast and other meals are crossed independently)
        if random.random() < p_c:
            b_c1, b_c2 = cls.ordered_crossover(parent1.breakfast_part, parent2.breakfast_part)
            l_c1, l_c2 = cls.ordered_crossover(parent1.lunch_dinner_part, parent2.lunch_dinner_part)
        else:
            b_c1, b_c2 = parent1.breakfast_part[:], parent2.breakfast_part[:]
            l_c1, l_c2 = parent1.lunch_dinner_part[:], parent2.lunch_dinner_part[:]
            
        # 2. Mutation Operation (Dynamic mutation probability for each part)
        pm_b = 1.0 / len(b_c1) if b_c1 else 0
        pm_l = 1.0 / len(l_c1) if l_c1 else 0
        
        b_c1 = cls.swap_mutation(b_c1, pm_b)
        b_c2 = cls.swap_mutation(b_c2, pm_b)
        l_c1 = cls.swap_mutation(l_c1, pm_l)
        l_c2 = cls.swap_mutation(l_c2, pm_l)
        
        # 3. Create New Chromosome Objects
        child1 = DietChromosome(b_c1, l_c1, randomize=False)
        child2 = DietChromosome(b_c2, l_c2, randomize=False)
        
        return child1, child2

    @staticmethod
    def binary_tournament(pop: list, fitness_key=None) -> object:
        """Binary Tournament Selection: Selects two random individuals, returns the better one.
        
        fitness_key: Function to be used for comparing individuals.
                     By default, quality_group and crowding_distance are used.
        """
        a, b = random.sample(range(len(pop)), 2)
        ind_a, ind_b = pop[a], pop[b]
        
        if fitness_key:
            return ind_a if fitness_key(ind_a) <= fitness_key(ind_b) else ind_b
        
        # Default: NSGA-II style comparison
        qa = getattr(ind_a, 'quality_group', float('inf'))
        qb = getattr(ind_b, 'quality_group', float('inf'))
        
        if qa != qb:
            return ind_a if qa < qb else ind_b
        
        da = getattr(ind_a, 'crowding_distance', 0.0)
        db = getattr(ind_b, 'crowding_distance', 0.0)
        return ind_a if da >= db else ind_b
