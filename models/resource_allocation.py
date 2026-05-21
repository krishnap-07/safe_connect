import math
from typing import List, Dict, Any, Tuple, Optional

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def smart_allocate_hospital(
    incident_lat: float, 
    incident_lon: float, 
    incident_severity: str, 
    hospitals: List[Dict[str, Any]], 
    vans: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], str, float]:
    """
    AI Resource Allocation using Weighted Scoring.
    Returns: (Selected Hospital Dict, Allocation Reason String, Distance in KM)
    """
    if not hospitals:
        return None, "No hospitals available.", 0.0

    best_hospital = None
    best_score = -float('inf')
    best_reason = ""
    best_distance = 0.0

    # Weightings depending on severity
    # For critical, distance is heavily weighted.
    # For low, capacity might be weighted more to spread out patients.
    is_critical = incident_severity in ["CRITICAL", "HIGH"]
    w_distance = -0.5 if is_critical else -0.3
    w_beds = 0.3 if is_critical else 0.5
    w_ambulances = 0.2

    for h in hospitals:
        dist_km = haversine_km(incident_lat, incident_lon, float(h["latitude"]), float(h["longitude"]))
        
        # Calculate available beds
        total_beds = h.get("total_beds", 50)
        admitted = h.get("admitted_patients", 0)
        available_beds = max(0, total_beds - admitted)
        
        if available_beds == 0 and is_critical:
            # Skip full hospitals for critical if possible
            continue
            
        # Count available vans assigned to this hospital (or generally nearby)
        # Assuming we can just find vans that are closer to this hospital
        h_vans = [
            v for v in vans 
            if v["status"] == "AVAILABLE" and 
            haversine_km(float(h["latitude"]), float(h["longitude"]), float(v["latitude"]), float(v["longitude"])) < 5.0
        ]
        available_ambulances = len(h_vans)

        # Normalize metrics roughly for scoring
        # dist: 0 to 50km
        # beds: 0 to 100
        # vans: 0 to 10
        norm_dist = min(dist_km / 20.0, 1.0) * 100 
        norm_beds = min(available_beds / 50.0, 1.0) * 100
        norm_vans = min(available_ambulances / 5.0, 1.0) * 100

        score = (w_distance * norm_dist) + (w_beds * norm_beds) + (w_ambulances * norm_vans)
        
        # Add penalty if it's too far
        if dist_km > 30.0:
            score -= 50

        if score > best_score:
            best_score = score
            best_hospital = h
            best_distance = dist_km
            
            # Formulate the reason
            best_reason = f"Score: {score:.1f}. Dist: {dist_km:.1f}km. Beds: {available_beds}. Vans: {available_ambulances}."

    # Fallback to nearest if all failed the strict checks
    if best_hospital is None and hospitals:
        hospitals.sort(key=lambda h: haversine_km(incident_lat, incident_lon, float(h["latitude"]), float(h["longitude"])))
        best_hospital = hospitals[0]
        best_distance = haversine_km(incident_lat, incident_lon, float(best_hospital["latitude"]), float(best_hospital["longitude"]))
        best_reason = "Fallback to nearest due to all hospitals being full."

    return best_hospital, best_reason, best_distance
