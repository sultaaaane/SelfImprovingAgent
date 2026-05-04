# 🧠 Self-Evolving Developer Agent

An autonomous multi-agent system that **writes, tests, and loads its own tools at runtime** — no restarts, no human approval.

Built with LangGraph + Ollama. Designed for software engineers.

## How It Works

```
User Query
    ↓
Planner Agent      → decomposes task, declares required tools
    ↓
Gap Detector       → compares required tools vs live registry
    ↓ (missing tools found)
Tool Writer Agent  → writes Python tool code with LLM
    ↓
Tool Tester Agent  → runs code in sandboxed subprocess
    ↓ (passes)
Tool Registry      → dynamically loads new tool into agent
    ↓
Worker Agent       → executes research/task with all tools
    ↓
Critic Agent       → scores output against plan checklist
    ↓ (score ≥ 7)
Synthesizer Agent  → formats and returns final answer
```

Every approved tool is **permanently saved** to `dynamic_tools/`. The agent gets smarter with every task.

## Setup

```bash
pip install -r requirements.txt
ollama pull qwen2.5-coder:7b   # or any model you prefer
cp .env.example .env           # set your MODEL name
python main.py
```

## Project Structure

```
self-evolving-agent/
├── main.py              # Entry point
├── agent.py             # LangGraph graph definition
├── registry.py          # Dynamic tool registry
├── sandbox.py           # Safe subprocess tool tester
├── nodes.py             # All agent node functions
├── prompts.py           # All system prompts
├── memory.py            # SQLite checkpointer
├── tools.py             # Base tools (search, read_page)
├── dynamic_tools/       # Auto-generated tools live here
├── logs/                # Per-session logs
└── tests/               # Tool unit tests
```

## Safety Model

- Generated code runs in **isolated subprocess** before loading
- Hard **15-second timeout** on all tool tests
- **Import whitelist** — only allowed packages can be used
- Max **3 retries** per tool before failing gracefully
- Tools only persist if they **pass sandbox testing**

## Example Session

```
You: "Audit the requests library for known CVEs and show me the latest version"

🔍 Planner: needs [search_cve, fetch_pypi_info, search_web]
⚠️  Gap: missing [search_cve, fetch_pypi_info]

🔧 Writing tool: search_cve...
✅ Tool test passed (found CVE data)
🔧 Writing tool: fetch_pypi_info...
✅ Tool test passed (fetched PyPI metadata)
📦 Registry updated: 2 new tools loaded

🤖 Worker researching...
🧐 Critic score: 8.5/10 → APPROVED
📄 Final report ready
```
