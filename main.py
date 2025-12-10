from scystream.sdk.core import entrypoint
from scystream.sdk.env.settings import (
    PostgresSettings,
    EnvSettings,
    InputSettings,
    OutputSettings,
    FileSettings
)
from scystream.sdk.file_handling.s3_manager import S3Operations
from sqlalchemy import create_engine
from author_network.core import build_author_index, coauthor_pairs
import pandas as pd
import bibtexparser


def _make_engine(settings: PostgresSettings):
    return create_engine(
        f"postgresql+psycopg2://{settings.PG_USER}:{settings.PG_PASS}"
        f"@{settings.PG_HOST}:{int(settings.PG_PORT)}/"
    )


def read_table_from_postgres(settings: PostgresSettings) -> pd.DataFrame:
    engine = _make_engine(settings)
    query = f"SELECT * FROM {settings.DB_TABLE};"
    return pd.read_sql(query, engine)


def write_df_to_postgres(df: pd.DataFrame, settings: PostgresSettings):
    engine = _make_engine(settings)
    df.to_sql(settings.DB_TABLE, engine, if_exists="replace", index=False)


def load_bib_file(path: str):
    """Load and parse a .bib file."""
    with open(path) as bib_file:
        return bibtexparser.load(bib_file)


class AuthorNetwork(PostgresSettings, OutputSettings):
    __identifier__ = "author_network"


class AuthorLocations(PostgresSettings, InputSettings):
    __identifier__ = "author_locations"


class BIBInput(FileSettings, InputSettings):
    __identifier__ = "bib_file"
    FILE_EXT: str = "bib"


class BibAuthorNetwork(EnvSettings):
    BIB_DOWNLOAD_PATH: str = "/tmp/input.bib"

    bib_input: BIBInput
    author_locations_input: AuthorLocations
    author_network_output: AuthorNetwork


@entrypoint(BibAuthorNetwork)
def create_author_network_graph(settings):
    S3Operations.download(settings.bib_input, settings.BIB_DOWNLOAD_PATH)

    with open(settings.BIB_DOWNLOAD_PATH) as bibtex_file:
        bib_db = bibtexparser.load(bibtex_file)

    # Read Table
    pg_input = read_table_from_postgres(settings.author_locations_input)

    author_index = build_author_index(pg_input)
    edges = coauthor_pairs(bib_db, author_index)

    write_df_to_postgres(edges, settings.author_network_output)
