from scystream.sdk.core import entrypoint
from scystream.sdk.env.settings import (
    DatabaseSettings,
    EnvSettings,
    InputSettings,
    OutputSettings,
    FileSettings,
)
from scystream.sdk.file_handling.s3_manager import S3Operations
from scystream.sdk.database_handling.database_manager import (
    PandasDatabaseOperations,
)
from author_network.core import build_author_index, coauthor_pairs
import bibtexparser


def load_bib_file(path: str):
    """Load and parse a .bib file."""
    with open(path) as bib_file:
        return bibtexparser.load(bib_file)


class AuthorNetwork(DatabaseSettings, OutputSettings):
    __identifier__ = "author_network"


class AuthorLocations(DatabaseSettings, InputSettings):
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
    db_in = PandasDatabaseOperations(settings.author_locations_input.DB_DSN)
    pg_input = db_in.read(table=settings.author_locations_input.DB_TABLE)

    author_index = build_author_index(pg_input)
    edges = coauthor_pairs(bib_db, author_index)

    network_out_db = PandasDatabaseOperations(
        settings.author_network_output.DB_DSN
    )
    network_out_db.write(
        table=settings.author_network_output.DB_TABLE, data=edges
    )
