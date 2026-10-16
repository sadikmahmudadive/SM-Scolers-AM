"""Local fallback configuration: where the Firebase credentials live."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalConfig:
    service_account_path: str
    project_id: str


def load_local_config(path: str | Path) -> LocalConfig:
    """Read a JSON file with `serviceAccountPath` and `projectId`
    (snake_case `service_account_path` / `project_id` also accepted)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    sa = raw.get("serviceAccountPath", raw.get("service_account_path"))
    pid = raw.get("projectId", raw.get("project_id"))
    if not sa or not pid:
        raise ValueError(f"{path}: serviceAccountPath and projectId are required")
    return LocalConfig(service_account_path=str(sa), project_id=str(pid))


def make_firestore_client(cfg: LocalConfig):
    """Initialise firebase_admin once and return its Firestore client."""
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(cfg.service_account_path),
            {"projectId": cfg.project_id},
        )
    return firestore.client()
