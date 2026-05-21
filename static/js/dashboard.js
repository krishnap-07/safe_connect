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
    let style = severityStyle(i.severity || "LOW");
    let incidentMarker;
    
    if (i.status === "RESOLVED") {
      style = { color: "#888", radius: 400 }; // Grey out resolved
      incidentMarker = L.circleMarker([i.latitude, i.longitude], {
        radius: isMini ? 3 : 5,
        color: style.color,
        fillColor: style.color,
        fillOpacity: 0.8,
        weight: 1
      }).addTo(map);
    } else if (i.severity === "CRITICAL") {
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

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = "none";
}

async function openHospitalReport(hospitalId) {
  const modal = document.getElementById("hospitalReportModal");
  const content = document.getElementById("hospitalModalContent");
  if (!modal || !content) return;
  
  content.innerHTML = "Loading data...";
  modal.style.display = "flex";
  
  try {
    const resp = await fetch(`/api/hospital/${hospitalId}/report`);
    const data = await resp.json();
    
    if (!data.success) {
      content.innerHTML = `<p style="color: var(--danger);">Error: ${data.message}</p>`;
      return;
    }
    
    const h = data.hospital;
    const incs = data.incidents || [];
    const pats = data.patients || [];
    
    let html = `
      <div style="margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: var(--accent);">${h.name}</h3>
        <p style="margin: 0; font-size: 13px; color: var(--muted);">${h.total_beds - pats.length} / ${h.total_beds} beds free</p>
      </div>
      
      <h4 style="margin-bottom: 8px; color: var(--text);">Assigned Disasters</h4>
      ${incs.length > 0 ? 
        `<ul style="list-style: none; padding: 0; margin: 0 0 20px 0; font-size: 13px;">
          ${incs.map(i => `<li style="padding: 8px; border: 1px solid var(--border); margin-bottom: 4px; border-radius: 4px; background: rgba(255,255,255,0.02);"><strong style="color: var(--warning);">#${i.id}</strong>: ${i.disaster_type} (Status: ${i.status})</li>`).join("")}
        </ul>` : 
        `<p style="font-size: 12px; color: var(--muted); margin-bottom: 20px;">No active disasters assigned.</p>`
      }
      
      <h4 style="margin-bottom: 8px; color: var(--text);">Admitted Patients</h4>
      ${pats.length > 0 ? 
        `<table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border); color: var(--muted);">
              <th style="padding: 8px;">Name</th>
              <th style="padding: 8px;">Condition</th>
              <th style="padding: 8px;">Notes</th>
            </tr>
          </thead>
          <tbody>
            ${pats.map(p => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 8px;">${p.patient_name}</td>
                <td style="padding: 8px; color: ${p.condition_status === 'CRITICAL' ? 'var(--danger)' : p.condition_status === 'STABLE' ? 'var(--ok)' : 'var(--warning)'};">${p.condition_status}</td>
                <td style="padding: 8px; color: var(--muted);">${p.notes || '-'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>` :
        `<p style="font-size: 12px; color: var(--muted);">No patients currently admitted.</p>`
      }
    `;
    
    content.innerHTML = html;
  } catch (err) {
    content.innerHTML = `<p style="color: var(--danger);">Failed to load hospital report.</p>`;
  }
}

async function openIncidentDetails(incidentId) {
  const modal = document.getElementById("incidentDetailModal");
  const content = document.getElementById("incidentModalContent");
  if (!modal || !content) return;
  
  content.innerHTML = "Loading intelligence...";
  modal.style.display = "flex";
  
  try {
    const resp = await fetch(`/api/incident/${incidentId}/details`);
    const data = await resp.json();
    
    if (!data.success) {
      content.innerHTML = `<p style="color: var(--danger);">Error: ${data.message}</p>`;
      return;
    }
    
    const i = data.incident;
    
    let html = `
      <div style="display: flex; gap: 20px;">
        ${i.image_path ? 
          `<div style="flex: 1; min-width: 200px;">
            <img src="/uploads/${i.image_path}" style="width: 100%; border-radius: 8px; border: 1px solid var(--border);" />
           </div>` : 
           `<div style="flex: 1; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px dashed var(--border); min-width: 200px;">
             <span style="color: var(--muted); font-size: 12px;">No image provided</span>
           </div>`
        }
        
        <div style="flex: 1.5; font-size: 13px; display: flex; flex-direction: column; gap: 12px;">
          <div>
            <span style="color: var(--muted); font-size: 11px;">CLASSIFICATION</span><br>
            <strong style="font-size: 16px; color: var(--accent);">${i.disaster_type}</strong>
            ${i.disaster_confidence ? `<span style="color: var(--muted); font-size: 11px; margin-left: 8px;">(${(i.disaster_confidence * 100).toFixed(1)}% conf)</span>` : ''}
          </div>
          
          <div style="background: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px; border: 1px solid var(--border);">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <div>
                <span style="color: var(--muted); font-size: 11px;">PRIORITY SCORE</span><br>
                <strong style="color: ${i.severity === 'CRITICAL' ? 'var(--danger)' : i.severity === 'HIGH' ? 'var(--warning)' : 'var(--ok)'}">${i.priority_score}% (${i.severity})</strong>
              </div>
              <div>
                <span style="color: var(--muted); font-size: 11px;">HUMAN LIFE DETECTED</span><br>
                <strong>${i.human_detected ? `<span style="color: var(--danger);">YES (${i.human_count} people)</span>` : '<span style="color: var(--ok);">NONE</span>'}</strong>
              </div>
              <div>
                <span style="color: var(--muted); font-size: 11px;">DAMAGE LEVEL</span><br>
                <strong>${i.damage_level || 'Unknown'}</strong>
              </div>
              <div>
                <span style="color: var(--muted); font-size: 11px;">WATER DEPTH</span><br>
                <strong>${i.water_depth || 'N/A'}</strong>
              </div>
            </div>
          </div>
          
          <div>
            <span style="color: var(--muted); font-size: 11px;">GPS COORDINATES</span><br>
            <code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; color: #fff;">${i.latitude.toFixed(6)}, ${i.longitude.toFixed(6)}</code>
          </div>
          
          <div>
            <span style="color: var(--muted); font-size: 11px;">CITIZEN DESCRIPTION</span><br>
            <p style="margin: 4px 0 0 0; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; border: 1px solid var(--border);">${i.description || 'No description provided.'}</p>
          </div>
        </div>
      </div>
    `;
    
    content.innerHTML = html;
  } catch (err) {
    content.innerHTML = `<p style="color: var(--danger);">Failed to load incident intelligence.</p>`;
  }
}
