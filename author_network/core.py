from itertools import combinations
import pandas as pd


def normalize_author_name(name: str) -> str:
    """
    Normalize personal names so that:
    - Commas are ignored
    - Order of components does not matter
    - Lowercase
    - Whitespace collapsed
    """
    if not name:
        return ""

    # Remove commas
    name = name.replace(",", " ")

    # Collapse multiple spaces
    parts = [p.strip() for p in name.split() if p.strip()]
    if not parts:
        return ""

    # Sort parts alphabetically (order becomes irrelevant)
    parts = sorted(parts, key=str.lower)

    return " ".join(parts).lower()


def build_author_index(df):
    """
    Convert an author-location table into a lookup dictionary.
    """
    index = {}

    for _, row in df.iterrows():
        name_raw = str(row.get("author", "")).strip()
        if not name_raw:
            continue

        name = normalize_author_name(name_raw)

        index[name] = {
            "institution": row.get("institution"),
            "similarity": float(row["similarity"]) if "similarity"
            in df.columns else None,
            "lat": float(row["lat"]) if "lat" in df.columns else None,
            "lon": float(row["lon"]) if "lon" in df.columns else None,
            "raw_rest": row.get("raw_rest"),
        }

    return index


def _extract_authors(author_field: str):
    if not author_field:
        return []

    return [
        normalize_author_name(a)
        for a in author_field.replace("\n", " ").split(" and ")
        if a.strip()
    ]


def coauthor_pairs(bib_db, author_index):
    """
    Build an edge list of co-authorship relationships.
    """
    rows = []

    for entry in bib_db.entries:
        bib_id = entry.get("ID")
        authors = _extract_authors(entry.get("author", ""))

        for a1, a2 in combinations(authors, 2):
            info1 = author_index.get(a1, {})
            info2 = author_index.get(a2, {})

            rows.append({
                "paper_id": bib_id,

                "author_1_id": a1,
                "author_1_lat": info1.get("lat"),
                "author_1_lon": info1.get("lon"),

                "author_2_id": a2,
                "author_2_lat": info2.get("lat"),
                "author_2_lon": info2.get("lon"),
            })

    return pd.DataFrame(rows)
