/* global L */

function severityStyle(severity) {
  if (severity === "CRITICAL") return { color: "#ff3252", radius: 1200 };
  if (severity === "HIGH") return { color: "#ff8a3c", radius: 900 };
  if (severity === "MEDIUM") return { color: "#ffd24d", radius: 650 };
  return { color: "#39d98a", radius: 450 };
}

function drawOpsLayers(map, data, isMini = false) {
  const allPoints = [];
  const incidentPointIconRadius = isMini ? 4 : 6;

  (data.incidents || []).forEach((i) => {
    const style = severityStyle(i.severity || "LOW");
    let incidentMarker;
    
    if (i.severity === "CRITICAL") {
      const pulseIcon = L.divIcon({
        className: 'pulse-marker',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });
      incidentMarker = L.marker([i.latitude, i.longitude], { icon: pulseIcon }).addTo(map);
    } else {
      incidentMarker = L.circleMarker([i.latitude, i.longitude], {
        radius: incidentPointIconRadius,
        color: style.color,
        fillColor: style.color,
        fillOpacity: 0.9,
        weight: 2
      }).addTo(map);
    }
    
    incidentMarker.bindPopup(
      `Incident #${i.id}<br/>Severity: ${i.severity || "LOW"}<br/>Priority: ${i.priority} (${i.priority_score || 0}%)<br/>Allocated: ${i.assigned_hospital_name || "Unassigned"}`,
    );
    allPoints.push([i.latitude, i.longitude]);
  });

  (data.hospitals || []).forEach((h) => {
    const hospitalIcon = L.divIcon({
      className: "hospital-marker-wrap",
      html: `<div class="hospital-pin">+</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
    L.marker([h.latitude, h.longitude], { icon: hospitalIcon })
      .addTo(map)
      .bindPopup(`Pune Rescue Hospital: ${h.name}<br/>Patients admitted: ${h.admitted_patients || 0}`);
    allPoints.push([h.latitude, h.longitude]);
  });

  (data.radar_incidents || []).forEach((i) => {
    if (i.status === "RESOLVED" || i.status === "CLOSED") return;
    const style = severityStyle(i.severity || "CRITICAL");
    L.circle([i.latitude, i.longitude], {
      radius: isMini ? Math.max(style.radius * 0.5, 250) : style.radius,
      color: style.color,
      fillColor: style.color,
      fillOpacity: 0.2,
    })
      .addTo(map)
      .bindPopup(`Radar Alert #${i.id}<br/>Severity: ${i.severity || "CRITICAL"}<br/>Priority: ${i.priority_score}%`);
    allPoints.push([i.latitude, i.longitude]);
  });

  if (allPoints.length > 0) {
    map.fitBounds(allPoints, { padding: [25, 25] });
  }
}

async function loadOpsMap() {
  const resp = await fetch("/api/ops-map");
  const data = await resp.json();

  const miniMapEl = document.getElementById("opsMiniMap");
  if (miniMapEl) {
    const miniMap = L.map("opsMiniMap", { zoomControl: false, attributionControl: false }).setView([20.5937, 78.9629], 5);
    
    // Tactical Map Theme (Dark & Grid blend)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { 
      maxZoom: 19,
      opacity: 0.3
    }).addTo(miniMap);
    
    miniMap.getContainer().style.background = 'transparent'; // Let the grid overlay show through

    drawOpsLayers(miniMap, data, true);
    
    const mapCard = miniMapEl.closest(".map-card-expandable");
    if (mapCard) {
      mapCard.addEventListener("transitionend", () => {
        miniMap.invalidateSize();
      });
    }
  }
}

async function loadNotifications() {
  const box = document.getElementById("notificationBox");
  const badge = document.getElementById("alertsBadge");
  
  try {
    const resp = await fetch("/api/notifications");
    const data = await resp.json();
    
    if (badge) {
      badge.textContent = data.notifications ? data.notifications.length : 0;
    }
    
    if (!box) return;
    
    if (data.notifications && data.notifications.length > 0) {
      box.innerHTML = data.notifications.map(n => 
        `<div style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 4px; font-size: 11px;">
          <strong style="color: #ffc107;">Incident #${n.id}</strong>: ${n.description} <br>
          <span style="font-size: 0.9em; color: var(--muted);">Status: ${n.status} | Priority: ${n.priority_score}%</span>
        </div>`
      ).join("");
    } else {
      box.innerHTML = '<p style="color: var(--muted); font-size: 10px; margin: 0;">No active alerts.</p>';
    }
  } catch (e) {
    console.error("Failed to load notifications", e);
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  try {
    await loadOpsMap();
  } catch (e) {
    console.log("Map not available on this dashboard.");
  }
  
  loadNotifications();
  setInterval(loadNotifications, 5000);
  
  const alertsBtn = document.getElementById("alertsBtn");
  if (alertsBtn) {
    alertsBtn.addEventListener("click", () => {
      const dropdown = document.getElementById("alertsDropdown");
      if (dropdown) {
        dropdown.style.display = dropdown.style.display === "none" || dropdown.style.display === "" ? "block" : "none";
      }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!alertsBtn.contains(e.target) && !document.getElementById("alertsDropdown").contains(e.target)) {
        document.getElementById("alertsDropdown").style.display = "none";
      }
    });
  }
});
