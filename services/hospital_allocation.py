from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Hospital:
    name: str
    latitude: float
    longitude: float


DEFAULT_HOSPITALS: List[Hospital] = [
    Hospital(name="Sassoon General Hospital",
             latitude=18.5286, longitude=73.8743),
    Hospital(name="Jehangir Hospital", latitude=18.5362, longitude=73.8849),
    Hospital(name="Ruby Hall Clinic", latitude=18.5368, longitude=73.8788),
    Hospital(name="Deenanath Mangeshkar Hospital",
             latitude=18.5079, longitude=73.8077),
    Hospital(name="KEM Hospital Pune", latitude=18.5048, longitude=73.8628),
    Hospital(name="Noble Hospital Hadapsar",
             latitude=18.4964, longitude=73.9260),
]

PUNE_BOUNDS = {
    "lat_min": 18.40,
    "lat_max": 18.68,
    "lon_min": 73.72,
    "lon_max": 74.05,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points (km).
    """
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * \
        math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def select_nearest_hospital(
    incident_lat: float,
    incident_lon: float,
    hospitals: Optional[Iterable[Hospital]] = None,
) -> Tuple[Hospital, float]:
    """
    Select the nearest hospital from a list using Haversine distance.
    Returns (hospital, distance_km).
    """
    hospitals = list(hospitals) if hospitals is not None else DEFAULT_HOSPITALS
    if not hospitals:
        raise ValueError("No hospitals available for allocation.")

    best = hospitals[0]
    best_dist = haversine_km(incident_lat, incident_lon,
                             best.latitude, best.longitude)

    for h in hospitals[1:]:
        d = haversine_km(incident_lat, incident_lon, h.latitude, h.longitude)
        if d < best_dist:
            best = h
            best_dist = d

    return best, float(best_dist)


def hospitals_from_rows(rows: List[Dict[str, Any]]) -> List[Hospital]:
    parsed: List[Hospital] = []
    for row in rows:
        parsed.append(Hospital(name=row["name"], latitude=float(
            row["latitude"]), longitude=float(row["longitude"])))
    return parsed


def is_pune_area(latitude: float, longitude: float) -> bool:
    return (
        PUNE_BOUNDS["lat_min"] <= float(latitude) <= PUNE_BOUNDS["lat_max"]
        and PUNE_BOUNDS["lon_min"] <= float(longitude) <= PUNE_BOUNDS["lon_max"]
    )


def filter_pune_hospital_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if is_pune_area(float(row["latitude"]), float(row["longitude"]))]
