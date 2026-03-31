import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import joblib

print("Loading investor_data.csv ...")
data = pd.read_csv("investor_data.csv")

risk_map = {"Conservative": 0, "Moderate": 1, "Aggressive": 2}
data["risk_score"] = data["risk_type"].map(risk_map)

features = ["age", "income", "horizon", "loss_tolerance", "risk_score"]
X = data[features]

scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X)

kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
kmeans.fit(X_scaled)
data["cluster"] = kmeans.labels_

# Auto-label clusters by sorting centroids on mean age
cluster_info = data.groupby("cluster")[["age", "risk_score"]].mean().sort_values("age")
labels = [
    "Young Aggressive Investor",
    "Mid-Age Balanced Investor",
    "Retired Conservative Investor"
]
label_map = {int(cid): lbl for (cid, _), lbl in zip(cluster_info.iterrows(), labels)}

print("\nCluster label mapping:", label_map)
print("\nCluster distribution:")
print(data.groupby("cluster")["risk_type"].value_counts())

joblib.dump({"model": kmeans, "scaler": scaler, "label_map": label_map}, "cluster_model.pkl")
print("\n cluster_model.pkl saved successfully!")