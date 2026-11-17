"""MongoDB collection: Report (CRUD, text search, array $push / $pull)."""
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING, DESCENDING

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import mongo_db
from ..deps import ensure_incident_exists, not_found
from ..mongo_setup import REPORT
from ..schemas import Attachment, ReportIn, ReportUpdate
from ..utils import new_id, utcnow

router = APIRouter(prefix="/api/reports", tags=["Reports (MongoDB)"])
col = mongo_db[REPORT]


@router.get("")
def list_reports(search: str | None = None, incident_id: int | None = None,
                 reported_by: str | None = None, order: str = "desc",
                 user: CurrentUser = Depends(get_current_user)):
    query: dict = {}
    if search:
        query["$text"] = {"$search": search}                 # uses the text index
    if incident_id:
        query["incident_id"] = incident_id
    if reported_by:
        query["reported_by.username"] = reported_by
    direction = ASCENDING if order == "asc" else DESCENDING
    return list(col.find(query, {"_id": 0}).sort("timestamp", direction))


@router.get("/stats")
def report_stats(user: CurrentUser = Depends(get_current_user)):
    """Aggregation with $unwind on the attachments array and $group by reporter."""
    return list(col.aggregate([
        {"$facet": {
            "by_reporter": [
                {"$group": {"_id": "$reported_by.username", "reports": {"$sum": 1},
                            "incidents": {"$addToSet": "$incident_id"}}},
                {"$project": {"_id": 0, "reporter": "$_id", "reports": 1,
                              "incidents": {"$size": "$incidents"}}},
            ],
            "attachments_by_type": [
                {"$unwind": "$attachments"},
                {"$group": {"_id": "$attachments.file_type", "count": {"$sum": 1}}},
                {"$project": {"_id": 0, "file_type": "$_id", "count": 1}},
            ],
        }},
    ]))[0]


@router.post("", status_code=201)
def create_report(body: ReportIn, user: CurrentUser = Depends(get_current_user)):
    ensure_incident_exists(user.role, body.incident_id)
    doc = {
        "report_id": new_id("RPT"), "incident_id": body.incident_id,
        "description": body.description.strip(),
        "reported_by": {"username": user.username, "role": user.role},
        "attachments": [a.model_dump() for a in body.attachments],
        "timestamp": utcnow(),
    }
    col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{report_id}")
def update_report(report_id: str, body: ReportUpdate, user: CurrentUser = Depends(get_current_user)):
    existing = col.find_one({"report_id": report_id}, {"reported_by": 1})
    if not existing:
        raise not_found("Report", report_id)
    if user.role != "admin" and existing["reported_by"]["username"] != user.username:
        raise HTTPException(403, "Security staff can only edit their own reports")
    return col.find_one_and_update(
        {"report_id": report_id},
        {"$set": {"description": body.description.strip(), "updated_at": utcnow()}},
        projection={"_id": 0}, return_document=True)


@router.post("/{report_id}/attachments")
def add_attachment(report_id: str, body: Attachment, user: CurrentUser = Depends(get_current_user)):
    res = col.find_one_and_update({"report_id": report_id},
                                  {"$push": {"attachments": body.model_dump()},
                                   "$set": {"updated_at": utcnow()}},
                                  projection={"_id": 0}, return_document=True)
    if not res:
        raise not_found("Report", report_id)
    return res


@router.delete("/{report_id}/attachments/{file_name}")
def remove_attachment(report_id: str, file_name: str, user: CurrentUser = Depends(get_current_user)):
    res = col.find_one_and_update({"report_id": report_id},
                                  {"$pull": {"attachments": {"file_name": file_name}}},
                                  projection={"_id": 0}, return_document=True)
    if not res:
        raise not_found("Report", report_id)
    return res


@router.delete("/{report_id}")
def delete_report(report_id: str, user: CurrentUser = Depends(require_admin)):
    if col.delete_one({"report_id": report_id}).deleted_count == 0:
        raise not_found("Report", report_id)
    return {"deleted": report_id}
