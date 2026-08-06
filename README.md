# Vacation Planner Agent

Multi-agent vacation planner built with LangGraph. A single orchestrator dispatches to
Flight, Hotel, Spots, and Weather sub-agents (each backed by a Python function tool over
local mock data) and produces a structured Markdown itinerary with an itemized budget
breakdown.

Tracked in Linear: MUN-14 / MUN-15.

## Status

Phase 1 (environment & data) in progress. No live APIs — all data is local mock data
sourced from Kaggle.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Kaggle credentials

Dataset downloads require a Kaggle API token at `~/.kaggle/kaggle.json`. See setup notes
in project history / ask for instructions.
