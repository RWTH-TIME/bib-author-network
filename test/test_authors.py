import pandas as pd
import pytest
from collections import namedtuple

from author_network.core import (
    normalize_author_name,
    build_author_index,
    _extract_authors,
    coauthor_pairs,
)

# ----------------------------------------------------------------------
# normalize_author_name
# ----------------------------------------------------------------------


@pytest.mark.parametrize("inp,expected", [
    ("Doe, John", "doe john"),
    ("John Doe", "doe john"),
    ("DOE,   JOHN", "doe john"),
    ("  John   R.   Doe ", "doe john r."),
    ("Doe, J.", "doe j."),
    ("", ""),
    (None, ""),
])
def test_normalize_author_name(inp, expected):
    assert normalize_author_name(inp) == expected


# ----------------------------------------------------------------------
# build_author_index
# ----------------------------------------------------------------------

def test_build_author_index():
    df = pd.DataFrame({
        "author": ["Doe, John", "Smith, Alice"],
        "institution": ["Uni A", "Uni B"],
        "similarity": [0.9, 0.8],
        "lat": [10, 20],
        "lon": [30, 40],
        "raw_rest": ["meta1", "meta2"]
    })

    index = build_author_index(df)

    assert "doe john" in index
    assert "alice smith" in index

    assert index["doe john"]["institution"] == "Uni A"
    assert index["doe john"]["lat"] == 10
    assert index["alice smith"]["lon"] == 40


# ----------------------------------------------------------------------
# _extract_authors
# ----------------------------------------------------------------------

def test_extract_authors():
    field = "Doe, John and Smith, Alice and Bob Johnson"
    authors = _extract_authors(field)

    assert authors == [
        "doe john",
        "alice smith",
        "bob johnson"
    ]


def test_extract_authors_empty():
    assert _extract_authors("") == []
    assert _extract_authors(None) == []


# ----------------------------------------------------------------------
# coauthor_pairs
# ----------------------------------------------------------------------

def test_coauthor_pairs():
    # Fake small bib DB for testing
    Entry = dict
    FakeBibDB = namedtuple("FakeBibDB", ["entries"])

    bib = FakeBibDB(entries=[
        Entry(ID="paper1", author="Doe, John and Smith, Alice"),
        Entry(ID="paper2", author="Doe, John and Bob Johnson"),
    ])

    # Author index matching normalized names
    author_index = {
        "doe john":   {"lat": 10, "lon": 20},
        "alice smith": {"lat": 30, "lon": 40},
        "bob johnson": {"lat": 50, "lon": 60},
    }

    df = coauthor_pairs(bib, author_index)

    # Should create 2 pairs (1 per paper)
    assert len(df) == 2

    # Ensure correct IDs
    assert set(df["paper_id"]) == {"paper1", "paper2"}

    # Check one row
    row1 = df[df["paper_id"] == "paper1"].iloc[0]
    assert row1["author_1_id"] in ("doe john", "smith alice")
    assert row1["author_2_id"] in ("doe john", "alice smith")

    # Check coordinates
    assert set(df["author_1_lat"]) == {10, 10}
    assert set(df["author_2_lat"]) == {30, 50}
