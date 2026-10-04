from fastapi.testclient import TestClient

from agentops_api.main import create_app


def test_demo_case_list_does_not_reveal_scenario_or_expected_labels() -> None:
    client = TestClient(create_app())

    response = client.get("/demo/cases")

    assert response.status_code == 200
    assert len(response.json()) == 7
    assert all(set(case) == {"case_id", "supplier"} for case in response.json())


def test_review_endpoint_returns_recommendation_and_citations() -> None:
    client = TestClient(create_app())

    response = client.post("/reviews", json={"case_id": "C03"})

    assert response.status_code == 200
    result = response.json()
    assert result["disposition"] == "escalate"
    assert result["human_final_decision_required"] is True
    finding = result["findings"][0]
    assert finding["issue_type"] == "liability_cap_below_policy_minimum"
    assert finding["contract_clause_ids"] == ["C03-01"]
    assert finding["policy_clause_ids"] == ["STD-LIABILITY-01"]
    assert finding["contract_evidence"][0]["text"].startswith("The supplier's aggregate liability")


def test_ai_review_route_is_explicit_and_returns_ai_mode(monkeypatch) -> None:
    from agentops_api import main
    from agentops_api.demo_data import load_demo_bundle
    from agentops_api.review_engine import review_case

    ai_result = review_case("C03", load_demo_bundle())
    ai_result["review_mode"] = "ai_assisted"
    monkeypatch.setattr(main, "review_case_with_model", lambda case_id: ai_result)
    client = TestClient(create_app())

    response = client.post("/reviews/ai", json={"case_id": "C03"})

    assert response.status_code == 200
    assert response.json()["review_mode"] == "ai_assisted"
    assert response.json()["human_final_decision_required"] is True


def test_ai_review_route_reports_missing_configuration(monkeypatch) -> None:
    from agentops_api import main

    def missing_configuration(_case_id: str) -> None:
        raise RuntimeError("Missing AI configuration: RELAYGUARD_BASE_URL")

    monkeypatch.setattr(main, "review_case_with_model", missing_configuration)
    client = TestClient(create_app())

    response = client.post("/reviews/ai", json={"case_id": "C03"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Missing AI configuration: RELAYGUARD_BASE_URL"


def test_unknown_review_case_returns_404() -> None:
    client = TestClient(create_app())

    response = client.post("/reviews", json={"case_id": "C99"})

    assert response.status_code == 404


def test_invalid_case_id_is_rejected_by_request_validation() -> None:
    client = TestClient(create_app())

    response = client.post("/reviews", json={"case_id": "not-a-case"})

    assert response.status_code == 422


def test_local_dashboard_is_served() -> None:
    response = TestClient(create_app()).get("/dashboard")
    assert response.status_code == 200
    assert "Procurement Review" in response.text
    assert "requirement_not_established" in response.text


def test_uploaded_text_can_be_reviewed_without_model_call() -> None:
    response = TestClient(create_app()).post(
        "/reviews/upload",
        data={"supplier": "Example Supplier", "mode": "baseline", "completeness": "excerpt"},
        files={"file": ("agreement.txt", b"The supplier's liability is capped at fees for six months.\n\nThe supplier will process customer personal data to provide cloud services.\n\nThe supplier will notify us promptly after a security incident.", "text/plain")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["review_mode"] == "deterministic_policy_baseline"
    assert result["document_completeness"] == "excerpt"
    assert result["source_clause_count"] == 3
    assert {finding["evidence_status"] for finding in result["findings"]} == {
        "confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"
    }


def test_upload_rejects_unsupported_file_type() -> None:
    response = TestClient(create_app()).post(
        "/reviews/upload", data={"mode": "baseline"},
        files={"file": ("contract.rtf", b"contract text", "text/rtf")},
    )
    assert response.status_code == 400


def test_uploaded_custom_policy_is_passed_to_ai_review(monkeypatch) -> None:
    from agentops_api import main

    captured = {}

    def fake_review(supplier, clauses, bundle, *, contract_completeness):
        captured["supplier"] = supplier
        captured["contract_completeness"] = contract_completeness
        captured["policies"] = bundle["policies"]
        return {"findings": [], "disposition": "approve", "review_mode": "ai_assisted_upload"}

    monkeypatch.setattr(main, "review_contract_with_model", fake_review)
    response = TestClient(create_app()).post(
        "/reviews/upload",
        data={"supplier": "Real Vendor", "mode": "ai", "completeness": "complete"},
        files=[
            ("file", ("agreement.txt", b"A supplier agreement containing enough text to review.", "text/plain")),
            ("policy_files", ("company-policy.txt", b"The supplier must give notice within 24 hours of a security incident.", "text/plain")),
        ],
    )
    assert response.status_code == 200
    assert captured["supplier"] == "Real Vendor"
    assert captured["contract_completeness"] == "complete"
    assert captured["policies"][0]["title"] == "company-policy.txt"
    assert captured["policies"][0]["clauses"][0]["clause_id"] == "POL-UP-01-001"


def test_custom_policy_cannot_silently_use_demo_rules_baseline() -> None:
    response = TestClient(create_app()).post(
        "/reviews/upload",
        data={"mode": "baseline"},
        files=[
            ("file", ("agreement.txt", b"A supplier agreement containing enough text to review.", "text/plain")),
            ("policy_files", ("company-policy.txt", b"The supplier must give notice within 24 hours of a security incident.", "text/plain")),
        ],
    )
    assert response.status_code == 400
    assert "Custom policy uploads require AI-assisted mode" in response.json()["detail"]
