"""
main.py — CLI entry point with rich terminal output.
"""

import logging
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

load_dotenv()
logging.basicConfig(level=logging.WARNING)  # suppress noisy logs in UI

console = Console()


def get_session() -> str:
    console.print(
        Panel(
            "[bold cyan]Self-Evolving Developer Agent[/bold cyan]\n"
            "[dim]Writes its own tools. Gets smarter every session.[/dim]",
            border_style="cyan",
        )
    )
    session = console.input(
        "\n[bold]Session name[/bold] (Enter for 'default'): "
    ).strip()
    return session or "default"


def print_node_event(node_name: str, output: dict):
    if node_name == "router":
        decision = output.get("route", "?")
        icon = "🔁" if decision == "recall" else "🔍"
        console.print(f"{icon}  Router → [bold]{decision}[/bold]")

    elif node_name == "planner":
        plan = output.get("plan", {})
        missing = output.get("missing_tools", [])
        reqs = plan.get("requirements", [])
        console.print(f"\n📋 [bold]Plan ready[/bold] — {len(reqs)} requirements")
        if missing:
            console.print(f"⚠️  Missing tools: [yellow]{', '.join(missing)}[/yellow]")
        else:
            console.print("✅ All required tools already in registry")

    elif node_name == "tool_writer":
        console.print("🔧 [bold]Tool Writer[/bold] generating code...")

    elif node_name == "tool_tester":
        passed = output.get("tool_test_passed", False)
        error = output.get("tool_test_error", "")
        remaining = output.get("missing_tools", [])
        if passed:
            console.print(
                f"✅ [green]Tool test passed[/green] — {len(remaining)} tools remaining"
            )
        else:
            console.print(f"❌ [red]Tool test failed[/red]: {error[:120]}")

    elif node_name == "worker":
        msgs = output.get("messages", [])
        if msgs:
            last = msgs[-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                for tc in last.tool_calls:
                    console.print(f"🛠  Using tool: [cyan]{tc['name']}[/cyan]")

    elif node_name == "tools":
        msgs = output.get("messages", [])
        for msg in msgs:
            if hasattr(msg, "name"):
                preview = str(msg.content)[:150].replace("\n", " ")
                console.print(f"   [dim]↳ {msg.name}: {preview}...[/dim]")

    elif node_name == "critic":
        critique = output.get("critique", {})
        score = critique.get("overall", 0)
        passed = output.get("approved", False)
        iteration = output.get("iteration", 1)
        color = "green" if passed else "yellow"
        icon = "✅" if passed else "🔄"
        console.print(
            f"{icon} [bold]Critic[/bold] iter {iteration}: "
            f"score=[{color}]{score:.1f}/10[/{color}] "
            f"{'APPROVED' if passed else 'NEEDS REVISION'}"
        )
        if not passed:
            for failure in critique.get("failures", [])[:3]:
                console.print(f"   [red]✗[/red] {failure}")

    elif node_name == "synthesizer":
        console.print("✍️  [bold]Synthesizer[/bold] formatting final report...")

    elif node_name == "fail":
        console.print(
            "⚠️  [yellow]Max attempts reached — returning best draft[/yellow]"
        )

    elif node_name == "recall":
        console.print("💾 [bold]Recall[/bold] — answering from memory")


def main():
    from agent import build_agent

    agent = build_agent()
    thread_id = get_session()
    config = {"configurable": {"thread_id": thread_id}}

    console.print(
        f"\n[dim]Session: {thread_id} | Model: {os.getenv('MODEL', 'qwen2.5-coder:7b')}[/dim]"
    )
    console.print(Rule(style="dim"))

    while True:
        try:
            query = console.input("\n[bold green]You:[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        if query.lower() == "/tools":
            from registry import registry

            console.print(
                Panel(
                    registry.describe(), title="Live Tool Registry", border_style="cyan"
                )
            )
            continue

        console.print(Rule(style="dim"))

        final_output = ""

        for event in agent.stream(
            {"messages": [HumanMessage(content=query)]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, output in event.items():
                print_node_event(node_name, output)
                if "final_output" in output and output["final_output"]:
                    final_output = output["final_output"]

        if final_output:
            console.print(Rule(style="dim"))
            console.print("\n[bold]FINAL REPORT[/bold]")
            console.print(Markdown(final_output))

            report_path = f"report_{thread_id}.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(final_output)
            console.print(f"\n[green]Report saved to {report_path}[/green]")

        console.print(Rule(style="dim"))


if __name__ == "__main__":
    main()
