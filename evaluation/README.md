# Evaluation

This project uses synthetic equipment manuals and sensor data. These results demonstrate the evaluation method; they do not measure real-world equipment reliability or safety.

## Retrieval

`rag_cases.json` contains 24 questions covering straightforward requests, paraphrases, thresholds, equipment-specific limits, and questions requiring two manual sections. `evaluate_retrieval.py` searches the live Azure AI Search index and writes `retrieval_report.json`.

| Metric | Result |
| --- | ---: |
| Hit@1 | 75% |
| Hit@3 | 100% |
| MRR@5 | 0.868 |
| Mean Recall@3 | 98% |
| Mean Recall@5 | 100% |
| Results from the correct equipment manual | 100% |

Hit@3 means **at least one** relevant section appeared in the top three. It does not mean every relevant section appeared there. For the two questions requiring both vibration and temperature guidance, mean Recall@3 was 75%; both sections appeared within the top five used by the application.

## Generated answers

`answer_cases.json` contains eight answerable and four unanswerable questions. `evaluate_answers.py` saves retrieved sections, generated answers, and citation checks in `answer_report.json`.

In one manual review of the 12 saved answers, no violation of the case-specific review criteria was observed. All eight answerable cases retrieved and cited their expected sections. The four unanswerable cases stated that the requested information was not in the supplied excerpts instead of inventing a value.

Automated citation checks only verify that citation numbers refer to retrieved sections and that expected sections were cited. They do not prove that every claim is supported. Answer quality and appropriate abstention require human review.

## Limitations

The manuals, questions, and sensor data are synthetic. The evaluation set is small and self-authored; it is not an independent test set. Generated answers may vary between runs. These results do not establish performance on real maintenance documents or authorize real-world operational decisions.