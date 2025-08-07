# -*- coding: utf-8 -*-
"""
FastAPI · Firestore → JSON (2 endpoints) · versión Render
--------------------------------------------------------
• GET /campana?campana_id=...  →  JSON list
• GET /estacion?campana_id=... →  JSON list

Auth:
  – 1 variable de entorno obligatoria  ➜  FIREBASE_KEY_B64
    (service-account.json codificado en base-64, ¡una sola línea!)

Despliegue en Render   ➜  START command:  uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import os, json, base64, warnings
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict

import numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import firebase_admin
from firebase_admin import credentials, firestore

warnings.filterwarnings("ignore", category=UserWarning)

# ────────────────────────────────  Firebase init
def init_firebase():
    if firebase_admin._apps:                      # ya inicializado
        return

    b64 = os.getenv("FIREBASE_KEY_B64", "").strip()
    if not b64:
        raise RuntimeError("❌  FIREBASE_KEY_B64 no está definida en las variables de entorno.")

    cred_info = json.loads(base64.b64decode(b64))
    firebase_admin.initialize_app(credentials.Certificate(cred_info))

init_firebase()
db        = firestore.client()
LOCAL_TZ  = ZoneInfo("America/Santiago")

# ────────────────────────────────  Colecciones & filtros
COLLECTIONS = {
    "campana":  {"name": "campana",  "filter_field": "campanaID"},
    "estacion": {"name": "Estacion", "filter_field": "campanaID"},  # ajusta si se llama distinto
}

# ────────────────────────────────  Helpers JSON-safe
def to_jsonable(v: Any) -> Any:
    from google.cloud.firestore_v1 import _helpers as _fs_helpers
    from google.cloud.firestore_v1._helpers import GeoPoint

    if isinstance(v, _fs_helpers.DatetimeWithNanoseconds):
        return v.replace(tzinfo=LOCAL_TZ).isoformat()
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=LOCAL_TZ)
        return v.astimezone(LOCAL_TZ).isoformat()
    if isinstance(v, GeoPoint):
        return {"latitude": v.latitude, "longitude": v.longitude}
    if isinstance(v, list):
        return [to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: to_jsonable(val) for k, val in v.items()}
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v

def doc_to_dict(doc) -> Dict[str, Any]:
    data = {k: to_jsonable(v) for k, v in (doc.to_dict() or {}).items()}
    data["id"] = doc.id
    return data

def fetch_collection(key: str, campana_id: str):
    cfg     = COLLECTIONS[key]
    col_ref = db.collection(cfg["name"]).where(cfg["filter_field"], "==", campana_id.strip('"'))
    return [doc_to_dict(d) for d in col_ref.stream()]

# ────────────────────────────────  FastAPI app
app = FastAPI(title="API Firestore → JSON (Campana / Estacion)")

# CORS – abierto; cambia allow_origins en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/campana")
def get_campana(campana_id: str = Query(..., description="ID de campaña")):
    items = fetch_collection("campana", campana_id)
    if not items:
        raise HTTPException(404, "Sin documentos en 'campana' para ese campana_id.")
    return JSONResponse(items)

@app.get("/estacion")
def get_estacion(campana_id: str = Query(..., description="ID de campaña")):
    items = fetch_collection("estacion", campana_id)
    if not items:
        raise HTTPException(404, "Sin documentos en 'Estacion' para ese campana_id.")
    return JSONResponse(items)
