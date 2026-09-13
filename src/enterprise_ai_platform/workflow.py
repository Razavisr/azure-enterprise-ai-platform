from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from enterprise_ai_platform.rag.generation import generate_grounded_answer
from enterprise_ai_platform.rag.retrieval import ManualHit, search_manuals


class RagState(TypedDict):
    question: str
    equipment_model: str
    hits: NotRequired[list[ManualHit]]
    answer: NotRequired[str]


def retrieve_manuals(state: RagState) -> dict[str, list[ManualHit]]:
    hits = search_manuals(state["question"], state["equipment_model"], top=5)
    return {"hits": hits}


def write_answer(state: RagState) -> dict[str, str]:
    hits = state.get("hits")
    if hits is None:
        raise RuntimeError("The retrieval step must run before answer generation.")

    return {"answer": generate_grounded_answer(state["question"], hits)}


builder = StateGraph(RagState)
builder.add_node("retrieve", retrieve_manuals)
builder.add_node("generate", write_answer)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)

rag_graph = builder.compile()
