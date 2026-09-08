"""
Priority Scoring + Failure Prediction + Anomaly Detection
These are the ML/rule-based intelligence layer that feeds the optimizer.
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")

SEVERITY_WEIGHT = {"Critical": 40, "High": 25, "Medium": 12, "Low": 5}


def compute_priority_scores():
    """
    Priority score = weighted combination of:
      - severity
      - overdue days
      - trains affected per day
    Score range roughly 0-100. Higher = more urgent.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM defects", conn)

    df["severity_component"] = df["severity"].map(SEVERITY_WEIGHT).fillna(5)
    df["overdue_component"] = df["overdue_days"].clip(lower=0, upper=90) / 90 * 30
    df["impact_component"] = (df["trains_affected_per_day"].clip(upper=50) / 50) * 30

    df["priority_score"] = (
        df["severity_component"] + df["overdue_component"] + df["impact_component"]
    ).round(2)

    # --- Failure prediction (simple RandomForest on synthetic labels) ---
    # We simulate a historical "failed_before_fix" label so the model has something to learn.
    # In production this would be trained on real historical failure records.
    rng = np.random.default_rng(42)
    df["failed_before_fix_label"] = (
        (df["severity_component"] + df["overdue_component"] > 40)
        & (rng.random(len(df)) > 0.4)
    ).astype(int)

    features = df[["severity_component", "overdue_component", "impact_component",
                    "estimated_duration_hours"]].fillna(0)
    labels = df["failed_before_fix_label"]

    if labels.sum() > 5 and labels.sum() < len(labels) - 5:
        clf = RandomForestClassifier(n_estimators=20, max_depth=6, n_jobs=-1, random_state=42)
        clf.fit(features, labels)
        df["risk_score"] = (clf.predict_proba(features)[:, 1] * 100).round(2)
    else:
        df["risk_score"] = df["priority_score"]  # fallback

    # Blend priority + risk for final ranking (60% explicit priority, 40% predicted risk)
    df["final_priority"] = (0.6 * df["priority_score"] + 0.4 * df["risk_score"]).round(2)

    cur = conn.cursor()
    records = [(float(row["final_priority"]), float(row["risk_score"]), row["defect_id"]) for _, row in df.iterrows()]
    conn.execute("BEGIN TRANSACTION")
    cur.executemany("UPDATE defects SET priority_score=?, risk_score=? WHERE defect_id=?", records)
    conn.commit()
    conn.close()

    print(f"Priority scores computed for {len(df)} defects.")
    return df


def detect_anomalies():
    """
    Anomaly Detection Agent: flags sections with unusually high defect clustering
    using IsolationForest on defect counts per section.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT section_id, COUNT(*) as defect_count, "
                      "AVG(overdue_days) as avg_overdue FROM defects "
                      "WHERE status != 'Completed' GROUP BY section_id", conn)
    conn.close()

    if len(df) < 5:
        return pd.DataFrame()

    model = IsolationForest(contamination=0.15, random_state=42)
    df["anomaly_flag"] = model.fit_predict(df[["defect_count", "avg_overdue"]])
    anomalies = df[df["anomaly_flag"] == -1].sort_values("defect_count", ascending=False)
    return anomalies[["section_id", "defect_count", "avg_overdue"]]


if __name__ == "__main__":
    compute_priority_scores()
    print("\nTop 5 most anomalous sections (unusual defect clustering):")
    print(detect_anomalies().head())
