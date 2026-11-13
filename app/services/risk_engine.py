from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split

FEATURES = ["age", "income", "horizon", "loss_tolerance", "experience"]
LABELS = ["Conservative", "Moderate", "Aggressive"]
MODEL_VERSION = "extratrees-risk-v1.0"
DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "investor_profiles.csv"


def _estimator() -> ExtraTreesClassifier:
    return ExtraTreesClassifier(
        n_estimators=400,
        max_features=0.9,
        min_samples_leaf=2,
        class_weight="balanced",
        bootstrap=False,
        n_jobs=-1,
        random_state=42,
    )


@lru_cache(maxsize=1)
def _trained_bundle():
    data = pd.read_csv(DATA_PATH)
    required = FEATURES + ["risk_type"]
    missing = sorted(set(required) - set(data.columns))
    if missing:
        raise ValueError(f"Investor dataset is missing columns: {', '.join(missing)}")
    data = data[required].dropna().copy()
    for column in FEATURES:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=FEATURES + ["risk_type"])
    data["risk_type"] = data["risk_type"].astype(str).str.strip().str.title()
    data = data[data["risk_type"].isin(LABELS)]
    if len(data) < 60 or data["risk_type"].nunique() < 3:
        raise ValueError("At least 60 valid investor records covering all three risk classes are required.")

    X, y = data[FEATURES], data["risk_type"]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_result = cross_validate(
        _estimator(), X, y, cv=cv,
        scoring={"accuracy": "accuracy", "balanced_accuracy": "balanced_accuracy", "macro_f1": "f1_macro"},
        n_jobs=1,
    )
    # Measure how much of the apparent score is already captured by age alone.
    age_only_result = cross_validate(
        _estimator(), X[["age"]], y, cv=cv, scoring="accuracy", n_jobs=1
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    holdout_model = _estimator().fit(X_train, y_train)
    holdout_pred = holdout_model.predict(X_test)
    holdout_report = classification_report(
        y_test, holdout_pred, labels=LABELS, output_dict=True, zero_division=0
    )

    model = _estimator().fit(X, y)
    metrics = {
        "samples": int(len(data)),
        "classes": {str(k): int(v) for k, v in y.value_counts().to_dict().items()},
        "cv_accuracy": float(np.mean(cv_result["test_accuracy"])),
        "cv_accuracy_std": float(np.std(cv_result["test_accuracy"], ddof=1)),
        "cv_balanced_accuracy": float(np.mean(cv_result["test_balanced_accuracy"])),
        "cv_macro_f1": float(np.mean(cv_result["test_macro_f1"])),
        "age_only_cv_accuracy": float(np.mean(age_only_result["test_score"])),
        "feature_ranges": {
            feature: {"min": float(X[feature].min()), "max": float(X[feature].max())}
            for feature in FEATURES
        },
        "holdout_accuracy": float(accuracy_score(y_test, holdout_pred)),
        "holdout_balanced_accuracy": float(balanced_accuracy_score(y_test, holdout_pred)),
        "holdout_macro_f1": float(f1_score(y_test, holdout_pred, average="macro")),
        "per_class": {
            label: {
                "precision": float(holdout_report[label]["precision"]),
                "recall": float(holdout_report[label]["recall"]),
                "f1": float(holdout_report[label]["f1-score"]),
                "support": int(holdout_report[label]["support"]),
            } for label in LABELS
        },
        "feature_importance": {
            feature: float(value)
            for feature, value in zip(FEATURES, model.feature_importances_)
        },
        "version": MODEL_VERSION,
        "dataset_note": "Validation uses the supplied 500-row dataset. Its collection method and label-generation process were not documented in the project files; scores must not be interpreted as real-world suitability accuracy.",
    }
    return model, metrics


def validate_assessment(payload: dict) -> dict:
    try:
        clean = {
            "age": int(payload["age"]),
            "income": float(payload["income"]),
            "horizon": int(payload["horizon"]),
            "loss_tolerance": int(payload["loss_tolerance"]),
            "experience": int(payload["experience"]),
        }
    except (KeyError, TypeError, ValueError):
        raise ValueError("Complete every field using valid numbers.")
    if not 18 <= clean["age"] <= 100:
        raise ValueError("Age must be between 18 and 100.")
    if not 0 < clean["income"] <= 1_000_000_000:
        raise ValueError("Income must be greater than zero, using the same scale as the training data.")
    if not 1 <= clean["horizon"] <= 50:
        raise ValueError("Investment horizon must be between 1 and 50 years.")
    if not 1 <= clean["loss_tolerance"] <= 100:
        raise ValueError("Loss tolerance must be between 1% and 100%.")
    if clean["experience"] not in (0, 1, 2):
        raise ValueError("Choose one of the available experience levels.")
    return clean


def assess_investor(payload: dict) -> dict:
    clean = validate_assessment(payload)
    model, metrics = _trained_bundle()
    row = pd.DataFrame([clean], columns=FEATURES)
    probabilities = model.predict_proba(row)[0]
    ranked = sorted(
        ((str(label), float(prob)) for label, prob in zip(model.classes_, probabilities)),
        key=lambda item: item[1], reverse=True,
    )
    category, top_probability = ranked[0]
    out_of_range = [
        feature for feature, value in clean.items()
        if value < metrics["feature_ranges"][feature]["min"]
        or value > metrics["feature_ranges"][feature]["max"]
    ]
    margin = top_probability - ranked[1][1]
    certainty = "Clear model separation" if margin >= 0.35 else (
        "Moderate model separation" if margin >= 0.15 else "Borderline classification"
    )
    guidance = {
        "Conservative": "The model classifies this profile in the conservative group. Prioritise liquidity, capital preservation and a measured equity allocation; assess near-term liabilities before investing.",
        "Moderate": "The model classifies this profile in the moderate group. A diversified mix may be appropriate, but the final allocation should reflect goals, liabilities and emergency reserves.",
        "Aggressive": "The model classifies this profile in the aggressive group. A longer horizon and higher stated loss tolerance do not remove drawdown risk; diversify and size positions carefully.",
    }
    return {
        "risk_category": category,
        "probabilities": {label: round(value, 6) for label, value in ranked},
        "confidence": round(top_probability * 100, 1),
        "separation": round(margin * 100, 1),
        "certainty_label": certainty,
        "guidance": guidance[category],
        "inputs": clean,
        "model_version": metrics["version"],
        "validation_note": metrics["dataset_note"],
        "out_of_range_fields": out_of_range,
        "domain_warning": (
            "One or more inputs are outside the observed training-data range. This is an extrapolation; treat the result as especially uncertain."
            if out_of_range else None
        ),
    }


def evaluation_metrics() -> dict:
    _model, metrics = _trained_bundle()
    return metrics
