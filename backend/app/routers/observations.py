"""MongoDB collection: Observations (CRUD + aggregation)."""
from fastapi import APIRouter, Depends
from pymongo import ASCENDING, DESCENDING

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import mongo_db
from ..deps import ensure_incident_exists, not_found
from ..mongo_setup import OBSERVATIONS
from ..schemas import ObservationIn, ObservationUpdate
from ..utils import new_id, utcnow

router = APIRouter(prefix="/api/observations", tags=["Observations (MongoDB)"])
col = mongo_db[OBSERVATIONS]
SORTS = {"timestamp", "incident_id", "observed_count", "authorized_count", "method"}


@router.get("")
def list_observations(incident_id: int | None = None, method: str | None = None,
                      gate_id: int | None = None, min_excess: int | None = None,
                      sort: str = "timestamp", order: str = "desc",
                      user: CurrentUser = Depends(get_current_user)):
    query: dict = {}
    if incident_id:
        query["incident_id"] = incident_id
    if method:
        query["method"] = method
    if gate_id:
        query["location.gate_id"] = gate_id                  # filter on nested field
    if min_excess is not None:                               # $expr compares two fields
        query["$expr"] = {"$gte": [{"$subtract": ["$observed_count", "$authorized_count"]},
                                   min_excess]}
    direction = ASCENDING if order == "asc" else DESCENDING
    cursor = col.find(query, {"_id": 0}).sort(sort if sort in SORTS else "timestamp", direction)
    return [{**d, "excess": d["observed_count"] - d["authorized_count"]} for d in cursor]


@router.get("/stats")
def observation_stats(user: CurrentUser = Depends(get_current_user)):
    """Aggregation pipeline: unauthorised entries per gate and per method."""
    per_gate = list(col.aggregate([
        {"$project": {"gate": "$location.gate_name",
                      "excess": {"$subtract": ["$observed_count", "$authorized_count"]}}},
        {"$group": {"_id": "$gate", "observations": {"$sum": 1},
                    "unauthorised_people": {"$sum": "$excess"},
                    "avg_excess": {"$avg": "$excess"}, "max_excess": {"$max": "$excess"}}},
        {"$sort": {"unauthorised_people": -1}},
        {"$project": {"_id": 0, "gate": "$_id", "observations": 1, "unauthorised_people": 1,
                      "max_excess": 1, "avg_excess": {"$round": ["$avg_excess", 2]}}},
    ]))
    per_method = list(col.aggregate([
        {"$group": {"_id": "$method", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}},
    ]))
    return {"per_gate": per_gate, "per_method": per_method}


@router.post("", status_code=201)
def create_observation(body: ObservationIn, user: CurrentUser = Depends(get_current_user)):
    inc = ensure_incident_exists(user.role, body.incident_id)
    doc = {
        "obs_id": new_id("OBS"), "incident_id": body.incident_id, "method": body.method,
        "observed_count": body.observed_count, "authorized_count": body.authorized_count,
        "timestamp": utcnow(),
        "location": {"gate_id": inc["gate_id"], "gate_name": inc["gate_name"],
                     "scan_id": inc["scan_id"]},
        "observed_by": user.username, "notes": body.notes,
        "tags": [t.strip().lower() for t in body.tags if t.strip()],
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{obs_id}")
def update_observation(obs_id: str, body: ObservationUpdate,
                       user: CurrentUser = Depends(get_current_user)):
    res = col.find_one_and_update(
        {"obs_id": obs_id},
        {"$set": {"method": body.method, "observed_count": body.observed_count,
                  "authorized_count": body.authorized_count, "notes": body.notes,
                  "tags": [t.strip().lower() for t in body.tags if t.strip()],
                  "updated_by": user.username, "updated_at": utcnow()}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise not_found("Observation", obs_id)
    return res


@router.delete("/{obs_id}")
def delete_observation(obs_id: str, user: CurrentUser = Depends(require_admin)):
    if col.delete_one({"obs_id": obs_id}).deleted_count == 0:
        raise not_found("Observation", obs_id)
    return {"deleted": obs_id}
