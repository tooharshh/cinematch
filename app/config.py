"""Environment configuration for local and container operation."""
import os
from pathlib import Path


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "movies_data.duckdb")).expanduser().resolve()
