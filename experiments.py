import argparse
import csv
import json
import os
import random
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
from dotenv import load_dotenv
from pymoo.algorithms.moo.spea2 import SPEA2
from pymoo.core.callback import Callback
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

from Algorithms.spea2_optimizer import DietCrossover, DietMutation, DietSampling
from Database.database_loader import DatabaseLoader
from Helpers.apply_user_preferences import apply_user_preferences
from Helpers.diversity import calculate_diversity_score, diversity_constraint_value, diversity_penalty
from Penalty.evaluator import Evaluator
from decoder import DietDecoder
from genetic import DietChromosome, GeneticOperators
from nsga2 import assign_quality_groups, calculate_crowding_distance, tournament_selection


RESULTS_DIR = Path("results")
SOLUTIONS_CSV = RESULTS_DIR / "experiment_solutions.csv"
CONVERGENCE_CSV = RESULTS_DIR / "experiment_convergence.csv"


class ExperimentalDietProblem(Problem):
    def __init__(self, user, foods_dict, evaluator, use_diversity=True, min_groups=4):
        super().__init__(n_var=1, n_obj=3, n_ieq_constr=1)
        self.user = user
        self.foods = foods_dict
        self.evaluator = evaluator
        self.use_diversity = use_diversity
        self.min_groups = min_groups

    def _evaluate(self, X, out, *args, **kwargs):
        preference = np.zeros(len(X))
        cost = np.zeros(len(X))
        time = np.zeros(len(X))
        diversity_g = np.zeros(len(X))

        for i in range(len(X)):
            chromosome = X[i, 0]
            breakfast, lunch_dinner, totals = DietDecoder.decode(chromosome, self.user, self.foods)
            menu_ids = breakfast + lunch_dinner
            penalty = self.evaluator.calculate_penalty(totals, self.user.dri_limits)

            preference_score = sum(self.foods[f_id].preference for f_id in menu_ids)
            cost_score = sum(self.foods[f_id].cost for f_id in menu_ids)
            time_score = sum(self.foods[f_id].prep_time + self.foods[f_id].cook_time for f_id in menu_ids)

            preference[i] = -preference_score + penalty
            cost[i] = cost_score + penalty
            time[i] = time_score + penalty
            diversity_g[i] = diversity_constraint_value(
                menu_ids,
                self.foods,
                use_diversity=self.use_diversity,
                min_groups=self.min_groups,
            )

        out["F"] = np.column_stack([preference, cost, time])
        out["G"] = diversity_g


class ParetoSizeCallback(Callback):
    def __init__(self):
        super().__init__()
        self.generations = []
        self.front_sizes = []

    def notify(self, algorithm):
        self.generations.append(int(algorithm.n_gen))
        opt = getattr(algorithm, "opt", None)
        self.front_sizes.append(int(len(opt)) if opt is not None else 0)


def split_food_ids(user_foods: Dict[int, object]) -> Tuple[List[int], List[int]]:
    all_food_ids = list(user_foods.keys())
    return all_food_ids[:94], all_food_ids[94:]


def evaluate_chromosome(chromosome, user, foods_dict, evaluator, use_diversity=True, min_groups=4) -> Dict[str, object]:
    breakfast, lunch_dinner, totals = DietDecoder.decode(chromosome, user, foods_dict)
    menu_ids = breakfast + lunch_dinner
    penalty = evaluator.calculate_penalty(totals, user.dri_limits)
    diversity_score = calculate_diversity_score(menu_ids, foods_dict)

    return {
        "breakfast_ids": breakfast,
        "lunch_dinner_ids": lunch_dinner,
        "menu_ids": menu_ids,
        "preference": sum(foods_dict[f_id].preference for f_id in menu_ids),
        "cost": sum(foods_dict[f_id].cost for f_id in menu_ids),
        "time": sum(foods_dict[f_id].prep_time + foods_dict[f_id].cook_time for f_id in menu_ids),
        "penalty": penalty + diversity_penalty(menu_ids, foods_dict, use_diversity, min_groups),
        "nutrition_penalty": penalty,
        "diversity_score": diversity_score,
        "nutrient_totals": totals,
        "dri_limits": user.dri_limits,
    }


def write_solution_rows(rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "algorithm",
        "user_id",
        "diversity_mode",
        "solution_rank",
        "preference",
        "cost",
        "time",
        "penalty",
        "nutrition_penalty",
        "diversity_score",
        "breakfast_ids",
        "lunch_dinner_ids",
        "menu_ids",
        "nutrient_totals",
        "dri_limits",
    ]
    with SOLUTIONS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_convergence_rows(rows: List[Dict[str, object]]) -> None:
    fieldnames = ["algorithm", "user_id", "diversity_mode", "generation", "pareto_front_size"]
    with CONVERGENCE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_solution_row(algorithm, user_id, diversity_mode, rank, metrics):
    row = {
        "algorithm": algorithm,
        "user_id": user_id,
        "diversity_mode": diversity_mode,
        "solution_rank": rank,
        "preference": round(metrics["preference"], 6),
        "cost": round(metrics["cost"], 6),
        "time": round(metrics["time"], 6),
        "penalty": round(metrics["penalty"], 6),
        "nutrition_penalty": round(metrics["nutrition_penalty"], 6),
        "diversity_score": metrics["diversity_score"],
        "breakfast_ids": json.dumps(metrics["breakfast_ids"]),
        "lunch_dinner_ids": json.dumps(metrics["lunch_dinner_ids"]),
        "menu_ids": json.dumps(metrics["menu_ids"]),
        "nutrient_totals": json.dumps(metrics["nutrient_totals"], ensure_ascii=False),
        "dri_limits": json.dumps(metrics["dri_limits"], ensure_ascii=False),
    }
    return row


def run_spea2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions):
    evaluator = Evaluator(lambda_weight=1.0)
    breakfast_ids, lunch_dinner_ids = split_food_ids(user_foods)
    problem = ExperimentalDietProblem(user, user_foods, evaluator, use_diversity=use_diversity)
    callback = ParetoSizeCallback()

    algorithm = SPEA2(
        pop_size=pop_size,
        sampling=DietSampling(breakfast_ids, lunch_dinner_ids),
        crossover=DietCrossover(prob=0.9),
        mutation=DietMutation(),
        eliminate_duplicates=False,
    )

    result = minimize(problem, algorithm, ("n_gen", n_gen), seed=42, verbose=False, callback=callback)
    chromosomes = []
    if result.X is not None:
        flat_x = np.atleast_1d(result.X).reshape(-1)
        chromosomes = [item for item in flat_x if item is not None]

    solution_rows = []
    for rank, chromosome in enumerate(chromosomes[:max_solutions], start=1):
        metrics = evaluate_chromosome(chromosome, user, user_foods, evaluator, use_diversity)
        solution_rows.append(make_solution_row("SPEA2", user.user_id, mode_name(use_diversity), rank, metrics))

    convergence_rows = [
        {
            "algorithm": "SPEA2",
            "user_id": user.user_id,
            "diversity_mode": mode_name(use_diversity),
            "generation": generation,
            "pareto_front_size": front_size,
        }
        for generation, front_size in zip(callback.generations, callback.front_sizes)
    ]
    return solution_rows, convergence_rows


def score_nsga2_population(population, user, user_foods, evaluator, use_diversity):
    for menu in population:
        metrics = evaluate_chromosome(menu, user, user_foods, evaluator, use_diversity)
        menu.preference_score = metrics["preference"]
        menu.price_score = metrics["cost"]
        menu.time_score = metrics["time"]
        menu.mistake_points = metrics["penalty"]
        menu.diversity_score = metrics["diversity_score"]


def rank_nsga2_population(population):
    assign_quality_groups(population)
    max_group = max((menu.quality_group for menu in population), default=0)
    for group in range(1, max_group + 1):
        front = [menu for menu in population if menu.quality_group == group]
        if front:
            calculate_crowding_distance(front)
    population.sort(key=lambda item: (item.quality_group, -item.crowding_distance))


def run_nsga2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions):
    evaluator = Evaluator(lambda_weight=1.0)
    breakfast_ids, lunch_dinner_ids = split_food_ids(user_foods)
    current = [DietChromosome(breakfast_ids, lunch_dinner_ids, randomize=True) for _ in range(pop_size)]
    convergence_rows = []

    score_nsga2_population(current, user, user_foods, evaluator, use_diversity)
    rank_nsga2_population(current)

    for generation in range(1, n_gen + 1):
        children = []
        while len(children) < pop_size:
            parent_1 = tournament_selection(current)
            parent_2 = tournament_selection(current)
            child_1, child_2 = GeneticOperators.evolve(parent_1, parent_2, p_c=0.9)
            children.append(child_1)
            if len(children) < pop_size:
                children.append(child_2)

        combined = current + children
        score_nsga2_population(combined, user, user_foods, evaluator, use_diversity)
        rank_nsga2_population(combined)
        current = combined[:pop_size]

        convergence_rows.append(
            {
                "algorithm": "NSGA-II",
                "user_id": user.user_id,
                "diversity_mode": mode_name(use_diversity),
                "generation": generation,
                "pareto_front_size": sum(1 for menu in current if menu.quality_group == 1),
            }
        )

    solution_rows = []
    for rank, chromosome in enumerate(current[:max_solutions], start=1):
        metrics = evaluate_chromosome(chromosome, user, user_foods, evaluator, use_diversity)
        solution_rows.append(make_solution_row("NSGA-II", user.user_id, mode_name(use_diversity), rank, metrics))

    return solution_rows, convergence_rows


def mode_name(use_diversity: bool) -> str:
    return "with_diversity" if use_diversity else "without_diversity"


def load_users_and_foods(user_ids: Iterable[int]):
    load_dotenv()
    db = DatabaseLoader()
    master_foods = db.load_foods()
    loaded = []
    for user_id in user_ids:
        user = db.load_user(user_id=user_id)
        loaded.append((user, apply_user_preferences(master_foods, user)))
    return loaded


def run_all(pop_size: int, n_gen: int, max_solutions: int, include_without_diversity: bool):
    RESULTS_DIR.mkdir(exist_ok=True)
    random.seed(42)
    np.random.seed(42)

    solution_rows = []
    convergence_rows = []
    modes = [True, False] if include_without_diversity else [True]

    for user, user_foods in load_users_and_foods([1, 2]):
        for use_diversity in modes:
            print(f"Running SPEA2 for user {user.user_id} ({mode_name(use_diversity)})")
            rows, conv = run_spea2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions)
            solution_rows.extend(rows)
            convergence_rows.extend(conv)

            print(f"Running NSGA-II for user {user.user_id} ({mode_name(use_diversity)})")
            rows, conv = run_nsga2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions)
            solution_rows.extend(rows)
            convergence_rows.extend(conv)

    write_solution_rows(solution_rows)
    write_convergence_rows(convergence_rows)
    print(f"Saved {SOLUTIONS_CSV}")
    print(f"Saved {CONVERGENCE_CSV}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run diet optimization experiments.")
    parser.add_argument("--pop-size", type=int, default=50)
    parser.add_argument("--n-gen", type=int, default=50)
    parser.add_argument("--max-solutions", type=int, default=50)
    parser.add_argument(
        "--with-only",
        action="store_true",
        help="Run only the diversity-enabled experiments.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_all(
        pop_size=args.pop_size,
        n_gen=args.n_gen,
        max_solutions=args.max_solutions,
        include_without_diversity=not args.with_only,
    )
