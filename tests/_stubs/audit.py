"""Test-only in-memory stand-in for Varun's modelproof.audit."""
LOG: list[dict] = []


def append(event: str, payload: dict, model_id: str | None = None, actor: str = "system") -> str:
    LOG.append({"event": event, "payload": payload, "model_id": model_id, "actor": actor})
    return str(len(LOG))


def read() -> list[dict]:
    return LOG


def verify_chain() -> bool:
    return True
