import json
import re
from pathlib import Path

from enterprise_ai_platform.workflow import rag_graph

EVALUATION_DIR = Path(__file__).parent
CASES_PATH = EVALUATION_DIR / "answer_cases.json"
REPORT_PATH = EVALUATION_DIR / "answer_report.json"


def evaluate_case(case: dict) -> dict:
    result = rag_graph.invoke(
        {
            "question": case["question"],
            "equipment_model": case["equipment_model"],
        }
    )

    hits = result["hits"]
    answer = result["answer"]

    # The application appends a source list. Check citations in the answer itself.
    answer_body = answer.split("\n\nRetrieved sources:\n", maxsplit=1)[0]
    citation_matches = re.findall(r"\[(\d+)\]", answer_body)
    citation_numbers = sorted({int(number) for number in citation_matches})
    invalid_citations = [number for number in citation_numbers if not 1 <= number <= len(hits)]
    cited_sections = [
        hits[number - 1].section_title for number in citation_numbers if 1 <= number <= len(hits)
    ]

    expected_sections = case["expected_sections"]
    retrieved_sections = [hit.section_title for hit in hits]

    return {
        "id": case["id"],
        "equipment_model": case["equipment_model"],
        "question": case["question"],
        "should_abstain": case["should_abstain"],
        "review_criteria": case["review_criteria"],
        "retrieved_sections": retrieved_sections,
        "citation_numbers": citation_numbers,
        "cited_sections": cited_sections,
        "invalid_citations": invalid_citations,
        "unparsed_citation_format": answer_body.count("[") > len(citation_matches),
        "expected_sections_retrieved": (
            None
            if case["should_abstain"]
            else all(section in retrieved_sections for section in expected_sections)
        ),
        "expected_sections_cited": (
            None
            if case["should_abstain"]
            else all(section in cited_sections for section in expected_sections)
        ),
        "answer": answer,
    }


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []

    for case in cases:
        print(f"Evaluating {case['id']}...")
        result = evaluate_case(case)
        results.append(result)

        REPORT_PATH.write_text(
            json.dumps({"cases": results}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        print(
            f"  citations={result['citation_numbers']}, "
            f"invalid={result['invalid_citations']}, "
            f"expected cited={result['expected_sections_cited']}"
        )

    print(f"\nSaved {len(results)} answers to {REPORT_PATH}")
    print("Review each answer against its review_criteria before claiming answer quality.")


if __name__ == "__main__":
    main()
