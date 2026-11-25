from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.nodes import ReasoningState, WorkflowNodes


def build_reasoning_graph(nodes: WorkflowNodes):
    graph = StateGraph(ReasoningState)
    graph.add_node("retrieve_and_reason", nodes.retrieve_and_reason)
    graph.add_node("generate_report", nodes.generate_report)
    graph.set_entry_point("retrieve_and_reason")
    graph.add_edge("retrieve_and_reason", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()
