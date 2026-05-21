from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DisasterPrediction:
    label: str
    confidence: float
    probabilities: Dict[str, float]


_model: Optional[object] = None
_labels: Optional[List[str]] = None


def _default_paths() -> Tuple[Path, Path]:
    base_dir = Path(__file__).resolve().parent
    model_path = base_dir / "disaster_model.h5"
    labels_path = base_dir / "disaster_labels.json"
    return model_path, labels_path


def load_disaster_model(model_path: Optional[str] = None, labels_path: Optional[str] = None) -> None:
    global _model, _labels

    mp, lp = _default_paths()
    model_path = Path(model_path) if model_path else mp
    labels_path = Path(labels_path) if labels_path else lp

    if not model_path.exists():
        raise FileNotFoundError(
            f"Disaster model not found at {model_path}. Train it with `python train_model.py`."
        )
    if not labels_path.exists():
        raise FileNotFoundError(
            f"Labels file not found at {labels_path}. Train it with `python train_model.py`."
        )

    try:
        import tensorflow as tf  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "TensorFlow is required for disaster classification. Install a TensorFlow version compatible with your Python."
        ) from e

    _model = tf.keras.models.load_model(str(model_path))
    _labels = json.loads(labels_path.read_text(encoding="utf-8"))


def _ensure_loaded() -> None:
    if _model is None or _labels is None:
        load_disaster_model()


def predict_disaster(image_path: str, *, image_size: int = 224) -> DisasterPrediction:
    """
    Predict disaster type from an image using a trained MobileNetV2-based classifier.
    Expects `models/disaster_model.h5` and `models/disaster_labels.json` to exist.
    """
    _ensure_loaded()
    assert _model is not None
    assert _labels is not None

    # Import lazily so the Flask app can start without TensorFlow installed.
    try:
        from tensorflow.keras.applications.mobilenet_v2 import preprocess_input  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "TensorFlow is required for disaster classification preprocessing."
        ) from e

    try:
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Disaster classification requires `numpy` and `pillow`."
        ) from e

    img = Image.open(image_path).convert("RGB").resize((image_size, image_size))
    arr = np.asarray(img, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)
    arr = preprocess_input(arr)

    probs = _model.predict(arr, verbose=0)[0]
    probs = np.asarray(probs, dtype=np.float32)

    if probs.ndim != 1 or probs.shape[0] != len(_labels):
        raise ValueError("Model output does not match labels length.")

    idx = int(np.argmax(probs))
    label = str(_labels[idx])
    confidence = float(probs[idx])
    prob_map = {str(lbl): float(p) for lbl, p in zip(_labels, probs)}

    return DisasterPrediction(label=label, confidence=confidence, probabilities=prob_map)

