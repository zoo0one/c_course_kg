from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, LiteralString, cast

from dotenv import load_dotenv
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing env var: {key}. Check {PROJECT_ROOT / '.env'}")
    return val


NEO4J_URI = _require_env("NEO4J_URI")
NEO4J_USER = _require_env("NEO4J_USER")
NEO4J_PASSWORD = _require_env("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self) -> None:
        self._driver.close()

    def run(self, query: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
        records, _, _ = self._driver.execute_query(
            cast(LiteralString, query),
            params or {},
            database_=NEO4J_DATABASE,
        )
        return [dict(r) for r in records]


neo4j_client = Neo4jClient()
