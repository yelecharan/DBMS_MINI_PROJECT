"""MongoDB collection: Alerts (CRUD, acknowledgement, aggregation with $lookup)."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING, DESCENDING

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import mongo_db
from ..deps import ensure_incident_exists, not_found
from ..mongo_setup import ALERTS, OBSERVATIONS
from ..schemas import AckIn, AlertIn, AlertUpdate
from ..utils import new_id, utcnow

router = APIRouter(prefix="/api/alerts", tags=["Alerts (MongoDB)"])
col = mongo_db[ALERTS]


@router.get("")
def list_alerts(ack_status: str | None = None, alert_type: str | None = None,
                severity: str | None = None, search: str | None = None,
                order: str = "desc", user: CurrentUser = Depends(get_current_user)):
    query: dict = {}
    if ack_status:
        query["ack_status"] = ack_status
    if alert_type:
        query["alert_type"] = alert_type
    if severity:
        query["severity"] = severity
    if search:
        query["message"] = {"$regex": re.escape(search), "$options": "i"}
    direction = ASCENDING if order == "asc" else DESCENDING
    return list(col.find(query, {"_id": 0}).sort("alert_time", direction))


@router.get("/summary")
def alert_summary(user: CurrentUser = Depends(get_current_user)):
    """$group by status/type and a $lookup joining Alerts with Observations."""
    by_status = list(col.aggregate([
        {"$group": {"_id": {"status": "$ack_status", "type": "$alert_type"},
                    "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "ack_status": "$_id.status", "alert_type": "$_id.type",
                      "count": 1}},
        {"$sort": {"ack_status": -1, "count": -1}},
    ]))
    pending_with_obs = list(col.aggregate([
        {"$match": {"ack_status": "PENDING"}},
        {"$lookup": {"from": OBSERVATIONS, "localField": "incident_id",
                     "foreignField": "incident_id", "as": "obs"}},
        {"$project": {"_id": 0, "alert_id": 1, "incident_id": 1, "severity": 1,
                      "alert_time": 1, "observations": {"$size": "$obs"},
                      "max_observed": {"$max": "$obs.observed_count"}}},
        {"$sort": {"alert_time": -1}},
    ]))
    return {"by_status": by_status, "pending_with_observations": pending_with_obs}


@router.post("", status_code=201)
def create_alert(body: AlertIn, user: CurrentUser = Depends(require_admin)):
    inc = ensure_incident_exists(user.role, body.incident_id)
    doc = {
        "alert_id": new_id("ALT"), "incident_id": body.incident_id, "alert_time": utcnow(),
        "alert_type": body.alert_type, "severity": inc["severity"],
        "message": body.message.strip(), "ack_status": "PENDING", "acknowledged": None,
        "recipients": body.recipients,
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{alert_id}/ack")
def acknowledge(alert_id: str, body: AckIn, user: CurrentUser = Depends(get_current_user)):
    res = col.find_one_and_update(
        {"alert_id": alert_id, "ack_status": "PENDING"},
        {"$set": {"ack_status": "ACKNOWLEDGED",
                  "acknowledged": {"by": user.username, "at": utcnow(), "comment": body.comment}}},
        projection={"_id": 0}, return_document=True)
    if not res:
        if col.count_documents({"alert_id": alert_id}) == 0:
            raise not_found("Alert", alert_id)
        raise HTTPException(409, "Alert already acknowledged")
    return res


@router.put("/{alert_id}")
def update_alert(alert_id: str, body: AlertUpdate, user: CurrentUser = Depends(require_admin)):
    res = col.find_one_and_update({"alert_id": alert_id},
                                  {"$set": {"alert_type": body.alert_type,
                                            "message": body.message.strip()}},
                                  projection={"_id": 0}, return_document=True)
    if not res:
        raise not_found("Alert", alert_id)
    return res


@router.post("/{alert_id}/reopen")
def reopen(alert_id: str, user: CurrentUser = Depends(require_admin)):
    res = col.find_one_and_update({"alert_id": alert_id},
                                  {"$set": {"ack_status": "PENDING", "acknowledged": None}},
                                  projection={"_id": 0}, return_document=True)
    if not res:
        raise not_found("Alert", alert_id)
    return res


@router.delete("/{alert_id}")
def delete_alert(alert_id: str, user: CurrentUser = Depends(require_admin)):
    if col.delete_one({"alert_id": alert_id}).deleted_count == 0:
        raise not_found("Alert", alert_id)
    return {"deleted": alert_id}
