# AAV Research Agent

Automated pipeline to fetch, summarize, and synthesize AAV-related research papers.

## Features
- Daily Google Scholar ingestion
- LLM-based summarization
- Aggregated literature synthesis
- Email delivery

## Architecture
[diagram or description]

## Setup

```bash
git clone ...
cd aav-research-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Create .env:
Add:
OPENAI_API_KEY=your_key_here
EMAIL_ADDRESS=...
EMAIL_PASSWORD=...
