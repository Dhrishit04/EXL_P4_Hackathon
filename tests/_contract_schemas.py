from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Level = Literal["H", "M", "L"]; RAG = Literal["green", "amber", "red"]
class Evidence(BaseModel):
    id: str
    kind: Literal["code","doc","metric","data"]
    path: str
    line_start: int
    line_end: int
    excerpt: str
    sha256: str = ""
class Facts(BaseModel):
    model_id: str
    language: Literal["SAS","R","Python"]
    files: list[dict]
    datasets_read: list[str] = []
    datasets_written: list[str] = []
    variables_created: list[str] = []
    variables_used: list[str] = []
    dead_variables: list[str] = []
    model_calls: list[dict] = []
    target: str | None = None
    parameters: dict[str, dict] = {}
    dependencies: list[str] = []
    evidence: list[Evidence] = []
class Feature(BaseModel):
    name: str
    transformation: str = ""
    evidence_id: str | None = None
class Drift(BaseModel):
    field: str
    doc_value: str
    code_value: str
    doc_evidence_id: str
    code_evidence_id: str
    verified: bool = False
class Finding(BaseModel):
    id: str
    model_id: str
    area: str
    severity: Literal["high","medium","low"]
    ss123_principle: Literal["P1","P2","P3","P4","P5"]
    description: str
    evidence_ids: list[str] = []
    recommendation: str = ""
    status: Literal["open","closed"] = "open"
class Approval(BaseModel):
    gate: Literal["discovery","documentation","redevelopment","validation","override"]
    decision: Literal["approve","reject"]
    reviewer: str
    comment: str = ""
    ts: datetime
    auto: bool = False
class InventoryRecord(BaseModel):
    model_id: str
    name: str
    version: str = "1.0"
    purpose: str = ""
    business_use: str = ""
    portfolio: str = ""
    model_type: Literal["PD","LGD","fraud","pricing","other"]
    methodology: str = ""
    platform_language: str
    source_files: list[dict] = []
    input_data: list[str] = []
    features: list[Feature] = []
    target_definition: str = ""
    outputs: list[str] = []
    upstream_models: list[str] = []
    downstream_models: list[str] = []
    owner_role: str = ""
    developer_role: str = ""
    validator_role: str = ""
    materiality: Level
    materiality_rationale: str = ""
    complexity: Level
    complexity_rationale: str = ""
    risk_tier: int
    ai_ml_flag: bool = False
    regulatory_use: str = ""
    documentation_status: Literal["current","outdated","missing"]
    doc_code_drifts: list[Drift] = []
    security_flags: list[Finding] = []
    last_validated: date | None = None
    next_validation_due: date | None = None
    monitoring_kpis: list[str] = []
    limitations: list[str] = []
    status: Literal["discovered","documented","redeveloped","validated","monitored","revalidation_required"] = "discovered"
    approvals: list[Approval] = []
class Claim(BaseModel):
    section: str
    text: str
    evidence_ids: list[str] = []
    status: Literal["supported","unsupported","contradicted"] = "unsupported"
    reason: str = ""
class Documentation(BaseModel):
    model_id: str
    claims: list[Claim]
    grounding_score: float
    drifts: list[Drift] = []
    generated_at: datetime
class ParityLevel(BaseModel):
    level: Literal["L1","L2","L3","L4","L5"]
    name: str
    passed: bool
    metric: str
    value: float
    tolerance: float
    details: dict = {}
class ParityCertificate(BaseModel):
    model_id: str
    overall: Literal["PASS","FAIL"]
    levels: list[ParityLevel]
    hashes: dict[str, str]
    versions: dict[str, str]
    mismatch_summary: dict = {}
    attempt: int
    run_id: str
    created_at: datetime
class CheckResult(BaseModel):
    test: str
    area: Literal["discrimination","calibration","stability","conceptual","benchmark","sensitivity","fairness","data_quality","implementation"]
    value: float | None
    threshold: str
    rag: RAG
    ss123_principle: str = "P4"
    details: dict = {}
class ValidationResults(BaseModel):
    model_id: str
    tests: list[CheckResult]
    tables: dict[str, list[dict]] = {}
    charts: dict[str, dict] = {}
class ValidationReport(BaseModel):
    model_id: str
    results: ValidationResults
    narrative: dict[str, str]
    findings: list[Finding]
    rating: Literal["Fit for use","Fit with conditions","Not fit"]
    claims: list[Claim] = []
    created_at: datetime
class MonitoringPoint(BaseModel):
    month: int
    score_psi: float
    csi: dict[str, float]
    gini: float
    observed_dr: float
    expected_dr: float
    jeffreys_failures: int
    breaches: list[str] = []
class MonitoringResult(BaseModel):
    model_id: str
    points: list[MonitoringPoint]
    trigger_month: int | None
    simulated: bool = True
