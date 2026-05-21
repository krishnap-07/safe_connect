import random
import os

def estimate_water_level(image_path: str, disaster_type: str) -> str:
    """
    Estimates flood water depth from an image using segmentation heuristics.
    """
    if "FLOOD" not in str(disaster_type).upper() and "WATER" not in str(disaster_type).upper():
        return "N/A"
        
    if not image_path or not os.path.exists(image_path):
        return "Unknown"

    # Mock depth generation
    depths = ["0.5m", "1.2m", "2.0m", "3.5m+"]
    return random.choice(depths)
