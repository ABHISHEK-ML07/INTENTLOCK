from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from app.models import IntentContract


class ContractNotFoundError(KeyError):
    pass


class ContractStore:
    """Small SQLite store for local prototype contracts."""

    def __init__(self, db_path: str | Path = "intentlock.db") -> None:
        self.db_path = str(db_path)
        self._lock = Lock()
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialise(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS contracts (
                    contract_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def save(self, contract: IntentContract) -> None:
        payload = contract.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO contracts(contract_id,status,payload,created_at) VALUES(?,?,?,?)",
                (contract.contract_id, contract.status.value, payload, contract.created_at.isoformat()),
            )

    def get(self, contract_id: str) -> IntentContract:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM contracts WHERE contract_id=?", (contract_id,)
            ).fetchone()
        if row is None:
            raise ContractNotFoundError(contract_id)
        return IntentContract.model_validate_json(row["payload"])


def canonical_contract_payload(contract: IntentContract) -> bytes:
    data: dict[str, Any] = contract.model_dump(
        mode="json", exclude={"contract_hash", "confirmed_at", "confirmed_by"}
    )
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
