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
        self.fronts_F = []

    def notify(self, algorithm):
        self.generations.append(int(algorithm.n_gen))
        opt = getattr(algorithm, "opt", None)
        self.front_sizes.append(int(len(opt)) if opt is not None else 0)
        if opt is not None:
            self.fronts_F.append(opt.get("F").copy())
        else:
            self.fronts_F.append(np.empty((0, 3)))


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
    fieldnames = ["algorithm", "user_id", "diversity_mode", "generation", "pareto_front_size", "hypervolume"]
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

    gen_fronts = list(zip(callback.generations, callback.front_sizes, callback.fronts_F))
    return solution_rows, gen_fronts


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
    gen_fronts = []

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

        front_menus = [menu for menu in current if menu.quality_group == 1]
        F_gen = np.array([[-m.preference_score + m.mistake_points, m.price_score + m.mistake_points, m.time_score + m.mistake_points] for m in front_menus])
        gen_fronts.append((generation, len(front_menus), F_gen))

    solution_rows = []
    for rank, chromosome in enumerate(current[:max_solutions], start=1):
        metrics = evaluate_chromosome(chromosome, user, user_foods, evaluator, use_diversity)
        solution_rows.append(make_solution_row("NSGA-II", user.user_id, mode_name(use_diversity), rank, metrics))

    return solution_rows, gen_fronts


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

    raw_results = []
    modes = [True, False] if include_without_diversity else [True]

    for user, user_foods in load_users_and_foods([1, 2]):
        for use_diversity in modes:
            mode = mode_name(use_diversity)
            print(f"Running SPEA2 for user {user.user_id} ({mode})")
            sol_rows, gen_fronts = run_spea2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions)
            raw_results.append({
                "user_id": user.user_id,
                "algorithm": "SPEA2",
                "diversity_mode": mode,
                "solution_rows": sol_rows,
                "gen_fronts": gen_fronts
            })

            print(f"Running NSGA-II for user {user.user_id} ({mode})")
            sol_rows, gen_fronts = run_nsga2_experiment(user, user_foods, use_diversity, pop_size, n_gen, max_solutions)
            raw_results.append({
                "user_id": user.user_id,
                "algorithm": "NSGA-II",
                "diversity_mode": mode,
                "solution_rows": sol_rows,
                "gen_fronts": gen_fronts
            })

    # Calculate one fixed global reference point across all runs.
    # The handout requires the same reference point for every algorithm.
    all_observed_F = []

    for run in raw_results:
        for _, _, F_gen in run["gen_fronts"]:
            if len(F_gen) > 0:
                all_observed_F.extend(F_gen.tolist())

        for row in run["solution_rows"]:
            all_observed_F.append([
                -row["preference"] + row["penalty"],
                row["cost"] + row["penalty"],
                row["time"] + row["penalty"],
            ])

    all_observed_F = np.array(all_observed_F)
    f_min = all_observed_F.min(axis=0)
    f_max = all_observed_F.max(axis=0)

    # Worst observed values plus 10% margin.
    global_ref_point = f_max + 0.1 * (f_max - f_min)
    print(f"Global Reference Point: {global_ref_point}")

    with open(RESULTS_DIR / "ref_points.json", "w") as f:
        json.dump({"global": global_ref_point.tolist()}, f)

    # Now we calculate Hypervolumes and prepare CSV rows
    final_solutions = []
    final_convergence = []
    hv_table_data = []

    from pymoo.indicators.hv import HV
    for run in raw_results:
        user_id = run["user_id"]
        alg = run["algorithm"]
        mode = run["diversity_mode"]
        ref = global_ref_point
        
        final_solutions.extend(run["solution_rows"])
        hv_indicator = HV(ref_point=ref)
        final_hv = 0.0

        for gen, size, F_gen in run["gen_fronts"]:
            if len(F_gen) > 0:
                hv_val = hv_indicator(F_gen)
            else:
                hv_val = 0.0
            
            final_convergence.append({
                "algorithm": alg,
                "user_id": user_id,
                "diversity_mode": mode,
                "generation": gen,
                "pareto_front_size": size,
                "hypervolume": round(hv_val, 6)
            })
            final_hv = hv_val

        hv_table_data.append({
            "User": f"User {user_id}",
            "Algorithm": alg,
            "Configuration": mode.replace("_", " ").title(),
            "Hypervolume (HV)": f"{final_hv:,.2f}",
            "Pareto Solutions Found": len(run["solution_rows"])
        })

    # Print the hypervolume table
    print("\n" + "="*70)
    print("         HYPERVOLUME EVALUATION TABLE")
    print("="*70)
    import pandas as pd
    hv_df = pd.DataFrame(hv_table_data)
    print(hv_df.to_string(index=False))
    print("="*70 + "\n")

    write_solution_rows(final_solutions)
    write_convergence_rows(final_convergence)
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
