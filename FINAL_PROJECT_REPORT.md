# SAFE_CONNECT: AI-Powered Disaster Response & Resource Allocation System
**Final Project Documentation**

---

## 1. Actual Working of the Project (System Workflow)

SAFE_CONNECT is a centralized, AI-driven disaster management ecosystem designed to eliminate chaos during emergencies. The workflow connects three distinct entities:

**A. The Citizen (Reporter)**
- A citizen accesses the public Gateway (no login required) and submits a disaster report with their precise GPS coordinates, a brief description, and a photo of the incident.
- **Behind the Scenes:** The backend instantly runs the image through a Computer Vision model to detect human life, runs damage assessment algorithms, and estimates water depth.
- The AI dynamically calculates a **Priority Score** (1-100) based on severity, damage, and human presence.
- The system automatically reverse-geocodes the coordinates and uses Gemini AI to broadcast a tri-lingual news alert to the city's Telegram channel.

**B. The Central Officer (Command Center)**
- The officer logs into a highly dense, 3-column tactical dashboard.
- They see the newly reported incident on a live Leaflet.js radar map. Critical incidents pulse in red.
- The officer has the ultimate authority to approve or reject **Pending Hospital Registrations**. The dashboard calculates the exact distance (using Haversine logic) between the new hospital and existing hospitals to ensure geographical coverage isn't overlapping.
- The officer commands rescue teams based on AI dispatch recommendations.

**C. The Hospital (Resource Center)**
- Hospitals must securely register and await Officer approval before they appear on the public map.
- Once approved, the Smart Allocation Algorithm routes disaster victims to the nearest appropriate hospital based on proximity and the hospital's live bed capacity.
- The hospital dashboard receives a real-time notification. They can manage patient admissions, update their live bed count, and mark rescue plans as "Executed."

---

## 2. Core Technical Concepts Used

> [!IMPORTANT]
> The project heavily leverages modern AI and spatial mapping algorithms to remove human error from emergency response.

1. **Computer Vision (YOLOv8):** Used for real-time human detection in disaster images to prioritize rescues where life is at immediate risk.
2. **Machine Learning (MobileNetV2 & Random Forest):** CNNs for disaster classification and regression models for fusing multimodal inputs into a singular priority score.
3. **Large Language Models (Gemini AI):** Used for intelligent multilingual translation and automated social media broadcasting.
4. **Geospatial Analytics (Haversine Formula):** Used mathematically to compute the shortest Earth-surface distance between victims and hospitals to ensure lightning-fast allocation.
5. **Role-Based Access Control (RBAC):** Strict session isolation ensuring Citizens, Hospitals, and Officers have completely sequestered data privileges.
6. **Asynchronous Polling & Web Sockets:** Real-time UI updates without page refreshes.

---

## 3. Team Contribution (5 Members)

### Member 1: AI & Machine Learning Lead
**Focus:** Core severity and classification models.
- **Responsibilities:**
  - Train and evaluate the **MobileNetV2 CNN** to classify disasters (Fire, Flood, Earthquake, etc.).
  - Develop and train the **Random Forest Regressor** that fuses multiple inputs (text, disaster type, human count, damage level) into a singular severity score.
  - Expose these models as Python inference functions to be consumed by the backend.

### Member 2: Computer Vision Engineer
**Focus:** Image analysis and extraction.
- **Responsibilities:**
  - Implement **YOLOv8 (Ultralytics)** for real-time human detection and bounding box extraction.
  - Develop the Computer Vision heuristics for **Damage Assessment** (calculating structural collapse) and **Flood Estimation** (water level depth).
  - Ensure image pre-processing pipelines are highly optimized so they don't delay the backend response.

### Member 3: Backend & Database Architect
**Focus:** Data flow, logic routing, and database schema.
- **Responsibilities:**
  - Build the Flask Backend API and manage SQLite database schemas (Incidents, Hospitals, Vans, Notifications).
  - Develop the **Haversine Resource Allocation algorithm** to match incidents to the nearest hospital.
  - Implement the **Incident Clustering Logic** (grouping 3+ reports within a 2km radius).
  - Handle authentication for Officers, Hospitals, and Van Sub-logins.

### Member 4: Frontend & UI/UX Developer
**Focus:** User interfaces and interactive maps.
- **Responsibilities:**
  - Build out the HTML/CSS/Vanilla JS for all 4 interfaces: Public Portal, Officer Dashboard, Hospital Dashboard, and Van Dashboard.
  - Implement the **Leaflet.js interactive maps**, ensuring custom pins (Hospitals, Vans, Radar Alerts) render correctly.
  - Build the "Expand Ticket" UI for officers to view informer details and raw AI logs.
  - Ensure the UI looks highly professional, modern, and responsive.

### Member 5: System Integrator & Real-Time Logistics
**Focus:** Tying systems together and managing live data.
- **Responsibilities:**
  - Implement the **Browser Geolocation API** in the Van Dashboard for real-time tracking.
  - Build the **Custom Notifications Engine** that alerts officers and handles the "Bed Capacity Overflow" spillover logic.
  - Write AJAX polling scripts so the Officer map updates live without page refreshes.
  - Manage overall project flow, integration testing, and final system presentation.
