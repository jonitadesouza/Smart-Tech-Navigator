# Smart Technology Navigator (STN)

**An AI agent that matches software solutions to business requirements — for buyers evaluating vendors, and for vendors proving fit.**

---

## Problem Statement

Every organization that buys enterprise software — ERP, CRM, HRMS, cloud platforms, dev tools, security software, or any other business-critical system — runs into the same expensive, unstructured process: a long list of business and technical requirements has to be manually checked against dozens of vendor spec sheets, sales decks, and product documentation pages.

This process is:

- **Slow** — a single evaluation can take a program or procurement team 2–3 weeks of manual cross-referencing.
- **Inconsistent** — different evaluators weigh requirements differently, and there's rarely a single, auditable scoring method.
- **Perishable** — vendor feature sets change constantly, so a comparison done last quarter may already be out of date.
- **Hard to defend** — when a vendor is chosen, there's often no clean, evidence-backed record of *why*, which becomes a problem in audits, renewals, or stakeholder pushback.

The same problem exists in reverse. When a vendor responds to an RFP, their sales and pre-sales teams manually rebuild the same kind of "fit" argument for every single deal — with no repeatable, evidence-based system for showing *how* their product maps to a specific client's stated requirements.

**In short: two sides of every enterprise software deal are solving the same matching problem manually, with no consistent, reusable, or defensible process.**

Smart Tech Navigator (STN) is built to solve this — as a general-purpose **software solution navigator**, not limited to any one category of software.

---

## Solution Overview

STN is an AI agent system, built on **Google's Agent Development Kit (ADK) 2.0 Workflow API**, that:

1. Takes raw, unstructured input — requirement documents, meeting notes, or RFP text — for *any* category of software solution.
2. Extracts and structures those requirements into a clean, schema-compliant, weighted format.
3. Researches candidate software solutions against those requirements using live web search.
4. Produces a ranked, weighted **scorecard** showing how well each option fits — with the reasoning behind each score.

The result: a defensible, repeatable fit assessment in minutes instead of weeks — usable by a buyer comparing multiple vendors, or by a vendor building the case for their own product against a specific client's requirements.

### Who it's for

| User | How they use STN |
|---|---|
| **Buyers / program managers / consultants** | Input your requirements once → get a structured, ranked scorecard comparing software options |
| **Vendors responding to RFPs** | Input the client's stated requirements → get an evidence-backed scorecard showing exactly how your product fits |

---

## Architecture

STN uses a deliberately **lean, single-agent** orchestration design (simplified down from an earlier multi-agent version) to keep latency and token cost low, while still cleanly separating responsibilities through **skills**.

```
                ┌───────────────────────────┐
 Raw input  →   │  Requirements Extractor    │  →  structured, weighted
 (docs,         │  skill                     │     requirements (JSON)
 notes, RFP)    └────────────┬──────────────┘
                             │
                             ▼
                ┌───────────────────────────┐
                │  Research loop             │  bounded by an explicit
                │  (web search: Serper)      │  call budget + stop
                │                            │  conditions
                └────────────┬──────────────┘
                             │
                             ▼
                ┌───────────────────────────┐
                │  Scorecard Builder skill   │  →  ranked, weighted
                │                            │     fit scorecard
                └───────────────────────────┘
```

*(A visual architecture diagram image should be added here — e.g. `docs/architecture.png` — for easier scanning on GitHub.)*

**Key design decisions:**

- **Single-agent, skills-based design** — rather than coordinating multiple agent processes, STN uses one orchestrated agent with two composable skills. This keeps the system fast and cheap to run repeatedly.
- **Bounded research loop** — the agent doesn't search indefinitely. Explicit call budgets and stop conditions ensure it gathers enough evidence to score confidently without runaway API usage or unpredictable cost.
- **Schema-compliant I/O throughout** — both skills enforce structured JSON input/output, so the pipeline stays reliable and machine-checkable end-to-end, rather than depending on free-text interpretation at every step.

---

## Skills

### 1. Requirements Extractor
Parses unstructured input (requirement docs, meeting notes, RFP text) into a structured, categorized, weighted requirement set — flagging must-haves vs. nice-to-haves.

### 2. Scorecard Builder
Takes the structured requirements and, using live web research, evaluates candidate software solutions against each one — producing a ranked, weighted scorecard with supporting rationale.

---

## Tech Stack

- **Google ADK 2.0** — Workflow API (graph-based orchestration: nodes, edges, `RequestInput`)
- **Antigravity IDE** — development environment
- **agents-cli** — used to scaffold the initial agent structure
- **Serper** — web search APIs for live vendor/solution research
- **Google Cloud Platform** — API infrastructure

---

## Setup Instructions

> ⚠️ Adjust file paths and commands below to match this repo's actual structure before publishing.

### Prerequisites
- Python 3.10+
- A Google Cloud project with billing enabled (free-tier quota is sufficient for testing)
- API keys for Serper or Tavily (web search)
- ADK 2.0 installed

### 1. Clone the repo
```bash
git clone https://github.com/<your-username>/smart-tech-navigator.git
cd smart-tech-navigator
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
Create a `.env` file in the project root (never commit this file):
```
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
SERPER_API_KEY=<your-serper-api-key>
TAVILY_API_KEY=<your-tavily-api-key>
```

### 4. Run the agent
```bash
python run_stn.py --input path/to/requirements.txt
```

### 5. Try the standalone demo
Open `stn_demo.html` in a browser to walk through a sample requirement set being extracted, researched, and scored end-to-end — no setup required.

### 6. Run the test suite
```bash
python -m pytest tests/
```
This runs the 10-case test suite validating the Requirements Extractor and Scorecard Builder across a range of requirement complexity and solution-matching scenarios.

---

## Security Notes

- No API keys or credentials are committed to this repository — all secrets are handled via environment variables (`.env`, excluded via `.gitignore`).
- Both skills enforce schema-validated JSON input/output to reduce the risk of malformed or injected data propagating through the scoring pipeline.
- The research loop is budget-bounded, both for cost control and to prevent unpredictable agent behavior.

---

## Project Structure

```
smart-tech-navigator/
├── run_stn.py                  # entry point
├── skills/
│   ├── requirements_extractor/
│   └── scorecard_builder/
├── stn_demo.html                # standalone demo
├── tests/                       # 10-case test suite
├── requirements.txt
└── README.md
```

*(Update this tree to reflect your actual folder layout.)*

---

## Roadmap

- Expand solution categories beyond initial testing set
- Add support for multi-format requirement input (PDF, DOCX, Slack threads)
- Optional hosted demo endpoint

---

## License

*(Add your chosen license here, e.g. MIT.)*
