"""
agent.py — LangGraph graph wiring for the self-evolving agent.
"""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition

from state import AgentState
from memory import get_checkpointer
from nodes import (
    router_node,
    route_decision,
    recall_node,
    planner_node,
    gap_decision,
    tool_writer_node,
    tool_tester_node,
    tool_loop_decision,
    worker_node,
    tools_node_wrapper,
    critic_node,
    critic_decision,
    synthesizer_node,
    fail_node,
)


def build_agent():
    graph = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    graph.add_node("router", router_node)
    graph.add_node("recall", recall_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tool_writer", tool_writer_node)
    graph.add_node("tool_tester", tool_tester_node)
    graph.add_node("worker", worker_node)
    graph.add_node("tools", tools_node_wrapper)
    graph.add_node("critic", critic_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("fail", fail_node)

    # ── Entry ──────────────────────────────────────────────────────────────────
    graph.set_entry_point("router")

    # router → recall or planner
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "recall": "recall",
            "planner": "planner",
        },
    )
    graph.add_edge("recall", END)

    # planner → tool_writer or worker (gap check)
    graph.add_conditional_edges(
        "planner",
        gap_decision,
        {
            "tool_writer": "tool_writer",
            "worker": "worker",
        },
    )

    # tool_writer → tool_tester (always)
    graph.add_edge("tool_writer", "tool_tester")

    # tool_tester → tool_writer (retry) | worker (done) | fail
    graph.add_conditional_edges(
        "tool_tester",
        tool_loop_decision,
        {
            "tool_writer": "tool_writer",
            "worker": "worker",
            "fail": "fail",
        },
    )

    # worker → tools (if tool calls) or critic (if final response)
    graph.add_conditional_edges(
        "worker", tools_condition, {"tools": "tools", "__end__": "critic"}
    )
    graph.add_edge("tools", "worker")

    # critic → synthesizer (approved) | worker (retry) | fail (max iters)
    graph.add_conditional_edges(
        "critic",
        critic_decision,
        {
            "synthesizer": "synthesizer",
            "worker": "worker",
            "fail": "fail",
        },
    )

    graph.add_edge("synthesizer", END)
    graph.add_edge("fail", END)

    # ── Compile ────────────────────────────────────────────────────────────────
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)
