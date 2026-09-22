import json
from collections import defaultdict
from pathlib import Path

from enterprise_ai_platform.rag.retrieval import search_manuals

EVALUATION_DIR = Path(__file__).parent
CASES_PATH = EVALUATION_DIR / "rag_cases.json"
REPORT_PATH = EVALUATION_DIR / "retrieval_report.json"


def evaluate_case(case: dict) -> dict:
    expected_sections = case.get("expected_sections", [case["expected_section"]])
    if not expected_sections or case["expected_section"] not in expected_sections:
        raise ValueError(f"Invalid expected sections for {case['id']}")

    hits = search_manuals(case["question"], case["equipment_model"], top=5)

    ranks = {
        section: next(
            (
                position
                for position, hit in enumerate(hits, start=1)
                if hit.section_title.casefold() == section.casefold()
                and hit.equipment_model == case["equipment_model"]
            ),
            None,
        )
        for section in expected_sections
    }

    first_rank = min(
        (rank for rank in ranks.values() if rank is not None),
        default=None,
    )
    recall_at_3 = sum(rank is not None and rank <= 3 for rank in ranks.values()) / len(ranks)
    recall_at_5 = sum(rank is not None and rank <= 5 for rank in ranks.values()) / len(ranks)

    return {
        "id": case["id"],
        "category": case["category"],
        "equipment_model": case["equipment_model"],
        "expected_ranks": ranks,
        "first_relevant_rank": first_rank,
        "recall_at_3": recall_at_3,
        "recall_at_5": recall_at_5,
        "correct_equipment": all(hit.equipment_model == case["equipment_model"] for hit in hits),
        "retrieved_sections": [hit.section_title for hit in hits],
    }


def summarize(rows: list[dict]) -> dict:
    count = len(rows)
    return {
        "cases": count,
        "hit_at_1": sum(row["first_relevant_rank"] == 1 for row in rows) / count,
        "hit_at_3": sum(
            row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 3
            for row in rows
        )
        / count,
        "mrr_at_5": sum(
            1 / row["first_relevant_rank"] if row["first_relevant_rank"] is not None else 0
            for row in rows
        )
        / count,
        "mean_recall_at_3": sum(row["recall_at_3"] for row in rows) / count,
        "mean_recall_at_5": sum(row["recall_at_5"] for row in rows) / count,
        "correct_equipment_rate": sum(row["correct_equipment"] for row in rows) / count,
    }


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not cases:
        raise ValueError("The evaluation dataset is empty.")

    results = [evaluate_case(case) for case in cases]
    groups: dict[str, list[dict]] = defaultdict(list)

    for result in results:
        groups[result["category"]].append(result)
        print(
            f"{result['id']}: ranks={result['expected_ranks']}, "
            f"recall@3={result['recall_at_3']:.0%}"
        )

    overall = summarize(results)
    by_category = {
        category: summarize(group_rows) for category, group_rows in sorted(groups.items())
    }

    report = {
        "top_k": 5,
        "overall": overall,
        "by_category": by_category,
        "cases": results,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nSummary")
    for category, metrics in [("overall", overall), *by_category.items()]:
        print(
            f"{category}: n={metrics['cases']}, "
            f"Hit@1={metrics['hit_at_1']:.0%}, "
            f"Hit@3={metrics['hit_at_3']:.0%}, "
            f"MRR@5={metrics['mrr_at_5']:.3f}, "
            f"Recall@3={metrics['mean_recall_at_3']:.0%}, "
            f"Recall@5={metrics['mean_recall_at_5']:.0%}"
        )

    print(f"\nFull report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
