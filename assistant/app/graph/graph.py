from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from . import nodes
from .state import AssistantState


def build_graph(db: Session):
    graph = StateGraph(AssistantState)

    graph.add_node("retrieve_summary", nodes.retrieve_summary)
    graph.add_node("retrieve_chunk", nodes.retrieve_chunk)
    graph.add_node("no_context_answer", nodes.no_context_answer)
    graph.add_node("build_context", nodes.make_build_context(db))
    graph.add_node("confidence_checker", nodes.confidence_checker)
    graph.add_node("query_rewriter", nodes.query_rewriter)
    graph.add_node("generate_answer", nodes.generate_answer_node)
    graph.add_node("extract_sources", nodes.extract_sources)

    graph.add_edge(START, "retrieve_summary")
    graph.add_edge("retrieve_summary", "retrieve_chunk")
    graph.add_conditional_edges(
        "retrieve_chunk",
        nodes.route_after_hits,
        {
            "build_context": "build_context",
            "query_rewriter": "query_rewriter",
            "no_context_answer": "no_context_answer",
        },
    )
    graph.add_edge("build_context", "confidence_checker")
    graph.add_conditional_edges(
        "confidence_checker",
        nodes.route_after_confidence,
        {
            "generate_answer": "generate_answer",
            "query_rewriter": "query_rewriter",
            "no_context_answer": "no_context_answer",
        },
    )
    graph.add_edge("query_rewriter", "retrieve_summary")
    graph.add_edge("generate_answer", "extract_sources")
    graph.add_edge("extract_sources", END)
    graph.add_edge("no_context_answer", END)

    return graph.compile()
