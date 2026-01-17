import os
import time
import pytest
import boto3
import psycopg2
import pandas as pd
from pathlib import Path
from botocore.exceptions import ClientError

from main import create_author_network_graph  # your entrypoint wrapper


# -----------------------------
# MinIO / Postgres test config
# -----------------------------

MINIO_USER = "minioadmin"
MINIO_PWD = "minioadmin"
BUCKET_NAME = "test"

POSTGRES_USER = "postgres"
POSTGRES_PWD = "postgres"


def ensure_bucket(s3, bucket):
    """Create bucket unless it exists."""
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            s3.create_bucket(Bucket=bucket)
        else:
            raise


# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def s3_minio():
    client = boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id=MINIO_USER,
        aws_secret_access_key=MINIO_PWD,
    )
    ensure_bucket(client, BUCKET_NAME)
    return client


@pytest.fixture(scope="session")
def postgres_conn():
    """Keep trying until postgres is ready."""
    for _ in range(30):
        try:
            conn = psycopg2.connect(
                host="127.0.0.1",
                port=5432,
                user=POSTGRES_USER,
                password=POSTGRES_PWD,
                database="postgres",
            )
            conn.autocommit = True
            yield conn
            conn.close()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Postgres did not start")


# -----------------------------
# END-TO-END ENTRYPOINT TEST
# -----------------------------


def test_author_network_entrypoint(s3_minio, postgres_conn):
    """
    End-to-end test of the author network generator:

    1. Upload input.bib to MinIO
    2. Upload input.csv to Postgres
    3. Set environment variables
    4. Invoke create_author_network_graph()
    5. Validate output edge table in Postgres
    """

    base = Path(__file__).parent / "files"
    bib_path = base / "savedrecs.bib"
    csv_path = base / "input.csv"

    # -----------------------------------
    # 1. Upload .bib file → MinIO bucket
    # -----------------------------------
    s3_minio.put_object(
        Bucket=BUCKET_NAME,
        Key="input.bib",
        Body=bib_path.read_bytes(),
    )

    # -----------------------------------
    # 2. Upload CSV → Postgres input table
    # -----------------------------------

    df_locations = pd.read_csv(csv_path)

    cur = postgres_conn.cursor()
    cur.execute("DROP TABLE IF EXISTS author_locations;")
    postgres_conn.commit()

    # Create table
    create_cols = ", ".join(
        f"{col} TEXT" for col in df_locations.columns
    )
    cur.execute(f"CREATE TABLE author_locations ({create_cols});")

    # Insert rows
    for _, row in df_locations.iterrows():
        values = ", ".join(
            f"'{str(row[c]).replace('\'', '')}'"
            for c in df_locations.columns
        )
        cur.execute(
            f"INSERT INTO author_locations VALUES ({values});"
        )
    postgres_conn.commit()

    # -----------------------------------
    # 3. Set environment variables
    # -----------------------------------

    env = {
        # Input bib file from MinIO
        "bib_file_S3_HOST": "http://127.0.0.1",
        "bib_file_S3_PORT": "9000",
        "bib_file_S3_ACCESS_KEY": MINIO_USER,
        "bib_file_S3_SECRET_KEY": MINIO_PWD,
        "bib_file_BUCKET_NAME": BUCKET_NAME,
        "bib_file_FILE_PATH": "",
        "bib_file_FILE_NAME": "input",
        "bib_file_FILE_EXT": "bib",

        # Input Postgres: author locations
        "author_locations_PG_HOST": "127.0.0.1",
        "author_locations_PG_PORT": "5432",
        "author_locations_PG_USER": POSTGRES_USER,
        "author_locations_PG_PASS": POSTGRES_PWD,
        "author_locations_DB_TABLE": "author_locations",

        # Output Postgres: edges
        "author_network_PG_HOST": "127.0.0.1",
        "author_network_PG_PORT": "5432",
        "author_network_PG_USER": POSTGRES_USER,
        "author_network_PG_PASS": POSTGRES_PWD,
        "author_network_DB_TABLE": "coauthor_edges",
    }

    for k, v in env.items():
        os.environ[k] = v

    # -----------------------------------
    # 4. Run entrypoint
    # -----------------------------------

    create_author_network_graph()

    # -----------------------------------
    # 5. Validate output in Postgres
    # -----------------------------------
    cur = postgres_conn.cursor()
    cur.execute("SELECT * FROM coauthor_edges ORDER BY paper_id;")

    rows = cur.fetchall()
    cols = [col.name for col in cur.description]

    df_out = pd.DataFrame(rows, columns=cols)

    # Basic checks
    assert not df_out.empty

    expected = {
        "paper_id",
        "author_1_id",
        "author_1_lat",
        "author_1_lon",
        "author_2_id",
        "author_2_lat",
        "author_2_lon",
    }
    assert expected.issubset(df_out.columns)

    # Must have at least one coauthor pair
    assert len(df_out) >= 1

    # Coordinates should be floats or NaN
    assert df_out["author_1_lat"].dtype == float
    assert df_out["author_1_lon"].dtype == float

    # Example: check a known author in input.bib
    assert (
        df_out["author_1_id"].str.contains("pompili", case=False).any()
        or df_out["author_2_id"].str.contains("pompili", case=False).any()
    )
    # Check at least one matching lat/lon is present
    assert df_out["author_1_lat"].notna().any(
    ) or df_out["author_2_lat"].notna().any()
