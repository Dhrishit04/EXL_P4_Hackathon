"""Test-only copy of the B6 schemas used by WP2 (Evidence, Facts, Finding, ParityLevel, ParityCertificate)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Level = Literal["H", "M", "L"]
RAG = Literal["green", "amber", "red"]


class Evidence(BaseModel):
    id: str
    kind: Literal["code", "doc", "metric", "data"]
    path: str
    line_start: int
    line_end: int
    excerpt: str
    sha256: str = ""


class Facts(BaseModel):
    model_id: str
    language: Literal["SAS", "R", "Python"]
    files: list[dict]  # {path, sha256, n_lines, kind: "code"|"doc"}
    datasets_read: list[str] = []
    datasets_written: list[str] = []
    variables_created: list[str] = []
    variables_used: list[str] = []
    dead_variables: list[str] = []
    model_calls: list[dict] = []  # {kind, text, evidence_id}
    target: str | None = None
    parameters: dict[str, dict] = {}  # name -> {value, evidence_id}
    dependencies: list[str] = []
    evidence: list[Evidence] = []


class Finding(BaseModel):
    id: str
    model_id: str
    area: str
    severity: Literal["high", "medium", "low"]
    ss123_principle: Literal["P1", "P2", "P3", "P4", "P5"]
    description: str
    evidence_ids: list[str] = []
    recommendation: str = ""
    status: Literal["open", "closed"] = "open"


class ParityLevel(BaseModel):
    level: Literal["L1", "L2", "L3", "L4", "L5"]
    name: str
    passed: bool
    metric: str
    value: float
    tolerance: float
    details: dict = {}


class ParityCertificate(BaseModel):
    model_id: str
    overall: Literal["PASS", "FAIL"]
    levels: list[ParityLevel]
    hashes: dict[str, str]
    versions: dict[str, str]
    mismatch_summary: dict = {}
    attempt: int
    run_id: str
    created_at: datetime
