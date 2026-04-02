import json
from openai import OpenAI


def build_reference_label(paper: dict) -> str:
    authors = paper.get("authors", [])
    year = paper.get("year") or "n.d."

    if not authors:
        author_text = "Unknown author"
    elif len(authors) == 1:
        author_text = authors[0]
    elif len(authors) == 2:
        author_text = f"{authors[0]} and {authors[1]}"
    else:
        author_text = f"{authors[0]} et al."

    return f"{author_text} ({year})"


def summarize_as_literature_review(client: OpenAI, paper_records: list[dict]) -> str:
    if not paper_records:
        return "No papers available for literature review."

    payload = []
    for paper in paper_records:
        payload.append({
            "citation_label": build_reference_label(paper),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year"),
            "link": paper.get("link", ""),
            "summary": paper.get("summary", ""),
        })

    papers_json = json.dumps(payload, ensure_ascii=False, indent=2)

    prompt = f"""
    Write a concise literature review in paragraph form based only on the papers below.

    Instructions:
    - Begin with a short framing paragraph introducing the main scientific topics.
    - Then synthesize the papers into 2-4 cohesive paragraphs.
    - Emphasize relationships across studies: shared themes, contrasts, methods, and implications.
    - Use inline citations in standard prose, for example "(Luo et al., 2026)".
    - Do not use bullet points.
    - End with a "References" section listing all cited papers with authors, year, title, and URL.
    - Do not invent any content beyond what is supported by the provided records.

    Papers:
    {papers_json}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content