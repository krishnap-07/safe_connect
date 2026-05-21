from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import threading
from typing import Dict, Optional

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database.db import (
    create_hospital,
    get_all_hospitals,
    get_all_incidents,
    get_hospital_by_id,
    get_hospital_by_username,
    get_patient_records_for_hospital,
    insert_incident,
    update_status,
    upsert_patient_record,
    update_hospital_details,
    approve_hospital,
    delete_hospital,
    get_incident_by_id,
    create_notification,
    _connect,
)
from models.disaster_classifier import DisasterPrediction, predict_disaster
from models.human_detection import HumanDetectionResult, detect_humans
from models.damage_assessment import assess_damage
from models.flood_estimation import estimate_water_level
from models.resource_allocation import smart_allocate_hospital
from models.severity_prediction import predict_severity
from services.hospital_allocation import (
    filter_pune_hospital_rows,
    is_pune_area,
    haversine_km,
)
from services.telegram_bot import send_telegram_alert, send_final_report_telegram


incidents_bp = Blueprint("incidents", __name__)


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def _officer_credentials() -> tuple[str, str]:
    user = current_app.config.get("OFFICER_USERNAME", "officer")
    password = current_app.config.get("OFFICER_PASSWORD", "officer123")
    return str(user), str(password)


def _officer_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "OFFICER":
            return redirect(url_for("incidents.officer_login"))
        return func(*args, **kwargs)

    return wrapper


def _hospital_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "HOSPITAL":
            return redirect(url_for("incidents.hospital_login"))
        return func(*args, **kwargs)

    return wrapper


def _severity_from_score(priority_score: int) -> str:
    if priority_score >= 90:
        return "CRITICAL"
    if priority_score >= 75:
        return "HIGH"
    if priority_score >= 50:
        return "MEDIUM"
    return "LOW"


@incidents_bp.get("/")
def index():
    return render_template("index.html")


@incidents_bp.get("/citizen")
def citizen():
    return render_template("citizen.html")


@incidents_bp.route("/officer/login", methods=["GET", "POST"])
def officer_login():
    if request.method == "GET":
        return render_template("officer_login.html")

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    expected_user, expected_pass = _officer_credentials()

    if username == expected_user and password == expected_pass:
        session["role"] = "OFFICER"
        session["officer_name"] = username
        return redirect(url_for("incidents.dashboard"))

    flash("Invalid officer credentials.", "error")
    return render_template("officer_login.html"), 401


@incidents_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("incidents.index"))


@incidents_bp.get("/dashboard")
@_officer_required
def dashboard():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    all_hospitals = filter_pune_hospital_rows(
        get_all_hospitals(current_app.config["SQLITE_PATH"]))
    approved_hospitals = [
        h for h in all_hospitals if h.get("status") == "APPROVED"]
    pending_hospitals = [
        h for h in all_hospitals if h.get("status") == "PENDING"]

    # Calculate nearest distance for pending hospitals
    for ph in pending_hospitals:
        min_dist = float('inf')
        for ah in approved_hospitals:
            d = haversine_km(ph["latitude"], ph["longitude"],
                             ah["latitude"], ah["longitude"])
            if d < min_dist:
                min_dist = d
        ph["nearest_distance"] = min_dist if min_dist != float('inf') else 0

    hospitals_by_id = {h["id"]: h for h in approved_hospitals}
    for incident in incidents:
        incident["severity"] = _severity_from_score(
            int(incident.get("priority_score") or 0))
        assigned_id = incident.get("assigned_hospital_id")
        assigned_hospital = hospitals_by_id.get(assigned_id)
        incident["assigned_hospital_name"] = assigned_hospital["name"] if assigned_hospital else "Unassigned"

        dtype = (incident.get("disaster_type") or "").upper()
        if "FIRE" in dtype:
            team = "Fire Brigade"
        elif "EARTHQUAKE" in dtype:
            team = "NDRF Rescue Team"
        elif "FLOOD" in dtype or "WATER" in dtype:
            team = "Coast Guard / Navy"
        elif "MEDICAL" in dtype or "INJURY" in dtype or "ACCIDENT" in dtype:
            team = "Ambulance & Medical Team"
        else:
            team = "Local Police"
        incident["help_team"] = team

    summary = {
        "total_incidents": len(incidents),
        "radar_alerts": len(
            [i for i in incidents if bool(i.get("human_detected")) and int(i.get(
                "priority_score") or 0) >= 90 and i["status"] not in ("RESOLVED", "CLOSED")]
        ),
        "total_hospitals": len(approved_hospitals),
    }
    return render_template("dashboard.html", incidents=incidents, hospitals=approved_hospitals, pending_hospitals=pending_hospitals, summary=summary)


@incidents_bp.get("/dashboard/past-incidents")
@_officer_required
def past_incidents():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    hospitals = filter_pune_hospital_rows(
        get_all_hospitals(current_app.config["SQLITE_PATH"]))
    hospitals_by_id = {h["id"]: h for h in hospitals}
    allocated = []
    for incident in incidents:
        assigned_id = incident.get("assigned_hospital_id")
        if assigned_id is None:
            continue
        incident["severity"] = _severity_from_score(
            int(incident.get("priority_score") or 0))
        assigned_hospital = hospitals_by_id.get(assigned_id)
        incident["assigned_hospital_name"] = assigned_hospital["name"] if assigned_hospital else "Unknown"
        allocated.append(incident)
    return render_template("past_incidents.html", incidents=allocated)


@incidents_bp.get("/api/incidents")
@_officer_required
def api_incidents():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    return jsonify(incidents)


@incidents_bp.post("/incidents/<int:incident_id>/status")
@_officer_required
def set_incident_status(incident_id: int):
    new_status = request.form.get("status", "").strip()
    if not new_status:
        return jsonify({"success": False, "message": "Missing status"}), 400
    update_status(current_app.config["SQLITE_PATH"], incident_id, new_status)
    return redirect(url_for("incidents.dashboard"))


@incidents_bp.post("/officer/hospital/<int:hospital_id>/approve")
@_officer_required
def approve_hospital_route(hospital_id: int):
    approve_hospital(current_app.config["SQLITE_PATH"], hospital_id)
    flash("Hospital approved successfully.", "ok")
    return redirect(url_for("incidents.dashboard"))


@incidents_bp.post("/officer/hospital/<int:hospital_id>/delete")
@_officer_required
def delete_hospital_route(hospital_id: int):
    delete_hospital(current_app.config["SQLITE_PATH"], hospital_id)
    flash("Hospital request rejected and deleted.", "ok")
    return redirect(url_for("incidents.dashboard"))


@incidents_bp.post("/report")
def report():
    description = (request.form.get("description") or "").strip()
    lat = request.form.get("latitude", type=float)
    lon = request.form.get("longitude", type=float)
    file = request.files.get("image")

    if not description:
        return jsonify({"success": False, "message": "Description is required"}), 400
    if lat is None or lon is None:
        return jsonify({"success": False, "message": "Latitude/Longitude are required"}), 400
    if file is None or file.filename == "":
        return jsonify({"success": False, "message": "Image is required"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"success": False, "message": "Unsupported image type"}), 400

    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    image_path = uploads_dir / unique_name
    file.save(str(image_path))

    warnings = []

    try:
        human: HumanDetectionResult = detect_humans(str(image_path))
    except Exception as e:
        warnings.append(f"Human detection unavailable: {e}")
        human = HumanDetectionResult(False, [], [])

    try:
        pred: DisasterPrediction = predict_disaster(str(image_path))
        disaster_type = pred.label
        disaster_conf = pred.confidence
    except FileNotFoundError:
        disaster_type = "unknown"
        disaster_conf = 0.0
        warnings.append(
            "Disaster classifier model not found. Train it with `python train_model.py` to enable predictions.")
    except Exception as e:
        disaster_type = "unknown"
        disaster_conf = 0.0
        warnings.append(f"Disaster classification unavailable: {e}")

    # Advanced CV calls
    damage_level = assess_damage(str(image_path))
    water_depth = estimate_water_level(str(image_path), disaster_type)

    # ML Multimodal Severity Prediction
    try:
        priority, priority_score = predict_severity(
            report_text=description,
            disaster_type=disaster_type,
            human_count=len(human.boxes_with_conf),
            damage_level=damage_level
        )
    except Exception as e:
        warnings.append(
            f"AI Severity Prediction failed ({e}), falling back to defaults.")
        priority, priority_score = "MEDIUM", 50

    all_hospital_rows = filter_pune_hospital_rows(
        get_all_hospitals(current_app.config["SQLITE_PATH"]))
    approved_hospitals = [
        h for h in all_hospital_rows if h.get("status") == "APPROVED"]

    matched_hospital: Optional[Dict[str, Any]] = None
    distance_km: Optional[float] = None
    hospital_name = "UNASSIGNED"
    hospital_lat = None
    hospital_lon = None
    allocation_reason = ""

    if approved_hospitals:
        matched_hospital, allocation_reason, distance_km = smart_allocate_hospital(
            lat, lon, priority, approved_hospitals, [])
        if matched_hospital:
            hospital_name = matched_hospital["name"]
            hospital_lat = matched_hospital["latitude"]
            hospital_lon = matched_hospital["longitude"]
    else:
        warnings.append(
            "No registered Pune hospitals available for allocation.")

    incident_id = insert_incident(
        current_app.config["SQLITE_PATH"],
        description=description,
        latitude=lat,
        longitude=lon,
        disaster_type=disaster_type,
        human_detected=human.human_detected,
        priority=priority,
        priority_score=priority_score,
        status="NEW",
        assigned_hospital_id=matched_hospital["id"] if matched_hospital else None,
        report_source="PUBLIC",
        image_path=unique_name,
        damage_level=damage_level,
        water_depth=water_depth,
        human_count=len(human.boxes_with_conf),
    )

    # Asynchronously trigger the AI Telegram Broadcast
    threading.Thread(target=send_telegram_alert, kwargs=dict(
        lat=lat,
        lon=lon,
        description=description,
        disaster_type=disaster_type,
        priority=priority,
        priority_score=priority_score,
        human_detected=human.human_detected,
        human_count=len(human.boxes_with_conf),
        damage_level=damage_level,
        water_depth=water_depth,
        hospital_name=hospital_name,
        image_path=unique_name,
    )).start()

    return jsonify(
        {
            "success": True,
            "incident": {
                "id": incident_id,
                "description": description,
                "latitude": lat,
                "longitude": lon,
                "disaster_type": disaster_type,
                "disaster_confidence": disaster_conf,
                "human_detected": human.human_detected,
                "boxes": human.boxes_with_conf,
                "priority": priority,
                "priority_score": priority_score,
                "status": "NEW",
                "damage_level": damage_level,
                "water_depth": water_depth,
                "human_count": len(human.boxes_with_conf),
            },
            "allocation": {
                "hospital": {"name": hospital_name, "latitude": hospital_lat, "longitude": hospital_lon},
                "distance_km": distance_km,
                "reason": allocation_reason,
            },
            "warnings": warnings,
        }
    )


@incidents_bp.route("/hospital/register", methods=["GET", "POST"])
def hospital_register():
    all_hospitals = get_all_hospitals(current_app.config["SQLITE_PATH"])
    approved_hospitals = [
        h for h in all_hospitals if h.get("status") == "APPROVED"]
    if request.method == "GET":
        return render_template("hospital_register.html", hospitals=approved_hospitals)

    name = (request.form.get("name") or "").strip()
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    message = (request.form.get("message") or "").strip()
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)
    file = request.files.get("image")

    if not all([name, username, password, message]) or latitude is None or longitude is None or not file:
        flash("All fields and image are required.", "error")
        return render_template("hospital_register.html"), 400
    if not is_pune_area(latitude, longitude):
        flash("Only Pune area hospitals can be registered.", "error")
        return render_template("hospital_register.html"), 400

    if get_hospital_by_username(current_app.config["SQLITE_PATH"], username):
        flash("Username already exists.", "error")
        return render_template("hospital_register.html"), 409

    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    unique_name = f"hospital_{uuid.uuid4().hex}_{safe_name}"
    image_path = uploads_dir / unique_name
    file.save(str(image_path))

    create_hospital(
        current_app.config["SQLITE_PATH"],
        name=name,
        username=username,
        password_hash=generate_password_hash(password),
        latitude=latitude,
        longitude=longitude,
        status="PENDING",
        image_path=unique_name,
        message=message
    )

    # Notify Officer
    with _connect(current_app.config["SQLITE_PATH"]) as conn:
        conn.execute(
            "INSERT INTO notifications (target_role, message, created_at) VALUES (?, ?, ?)",
            ("OFFICER", f"New hospital registration request from {name}.", datetime.now(
                timezone.utc).isoformat())
        )
        conn.commit()

    flash("Hospital registered successfully! The Officer has been notified and must approve your request before you can log in.", "ok")
    return redirect(url_for("incidents.hospital_login"))


@incidents_bp.route("/hospital/login", methods=["GET", "POST"])
def hospital_login():
    if request.method == "GET":
        return render_template("hospital_login.html")

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    hospital = get_hospital_by_username(
        current_app.config["SQLITE_PATH"], username)

    if not hospital or not check_password_hash(hospital["password_hash"], password):
        flash("Invalid hospital credentials.", "error")
        return render_template("hospital_login.html"), 401

    if hospital.get("status") != "APPROVED":
        flash("Your account is pending Officer approval. Please wait for the Officer to approve your registration.", "error")
        return render_template("hospital_login.html"), 401

    session["role"] = "HOSPITAL"
    session["hospital_id"] = hospital["id"]
    session["hospital_name"] = hospital["name"]
    return redirect(url_for("incidents.hospital_dashboard"))


@incidents_bp.route("/hospital/dashboard", methods=["GET", "POST"])
@_hospital_required
def hospital_dashboard():
    hospital = get_hospital_by_id(
        current_app.config["SQLITE_PATH"], int(session["hospital_id"]))
    if hospital is None:
        session.clear()
        return redirect(url_for("incidents.hospital_login"))

    if request.method == "POST":
        incident_id = request.form.get("incident_id", type=int)
        patient_name = (request.form.get("patient_name") or "").strip()
        condition_status = (request.form.get("condition_status") or "").strip()
        admitted = (request.form.get("admitted") or "yes") == "yes"
        notes = (request.form.get("notes") or "").strip()
        record_id = request.form.get("record_id", type=int)
        if not patient_name or not condition_status:
            flash("Patient name and condition are required.", "error")
        else:
            upsert_patient_record(
                current_app.config["SQLITE_PATH"],
                hospital_id=hospital["id"],
                incident_id=incident_id,
                patient_name=patient_name,
                condition_status=condition_status,
                admitted=admitted,
                notes=notes,
                record_id=record_id,
            )
            flash("Patient record saved.", "ok")
        return redirect(url_for("incidents.hospital_dashboard"))

    records = get_patient_records_for_hospital(
        current_app.config["SQLITE_PATH"], hospital["id"])
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    assigned = [i for i in incidents if i.get(
        "assigned_hospital_id") == hospital["id"]]

    return render_template(
        "hospital_dashboard.html",
        hospital=hospital,
        records=records,
        incidents=assigned,
    )


@incidents_bp.post("/hospital/update-details")
@_hospital_required
def update_hospital_details_route():
    hospital_id = int(session["hospital_id"])
    total_beds = request.form.get("total_beds", type=int)

    if total_beds is not None and total_beds >= 0:
        update_hospital_details(
            current_app.config["SQLITE_PATH"], hospital_id, total_beds)
        flash(f"Hospital capacity updated to {total_beds} beds.", "ok")
    else:
        flash("Invalid bed capacity.", "error")

    return redirect(url_for("incidents.hospital_dashboard"))


@incidents_bp.get("/hospital/past-patients")
@_hospital_required
def hospital_past_patients():
    hospital = get_hospital_by_id(
        current_app.config["SQLITE_PATH"], int(session["hospital_id"]))
    if hospital is None:
        session.clear()
        return redirect(url_for("incidents.hospital_login"))

    records = get_patient_records_for_hospital(
        current_app.config["SQLITE_PATH"], hospital["id"])
    return render_template("hospital_past_patients.html", hospital=hospital, records=records)


@incidents_bp.get("/api/ops-map")
@_officer_required
def ops_map_data():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    all_hospitals = filter_pune_hospital_rows(
        get_all_hospitals(current_app.config["SQLITE_PATH"]))
    approved_hospitals = [
        h for h in all_hospitals if h.get("status") == "APPROVED"]
    hospitals_by_id = {h["id"]: h for h in approved_hospitals}
    for incident in incidents:
        incident["severity"] = _severity_from_score(
            int(incident.get("priority_score") or 0))
        assigned_id = incident.get("assigned_hospital_id")
        assigned_hospital = hospitals_by_id.get(assigned_id)
        incident["assigned_hospital_name"] = assigned_hospital["name"] if assigned_hospital else "Unassigned"
    radar_incidents = [
        i for i in incidents if bool(i.get("human_detected")) and int(i.get("priority_score") or 0) >= 90 and i["status"] not in ("RESOLVED", "CLOSED")
    ]
    return jsonify({"incidents": incidents, "radar_incidents": radar_incidents, "hospitals": approved_hospitals, "vans": []})


@incidents_bp.get("/api/public-radars")
def public_radars():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    all_hospitals = filter_pune_hospital_rows(
        get_all_hospitals(current_app.config["SQLITE_PATH"]))
    approved_hospitals = [
        h for h in all_hospitals if h.get("status") == "APPROVED"]
    radar_incidents = []
    active_incidents = []
    for incident in incidents:
        priority_score = int(incident.get("priority_score") or 0)

        if incident["status"] in ["NEW", "IN_PROGRESS"]:
            active_incidents.append(incident)

        if not bool(incident.get("human_detected")):
            continue

        if incident["status"] in ["RESOLVED", "CLOSED"]:
            continue

        incident["severity"] = _severity_from_score(priority_score)
        radar_incidents.append(incident)

    return jsonify({
        "radar_incidents": radar_incidents,
        "hospitals": approved_hospitals,
        "vans": [],
        "active_incidents": active_incidents
    })


@incidents_bp.get("/api/nearby-incidents")
def nearby_incidents():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"incidents": []})

    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    hospitals = get_all_hospitals(current_app.config["SQLITE_PATH"])
    hospitals_by_id = {h["id"]: h for h in hospitals}

    results = []
    for inc in incidents:
        dist = haversine_km(lat, lon, float(
            inc["latitude"]), float(inc["longitude"]))
        assigned_h = hospitals_by_id.get(inc.get("assigned_hospital_id"))
        hospital_name = assigned_h["name"] if assigned_h else "Unassigned"

        results.append({
            "id": inc["id"],
            "disaster_type": inc["disaster_type"],
            "distance_km": dist,
            "status": inc["status"],
            "assigned_hospital_name": hospital_name
        })

    results.sort(key=lambda x: x["distance_km"])
    return jsonify({"incidents": results[:5]})


@incidents_bp.get("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@incidents_bp.get("/api/notifications")
def get_notifications():
    incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    role = session.get("role")

    if role == "OFFICER":
        recent = [i for i in incidents if i["status"] == "NEW"][:5]
        return jsonify({"notifications": recent})
    elif role == "HOSPITAL":
        hospital_id = session.get("hospital_id")
        recent = [i for i in incidents if i["status"] ==
                  "NEW" and i.get("assigned_hospital_id") == hospital_id][:5]
        return jsonify({"notifications": recent})
    return jsonify({"notifications": []})


@incidents_bp.post("/hospital/plan_executed/<int:incident_id>")
@_hospital_required
def plan_executed(incident_id: int):
    update_status(current_app.config["SQLITE_PATH"],
                  incident_id, "IN_PROGRESS")
    flash("Plan Executed. Incident is now in progress.", "ok")
    return redirect(url_for("incidents.hospital_dashboard"))


@incidents_bp.post("/officer/execution_completed/<int:incident_id>")
@_officer_required
def execution_completed(incident_id: int):
    update_status(current_app.config["SQLITE_PATH"], incident_id, "RESOLVED")
    return redirect(url_for("incidents.dashboard"))


@incidents_bp.get("/api/hospital/<int:hospital_id>/report")
@_officer_required
def get_hospital_report(hospital_id: int):
    hospital = get_hospital_by_id(
        current_app.config["SQLITE_PATH"], hospital_id)
    if not hospital:
        return jsonify({"success": False, "message": "Hospital not found"}), 404

    all_incidents = get_all_incidents(current_app.config["SQLITE_PATH"])
    assigned_incidents = [i for i in all_incidents if i.get(
        "assigned_hospital_id") == hospital_id]

    patient_records = get_patient_records_for_hospital(
        current_app.config["SQLITE_PATH"], hospital_id)
    admitted_patients = [p for p in patient_records if p.get("admitted") == 1]

    return jsonify({
        "success": True,
        "hospital": hospital,
        "incidents": assigned_incidents,
        "patients": admitted_patients
    })


@incidents_bp.get("/api/incident/<int:incident_id>/details")
@_officer_required
def get_incident_details(incident_id: int):
    incident = get_incident_by_id(
        current_app.config["SQLITE_PATH"], incident_id)
    if not incident:
        return jsonify({"success": False, "message": "Incident not found"}), 404

    return jsonify({
        "success": True,
        "incident": incident
    })


@incidents_bp.post("/officer/escalate/<int:incident_id>")
@_officer_required
def escalate_incident(incident_id: int):
    incident = get_incident_by_id(
        current_app.config["SQLITE_PATH"], incident_id)
    if not incident:
        flash("Incident not found.", "error")
        return redirect(url_for("incidents.dashboard"))

    all_hospitals = get_all_hospitals(current_app.config["SQLITE_PATH"])
    # Exclude currently assigned
    candidates = [
        h for h in all_hospitals
        if h.get("status") == "APPROVED" and h.get("id") != incident.get("assigned_hospital_id")
    ]

    # We need a severity string, fallback to HIGH if unknown
    severity = incident.get("severity")
    if not severity and incident.get("priority_score"):
        # Roughly calculate severity from priority_score as done in public_radars
        score = int(incident["priority_score"])
        if score >= 80:
            severity = "CRITICAL"
        elif score >= 60:
            severity = "HIGH"
        elif score >= 40:
            severity = "MEDIUM"
        else:
            severity = "LOW"
    elif not severity:
        severity = "HIGH"

    best_hospital, reason, distance = smart_allocate_hospital(
        float(incident["latitude"]),
        float(incident["longitude"]),
        severity,
        candidates,
        []
    )

    if best_hospital:
        message = f"🚨 ESCALATION: Backup requested for Incident #{incident['id']} ({incident['disaster_type']}). Please prepare for overflow."
        create_notification(
            current_app.config["SQLITE_PATH"], "HOSPITAL", best_hospital["id"], message)
        flash(
            f"Escalation sent to backup hospital: {best_hospital['name']}", "ok")
    else:
        flash("No backup hospitals available to notify.", "error")

    return redirect(url_for("incidents.dashboard"))


@incidents_bp.get("/api/incident/<int:incident_id>/final-report")
@_officer_required
def get_incident_final_report(incident_id: int):
    incident = get_incident_by_id(
        current_app.config["SQLITE_PATH"], incident_id)
    if not incident:
        return jsonify({"success": False, "message": "Incident not found"}), 404

    # Get all patients for this incident by checking all hospital records, or just querying DB directly.
    # We can query DB directly
    db_path = current_app.config["SQLITE_PATH"]
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM patient_records WHERE incident_id = ?", (incident_id,)).fetchall()

    records = [dict(r) for r in rows]
    rescued_count = sum(1 for r in records if r.get(
        "condition_status") != "DEAD")
    dead_count = sum(1 for r in records if r.get("condition_status") == "DEAD")

    # Get assigned hospital name
    hospital_name = "Unassigned"
    if incident.get("assigned_hospital_id"):
        from database.db import get_hospital_by_id
        hospital = get_hospital_by_id(
            db_path, incident["assigned_hospital_id"])
        if hospital:
            hospital_name = hospital["name"]

    return jsonify({
        "success": True,
        "incident": incident,
        "hospital_name": hospital_name,
        "rescued_count": rescued_count,
        "dead_count": dead_count
    })


@incidents_bp.post("/officer/incident/<int:incident_id>/post-final-news")
@_officer_required
def post_final_news(incident_id: int):
    incident = get_incident_by_id(
        current_app.config["SQLITE_PATH"], incident_id)
    if not incident:
        flash("Incident not found.", "error")
        return redirect(url_for("incidents.past_incidents"))

    db_path = current_app.config["SQLITE_PATH"]
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM patient_records WHERE incident_id = ?", (incident_id,)).fetchall()

    records = [dict(r) for r in rows]
    rescued_count = sum(1 for r in records if r.get(
        "condition_status") != "DEAD")
    dead_count = sum(1 for r in records if r.get("condition_status") == "DEAD")

    hospital_name = "Unassigned"
    if incident.get("assigned_hospital_id"):
        from database.db import get_hospital_by_id
        hospital = get_hospital_by_id(
            db_path, incident["assigned_hospital_id"])
        if hospital:
            hospital_name = hospital["name"]

    success = send_final_report_telegram(
        incident, rescued_count, dead_count, hospital_name)

    if success:
        flash("Final news broadcasted successfully to Telegram!", "ok")
    else:
        flash("Failed to broadcast final news.", "error")

    return redirect(url_for("incidents.past_incidents"))
