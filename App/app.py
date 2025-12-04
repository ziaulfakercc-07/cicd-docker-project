"""
FastAPI backend for the Real-Time Fleet/Asset Tracker.
This file is heavily commented for students to learn the design.

Key features:
- Serves static frontend (Leaflet map)
- WebSocket endpoint for pushing live updates to all connected clients
- In-memory asset manager + background "simulator" that moves assets
- Simple REST APIs for listing/creating/updating assets
"""

import asyncio
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# -------------------------- Configuration --------------------------
ASSET_COUNT = int(os.getenv("ASSET_COUNT", "20"))
CITY_CENTER_LAT = float(os.getenv("CITY_CENTER_LAT", "31.5204"))  # Lahore
CITY_CENTER_LNG = float(os.getenv("CITY_CENTER_LNG", "74.3587"))
TICK_MS = int(os.getenv("TICK_MS", "1000"))        # push every N ms
MAX_SPEED_KPH = float(os.getenv("MAX_SPEED_KPH", "50"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

random.seed(RANDOM_SEED)

# ---------------------- Utility math functions ---------------------
def km_to_deg_lat(km: float) -> float:
    """Approx conversion of km to degrees latitude"""
    return km / 111.0

def km_to_deg_lng(km: float, at_lat_deg: float) -> float:
    """Approx conversion of km to degrees longitude (varies by latitude)"""
    return km / (111.320 * math.cos(math.radians(at_lat_deg)))

def clamp(v, vmin, vmax):
    return max(vmin, min(v, vmax))

# ----------------------------- Models ------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def make_asset(i: int) -> dict:
    """Create a random asset near the city center"""
    # Random offset within ~3km box
    lat = CITY_CENTER_LAT + km_to_deg_lat(random.uniform(-1.5, 1.5))
    lng = CITY_CENTER_LNG + km_to_deg_lng(random.uniform(-1.5, 1.5), CITY_CENTER_LAT)
    heading = random.uniform(0, 360)
    speed = random.uniform(5, MAX_SPEED_KPH)  # 5..MAX km/h

    return {
        "id": f"asset-{i+1:03d}",
        "name": f"Vehicle {i+1:03d}",
        "lat": lat,
        "lng": lng,
        "heading_deg": heading,
        "speed_kph": speed,
        "status": "moving",
        "last_update": now_iso(),
    }

# ---------------------- Connection manager -------------------------
class ConnectionManager:
    """Tracks WebSocket clients and broadcasts updates to all"""
    def __init__(self):
        self.active: List[WebSocket] = []
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.active.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast(self, message: dict):
        # Send to every client; silently drop failures
        data = json.dumps(message)
        async with self.lock:
            coros = []
            for ws in self.active:
                coros.append(ws.send_text(data))
            if coros:
                await asyncio.gather(*coros, return_exceptions=True)

# --------------------------- Asset store ---------------------------
class AssetManager:
    """In-memory storage + simple motion simulation"""
    def __init__(self):
        self.assets: Dict[str, dict] = {}
        self.lock = asyncio.Lock()

    async def init_assets(self, n: int):
        async with self.lock:
            for i in range(n):
                a = make_asset(i)
                self.assets[a["id"]] = a

    async def list_assets(self) -> List[dict]:
        async with self.lock:
            return list(self.assets.values())

    async def upsert_asset(self, a: dict):
        async with self.lock:
            self.assets[a["id"]] = a

    async def update_asset_fields(self, asset_id: str, **fields):
        async with self.lock:
            if asset_id not in self.assets:
                raise KeyError(asset_id)
            self.assets[asset_id].update(fields)
            self.assets[asset_id]["last_update"] = now_iso()
            return self.assets[asset_id]

    async def step_simulation(self, dt_seconds: float):
        """Move each asset a small amount according to its speed and heading"""
        async with self.lock:
            for a in self.assets.values():
                # Randomly vary heading slightly to avoid straight lines
                a["heading_deg"] = (a["heading_deg"] + random.uniform(-10, 10)) % 360
                # Randomly vary speed a little
                a["speed_kph"] = clamp(a["speed_kph"] + random.uniform(-2, 2), 0, MAX_SPEED_KPH)

                # Convert speed to km/s, then distance traveled in this tick
                km_per_s = a["speed_kph"] / 3600.0
                dist_km = km_per_s * dt_seconds

                # Move along heading
                heading_rad = math.radians(a["heading_deg"])
                d_north_km = math.cos(heading_rad) * dist_km
                d_east_km  = math.sin(heading_rad) * dist_km

                a["lat"] += km_to_deg_lat(d_north_km)
                a["lng"] += km_to_deg_lng(d_east_km, a["lat"])
                a["last_update"] = now_iso()

# ----------------------------- App init ----------------------------
app = FastAPI(title="Fleet Tracker", version="1.0.0")

# Serve static files (our frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = ConnectionManager()
assets = AssetManager()

# --------------------------- Background tasks ----------------------
async def simulation_loop():
    """Background task: move assets every TICK_MS and broadcast incremental updates"""
    await assets.init_assets(ASSET_COUNT)
    # Initial broadcast won't happen until clients connect (they get a snapshot)
    tick = max(TICK_MS, 100) / 1000.0  # seconds
    while True:
        start = time.perf_counter()
        await assets.step_simulation(dt_seconds=tick)
        # Broadcast each asset's latest position as an incremental update
        # (Design choice for teaching; could also batch updates)
        current = await assets.list_assets()
        for a in current:
            await manager.broadcast({"type": "asset_update", "data": a})

        elapsed = time.perf_counter() - start
        await asyncio.sleep(max(0, tick - elapsed))

@app.on_event("startup")
async def on_startup():
    # Kick off the simulation background task
    asyncio.create_task(simulation_loop())

# ----------------------------- Routes ------------------------------
@app.get("/")
async def index():
    # Serve our static index.html
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "time": now_iso()}

@app.get("/api/assets")
async def get_assets():
    lst = await assets.list_assets()
    return JSONResponse(lst)

@app.post("/api/assets")
async def create_asset(payload: dict = Body(...)):
    # Expect at least an id and name; lat/lng optional (defaults near center)
    asset_id = payload.get("id")
    name = payload.get("name")
    if not asset_id or not name:
        raise HTTPException(400, "Fields 'id' and 'name' are required")

    lat = payload.get("lat", CITY_CENTER_LAT)
    lng = payload.get("lng", CITY_CENTER_LNG)
    speed = float(payload.get("speed_kph", random.uniform(5, MAX_SPEED_KPH)))
    heading = float(payload.get("heading_deg", random.uniform(0, 360)))
    status = payload.get("status", "moving")

    a = {
        "id": asset_id,
        "name": name,
        "lat": float(lat),
        "lng": float(lng),
        "speed_kph": speed,
        "heading_deg": heading,
        "status": status,
        "last_update": now_iso(),
    }
    await assets.upsert_asset(a)
    # Also notify clients immediately
    await manager.broadcast({"type": "asset_update", "data": a})
    return a

@app.patch("/api/assets/{asset_id}")
async def patch_asset(asset_id: str, payload: dict = Body(...)):
    try:
        updated = await assets.update_asset_fields(asset_id, **payload)
    except KeyError:
        raise HTTPException(404, f"Asset {asset_id} not found")
    # Notify clients
    await manager.broadcast({"type": "asset_update", "data": updated})
    return updated

# --------------------------- WebSocket -----------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    # 1) Accept connection
    await manager.connect(ws)
    try:
        # 2) Send a full snapshot first (so the map can render immediately)
        snapshot = await assets.list_assets()
        await ws.send_text(json.dumps({"type": "snapshot", "data": snapshot}))

        # 3) Keep the connection open; we don't require client messages in this demo
        while True:
            # If the client sends anything, just ignore or echo back
            await ws.receive_text()
    except WebSocketDisconnect:
        # Client disconnected normally
        pass
    except Exception:
        # Any other exception – close the socket gracefully
        pass
    finally:
        await manager.disconnect(ws)
