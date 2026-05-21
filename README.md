# SAFE_CONNECT

ML-assisted disaster response platform with role-based workflows for:
- Public incident reporting
- Main officer operations dashboard
- Registered hospital admission updates

## Core Features

- Public report registration with image upload and geo-location.
- Human detection using YOLOv8.
- Disaster classification using TensorFlow model.
- Priority scoring and severity mapping.
- Officer-only dashboard with radar overlays, hospital tags, and rescue van tracking.
- Registered Pune hospital allocation (nearest hospital auto-assignment).
- Hospital module for patient admission and record updates.

## Project Structure

```text
safer/
├── app.py                          # Flask app entry point
├── routes/
│   └── incidents.py                # All web routes and API endpoints
├── database/
│   └── db.py                       # SQLite schema + data access helpers
├── services/
│   ├── decision_logic.py           # Priority and severity logic
│   └── hospital_allocation.py      # Nearest-hospital selection + Pune filtering
├── models/
│   ├── human_detection.py          # YOLOv8 person detection
│   ├── disaster_classifier.py      # TensorFlow disaster prediction
│   ├── disaster_model.h5           # Trained classifier model
│   └── disaster_labels.json        # Class labels for classifier
├── templates/
│   ├── index.html                  # Public report page
│   ├── officer_login.html          # Officer login
│   ├── dashboard.html              # Officer dashboard
│   ├── past_incidents.html         # Officer past allocations
│   ├── hospital_register.html      # Hospital registration
│   ├── hospital_login.html         # Hospital login
│   └── hospital_dashboard.html     # Hospital operations
├── static/
│   ├── css/style.css               # Shared UI styles
│   └── js/
│       ├── map.js                  # Public map logic
│       └── dashboard.js            # Officer map + tracking logic
├── data/                           # Dataset-related files
├── instance/                       # SQLite database storage
├── uploads/                        # Uploaded incident images
├── import_dataset.py               # Dataset import helper
├── prepare_classifier_dataset.py   # Classifier dataset preparation
├── train_model.py                  # Disaster model training script
└── requirements.txt                # Python dependencies
```

## Setup

1. Create and activate virtual environment:
   - Windows PowerShell:
     - `python -m venv .venv311`
     - `.\.venv311\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run app:
   - `python app.py`
4. Open:
   - `http://127.0.0.1:5000`

## Default Officer Login

- Username: `officer`
- Password: `officer123`

(Can be changed via environment variables `OFFICER_USERNAME` and `OFFICER_PASSWORD`.)

## Notes for Demo

- Register at least one Pune-area hospital before incident submission for auto-allocation.
- If no hospital is registered, incidents are stored with unassigned hospital and a warning.
- Model loading requires TensorFlow in the active environment.
