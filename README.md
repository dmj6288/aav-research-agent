# AAV Research Agent

Automated pipeline to fetch, summarize, and synthesize AAV-related research papers.

## Features
- Daily Google Scholar ingestion
- LLM-based summarization
- Aggregated literature synthesis
- Email delivery

## Architecture
<img width="1536" height="1024" alt="ChatGPT Image Apr 2, 2026, 06_40_03 PM" src="https://github.com/user-attachments/assets/e8733f46-2b3f-4ee0-8e9f-50aeaac6e8a3" />


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
