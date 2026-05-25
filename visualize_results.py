import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


RESULTS_DIR = Path("results")
SOLUTIONS_CSV = RESULTS_DIR / "experiment_solutions.csv"
CONVERGENCE_CSV = RESULTS_DIR / "experiment_convergence.csv"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(row, key):
    return float(row[key])


def as_int(row, key):
    return int(float(row[key]))


def group_rows(rows, keys):
    grouped = {}
    for row in rows:
        key = tuple(row[item] for item in keys)
        grouped.setdefault(key, []).append(row)
    return grouped


def save_pareto_plots(solution_rows):
    for (user_id, algorithm, mode), rows in group_rows(
        solution_rows,
        ["user_id", "algorithm", "diversity_mode"],
    ).items():
        plt.figure(figsize=(8, 6))
        x = [as_float(row, "cost") for row in rows]
        y = [as_float(row, "preference") for row in rows]
        colors = [as_float(row, "diversity_score") for row in rows]
        scatter = plt.scatter(x, y, c=colors, cmap="viridis", edgecolors="black", linewidths=0.3)
        plt.colorbar(scatter, label="Distinct food groups")
        plt.xlabel("Cost")
        plt.ylabel("Preference")
        plt.title(f"Pareto Front - User {user_id} - {algorithm} - {mode}")
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / f"pareto_user{user_id}_{algorithm}_{mode}.png", dpi=160)
        plt.close()


def save_convergence_plots(convergence_rows):
    for (user_id, algorithm, mode), rows in group_rows(
        convergence_rows,
        ["user_id", "algorithm", "diversity_mode"],
    ).items():
        rows = sorted(rows, key=lambda item: as_int(item, "generation"))
        plt.figure(figsize=(8, 5))
        plt.plot(
            [as_int(row, "generation") for row in rows],
            [as_int(row, "pareto_front_size") for row in rows],
            marker="o",
            markersize=3,
        )
        plt.xlabel("Generation")
        plt.ylabel("Pareto front size")
        plt.title(f"Convergence - User {user_id} - {algorithm} - {mode}")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / f"convergence_user{user_id}_{algorithm}_{mode}.png", dpi=160)
        plt.close()


def save_diversity_bar_chart(solution_rows):
    grouped = group_rows(solution_rows, ["user_id", "algorithm", "diversity_mode"])
    labels = []
    values = []
    for key, rows in sorted(grouped.items()):
        user_id, algorithm, mode = key
        labels.append(f"U{user_id}\n{algorithm}\n{mode.replace('_', ' ')}")
        values.append(sum(as_float(row, "diversity_score") for row in rows) / max(len(rows), 1))

    plt.figure(figsize=(12, 6))
    plt.bar(labels, values, color="#4c78a8")
    plt.ylabel("Average distinct food groups")
    plt.title("Average Menu Diversity by Algorithm and User")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "diversity_bar_chart.png", dpi=160)
    plt.close()


def nutrient_rows_for_table(solution):
    totals = json.loads(solution["nutrient_totals"])
    dri = json.loads(solution["dri_limits"])
    important = [
        "Energy",
        "Protein",
        "Carbohydrate, by difference",
        "Fiber, total dietary",
        "Sodium, Na",
        "Total lipid (fat)",
    ]
    rows = []
    for nutrient in important:
        if nutrient in dri:
            total = float(totals.get(nutrient, 0.0))
            lower, upper = dri[nutrient]
            rows.append([nutrient, f"{total:.2f}", f"{float(lower):.2f}", f"{float(upper):.2f}"])
    return rows


def save_sample_menu_tables(solution_rows):
    grouped = group_rows(solution_rows, ["user_id", "algorithm", "diversity_mode"])
    for (user_id, algorithm, mode), rows in grouped.items():
        best = sorted(
            rows,
            key=lambda item: (
                -as_float(item, "preference"),
                as_float(item, "cost"),
                as_float(item, "penalty"),
            ),
        )[:3]

        fig, axes = plt.subplots(len(best), 1, figsize=(10, 3.2 * len(best)))
        if len(best) == 1:
            axes = [axes]

        for ax, row in zip(axes, best):
            ax.axis("off")
            menu_ids = json.loads(row["menu_ids"])
            title = (
                f"Rank {row['solution_rank']} | pref={as_float(row, 'preference'):.2f} "
                f"cost={as_float(row, 'cost'):.2f} diversity={row['diversity_score']} "
                f"foods={len(menu_ids)}"
            )
            ax.set_title(title, loc="left", fontsize=10)
            table = ax.table(
                cellText=nutrient_rows_for_table(row),
                colLabels=["Nutrient", "Menu total", "DRI low", "DRI high"],
                loc="center",
                cellLoc="left",
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.25)

        fig.suptitle(f"Sample Menu Nutrient Tables - User {user_id} - {algorithm} - {mode}", y=0.99)
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / f"sample_menu_user{user_id}_{algorithm}_{mode}.png", dpi=160)
        plt.close()


def main():
    if not SOLUTIONS_CSV.exists() or not CONVERGENCE_CSV.exists():
        raise FileNotFoundError("Run experiments.py first to create CSV files in results/.")

    RESULTS_DIR.mkdir(exist_ok=True)
    solution_rows = read_csv(SOLUTIONS_CSV)
    convergence_rows = read_csv(CONVERGENCE_CSV)

    save_pareto_plots(solution_rows)
    save_convergence_plots(convergence_rows)
    save_sample_menu_tables(solution_rows)
    save_diversity_bar_chart(solution_rows)
    print(f"Saved plots to {RESULTS_DIR.resolve()}")


if __name__ == "__main__":
    main()
