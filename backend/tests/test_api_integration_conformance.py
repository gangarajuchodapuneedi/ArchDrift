"""Integration tests for conformance mode via API endpoints.

These tests verify:
1. POST /analyze-repo accepts classifier_mode="conformance" even when env not set
2. GET /drifts returns latest analyzed drifts (not demo drifts)
3. Architecture drifts in conformance mode have classifier_mode_used and conformance fields populated
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.drift_store import set_latest_drifts


def _write_architecture_config(tmpdir: Path):
    """Create architecture config files in tmpdir/architecture."""
    config_dir = tmpdir / "architecture"
    config_dir.mkdir(parents=True, exist_ok=True)

    # module_map.json
    module_map = {
        "version": "1.0",
        "unmapped_module_id": "unmapped",
        "modules": [
            {"id": "ui", "roots": ["ui"]},
            {"id": "core", "roots": ["core"]},
        ],
    }
    (config_dir / "module_map.json").write_text(json.dumps(module_map), encoding="utf-8")

    # allowed_rules.json
    allowed_rules = {
        "version": "1.0",
        "deny_by_default": False,
        "allowed_edges": [],
    }
    (config_dir / "allowed_rules.json").write_text(json.dumps(allowed_rules), encoding="utf-8")

    # exceptions.json (none)
    exceptions = {"version": "1.0", "exceptions": []}
    (config_dir / "exceptions.json").write_text(json.dumps(exceptions), encoding="utf-8")

    return config_dir


def test_post_analyze_repo_with_conformance_mode_override(monkeypatch, tmp_path):
    """Test POST /analyze-repo with classifier_mode="conformance" works even when env not set."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    # Create a minimal test repo structure
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    (repo_dir / "ui").mkdir()
    (repo_dir / "ui" / "main.py").write_text("from core import helper\n")
    (repo_dir / "core").mkdir()
    (repo_dir / "core" / "helper.py").write_text("# Helper module\n")
    (repo_dir / ".git").mkdir()
    (repo_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    config_dir = _write_architecture_config(tmp_path)

    # Mock the analyze_repo_for_drifts to return test drifts
    from models.drift import Drift

    mock_drifts = [
        Drift(
            id="test-001",
            date="2024-01-01T10:00:00Z",
            type="negative",
            title="Test architecture drift",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["ui/main.py"],
            commit_hash="abc123def456",
            repo_url=str(repo_dir),
            driftType="architecture",
            classifier_mode_used="conformance",
            classification="negative",
            baseline_hash="test_baseline_hash",
            rules_hash="test_rules_hash",
            reason_codes=[],
        )
    ]

    with patch("api.routes.analyze_repo_for_drifts", return_value=mock_drifts):
        client = TestClient(app)
        response = client.post(
            "/analyze-repo",
            json={
                "repo_url": str(repo_dir),
                "max_commits": 10,
                "max_drifts": 5,
                "classifier_mode": "conformance",
            },
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        drifts = response.json()
        assert len(drifts) > 0, "Expected at least one drift"

        # Verify classifier_mode_used is set
        for drift in drifts:
            assert drift["classifier_mode_used"] == "conformance", (
                f"Expected classifier_mode_used='conformance', got {drift.get('classifier_mode_used')}"
            )

        # For architecture drifts, verify conformance fields
        arch_drifts = [d for d in drifts if d.get("driftType") == "architecture"]
        if len(arch_drifts) > 0:
            for drift in arch_drifts:
                assert drift.get("classifier_mode_used") == "conformance"
                # Classification should be set (even if "unknown" due to missing baseline)
                assert drift.get("classification") is not None, (
                    "Architecture drifts in conformance mode should have classification set"
                )
                # baseline_hash and rules_hash should be set OR reason_codes explain why not
                if drift.get("baseline_hash") is None and drift.get("rules_hash") is None:
                    assert len(drift.get("reason_codes", [])) > 0, (
                        "If baseline_hash and rules_hash are None, reason_codes must explain why"
                    )


def test_get_drifts_returns_latest_analyzed_drifts(monkeypatch):
    """Test GET /drifts returns latest analyzed drifts, not demo drifts."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    from models.drift import Drift

    # Set latest drifts
    latest_drifts = [
        Drift(
            id="latest-001",
            date="2024-02-01T10:00:00Z",
            type="negative",
            title="Latest analyzed drift",
            summary="Latest summary",
            functionality="Latest functionality",
            files_changed=["test.py"],
            commit_hash="latest123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",
            classifier_mode_used="conformance",
            classification="negative",
            baseline_hash="latest_baseline_hash",
            rules_hash="latest_rules_hash",
            reason_codes=[],
        )
    ]
    set_latest_drifts(latest_drifts)

    try:
        client = TestClient(app)
        response = client.get("/drifts")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "items" in data, "Response should have 'items' field"
        items = data["items"]

        # Should return latest drifts, not demo drifts
        assert len(items) > 0, "Expected at least one drift"
        # Check that we got the latest drift (not demo drift)
        drift_ids = [d["id"] for d in items]
        assert "latest-001" in drift_ids, "Should return latest analyzed drifts, not demo drifts"

        # Verify the latest drift has conformance fields
        latest_drift = next((d for d in items if d["id"] == "latest-001"), None)
        assert latest_drift is not None, "Latest drift should be in response"
        assert latest_drift["classifier_mode_used"] == "conformance"
        assert latest_drift["classification"] is not None
    finally:
        # Clean up: clear latest drifts by setting to None
        import services.drift_store
        services.drift_store._LATEST_DRIFTS = None


def test_post_analyze_repo_invalid_classifier_mode_returns_422():
    """Test POST /analyze-repo with invalid classifier_mode returns 422."""
    client = TestClient(app)
    response = client.post(
        "/analyze-repo",
        json={
            "repo_url": "https://github.com/test/repo",
            "max_commits": 10,
            "max_drifts": 5,
            "classifier_mode": "invalid_mode",
        },
    )

    assert response.status_code == 422, f"Expected 422 for invalid classifier_mode, got {response.status_code}"
    assert "Invalid classifier_mode" in response.json()["detail"]


def test_post_analyze_repo_conformance_architecture_drift_has_fields(monkeypatch, tmp_path):
    """Test that architecture drifts in conformance mode have all required conformance fields."""
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    from models.drift import Drift

    # Create a drift with all conformance fields populated
    mock_drifts = [
        Drift(
            id="arch-001",
            date="2024-01-01T10:00:00Z",
            type="negative",
            title="Architecture drift with conformance",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["ui/main.py"],
            commit_hash="arch123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",
            classifier_mode_used="conformance",
            classification="negative",
            edges_added_count=2,
            edges_removed_count=1,
            forbidden_edges_added_count=1,
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash="abc123def456",
            rules_hash="def456ghi789",
            reason_codes=[],
            evidence_preview=[],
        )
    ]

    with patch("api.routes.analyze_repo_for_drifts", return_value=mock_drifts):
        client = TestClient(app)
        response = client.post(
            "/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "max_commits": 10,
                "max_drifts": 5,
                "classifier_mode": "conformance",
            },
        )

        assert response.status_code == 200
        drifts = response.json()
        arch_drifts = [d for d in drifts if d.get("driftType") == "architecture"]

        assert len(arch_drifts) > 0, "Expected at least one architecture drift"

        for drift in arch_drifts:
            # Verify classifier_mode_used
            assert drift["classifier_mode_used"] == "conformance"

            # Verify classification is set
            assert drift["classification"] is not None
            assert drift["classification"] in ["positive", "negative", "needs_review", "unknown", "no_change"]

            # Verify baseline_hash and rules_hash are set (or reason_codes explain why not)
            if drift["baseline_hash"] is None and drift["rules_hash"] is None:
                assert len(drift.get("reason_codes", [])) > 0, (
                    "If baseline_hash and rules_hash are None, reason_codes must explain why"
                )
            else:
                # If hashes are set, verify they are strings
                if drift["baseline_hash"] is not None:
                    assert isinstance(drift["baseline_hash"], str)
                if drift["rules_hash"] is not None:
                    assert isinstance(drift["rules_hash"], str)


def test_post_analyze_repo_evidence_preview_populated_for_forbidden_edges(monkeypatch, tmp_path):
    """
    Test that evidence_preview is populated and returned via API when forbidden_edges_added_count > 0.
    
    Manual verification command (PowerShell):
    ```powershell
    $response = Invoke-RestMethod -Uri "http://localhost:8000/analyze-repo" -Method POST -ContentType "application/json" -Body (@{
        repo_url = "https://github.com/cosmicpython/code"
        max_commits = 30
        max_drifts = 5
        classifier_mode = "conformance"
    } | ConvertTo-Json)
    
    $driftWithForbidden = $response | Where-Object { $_.forbidden_edges_added_count -gt 0 } | Select-Object -First 1
    if ($driftWithForbidden) {
        Write-Host "Drift ID: $($driftWithForbidden.id)"
        Write-Host "Forbidden edges added: $($driftWithForbidden.forbidden_edges_added_count)"
        Write-Host "Evidence preview count: $($driftWithForbidden.evidence_preview.Count)"
        Write-Host "Evidence preview:"
        $driftWithForbidden.evidence_preview | ConvertTo-Json -Depth 10
        Write-Host "Baseline hash: $($driftWithForbidden.baseline_hash)"
        Write-Host "Rules hash: $($driftWithForbidden.rules_hash)"
    } else {
        Write-Host "No drift with forbidden_edges_added_count > 0 found"
    }
    ```
    """
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    from models.drift import Drift

    # Create a drift with forbidden_edges_added_count > 0 and evidence_preview populated
    mock_drifts = [
        Drift(
            id="arch-evidence-001",
            date="2024-01-01T10:00:00Z",
            type="negative",
            title="Architecture drift with forbidden edges",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["ui/main.py"],
            commit_hash="evidence123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",
            classifier_mode_used="conformance",
            classification="negative",
            edges_added_count=2,
            edges_removed_count=0,
            forbidden_edges_added_count=2,
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash="abc123def456",
            rules_hash="def456ghi789",
            reason_codes=[],
            evidence_preview=[
                {
                    "rule": "forbidden_edge_added",
                    "from_module": "ui",
                    "to_module": "core",
                    "src_file": "ui/app.js",
                    "to_file": "",
                    "import_ref": "../core/svc.js",
                    "import_text": "../core/svc.js",
                },
                {
                    "rule": "forbidden_edge_added",
                    "from_module": "api",
                    "to_module": "db",
                    "src_file": "api/routes.py",
                    "to_file": "",
                    "import_ref": "from db import models",
                    "import_text": "from db import models",
                },
            ],
        )
    ]

    with patch("api.routes.analyze_repo_for_drifts", return_value=mock_drifts):
        client = TestClient(app)
        response = client.post(
            "/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "max_commits": 10,
                "max_drifts": 5,
                "classifier_mode": "conformance",
            },
        )

        assert response.status_code == 200
        drifts = response.json()
        
        # Find drift with forbidden_edges_added_count > 0
        drift_with_forbidden = next(
            (d for d in drifts if d.get("forbidden_edges_added_count", 0) > 0), None
        )
        
        assert drift_with_forbidden is not None, "Expected at least one drift with forbidden_edges_added_count > 0"
        
        # Verify evidence_preview exists and is non-empty
        assert "evidence_preview" in drift_with_forbidden, "evidence_preview field must be present"
        assert len(drift_with_forbidden["evidence_preview"]) > 0, (
            "evidence_preview must be non-empty when forbidden_edges_added_count > 0"
        )
        assert len(drift_with_forbidden["evidence_preview"]) <= 10, (
            "evidence_preview must not exceed 10 items"
        )
        
        # Verify evidence_preview structure
        for ev in drift_with_forbidden["evidence_preview"]:
            assert "rule" in ev, "Evidence item must have 'rule' field"
            assert "from_module" in ev, "Evidence item must have 'from_module' field"
            assert "to_module" in ev, "Evidence item must have 'to_module' field"
            assert "src_file" in ev, "Evidence item must have 'src_file' field"
            assert "import_text" in ev, "Evidence item must have 'import_text' field"
        
        # Verify baseline_hash and rules_hash are present
        assert drift_with_forbidden["baseline_hash"] is not None, "baseline_hash must be present"
        assert drift_with_forbidden["rules_hash"] is not None, "rules_hash must be present"
        assert isinstance(drift_with_forbidden["baseline_hash"], str)
        assert isinstance(drift_with_forbidden["rules_hash"], str)
        
        # Verify GET /drifts also returns evidence_preview
        get_response = client.get("/drifts")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert "items" in get_data
        
        get_drift = next(
            (d for d in get_data["items"] if d.get("id") == "arch-evidence-001"), None
        )
        assert get_drift is not None, "Drift should be retrievable via GET /drifts"
        assert "evidence_preview" in get_drift
        assert len(get_drift["evidence_preview"]) > 0
        
        # Verify GET /drifts/{id} also returns evidence_preview
        get_single_response = client.get(f"/drifts/arch-evidence-001")
        assert get_single_response.status_code == 200
        single_drift = get_single_response.json()
        assert "evidence_preview" in single_drift
        assert len(single_drift["evidence_preview"]) > 0
        assert single_drift["baseline_hash"] is not None
        assert single_drift["rules_hash"] is not None
        assert single_drift["classifier_mode_used"] == "conformance"
        assert single_drift["classification"] == "negative"
        assert single_drift["reason_codes"] == []


def test_get_drifts_returns_evidence_preview_after_analyze_repo(monkeypatch, tmp_path):
    """
    Test that GET /drifts returns evidence_preview after POST /analyze-repo in conformance mode.
    
    This test verifies the full flow:
    1. POST /analyze-repo with classifier_mode="conformance" returns drifts with evidence_preview
    2. GET /drifts returns the same drifts with evidence_preview preserved
    3. GET /drifts/{id} returns the same drift with evidence_preview preserved
    """
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    from models.drift import Drift

    # Create a drift with forbidden_edges_added_count > 0 and evidence_preview populated
    drift_id = "test-evidence-001"
    mock_drifts = [
        Drift(
            id=drift_id,
            date="2024-01-01T10:00:00Z",
            type="negative",
            title="Test drift with forbidden edges",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["ui/main.py"],
            commit_hash="test123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",
            classifier_mode_used="conformance",
            classification="negative",
            edges_added_count=2,
            edges_removed_count=0,
            forbidden_edges_added_count=1,
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash="test_baseline_hash_123",
            rules_hash="test_rules_hash_456",
            reason_codes=[],
            evidence_preview=[
                {
                    "rule": "forbidden_edge_added",
                    "from_module": "ui",
                    "to_module": "core",
                    "src_file": "ui/app.js",
                    "to_file": "",
                    "import_ref": "../core/svc.js",
                    "import_text": "../core/svc.js",
                    "direction": "added",
                },
            ],
        )
    ]

    with patch("api.routes.analyze_repo_for_drifts", return_value=mock_drifts):
        client = TestClient(app)
        
        # Step 1: POST /analyze-repo
        analyze_response = client.post(
            "/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "max_commits": 10,
                "max_drifts": 5,
                "classifier_mode": "conformance",
            },
        )
        
        assert analyze_response.status_code == 200
        analyze_drifts = analyze_response.json()
        
        # Find drift with forbidden_edges_added_count > 0 from analyze-repo response
        drift_from_analyze = next(
            (d for d in analyze_drifts if d.get("forbidden_edges_added_count", 0) > 0), None
        )
        
        assert drift_from_analyze is not None, "Expected drift with forbidden_edges_added_count > 0 from /analyze-repo"
        drift_id_from_analyze = drift_from_analyze["id"]
        
        # Verify evidence_preview in analyze-repo response
        assert "evidence_preview" in drift_from_analyze
        assert len(drift_from_analyze["evidence_preview"]) > 0
        assert len(drift_from_analyze["evidence_preview"]) <= 10
        assert drift_from_analyze["baseline_hash"] is not None
        assert drift_from_analyze["rules_hash"] is not None
        
        # Step 2: GET /drifts
        get_drifts_response = client.get("/drifts")
        assert get_drifts_response.status_code == 200
        get_drifts_data = get_drifts_response.json()
        assert "items" in get_drifts_data
        
        # Find the same drift in GET /drifts response
        drift_from_get = next(
            (d for d in get_drifts_data["items"] if d.get("id") == drift_id_from_analyze), None
        )
        
        assert drift_from_get is not None, f"Drift {drift_id_from_analyze} should be in GET /drifts response"
        
        # Verify evidence_preview is present and non-empty in GET /drifts response
        assert "evidence_preview" in drift_from_get, "evidence_preview must be present in GET /drifts response"
        assert len(drift_from_get["evidence_preview"]) > 0, (
            f"evidence_preview must be non-empty in GET /drifts response (found {len(drift_from_get.get('evidence_preview', []))} items)"
        )
        assert len(drift_from_get["evidence_preview"]) <= 10, "evidence_preview must not exceed 10 items"
        
        # Verify all required fields are present
        assert drift_from_get["baseline_hash"] is not None, "baseline_hash must be present in GET /drifts"
        assert drift_from_get["rules_hash"] is not None, "rules_hash must be present in GET /drifts"
        assert drift_from_get["classifier_mode_used"] == "conformance"
        assert drift_from_get["classification"] == "negative"
        assert isinstance(drift_from_get["reason_codes"], list)
        assert drift_from_get["forbidden_edges_added_count"] == 1
        
        # Step 3: GET /drifts/{id}
        get_single_response = client.get(f"/drifts/{drift_id_from_analyze}")
        assert get_single_response.status_code == 200
        single_drift = get_single_response.json()
        
        # Verify evidence_preview is present and non-empty in GET /drifts/{id} response
        assert "evidence_preview" in single_drift, "evidence_preview must be present in GET /drifts/{id} response"
        assert len(single_drift["evidence_preview"]) > 0, (
            f"evidence_preview must be non-empty in GET /drifts/{{id}} response (found {len(single_drift.get('evidence_preview', []))} items)"
        )
        assert len(single_drift["evidence_preview"]) <= 10
        
        # Verify all required fields are present
        assert single_drift["baseline_hash"] is not None
        assert single_drift["rules_hash"] is not None
        assert single_drift["classifier_mode_used"] == "conformance"
        assert single_drift["classification"] == "negative"
        assert isinstance(single_drift["reason_codes"], list)
        assert single_drift["forbidden_edges_added_count"] == 1
        
        # Verify evidence_preview structure matches
        assert len(single_drift["evidence_preview"]) == len(drift_from_analyze["evidence_preview"])
        for ev in single_drift["evidence_preview"]:
            assert "from_module" in ev
            assert "to_module" in ev
            assert "src_file" in ev
            assert "import_text" in ev


def test_classifier_mode_used_normalization_in_conformance_mode(monkeypatch, tmp_path):
    """
    Test that classifier_mode_used is normalized correctly:
    - Drifts with conformance evidence get classifier_mode_used="conformance"
    - Drifts without conformance evidence get classifier_mode_used="keywords" (so UI uses drift.type)
    
    This prevents "Unknown explosion" where many drifts show as Unknown because
    classifier_mode_used="conformance" but classification=null.
    """
    # Ensure env var is not set
    monkeypatch.delenv("DRIFT_CLASSIFIER_MODE", raising=False)

    from models.drift import Drift

    # Create drifts with mixed conformance application:
    # 1. Architecture drift with conformance applied (has classification, baseline_hash, violations)
    # 2. Non-architecture drift (no conformance applied, should get classifier_mode_used="keywords")
    # 3. Architecture drift without conformance (no baseline, should get classifier_mode_used="keywords")
    mock_drifts = [
        Drift(
            id="conformance-applied-001",
            date="2024-01-01T10:00:00Z",
            type="negative",  # Keywords type
            title="Architecture drift with conformance",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["ui/main.py"],
            commit_hash="conformance123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",
            classifier_mode_used="conformance",  # Will be normalized
            classification="negative",  # Conformance applied
            edges_added_count=2,
            edges_removed_count=0,
            forbidden_edges_added_count=1,  # Has violations
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash="abc123def456",  # Has baseline
            rules_hash="def456ghi789",  # Has rules
            reason_codes=[],
            evidence_preview=[{"from_module": "ui", "to_module": "core"}],
        ),
        Drift(
            id="no-conformance-001",
            date="2024-01-02T10:00:00Z",
            type="negative",  # Keywords type
            title="Schema drift (non-architecture)",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["db/schema.sql"],
            commit_hash="noconformance123",
            repo_url="https://github.com/test/repo",
            driftType="schema_db",  # Not architecture, so conformance not applied
            classifier_mode_used="conformance",  # Will be normalized to "keywords"
            classification=None,  # No conformance classification
            edges_added_count=0,
            edges_removed_count=0,
            forbidden_edges_added_count=0,
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash=None,  # No baseline
            rules_hash=None,  # No rules
            reason_codes=[],  # No reason codes
            evidence_preview=[],  # No evidence
        ),
        Drift(
            id="no-conformance-002",
            date="2024-01-03T10:00:00Z",
            type="positive",  # Keywords type
            title="Architecture drift without baseline",
            summary="Test summary",
            functionality="Test functionality",
            files_changed=["api/routes.py"],
            commit_hash="nobaseline123",
            repo_url="https://github.com/test/repo",
            driftType="architecture",  # Architecture but no baseline
            classifier_mode_used="conformance",  # Will be normalized to "keywords"
            classification=None,  # No conformance classification (baseline missing)
            edges_added_count=0,
            edges_removed_count=0,
            forbidden_edges_added_count=0,
            forbidden_edges_removed_count=0,
            cycles_added_count=0,
            cycles_removed_count=0,
            baseline_hash=None,  # No baseline
            rules_hash=None,  # No rules
            reason_codes=[],  # No reason codes
            evidence_preview=[],  # No evidence
        ),
    ]

    with patch("api.routes.analyze_repo_for_drifts", return_value=mock_drifts):
        client = TestClient(app)
        response = client.post(
            "/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "max_commits": 10,
                "max_drifts": 5,
                "classifier_mode": "conformance",
            },
        )

        assert response.status_code == 200
        drifts = response.json()
        
        # Find drift with conformance applied
        drift_with_conformance = next(
            (d for d in drifts if d.get("id") == "conformance-applied-001"), None
        )
        assert drift_with_conformance is not None
        
        # Should have classifier_mode_used="conformance" (conformance was applied)
        assert drift_with_conformance["classifier_mode_used"] == "conformance", (
            "Drift with conformance evidence should have classifier_mode_used='conformance'"
        )
        assert drift_with_conformance["classification"] == "negative"
        assert drift_with_conformance["baseline_hash"] is not None
        assert drift_with_conformance["forbidden_edges_added_count"] > 0
        
        # Find drift without conformance (non-architecture)
        drift_no_conformance_1 = next(
            (d for d in drifts if d.get("id") == "no-conformance-001"), None
        )
        assert drift_no_conformance_1 is not None
        
        # Should have classifier_mode_used="keywords" (conformance was NOT applied)
        assert drift_no_conformance_1["classifier_mode_used"] == "keywords", (
            "Drift without conformance evidence should have classifier_mode_used='keywords' "
            f"(got {drift_no_conformance_1.get('classifier_mode_used')})"
        )
        assert drift_no_conformance_1["classification"] is None
        assert drift_no_conformance_1["type"] == "negative"  # Should use type field
        
        # Find drift without conformance (architecture but no baseline)
        drift_no_conformance_2 = next(
            (d for d in drifts if d.get("id") == "no-conformance-002"), None
        )
        assert drift_no_conformance_2 is not None
        
        # Should have classifier_mode_used="keywords" (conformance was NOT applied)
        assert drift_no_conformance_2["classifier_mode_used"] == "keywords", (
            "Drift without conformance evidence should have classifier_mode_used='keywords' "
            f"(got {drift_no_conformance_2.get('classifier_mode_used')})"
        )
        assert drift_no_conformance_2["classification"] is None
        assert drift_no_conformance_2["type"] == "positive"  # Should use type field
        
        # Verify at least one drift has conformance_applied=True AND classifier_mode_used=="conformance"
        conformance_drifts = [
            d for d in drifts 
            if d.get("classifier_mode_used") == "conformance"
        ]
        assert len(conformance_drifts) > 0, "Should have at least one drift with classifier_mode_used='conformance'"
        
        # Verify at least one drift has conformance_applied=False AND classifier_mode_used=="keywords"
        keywords_drifts = [
            d for d in drifts 
            if d.get("classifier_mode_used") == "keywords"
        ]
        assert len(keywords_drifts) > 0, (
            "Should have at least one drift with classifier_mode_used='keywords' "
            "(these should not show as Unknown in UI anymore)"
        )