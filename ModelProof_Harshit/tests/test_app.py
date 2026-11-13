from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
AppTest = importlib.import_module("streamlit.testing.v1").AppTest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "artifacts_sample"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize(
    "script",
    [
        "app/Home.py",
        "app/pages/1_Inventory.py",
        "app/pages/2_Model_Detail.py",
        "app/pages/3_Review_Queue.py",
        "app/pages/4_Audit_Log.py",
        "app/pages/5_Business_Case.py",
    ],
)
def test_pages_render_without_exceptions(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    monkeypatch.setenv("MODELPROOF_ARTIFACTS", str(FIXTURES))
    import app._data

    importlib.reload(app._data)
    app_test = AppTest.from_file(str(ROOT / script), default_timeout=10).run()
    assert not app_test.exception, [exception.message for exception in app_test.exception]
    assert any("FIXTURE DATA" in item.value for item in app_test.error)


def test_artifact_resolution_prioritizes_secret_then_environment(tmp_path: Path) -> None:
    from app._data import resolve_artifacts

    secret_dir = tmp_path / "secret"
    environment_dir = tmp_path / "environment"
    for path in (secret_dir, environment_dir):
        (path / "inventory").mkdir(parents=True)
        (path / "inventory" / "inventory.json").write_text("[]", encoding="utf-8")

    selected, is_fixture = resolve_artifacts(str(secret_dir), str(environment_dir), root=tmp_path)
    assert selected == secret_dir
    assert not is_fixture

    selected, is_fixture = resolve_artifacts(None, str(environment_dir), root=tmp_path)
    assert selected == environment_dir
    assert not is_fixture


def test_artifact_resolution_falls_back_to_fixtures(tmp_path: Path) -> None:
    from app._data import resolve_artifacts

    fallback = tmp_path / "tests" / "fixtures" / "artifacts_sample"
    fallback.mkdir(parents=True)
    selected, is_fixture = resolve_artifacts("missing", None, root=tmp_path)
    assert selected == fallback
    assert is_fixture


def test_review_approval_calls_graph_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELPROOF_ARTIFACTS", str(FIXTURES))
    from modelproof import graph

    resumed: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(graph, "pending_gates", lambda: [{
        "thread_id": "FIXTURE-thread",
        "model_id": "CR-PD-002",
        "gate": "validation",
        "summary": "FIXTURE review request",
        "artifacts": [],
    }])
    monkeypatch.setattr(
        graph,
        "resume",
        lambda thread_id, decision, comment, reviewer: resumed.append(
            (thread_id, decision, comment, reviewer)
        ) or {},
    )
    app_test = AppTest.from_file(str(ROOT / "app/pages/3_Review_Queue.py"), default_timeout=10).run()
    app_test.text_input(key="reviewer-FIXTURE-thread").set_value("FIXTURE reviewer")
    app_test.text_area(key="comment-FIXTURE-thread").set_value("FIXTURE approval comment")
    app_test.button[0].click().run()

    assert resumed == [(
        "FIXTURE-thread",
        "approve",
        "FIXTURE approval comment",
        "FIXTURE reviewer",
    )]
