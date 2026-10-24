"""SoilSage Explainable Crop Recommendation Model package."""
import sys
from . import ebm_model
from .ebm_model import AgronomicEBMClassifier, CROP_AGRONOMY, FEATURE_META, FEATURE_NAMES

# Backward-compatibility alias for legacy pickled models referencing 'random_forest'
sys.modules.setdefault("random_forest", sys.modules[__name__])
sys.modules.setdefault("random_forest.ebm_model", ebm_model)

__all__ = [
    "AgronomicEBMClassifier",
    "CROP_AGRONOMY",
    "FEATURE_META",
    "FEATURE_NAMES",
]
