"""
nodes.py — All LangGraph node functions for the self-evolving agent.
"""

import json
import logging
import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from prompts import (
    CRITIC_PROMPT,
    PLANNER_PROMPT,
    RECALL_PROMPT,
    ROUTER_PROMPT,
    SYNTHESIZER_PROMPT,
    TOOL_REWRITER_PROMPT,
    TOOL_WRITER_PROMPT,
    WORKER_PROMPT,
    WORKER_WITH_CRITIQUE_PROMPT,
)
from registry import registry
from sandbox import persist_tool, run_in_sandbox
from state import AgentState

logger = logging.getLogger(__name__)

MODEL = os.getenv("MODEL", "qwen2.5-coder:7b")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", 3))
MAX_TOOL_RETRIES = int(os.getenv("MAX_TOOL_RETRIES", 3))
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", 15))
MIN_CRITIC_SCORE = float(os.getenv("MIN_CRITIC_SCORE", 7.0))

# Two LLM instances: creative for writing, strict for critiquing
llm = ChatOllama(model=MODEL, temperature=0.3)
llm_strict = ChatOllama(model=MODEL, temperature=0.0)


# ── Router ────────────────────────────────────────────────────────────────────


def router_node(state: AgentState) -> AgentState:
    # If there's only 1 message (the current query), skip LLM — always research
    if len(state["messages"]) <= 1:
        logger.info("[router] → research (no history)")
        return {"route": "research"}

    messages = [SystemMessage(content=ROUTER_PROMPT)] + state["messages"]
    response = llm_strict.invoke(messages)
    decision = response.content.strip().lower()
    # Only recall if the model is explicitly confident — default to research
    route = "recall" if decision.startswith("recall") else "research"
    logger.info(f"[router] → {route}")
    return {"route": route}


def route_decision(state: AgentState) -> Literal["recall", "planner"]:
    return "recall" if state.get("route") == "recall" else "planner"


# ── Recall ────────────────────────────────────────────────────────────────────


def recall_node(state: AgentState) -> AgentState:
    messages = [SystemMessage(content=RECALL_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response], "final_output": response.content}


# ── Planner ───────────────────────────────────────────────────────────────────


def planner_node(state: AgentState) -> AgentState:
    existing_tools = registry.describe()
    user_query = state["messages"][-1].content

    prompt = f"{PLANNER_PROMPT}\n\nExisting tools in registry:\n{existing_tools}"
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_query),
    ]

    response = llm_strict.invoke(messages)

    try:
        raw = response.content.strip()
        # Strip markdown fences if model wraps in them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        plan = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[planner] Could not parse JSON, using fallback plan")
        plan = {
            "requirements": ["Provide a thorough answer to the query"],
            "required_tools": [],
        }

    required = plan.get("required_tools", [])
    # Filter out tools that already exist
    missing = [t for t in required if not registry.has_tool(t)]

    logger.info(
        f"[planner] requirements={len(plan['requirements'])}, missing_tools={missing}"
    )
    return {
        "plan": plan,
        "required_tools": required,
        "missing_tools": missing,
        "iteration": 0,
        "tool_retries": 0,
        "approved": False,
    }


def gap_decision(state: AgentState) -> Literal["tool_writer", "worker"]:
    return "tool_writer" if state.get("missing_tools") else "worker"


# ── Tool Writer ───────────────────────────────────────────────────────────────


def tool_writer_node(state: AgentState) -> AgentState:
    tool_name = state["missing_tools"][0]
    existing = registry.describe()

    # If we have a previous error, use the rewriter prompt
    last_error = state.get("tool_test_error", "")
    last_code = state.get("generated_tool_code", "")

    if last_error and last_code:
        prompt = TOOL_REWRITER_PROMPT.format(error=last_error, original_code=last_code)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Fix the tool named: {tool_name}"),
        ]
    else:
        messages = [
            SystemMessage(content=TOOL_WRITER_PROMPT),
            HumanMessage(
                content=(
                    f"Write a tool named: {tool_name}\n\n"
                    f"Existing tools (do not duplicate):\n{existing}"
                )
            ),
        ]

    response = llm.invoke(messages)
    code = response.content.strip()

    # Strip markdown fences if present
    if "```python" in code:
        code = code.split("```python", 1)[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```", 1)[1].split("```")[0].strip()

    logger.info(f"[tool_writer] Generated code for '{tool_name}' ({len(code)} chars)")
    return {"generated_tool_code": code, "tool_test_error": ""}


def tool_tester_node(state: AgentState) -> AgentState:
    tool_name = state["missing_tools"][0]
    code = state["generated_tool_code"]
    retries = state.get("tool_retries", 0)

    # Validate imports before running anything
    ok, msg = registry.validate_imports(code)
    if not ok:
        logger.warning(f"[tool_tester] Import validation failed: {msg}")
        return {
            "tool_test_passed": False,
            "tool_test_error": msg,
            "tool_retries": retries + 1,
        }

    # Run in sandbox
    passed, output = run_in_sandbox(
        tool_code=code,
        tool_name=tool_name,
        test_input="python",
        timeout=TOOL_TIMEOUT,
    )

    if passed:
        # Persist to disk and load into live registry
        path = persist_tool(tool_name, code)
        ok, load_msg = registry.load_from_file(str(path))
        if ok:
            # Move to next missing tool (if any)
            remaining = state["missing_tools"][1:]
            logger.info(f"[tool_tester] ✅ {tool_name} loaded. Remaining: {remaining}")
            return {
                "tool_test_passed": True,
                "tool_test_error": "",
                "missing_tools": remaining,
                "tool_retries": 0,
            }
        else:
            return {
                "tool_test_passed": False,
                "tool_test_error": f"Load failed: {load_msg}",
                "tool_retries": retries + 1,
            }
    else:
        logger.warning(f"[tool_tester] ❌ {tool_name} failed: {output}")
        return {
            "tool_test_passed": False,
            "tool_test_error": output,
            "tool_retries": retries + 1,
        }


def tool_loop_decision(state: AgentState) -> Literal["tool_writer", "worker", "fail"]:
    retries = state.get("tool_retries", 0)
    missing = state.get("missing_tools", [])

    if retries >= MAX_TOOL_RETRIES:
        logger.error(
            f"[tool_loop] Max retries hit for tool '{missing[0] if missing else '?'}'"
        )
        return "fail"

    if not state.get("tool_test_passed", False):
        return "tool_writer"  # retry with error context

    if missing:
        return "tool_writer"  # write the next missing tool

    return "worker"  # all tools ready


# ── Worker ────────────────────────────────────────────────────────────────────


def worker_node(state: AgentState) -> AgentState:
    from langgraph.prebuilt import ToolNode

    tools = registry.get_all()
    llm_with_tools = llm.bind_tools(tools)

    critique = state.get("critique", {})
    iteration = state.get("iteration", 0)

    if critique and iteration > 0:
        instructions = critique.get("instructions", "")
        failures = "\n".join(f"- {f}" for f in critique.get("failures", []))
        system_content = WORKER_WITH_CRITIQUE_PROMPT.format(
            critique=f"Failures:\n{failures}\n\nInstructions: {instructions}"
        )
    else:
        system_content = WORKER_PROMPT

    messages = [SystemMessage(content=system_content)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response], "draft": response.content}


def tools_node_wrapper(state: AgentState) -> AgentState:
    """Thin wrapper so ToolNode uses the live registry tools."""
    from langgraph.prebuilt import ToolNode

    tools = registry.get_all()
    node = ToolNode(tools)
    return node.invoke(state)


# ── Critic ────────────────────────────────────────────────────────────────────


def critic_node(state: AgentState) -> AgentState:
    plan = state.get("plan", {})
    requirements = plan.get("requirements", ["Provide a complete answer"])
    draft = state.get("draft", "")
    iteration = state.get("iteration", 0)

    req_text = "\n".join(f"- {r}" for r in requirements)
    messages = [
        SystemMessage(content=CRITIC_PROMPT),
        HumanMessage(
            content=f"Requirements checklist:\n{req_text}\n\nAgent draft:\n{draft}"
        ),
    ]

    response = llm_strict.invoke(messages)

    try:
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        critique = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[critic] Could not parse JSON critique")
        critique = {
            "scores": {},
            "overall": 5.0,
            "passed": False,
            "failures": ["Could not evaluate — invalid critic response"],
            "instructions": "Rewrite the report more thoroughly",
        }

    approved = (
        critique.get("passed", False) and critique.get("overall", 0) >= MIN_CRITIC_SCORE
    )
    logger.info(
        f"[critic] score={critique.get('overall'):.1f} passed={approved} iter={iteration}"
    )

    return {
        "critique": critique,
        "approved": approved,
        "iteration": iteration + 1,
    }


def critic_decision(state: AgentState) -> Literal["synthesizer", "worker", "fail"]:
    if state.get("approved"):
        return "synthesizer"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        logger.warning("[critic] Max iterations reached — returning best draft")
        return "fail"
    return "worker"


# ── Synthesizer ───────────────────────────────────────────────────────────────


def synthesizer_node(state: AgentState) -> AgentState:
    draft = state.get("draft", "")
    messages = [
        SystemMessage(content=SYNTHESIZER_PROMPT),
        HumanMessage(content=draft),
    ]
    response = llm.invoke(messages)
    return {"messages": [response], "final_output": response.content}


# ── Fail / fallback ───────────────────────────────────────────────────────────


def fail_node(state: AgentState) -> AgentState:
    draft = state.get("draft", "")
    critique = state.get("critique", {})
    failures = critique.get("failures", [])

    msg = (
        "⚠️ The agent could not fully satisfy all requirements after maximum attempts.\n"
        "Here is the best draft produced:\n\n"
        + draft
        + (
            "\n\nUnresolved issues:\n" + "\n".join(f"- {f}" for f in failures)
            if failures
            else ""
        )
    )
    from langchain_core.messages import AIMessage

    return {"messages": [AIMessage(content=msg)], "final_output": msg}
