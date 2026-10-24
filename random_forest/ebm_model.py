"""
Explainable Boosting Machine (EBM) for SoilSage Crop Recommendation.

Upgrades the black-box RandomForestClassifier to an interpretable additive
boosting model that predicts the best crop AND explains in simple, farmer-friendly
language why the recommended crop is the best fit for the current soil and weather.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple, Union

import numpy as np
import pandas as pd

FEATURE_NAMES: List[str] = [
    "Nitrogen",
    "phosphorus",
    "potassium",
    "temperature",
    "humidity",
    "ph",
    "rainfall",
]

FEATURE_META: Dict[str, Dict[str, str]] = {
    "Nitrogen": {
        "key": "n",
        "label": "Nitrogen (N)",
        "short": "Nitrogen",
        "unit": "mg/kg",
        "benefit": "healthy leaf and stem growth",
    },
    "phosphorus": {
        "key": "p",
        "label": "Phosphorus (P)",
        "short": "Phosphorus",
        "unit": "mg/kg",
        "benefit": "strong root development and flowering",
    },
    "potassium": {
        "key": "k",
        "label": "Potassium (K)",
        "short": "Potassium",
        "unit": "mg/kg",
        "benefit": "crop immunity, water balance, and grain/fruit quality",
    },
    "temperature": {
        "key": "temperature",
        "label": "Temperature",
        "short": "Temperature",
        "unit": "°C",
        "benefit": "steady germination and active plant growth",
    },
    "humidity": {
        "key": "humidity",
        "label": "Humidity",
        "short": "Humidity",
        "unit": "%",
        "benefit": "healthy moisture balance without leaf stress",
    },
    "ph": {
        "key": "ph",
        "label": "Soil pH",
        "short": "Soil pH",
        "unit": "pH",
        "benefit": "easy nutrient uptake by the roots",
    },
    "rainfall": {
        "key": "rainfall",
        "label": "Rainfall (30d)",
        "short": "Rainfall",
        "unit": "mm",
        "benefit": "natural soil moisture for the growing season",
    },
}

CROP_AGRONOMY: Dict[str, Dict[str, str]] = {
    "rice": {
        "summary": "Rice thrives in wet, humid conditions with plenty of nitrogen to support lush leafy growth and full grain heads.",
        "water_note": "High water requirement",
        "soil_note": "Prefers moisture-retaining clay or loamy soil",
    },
    "maize": {
        "summary": "Maize grows best in well-drained soil with strong nitrogen levels, warm air, and moderate rainfall.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers well-drained loamy soil",
    },
    "chickpea": {
        "summary": "Chickpea is a hardy pulse crop that thrives in cooler, drier weather and naturally enriches soil nitrogen through its roots.",
        "water_note": "Low to moderate water requirement",
        "soil_note": "Prefers well-drained neutral to slightly alkaline soil",
    },
    "kidneybeans": {
        "summary": "Kidney beans do best in mild weather and slightly acidic soil with good phosphorus for strong root establishment.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers friable, slightly acidic loam",
    },
    "pigeonpeas": {
        "summary": "Pigeonpea has deep roots that handle warm weather well and needs good phosphorus while fixing its own nitrogen.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers deep, well-drained soil",
    },
    "mothbeans": {
        "summary": "Mothbean is highly drought-tolerant and thrives in warm, low-rainfall conditions across a wide pH range.",
        "water_note": "Very low water requirement",
        "soil_note": "Thrives in light sandy or loamy soil",
    },
    "mungbean": {
        "summary": "Mungbean matures quickly in warm, humid conditions with light rainfall and moderate phosphorus.",
        "water_note": "Low to moderate water requirement",
        "soil_note": "Prefers warm, well-drained loam",
    },
    "blackgram": {
        "summary": "Blackgram grows well in warm temperatures and neutral soil with good phosphorus reserves.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers neutral clay-loam soil",
    },
    "lentil": {
        "summary": "Lentil is well-suited to mild temperatures and low rainfall, using soil phosphorus for strong root and seed growth.",
        "water_note": "Low water requirement",
        "soil_note": "Prefers neutral, well-drained loam",
    },
    "pomegranate": {
        "summary": "Pomegranate thrives in mild temperatures and steady potassium levels that support healthy fruit skin and sweetness.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers well-drained loamy soil",
    },
    "banana": {
        "summary": "Banana is a heavy feeder that loves warm, humid weather and rich nitrogen and phosphorus for strong stem and bunch growth.",
        "water_note": "High water requirement",
        "soil_note": "Prefers deep, nutrient-rich loamy soil",
    },
    "mango": {
        "summary": "Mango suits warm tropical temperatures and moderate humidity, which keeps blossoms healthy and fruit set strong.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers deep, well-drained slightly acidic soil",
    },
    "grapes": {
        "summary": "Grapes thrive when phosphorus and potassium are high and rainfall is moderate, helping berries develop rich sweetness.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers well-drained, potassium-rich soil",
    },
    "watermelon": {
        "summary": "Watermelon uses rich nitrogen for vine growth and potassium for sweet, crisp fruit under warm temperatures and light rain.",
        "water_note": "Low to moderate water requirement",
        "soil_note": "Prefers warm, well-drained sandy loam",
    },
    "muskmelon": {
        "summary": "Muskmelon loves warm, humid air with low rainfall and rich nitrogen, keeping the root zone dry and fruit sweet.",
        "water_note": "Low water requirement",
        "soil_note": "Prefers warm sandy-loam soil",
    },
    "apple": {
        "summary": "Apple thrives in cool, humid conditions with rich phosphorus and potassium for strong blossoms and crisp fruit.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers cool, slightly acidic loamy soil",
    },
    "orange": {
        "summary": "Orange grows well in humid, mild-to-warm weather with balanced, low-salt soil and steady moisture.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers well-drained neutral soil",
    },
    "papaya": {
        "summary": "Papaya grows rapidly in warm, humid conditions when soil pH is near neutral and NPK nutrients are well balanced.",
        "water_note": "Moderate to high water requirement",
        "soil_note": "Prefers warm, strictly drained neutral loam",
    },
    "coconut": {
        "summary": "Coconut thrives in warm coastal-style humidity and high rainfall, even when soil nitrogen and phosphorus are modest.",
        "water_note": "High water requirement",
        "soil_note": "Prefers sandy or alluvial well-drained soil",
    },
    "cotton": {
        "summary": "Cotton is a nitrogen-loving crop that thrives in warm weather and moderate rainfall for strong branching and boll growth.",
        "water_note": "Moderate water requirement",
        "soil_note": "Prefers deep black soil or rich loam",
    },
    "jute": {
        "summary": "Jute thrives in warm, humid monsoon conditions with plenty of rainfall and nitrogen for tall, strong fiber stalks.",
        "water_note": "High water requirement",
        "soil_note": "Prefers rich alluvial loamy soil",
    },
    "coffee": {
        "summary": "Coffee grows best in mild temperatures, high nitrogen, and generous rainfall with well-drained, slightly acidic-to-neutral soil.",
        "water_note": "High water requirement",
        "soil_note": "Prefers humus-rich, well-drained soil",
    },
}


class AgronomicEBMClassifier:
    """
    Explainable Boosting Machine (EBM) classifier for crop recommendation.
    Learns cyclic gradient-boosted 1D shape functions per soil/climate feature
    alongside crop tolerance envelopes, providing both accurate predictions
    and clear farmer-friendly explanations.
    """

    def __init__(
        self,
        n_bins: int = 64,
        n_rounds: int = 120,
        learning_rate: float = 0.08,
        niche_weight: float = 0.55,
        temperature: float = 0.35,
        random_state: int = 42,
    ):
        self.n_bins = n_bins
        self.n_rounds = n_rounds
        self.learning_rate = learning_rate
        self.niche_weight = niche_weight
        self.temperature = temperature
        self.random_state = random_state

        self.feature_names_: List[str] = list(FEATURE_NAMES)
        self.classes_: np.ndarray = np.array([], dtype=object)
        self.grid_edges_: List[np.ndarray] = []
        self.shape_tables_: np.ndarray = np.empty(0)
        self.intercept_: np.ndarray = np.empty(0)
        self.crop_stats_: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.global_stats_: Dict[str, Dict[str, float]] = {}
        self.feature_importances_: np.ndarray = np.empty(0)
        self.cv_accuracy_: float = 0.0

    def _to_matrix(self, X: Union[pd.DataFrame, np.ndarray, Sequence[Any]]) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            cols = [c for c in self.feature_names_ if c in X.columns]
            if len(cols) == len(self.feature_names_):
                arr = X[self.feature_names_].to_numpy(dtype=float)
            else:
                arr = X.to_numpy(dtype=float)
        else:
            arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr[:, : len(self.feature_names_)]

    @staticmethod
    def _smooth_1d(arr: np.ndarray, sigma: float = 1.15) -> np.ndarray:
        radius = int(math.ceil(3 * sigma))
        offsets = np.arange(-radius, radius + 1, dtype=float)
        kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
        kernel /= kernel.sum()
        padded = np.pad(arr, (radius, radius), mode="edge")
        return np.convolve(padded, kernel, mode="valid")

    def _compute_niche_table(
        self, bin_centers: np.ndarray, stats: Dict[str, float]
    ) -> np.ndarray:
        q15, q85 = stats["q15"], stats["q85"]
        f_min, f_max = stats["min"], stats["max"]
        median = stats["median"]
        std = max(stats["std"], (f_max - f_min) * 0.15, 1e-3)

        core_dist = np.where(
            bin_centers < q15,
            (q15 - bin_centers) / std,
            np.where(bin_centers > q85, (bin_centers - q85) / std, 0.0),
        )
        outer_dist = np.where(
            bin_centers < f_min,
            (f_min - bin_centers) / std,
            np.where(bin_centers > f_max, (bin_centers - f_max) / std, 0.0),
        )
        center_dist = np.abs(bin_centers - median) / (std * 2.5)
        score = 0.85 - 0.15 * np.minimum(center_dist, 1.0) - 0.65 * (core_dist ** 1.6) - 1.35 * (outer_dist ** 2.0)
        return np.clip(score, -8.0, 1.0)

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Sequence[Any]) -> "AgronomicEBMClassifier":
        X_mat = self._to_matrix(X)
        y_arr = np.asarray(y, dtype=str)
        self.classes_ = np.unique(y_arr)
        n_samples, n_features = X_mat.shape
        n_classes = len(self.classes_)
        class_to_idx = {c: i for i, c in enumerate(self.classes_)}
        y_idx = np.array([class_to_idx[c] for c in y_arr], dtype=int)
        Y_onehot = np.eye(n_classes, dtype=float)[y_idx]

        self.global_stats_ = {}
        for j, fname in enumerate(self.feature_names_):
            col = X_mat[:, j]
            self.global_stats_[fname] = {
                "min": float(np.min(col)),
                "max": float(np.max(col)),
                "mean": float(np.mean(col)),
                "median": float(np.median(col)),
                "std": float(np.std(col) + 1e-6),
            }

        self.crop_stats_ = {}
        for c in self.classes_:
            mask = y_arr == c
            X_c = X_mat[mask]
            self.crop_stats_[c] = {}
            for j, fname in enumerate(self.feature_names_):
                col = X_c[:, j]
                self.crop_stats_[c][fname] = {
                    "min": float(np.min(col)),
                    "q10": float(np.percentile(col, 10)),
                    "q15": float(np.percentile(col, 15)),
                    "q25": float(np.percentile(col, 25)),
                    "median": float(np.median(col)),
                    "mean": float(np.mean(col)),
                    "q75": float(np.percentile(col, 75)),
                    "q85": float(np.percentile(col, 85)),
                    "q90": float(np.percentile(col, 90)),
                    "max": float(np.max(col)),
                    "std": float(np.std(col) + 1e-6),
                }

        self.grid_edges_ = []
        bin_indices = np.zeros((n_samples, n_features), dtype=int)
        bin_centers_list = []
        for j, fname in enumerate(self.feature_names_):
            col = X_mat[:, j]
            pad = (np.max(col) - np.min(col)) * 0.08 + 1e-3
            q_edges = np.quantile(col, np.linspace(0, 1, self.n_bins // 2 + 1))
            u_edges = np.linspace(np.min(col) - pad, np.max(col) + pad, self.n_bins // 2 + 1)
            merged = np.unique(np.concatenate([q_edges, u_edges]))
            edges = np.interp(
                np.linspace(0, len(merged) - 1, self.n_bins + 1),
                np.arange(len(merged)),
                merged,
            )
            self.grid_edges_.append(edges)
            centers = 0.5 * (edges[:-1] + edges[1:])
            bin_centers_list.append(centers)
            b_idx = np.clip(np.digitize(col, edges[1:-1]), 0, self.n_bins - 1)
            bin_indices[:, j] = b_idx

        self.shape_tables_ = np.zeros((n_classes, n_features, self.n_bins), dtype=float)
        for c_i, c in enumerate(self.classes_):
            for j, fname in enumerate(self.feature_names_):
                niche_curve = self._compute_niche_table(
                    bin_centers_list[j], self.crop_stats_[c][fname]
                )
                self.shape_tables_[c_i, j, :] = self.niche_weight * niche_curve

        self.intercept_ = np.zeros(n_classes, dtype=float)

        scores = np.zeros((n_samples, n_classes), dtype=float)
        for j in range(n_features):
            scores += self.shape_tables_[:, j, bin_indices[:, j]].T

        for _round in range(self.n_rounds):
            for j in range(n_features):
                shifted = scores - np.max(scores, axis=1, keepdims=True)
                exp_s = np.exp(shifted)
                probs = exp_s / np.sum(exp_s, axis=1, keepdims=True)
                residuals = Y_onehot - probs

                b_j = bin_indices[:, j]
                delta_table = np.zeros((n_classes, self.n_bins), dtype=float)
                counts = np.bincount(b_j, minlength=self.n_bins).astype(float)
                denom = counts + 2.5

                for c_i in range(n_classes):
                    grad_sum = np.bincount(b_j, weights=residuals[:, c_i], minlength=self.n_bins)
                    raw_step = grad_sum / denom
                    smoothed_step = self._smooth_1d(raw_step, sigma=1.1)
                    delta_table[c_i, :] = self.learning_rate * smoothed_step

                delta_table -= np.mean(delta_table, axis=0, keepdims=True)
                self.shape_tables_[:, j, :] += delta_table
                scores += delta_table[:, b_j].T

        imp = np.zeros(n_features, dtype=float)
        for j in range(n_features):
            imp[j] = float(np.mean(np.abs(self.shape_tables_[:, j, bin_indices[:, j]])))
        self.feature_importances_ = imp / (np.sum(imp) + 1e-9)

        return self

    def _eval_feature_contributions(self, X_mat: np.ndarray) -> np.ndarray:
        n_samples = X_mat.shape[0]
        n_classes = len(self.classes_)
        n_features = len(self.feature_names_)
        contribs = np.zeros((n_samples, n_classes, n_features), dtype=float)

        for j, fname in enumerate(self.feature_names_):
            edges = self.grid_edges_[j]
            centers = 0.5 * (edges[:-1] + edges[1:])
            vals = X_mat[:, j]
            for c_i in range(n_classes):
                c_stats = self.crop_stats_[self.classes_[c_i]][fname]
                base_val = np.interp(vals, centers, self.shape_tables_[c_i, j, :])
                std = max(c_stats["std"], 1e-3)
                under = np.maximum(0.0, (c_stats["min"] - vals) / std)
                over = np.maximum(0.0, (vals - c_stats["max"]) / std)
                tail_penalty = -0.45 * (under ** 1.8 + over ** 1.8)
                contribs[:, c_i, j] = base_val + tail_penalty

        return contribs

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray, Sequence[Any]]) -> np.ndarray:
        X_mat = self._to_matrix(X)
        contribs = self._eval_feature_contributions(X_mat)
        logits = self.intercept_[None, :] + np.sum(contribs, axis=2)
        scaled = logits / max(self.temperature, 0.05)
        scaled -= np.max(scaled, axis=1, keepdims=True)
        exp_s = np.exp(scaled)
        return exp_s / np.sum(exp_s, axis=1, keepdims=True)

    def predict(self, X: Union[pd.DataFrame, np.ndarray, Sequence[Any]]) -> np.ndarray:
        probs = self.predict_proba(X)
        idx = np.argmax(probs, axis=1)
        return self.classes_[idx]

    def score(self, X: Union[pd.DataFrame, np.ndarray], y: Sequence[Any]) -> float:
        preds = self.predict(X)
        y_arr = np.asarray(y, dtype=str)
        return float(np.mean(preds == y_arr))

    @staticmethod
    def _feature_fit_score(val: float, stats: Dict[str, float]) -> Tuple[int, str]:
        q15, q85 = stats["q15"], stats["q85"]
        f_min, f_max = stats["min"], stats["max"]
        median = stats["median"]
        std = max(stats["std"], (f_max - f_min) * 0.2, 1e-3)

        if q15 <= val <= q85:
            half_span = max(0.5 * (q85 - q15), 1e-3)
            dev = abs(val - median) / half_span
            pct = int(round(100 - min(12.0, dev * 10.0)))
            return max(88, min(100, pct)), "ideal"

        if f_min <= val < q15:
            ratio = (val - f_min) / max(q15 - f_min, 1e-3)
            pct = int(round(70 + 17 * ratio))
            return max(68, min(87, pct)), "good"

        if q85 < val <= f_max:
            ratio = (f_max - val) / max(f_max - q85, 1e-3)
            pct = int(round(70 + 17 * ratio))
            return max(68, min(87, pct)), "good"

        if val < f_min:
            z = (f_min - val) / std
            pct = int(round(68 * math.exp(-0.55 * z)))
            return max(10, min(65, pct)), "low"

        z = (val - f_max) / std
        pct = int(round(68 * math.exp(-0.55 * z)))
        return max(10, min(65, pct)), "high"

    @staticmethod
    def _fmt_val(fname: str, val: float) -> str:
        if fname in ("Nitrogen", "phosphorus", "potassium"):
            return f"{val:.0f}"
        if fname == "ph":
            return f"{val:.2f}"
        return f"{val:.1f}"

    def _build_farmer_note(
        self,
        crop: str,
        fname: str,
        val: float,
        status: str,
        stats: Dict[str, float],
    ) -> str:
        meta = FEATURE_META[fname]
        unit = meta["unit"]
        benefit = meta["benefit"]
        crop_title = crop.capitalize()
        lo_str = self._fmt_val(fname, stats["min"])
        hi_str = self._fmt_val(fname, stats["max"])
        unit_sfx = f" {unit}" if unit != "pH" else ""
        range_str = f"{lo_str}–{hi_str}{unit_sfx}"

        if status == "ideal":
            return f"Right in {crop_title}'s ideal range ({range_str}) for {benefit}."
        if status == "good":
            return f"Fits within {crop_title}'s comfortable range ({range_str}) for {benefit}."
        if status == "low":
            return f"Slightly below {crop_title}'s preferred {range_str}; the fertilizer mix helps boost this."
        return f"Above {crop_title}'s usual {range_str} range; monitor soil balance."

    def explain_reading(
        self, values: Sequence[float], top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Generates a clean, farmer-friendly explanation for why the predicted crop
        is the best match for the current 7 readings [N, P, K, temp, humidity, pH, rainfall].
        """
        arr = np.asarray(values[:7], dtype=float).reshape(1, 7)
        probs = self.predict_proba(arr)[0]
        contribs = self._eval_feature_contributions(arr)[0]

        ranked_idx = np.argsort(probs)[::-1]
        best_idx = int(ranked_idx[0])
        best_crop = str(self.classes_[best_idx])
        best_prob = float(probs[best_idx])
        best_contribs = contribs[best_idx]

        crop_stats = self.crop_stats_[best_crop]
        agronomy = CROP_AGRONOMY.get(
            best_crop.lower(),
            {
                "summary": f"{best_crop.capitalize()} is well-suited to your current soil nutrients and local weather.",
                "water_note": "Moderate water requirement",
                "soil_note": "Prefers balanced loamy soil",
            },
        )

        factors: List[Dict[str, Any]] = []
        fit_scores: List[int] = []

        for j, fname in enumerate(self.feature_names_):
            val = float(arr[0, j])
            f_stats = crop_stats[fname]
            meta = FEATURE_META[fname]
            fit_pct, status = self._feature_fit_score(val, f_stats)
            fit_scores.append(fit_pct)

            lo_s = self._fmt_val(fname, f_stats["min"])
            hi_s = self._fmt_val(fname, f_stats["max"])
            u_s = f" {meta['unit']}" if meta["unit"] != "pH" else ""

            factors.append(
                {
                    "feature": meta["key"],
                    "label": meta["label"],
                    "short": meta["short"],
                    "unit": meta["unit"],
                    "value": round(val, 2),
                    "value_display": f"{self._fmt_val(fname, val)}{u_s}",
                    "ideal_range": f"{lo_s}–{hi_s}{u_s}",
                    "optimal_median": round(f_stats["median"], 2),
                    "fit_pct": fit_pct,
                    "status": status,
                    "reason": self._build_farmer_note(
                        best_crop, fname, val, status, f_stats
                    ),
                }
            )

        sorted_by_fit = sorted(factors, key=lambda d: d["fit_pct"], reverse=True)
        top_matches = sorted_by_fit[:3]
        mean_fit = sum(fit_scores) / len(fit_scores)
        min_fit = min(fit_scores)
        overall_suitability = int(round(0.72 * mean_fit + 0.28 * min_fit))

        crop_title = best_crop.capitalize()
        top_phrases = [f"{m['short']} ({m['value_display']})" for m in top_matches]
        summary = (
            f"{crop_title} is the best fit for your field because your "
            f"{', '.join(top_phrases[:2])}, and {top_phrases[2]} match what {crop_title} needs to grow well. "
            f"{agronomy['summary']}"
        )

        # Why best_crop beat #2 alternative in plain farmer terms
        comparisons: List[Dict[str, Any]] = []
        for alt_rank in range(1, min(top_k, len(ranked_idx))):
            alt_idx = int(ranked_idx[alt_rank])
            alt_crop = str(self.classes_[alt_idx])
            alt_stats = self.crop_stats_[alt_crop]
            diffs = best_contribs - contribs[alt_idx]
            decisive_j = int(np.argmax(diffs))
            fname = self.feature_names_[decisive_j]
            meta = FEATURE_META[fname]
            val = float(arr[0, decisive_j])
            u_s = f" {meta['unit']}" if meta["unit"] != "pH" else ""
            alt_range = (
                f"{self._fmt_val(fname, alt_stats[fname]['min'])}–"
                f"{self._fmt_val(fname, alt_stats[fname]['max'])}{u_s}"
            )
            best_range = (
                f"{self._fmt_val(fname, crop_stats[fname]['min'])}–"
                f"{self._fmt_val(fname, crop_stats[fname]['max'])}{u_s}"
            )
            v_disp = f"{self._fmt_val(fname, val)}{u_s}"

            comparisons.append(
                {
                    "crop": alt_crop.capitalize(),
                    "reason": (
                        f"Why {crop_title} over {alt_crop.capitalize()}? Your {meta['short'].lower()} "
                        f"({v_disp}) fits {crop_title} ({best_range}) much better than "
                        f"{alt_crop.capitalize()} (which needs {alt_range})."
                    ),
                }
            )

        return {
            "crop": best_crop,
            "confidence": round(best_prob, 4),
            "overall_suitability": overall_suitability,
            "summary": summary,
            "water_note": agronomy.get("water_note", ""),
            "soil_note": agronomy.get("soil_note", ""),
            "factors": factors,
            "comparisons": comparisons,
        }

    def explain(self, X: Union[pd.DataFrame, np.ndarray, Sequence[Any]]) -> List[Dict[str, Any]]:
        X_mat = self._to_matrix(X)
        return [self.explain_reading(row) for row in X_mat]
