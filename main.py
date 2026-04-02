import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
import importlib.util
from datetime import datetime
from datetime import date

print("RUNNING FILE:", __file__)

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
MAX_CHARS = 3000

print("PROJECT_ROOT =", PROJECT_ROOT)
print("SRC_PATH =", SRC_PATH)

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

print("sys.path[0] =", sys.path[0])
print("find_spec(aav_agent) =", importlib.util.find_spec("aav_agent"))

digest_dir = PROJECT_ROOT / "data" / "processed" / "digests"
digest_dir.mkdir(parents=True, exist_ok=True)
        

from aav_agent.tools.gmail_ingest import GmailIngestor, extract_google_scholar_candidates
from aav_agent.tools.openalex_client import fetch_openalex_data
from aav_agent.llm.summarizer import summarize_paper
from aav_agent.llm.lit_review_summarizer import summarize_as_literature_review
from aav_agent.tools.gmail_sender import GmailSender

import json

def load_seen(path):
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()

def save_seen(path, seen):
    path.write_text(json.dumps(list(seen), indent=2))

def main():

    print("SRC_PATH:", SRC_PATH)
    print("Is SRC_PATH in sys.path?", str(SRC_PATH) in sys.path)
    print("sys.path[0]:", sys.path[0])

    print(SRC_PATH)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    print("Environment is configured correctly.")

    seen_path = PROJECT_ROOT / "data" / "processed" / "seen_papers.json"
    seen = load_seen(seen_path)
    

    credentials_path = PROJECT_ROOT / "data" / "raw" / "gmail_credentials.json"
    token_path = PROJECT_ROOT / "data" / "raw" / "gmail_token.json"

    ingestor = GmailIngestor(credentials_path, token_path)
    emails = ingestor.fetch_scholar_emails(max_results=2)

    for email in emails:
        candidates = extract_google_scholar_candidates(email)

        full_digest = f"Daily Research Digest\nGenerated on: {datetime.now()}\n\n"
        paper_records = []

        for paper in candidates:

            try:
                print(f"Processing paper: {paper.title}")

                if paper.link in seen:
                    continue

                seen.add(paper.link)

                print("\n--- PAPER ---")
                print("Title:", paper.title)
                print("Link:", paper.link)

                enriched = fetch_openalex_data(paper.title)

                abstract = enriched.get("abstract") if enriched else None

                if not abstract:
                    print("Using fallback (title-only summary)")
                    abstract = f"No abstract available. Title: {paper.title}"

                summary = summarize_paper(client, paper.title, abstract[:MAX_CHARS])

                print("\n--- SUMMARY ---")
                #print(summary)

                if summary:
                    full_digest += f"""
                    ============================================================
                    Title: {paper.title}
                    Link: {paper.link}

                    {summary}
                    """

                    paper_records.append({
                        "title": paper.title,
                        "link": paper.link,
                        "authors": enriched.get("authors", []) if enriched else [],
                        "year": enriched.get("year") if enriched else None,
                        "summary": summary,
                    })
                
            except Exception as e:
                print(f"Error processing paper '{paper.title}': {e}")
                print("Skipping to next paper.")

    literature_review = summarize_as_literature_review(client, paper_records)

    print("\n--- DAILY LITERATURE REVIEW ---\n")
    print(literature_review)

    full_digest += f"""

    ============================================================
    DAILY LITERATURE REVIEW
    ============================================================

    {literature_review}
    """

    digest_path = digest_dir / f"{date.today().isoformat()}_digest.txt"
    digest_path.write_text(full_digest, encoding="utf-8")

    print(f"Digest saved to: {digest_path}")

    sender = GmailSender(credentials_path, token_path)
    recipient_email = "dennis.joshy@gmail.com"
    subject = f"AAV Research Daily Digest - {date.today().isoformat()}"

    sender.send_email(
        to_email=recipient_email,
        subject=subject,
        body_text=full_digest,
    )

    print(f"Digest emailed to: {recipient_email}")

    save_seen(seen_path, seen)

if __name__ == "__main__":
    main()