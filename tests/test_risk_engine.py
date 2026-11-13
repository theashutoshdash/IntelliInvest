import pytest
from app.services.risk_engine import assess_investor, validate_assessment, evaluation_metrics


def sample_payload():
    return {
        "age": 31,
        "income": 85000,
        "horizon": 15,
        "loss_tolerance": 24,
        "experience": 1,
    }


def test_valid_assessment_returns_probabilities():
    result = assess_investor(sample_payload())
    assert result["risk_category"] in {"Conservative", "Moderate", "Aggressive"}
    assert abs(sum(result["probabilities"].values()) - 1.0) < 1e-6
    assert 0 <= result["confidence"] <= 100


def test_age_out_of_range_is_rejected():
    payload = sample_payload()
    payload["age"] = 14
    with pytest.raises(ValueError):
        validate_assessment(payload)


def test_unknown_experience_is_rejected():
    payload = sample_payload()
    payload["experience"] = 4
    with pytest.raises(ValueError):
        validate_assessment(payload)


def test_evaluation_reports_multiple_metrics():
    metrics = evaluation_metrics()
    assert metrics["samples"] >= 60
    assert 0 <= metrics["cv_accuracy"] <= 1
    assert 0 <= metrics["cv_balanced_accuracy"] <= 1
    assert 0 <= metrics["cv_macro_f1"] <= 1
    assert set(metrics["per_class"]) == {"Conservative", "Moderate", "Aggressive"}
    assert 0 <= metrics["age_only_cv_accuracy"] <= 1


def test_assessment_flags_inputs_outside_training_domain():
    payload = sample_payload()
    payload["income"] = 250000
    result = assess_investor(payload)
    assert "income" in result["out_of_range_fields"]
    assert result["domain_warning"]
