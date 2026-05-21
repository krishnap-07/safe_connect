from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ultralytics import YOLO


@dataclass(frozen=True)
class HumanDetectionResult:
    human_detected: bool
    boxes_xyxy: List[Tuple[int, int, int, int]]
    boxes_with_conf: List[Tuple[int, int, int, int, float]]


_yolo_model: Optional["YOLO"] = None


def _get_model(weights: str = "yolov8n.pt") -> "YOLO":
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO(weights)
    return _yolo_model


def detect_humans(image_path: str, *, conf: float = 0.25, iou: float = 0.45) -> HumanDetectionResult:
    """
    Detect humans (COCO class 'person' = 0) in an image using YOLOv8.
    Returns a boolean and bounding boxes.
    """
    try:
        import cv2
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "OpenCV is required for human detection. Install `opencv-python`."
        ) from e

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Unable to read image: {image_path}")

    try:
        # Ultralytics is heavy; import lazily so the web app can still start without it.
        model = _get_model()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "YOLOv8 human detection requires `ultralytics`. Install it (and its deps) to enable human detection."
        ) from e

    results = model.predict(source=img, conf=conf, iou=iou, verbose=False)

    boxes_xyxy: List[Tuple[int, int, int, int]] = []
    boxes_with_conf: List[Tuple[int, int, int, int, float]] = []

    if not results:
        return HumanDetectionResult(False, boxes_xyxy, boxes_with_conf)

    r0 = results[0]
    if r0.boxes is None or r0.boxes.cls is None:
        return HumanDetectionResult(False, boxes_xyxy, boxes_with_conf)

    for box, cls, c in zip(r0.boxes.xyxy, r0.boxes.cls, r0.boxes.conf):
        if int(cls.item()) != 0:
            continue
        x1, y1, x2, y2 = [int(round(v)) for v in box.tolist()]
        conf_score = float(c.item())
        boxes_xyxy.append((x1, y1, x2, y2))
        boxes_with_conf.append((x1, y1, x2, y2, conf_score))

    return HumanDetectionResult(len(boxes_xyxy) > 0, boxes_xyxy, boxes_with_conf)
