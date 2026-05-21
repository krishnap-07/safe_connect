from __future__ import annotations


def decide_priority(num_humans: int, disaster_type: str, disaster_conf: float) -> tuple[str, int]:
    """
    Decision rule:
    - If humans are detected (num_humans > 0) -> HIGH priority (>90 depending on number)
    - If no humans but disaster classified (conf > 0.5) -> MEDIUM priority (>70)
    - Else -> LOW priority
    """
    if num_humans > 0:
        score = min(90 + num_humans * 2, 100)
        return "HIGH", score
    elif disaster_conf > 0.5 and disaster_type not in ("unknown", "None", "", None):
        return "MEDIUM", 75
    return "LOW", 45
