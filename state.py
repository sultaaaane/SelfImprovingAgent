"""
state.py — Shared state schema for the self-evolving agent graph.
"""

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Conversation
    messages: Annotated[list, add_messages]

    # Routing
    route: str                    # "recall" | "research"

    # Planning
    plan: dict                    # {requirements: [...], required_tools: [...]}
    required_tools: list[str]     # tools the planner declared it needs
    missing_tools: list[str]      # tools not yet in registry

    # Tool generation
    generated_tool_code: str      # latest tool code written by tool_writer
    tool_test_passed: bool        # did the sandbox test pass?
    tool_test_error: str          # error message if test failed
    tool_retries: int             # how many times we've retried one tool

    # Worker / critic loop
    draft: str                    # current worker output
    critique: dict                # critic's last JSON evaluation
    iteration: int                # how many critic→worker loops we've done
    approved: bool                # critic approved the output?

    # Output
    final_output: str             # the cleaned synthesizer output
