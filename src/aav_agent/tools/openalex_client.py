import requests


def fetch_openalex_data(title: str) -> dict:
    url = "https://api.openalex.org/works"
    params = {
        "search": title,
        "per_page": 1
    }

    response = requests.get(url, params=params)
    data = response.json()

    if not data["results"]:
        return {}

    work = data["results"][0]

    return {
        "title": work.get("title"),
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "authors": [a["author"]["display_name"] for a in work.get("authorships", [])],
        "year": work.get("publication_year"),
        "openalex_id": work.get("id")
    }


def _reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words.sort()
    return " ".join(word for _, word in words)