// Frontend logic for the Fleet Tracker
// This file shows how to:
// 1) Initialize a Leaflet map
// 2) Open a WebSocket to the backend
// 3) Render live-updating asset markers

let map;
let markers = {}; // id -> Leaflet marker
let bounds = L.latLngBounds();
let ws;
let reconnectDelay = 1000; // start with 1s

// Helper to create (or update) a marker
function upsertMarker(asset) {
  const { id, name, lat, lng, heading_deg, speed_kph, status } = asset;
  const pos = [lat, lng];

  if (markers[id]) {
    markers[id].setLatLng(pos);
    markers[id].bindPopup(`<b>${name}</b><br/>Speed: ${speed_kph.toFixed(1)} kph<br/>Heading: ${heading_deg.toFixed(0)}°<br/>Status: ${status}`);
  } else {
    const marker = L.marker(pos, { title: name });
    marker.bindPopup(`<b>${name}</b><br/>Speed: ${speed_kph.toFixed(1)} kph<br/>Heading: ${heading_deg.toFixed(0)}°<br/>Status: ${status}`);
    marker.addTo(map);
    markers[id] = marker;
  }

  bounds.extend(pos);
}

// Connect (or reconnect) the WebSocket
function connectWS() {
  const statusEl = document.getElementById('ws-status');
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${window.location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    statusEl.textContent = 'Connected';
    statusEl.style.background = '#065f46';
    // Reset backoff
    reconnectDelay = 1000;
  };

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === 'snapshot') {
      // Reset
      bounds = L.latLngBounds();
      Object.values(markers).forEach(m => m.remove());
      markers = {};

      msg.data.forEach(upsertMarker);
      document.getElementById('asset-count').textContent = `Assets on map: ${msg.data.length}`;
    } else if (msg.type === 'asset_update') {
      upsertMarker(msg.data);
    }
  };

  ws.onclose = () => {
    statusEl.textContent = 'Reconnecting…';
    statusEl.style.background = '#7c2d12';
    setTimeout(connectWS, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 10000); // exponential backoff up to 10s
  };

  ws.onerror = () => {
    // Let onclose handle reconnect
    ws.close();
  };
}

function initMap() {
  map = L.map('map');

  // Tile layer (OpenStreetMap)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Initial view (centered in Lahore for this demo; will fit markers after snapshot)
  map.setView([31.5204, 74.3587], 12);

  document.getElementById('btn-zoom-fit').addEventListener('click', () => {
    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.2));
    }
  });

  document.getElementById('btn-snapshot').addEventListener('click', async () => {
    // Ask server for a fresh snapshot via a simple fetch to force-reload:
    await fetch('/api/assets'); // no-op; server will still push periodic updates
    // The server sends snapshots only when a client connects, but this
    // endpoint can be repurposed by students as an exercise to push snapshots.
  });

  connectWS();
}

window.addEventListener('load', initMap);
