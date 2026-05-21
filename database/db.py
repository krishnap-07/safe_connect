import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


INCIDENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    disaster_type TEXT NOT NULL,
    human_detected INTEGER NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    image_path TEXT,
    created_at TEXT NOT NULL
);
"""

HOSPITALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS hospitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    total_beds INTEGER NOT NULL DEFAULT 50,
    status TEXT NOT NULL DEFAULT 'PENDING',
    image_path TEXT,
    message TEXT,
    created_at TEXT NOT NULL
);
"""

PATIENT_RECORDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS patient_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id INTEGER NOT NULL,
    incident_id INTEGER,
    patient_name TEXT NOT NULL,
    condition_status TEXT NOT NULL,
    admitted INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(hospital_id) REFERENCES hospitals(id),
    FOREIGN KEY(incident_id) REFERENCES incidents(id)
);
"""

NOTIFICATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_role TEXT NOT NULL,
    target_hospital_id INTEGER,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(INCIDENTS_SCHEMA)
        conn.execute(HOSPITALS_SCHEMA)
        conn.execute(PATIENT_RECORDS_SCHEMA)
        conn.execute(NOTIFICATIONS_SCHEMA)
        for migration_sql in [
            "ALTER TABLE incidents ADD COLUMN priority_score INTEGER DEFAULT 0",
            "ALTER TABLE incidents ADD COLUMN assigned_hospital_id INTEGER REFERENCES hospitals(id)",
            "ALTER TABLE incidents ADD COLUMN report_source TEXT NOT NULL DEFAULT 'PUBLIC'",
            "ALTER TABLE incidents ADD COLUMN image_path TEXT",
            "ALTER TABLE incidents ADD COLUMN damage_level TEXT",
            "ALTER TABLE incidents ADD COLUMN water_depth TEXT",
            "ALTER TABLE incidents ADD COLUMN human_count INTEGER DEFAULT 0",
            "ALTER TABLE incidents ADD COLUMN informer_name TEXT",
            "ALTER TABLE incidents ADD COLUMN informer_contact TEXT",
            "ALTER TABLE hospitals ADD COLUMN total_beds INTEGER NOT NULL DEFAULT 50",
            "ALTER TABLE hospitals ADD COLUMN status TEXT NOT NULL DEFAULT 'APPROVED'",
            "ALTER TABLE hospitals ADD COLUMN image_path TEXT",
            "ALTER TABLE hospitals ADD COLUMN message TEXT",
            "DROP TABLE IF EXISTS rescue_vans",
        ]:
            try:
                conn.execute(migration_sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()


def insert_incident(
    db_path: str,
    *,
    description: str,
    latitude: float,
    longitude: float,
    disaster_type: str,
    human_detected: bool,
    priority: str,
    priority_score: int,
    status: str = "NEW",
    created_at: Optional[str] = None,
    assigned_hospital_id: Optional[int] = None,
    report_source: str = "PUBLIC",
    image_path: Optional[str] = None,
    damage_level: Optional[str] = None,
    water_depth: Optional[str] = None,
    human_count: int = 0,
) -> int:
    created_at = created_at or datetime.now(timezone.utc).isoformat()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO incidents
                (
                    description, latitude, longitude, disaster_type, human_detected, priority, priority_score,
                    status, created_at, assigned_hospital_id, report_source, image_path, damage_level, water_depth, human_count
                )
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                description,
                float(latitude),
                float(longitude),
                disaster_type,
                1 if human_detected else 0,
                priority,
                int(priority_score),
                status,
                created_at,
                assigned_hospital_id,
                report_source,
                image_path,
                damage_level,
                water_depth,
                human_count,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_all_incidents(db_path: str) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY datetime(created_at) DESC, id DESC").fetchall()
        return [dict(r) for r in rows]


def get_incident_by_id(db_path: str, incident_id: int) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?",
                           (int(incident_id),)).fetchone()
        return dict(row) if row else None


def update_status(db_path: str, incident_id: int, new_status: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE incidents SET status = ? WHERE id = ?",
                     (new_status, int(incident_id)))
        conn.commit()


def create_hospital(
    db_path: str,
    *,
    name: str,
    username: str,
    password_hash: str,
    latitude: float,
    longitude: float,
    total_beds: int = 50,
    status: str = "PENDING",
    image_path: Optional[str] = None,
    message: Optional[str] = None,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO hospitals (name, username, password_hash, latitude, longitude, total_beds, status, image_path, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, username, password_hash, float(latitude), float(longitude),
             int(total_beds), status, image_path, message, created_at),
        )
        hospital_id = int(cur.lastrowid)

        conn.commit()
        return hospital_id


def approve_hospital(db_path: str, hospital_id: int) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE hospitals SET status = 'APPROVED' WHERE id = ?", (int(hospital_id),))
        conn.commit()


def delete_hospital(db_path: str, hospital_id: int) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM hospitals WHERE id = ?", (int(hospital_id),))
        conn.commit()


def update_hospital_details(db_path: str, hospital_id: int, total_beds: int) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE hospitals SET total_beds = ? WHERE id = ?",
            (int(total_beds), int(hospital_id))
        )
        conn.commit()


def get_hospital_by_username(db_path: str, username: str) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM hospitals WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_hospital_by_id(db_path: str, hospital_id: int) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM hospitals WHERE id = ?",
                           (int(hospital_id),)).fetchone()
        return dict(row) if row else None


def get_all_hospitals(db_path: str) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                h.*,
                COALESCE(SUM(CASE WHEN pr.admitted = 1 THEN 1 ELSE 0 END), 0) AS admitted_patients
            FROM hospitals h
            LEFT JOIN patient_records pr ON pr.hospital_id = h.id
            GROUP BY h.id
            ORDER BY datetime(h.created_at) DESC, h.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_patient_record(
    db_path: str,
    *,
    hospital_id: int,
    incident_id: Optional[int],
    patient_name: str,
    condition_status: str,
    admitted: bool,
    notes: str,
    record_id: Optional[int] = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        if record_id is None:
            cur = conn.execute(
                """
                INSERT INTO patient_records
                    (hospital_id, incident_id, patient_name, condition_status, admitted, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(hospital_id), incident_id, patient_name,
                 condition_status, 1 if admitted else 0, notes, now, now),
            )
            conn.commit()
            return int(cur.lastrowid)

        conn.execute(
            """
            UPDATE patient_records
            SET patient_name = ?, condition_status = ?, admitted = ?, notes = ?, updated_at = ?
            WHERE id = ? AND hospital_id = ?
            """,
            (patient_name, condition_status, 1 if admitted else 0,
             notes, now, int(record_id), int(hospital_id)),
        )
        conn.commit()
        return int(record_id)


def get_patient_records_for_hospital(db_path: str, hospital_id: int) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT pr.*, i.description AS incident_description
            FROM patient_records pr
            LEFT JOIN incidents i ON i.id = pr.incident_id
            WHERE pr.hospital_id = ?
            ORDER BY datetime(pr.updated_at) DESC, pr.id DESC
            """,
            (int(hospital_id),),
        ).fetchall()
        return [dict(r) for r in rows]


def create_notification(db_path: str, target_role: str, target_hospital_id: Optional[int], message: str) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO notifications (target_role, target_hospital_id, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (target_role, target_hospital_id, message, created_at),
        )
        conn.commit()
