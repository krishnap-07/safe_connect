/* global L */

let map;
let marker;

/* Radar layer group — cleared and redrawn on each refresh */
let radarLayerGroup = null;
let hospitalLayerGroup = null;

function publicSeverityStyle(severity) {
  if (severity === "CRITICAL") return { color: "#ef4444", radius: 900, pulseSize: 60, label: "CRITICAL" };
  if (severity === "HIGH") return { color: "#f59e0b", radius: 700, pulseSize: 48, label: "HIGH" };
  if (severity === "MEDIUM") return { color: "#3b82f6", radius: 500, pulseSize: 36, label: "MEDIUM" };
  return { color: "#22c55e", radius: 350, pulseSize: 28, label: "LOW" };
}

function makePublicHospitalIcon(name) {
  return L.divIcon({
    className: "hospital-marker-wrap",
    html: `<div class="hospital-pin">+</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

/* Create a pulsing radar divIcon for an incident */
function makeRadarIcon(style) {
  const size = style.pulseSize;
  return L.divIcon({
    className: "",
    html: `
      <div class="radar-signal" style="--radar-color: ${style.color}; --radar-size: ${size}px;">
        <div class="radar-ring radar-ring-1"></div>
        <div class="radar-ring radar-ring-2"></div>
        <div class="radar-ring radar-ring-3"></div>
        <div class="radar-core"></div>
      </div>
    `,
    iconSize: [size * 2.5, size * 2.5],
    iconAnchor: [size * 1.25, size * 1.25],
  });
}

function setLatLon(lat, lon) {
  const latInput = document.getElementById("latitude");
  const lonInput = document.getElementById("longitude");
  const coordText = document.getElementById("coordText");

  if (latInput) latInput.value = String(lat);
  if (lonInput) lonInput.value = String(lon);
  if (coordText) coordText.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
  
  fetchNearbyIncidents(lat, lon);
}

async function fetchNearbyIncidents(lat, lon) {
  const card = document.getElementById("nearbyCard");
  const tbody = document.getElementById("nearbyTableBody");
  if (!card || !tbody) return;

  try {
    const resp = await fetch(`/api/nearby-incidents?lat=${lat}&lon=${lon}`);
    const data = await resp.json();
    
    if (data.incidents && data.incidents.length > 0) {
      card.style.display = "block";
      tbody.innerHTML = data.incidents.map(i => {
        let statusStyle = i.status === "RESOLVED" ? "color: #22c55e;" : "color: #ef4444;";
        return `
          <tr>
            <td><strong>#${i.id}</strong> ${i.disaster_type}</td>
            <td>${i.distance_km.toFixed(2)} km</td>
            <td><strong style="${statusStyle}">${i.status}</strong></td>
            <td>${i.assigned_hospital_name}</td>
          </tr>
        `;
      }).join("");
    } else {
      card.style.display = "none";
    }
  } catch (err) {
    console.error("Failed to fetch nearby incidents", err);
  }
}

function placeMarker(lat, lon) {
  if (!map) return;
  const ll = [lat, lon];
  if (!marker) {
    marker = L.marker(ll, { draggable: true }).addTo(map);
    marker.on("dragend", () => {
      const p = marker.getLatLng();
      setLatLon(p.lat, p.lng);
    });
  } else {
    marker.setLatLng(ll);
  }
}

async function getBrowserLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );
  });
}

/* Draw or refresh the radar overlay — called on init and every 10s */
async function refreshRadarLayer() {
  try {
    const resp = await fetch("/api/public-radars");
    if (!resp.ok) return;
    const data = await resp.json();

    // Clear old layers
    if (radarLayerGroup) radarLayerGroup.clearLayers();
    else radarLayerGroup = L.layerGroup().addTo(map);

    if (hospitalLayerGroup) hospitalLayerGroup.clearLayers();
    else hospitalLayerGroup = L.layerGroup().addTo(map);

    // Draw hospitals
    (data.hospitals || []).forEach((h) => {
      L.marker([h.latitude, h.longitude], { icon: makePublicHospitalIcon(h.name) })
        .bindPopup(`Rescue Hospital: ${h.name}<br/>Admitted patients: ${h.admitted_patients || 0}`)
        .addTo(hospitalLayerGroup);
    });

    // Draw animated radar signals for each incident
    (data.radar_incidents || []).forEach((i) => {
      const style = publicSeverityStyle(i.severity || "LOW");

      // Outer transparent severity zone
      L.circle([i.latitude, i.longitude], {
        radius: style.radius,
        color: style.color,
        fillColor: style.color,
        fillOpacity: 0.08,
        weight: 1,
        dashArray: "6 4",
      }).addTo(radarLayerGroup);

      // Pulsing radar icon
      const icon = makeRadarIcon(style);
      L.marker([i.latitude, i.longitude], { icon })
        .bindPopup(
          `<div style="font-family: system-ui; min-width: 180px;">
            <strong style="color: ${style.color};">\u26a0 ${style.label} ALERT</strong><br/>
            <span style="font-size: 12px;">Incident #${i.id}</span><br/>
            <span style="font-size: 12px;">Priority Score: <strong>${i.priority_score || 0}%</strong></span><br/>
            <span style="font-size: 11px; color: #888;">Type: ${i.disaster_type || "Unknown"}</span>
          </div>`
        )
        .addTo(radarLayerGroup);
    });

  } catch {
    // best-effort
  }
}

async function initMap() {
  map = L.map("map", { zoomControl: true });
  map.setView([20.5937, 78.9629], 5); // India default

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  // Initial radar draw
  await refreshRadarLayer();

  // Auto-refresh radar every 10 seconds (picks up new disasters instantly)
  setInterval(refreshRadarLayer, 10000);

  map.on("click", (e) => {
    setLatLon(e.latlng.lat, e.latlng.lng);
    placeMarker(e.latlng.lat, e.latlng.lng);
  });

  const locateBtn = document.getElementById("locateBtn");
  if (locateBtn) {
    locateBtn.addEventListener("click", async () => {
      locateBtn.disabled = true;
      locateBtn.textContent = "Locating…";
      try {
        const p = await getBrowserLocation();
        map.setView([p.lat, p.lon], 15);
        setLatLon(p.lat, p.lon);
        placeMarker(p.lat, p.lon);
      } catch (e) {
        // eslint-disable-next-line no-alert
        alert("Unable to get location. Allow location permission, or click on the map to set coordinates.");
      } finally {
        locateBtn.disabled = false;
        locateBtn.textContent = "Use my location";
      }
    });
  }

  // best-effort auto locate on load
  try {
    const p = await getBrowserLocation();
    map.setView([p.lat, p.lon], 15);
    setLatLon(p.lat, p.lon);
    placeMarker(p.lat, p.lon);
  } catch {
    // user can click on map
  }
}

async function wireForm() {
  const form = document.getElementById("reportForm");
  const resultBox = document.getElementById("resultBox");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById("submitBtn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";
    }

    if (resultBox) {
      resultBox.textContent = "Analyzing image, detecting humans, classifying disaster, and storing incident…";
    }

    try {
      const fd = new FormData(form);
      const resp = await fetch("/report", { method: "POST", body: fd });
      const data = await resp.json();

      if (!resp.ok || !data.success) {
        throw new Error(data.message || "Request failed");
      }

      const inc = data.incident;
      const alloc = data.allocation;

      const warnings = (data.warnings || []).length ? `\nWarnings: ${data.warnings.join(" ")}` : "";
      const humanText = inc.human_detected ? `YES (${inc.human_count} people detected)` : "NO";

      if (resultBox) {
        const resultText = 
          `Saved incident #${inc.id}\n` +
          `Disaster type: ${inc.disaster_type} (${(inc.disaster_confidence * 100).toFixed(1)}%)\n` +
          `Humans Detected: ${humanText}\n` +
          `Priority: ${inc.priority}\n` +
          `Nearest hospital: ${alloc.hospital.name} (${alloc.distance_km.toFixed(2)} km)\n` +
          `${warnings}`;
          
        const imgSrc = document.getElementById('imagePreview').src;
        resultBox.innerHTML = `
          <div style="margin-bottom: 10px;"><img src="${imgSrc}" style="max-height: 150px; border-radius: 4px;"></div>
          <pre style="margin:0; white-space: pre-wrap; font-family: inherit;">${resultText}</pre>
        `;
        resultBox.style.display = 'block';
        
        setTimeout(() => {
          resultBox.style.display = 'none';
          resultBox.innerHTML = '';
        }, 5000);
      }

      // Immediately refresh the radar so the new incident shows up
      await refreshRadarLayer();

      form.reset();
      document.getElementById('imagePreviewContainer').style.display = 'none';
      document.getElementById('imagePreview').src = '';
    } catch (err) {
      if (resultBox) resultBox.textContent = `Error: ${err.message}`;
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit report";
      }
    }
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  await initMap();
  await wireForm();
  
  const mapContainer = document.getElementById("map");
  if (mapContainer && map) {
    mapContainer.addEventListener("transitionend", () => {
      map.invalidateSize();
    });
  }
});

