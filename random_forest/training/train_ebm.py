#!/usr/bin/env python3
"""Train and save the SoilSage Explainable Boosting Machine crop model."""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from random_forest.ebm_model import AgronomicEBMClassifier, FEATURE_NAMES


def train_and_save():
    dataset_path = REPO_ROOT / "random_forest" / "dataset" / "Crop_recommendation.csv"
    output_path = REPO_ROOT / "random_forest" / "model" / "soil_model.pkl"

    df = pd.read_csv(dataset_path).dropna(axis=1, how="all")
    X = df[FEATURE_NAMES]
    y = df["label"]

    rng = np.random.RandomState(42)
    indices = rng.permutation(len(df))
    split = int(len(df) * 0.8)
    train_idx, test_idx = indices[:split], indices[split:]

    eval_model = AgronomicEBMClassifier(random_state=42)
    eval_model.fit(X.iloc[train_idx], y.iloc[train_idx])
    test_acc = eval_model.score(X.iloc[test_idx], y.iloc[test_idx])

    final_model = AgronomicEBMClassifier(random_state=42)
    final_model.fit(X, y)
    final_model.cv_accuracy_ = round(float(test_acc), 4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        pickle.dump(final_model, fh, protocol=4)

    print(f"80/20 Validation Accuracy: {test_acc * 100:.2f}%")
    print(f"Saved soil_model.pkl to {output_path}")


if __name__ == "__main__":
    train_and_save()
