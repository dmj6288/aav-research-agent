from openai import OpenAI


def summarize_paper(client: OpenAI, title: str, abstract: str) -> str:
    if not abstract:
        return "No abstract available."

    prompt = f"""
Summarize concisely:

Title: {title}
Abstract: {abstract}

Output:
- Key idea (1 sentence)
- Method (1–2 sentences)
- Why it matters (1 sentence)
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content