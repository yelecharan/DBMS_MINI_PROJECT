"""MongoDB collection definitions: $jsonSchema validators + indexes.

Collections (R6..R8 of the relational schema):
  Observations  - manual / simulated head-count compared with authorised scans
  Report        - incident reports written by security staff
  Alerts        - alerts raised for incidents, acknowledged by staff
Each document carries `incident_id`, an application-level reference to
incidents.incident_id in PostgreSQL (validated by the backend).
"""
from pymongo import ASCENDING, DESCENDING, IndexModel, TEXT
from pymongo.database import Database

OBSERVATIONS = "Observations"
REPORT = "Report"
ALERTS = "Alerts"

VALIDATORS = {
    OBSERVATIONS: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["obs_id", "incident_id", "method", "observed_count",
                         "authorized_count", "timestamp"],
            "properties": {
                "obs_id": {"bsonType": "string"},
                "incident_id": {"bsonType": "int", "minimum": 1},
                "method": {"enum": ["MANUAL_HEADCOUNT", "GUARD_PATROL", "TURNSTILE_COUNTER",
                                    "SIMULATED"]},
                "observed_count": {"bsonType": "int", "minimum": 0},
                "authorized_count": {"bsonType": "int", "minimum": 0},
                "timestamp": {"bsonType": "date"},
                "location": {                                   # nested document
                    "bsonType": "object",
                    "properties": {
                        "gate_id": {"bsonType": "int"},
                        "gate_name": {"bsonType": "string"},
                        "scan_id": {"bsonType": "int"},
                    },
                },
                "observed_by": {"bsonType": "string"},
                "notes": {"bsonType": "string"},
                "tags": {"bsonType": "array", "items": {"bsonType": "string"}},   # array
            },
        }
    },
    REPORT: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["report_id", "incident_id", "description", "reported_by", "timestamp"],
            "properties": {
                "report_id": {"bsonType": "string"},
                "incident_id": {"bsonType": "int", "minimum": 1},
                "description": {"bsonType": "string", "minLength": 10},
                "reported_by": {                                # nested document
                    "bsonType": "object",
                    "required": ["username", "role"],
                    "properties": {
                        "username": {"bsonType": "string"},
                        "role": {"enum": ["admin", "security"]},
                    },
                },
                "attachments": {                                # array of nested documents
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["file_name", "file_type"],
                        "properties": {
                            "file_name": {"bsonType": "string"},
                            "file_type": {"bsonType": "string"},
                            "note": {"bsonType": "string"},
                        },
                    },
                },
                "timestamp": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        }
    },
    ALERTS: {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["alert_id", "incident_id", "alert_time", "alert_type", "message",
                         "ack_status"],
            "properties": {
                "alert_id": {"bsonType": "string"},
                "incident_id": {"bsonType": "int", "minimum": 1},
                "alert_time": {"bsonType": "date"},
                "alert_type": {"enum": ["TAILGATING", "ESCALATION", "REPEAT_OFFENDER",
                                        "SYSTEM"]},
                "severity": {"enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "message": {"bsonType": "string"},
                "ack_status": {"enum": ["PENDING", "ACKNOWLEDGED"]},
                "acknowledged": {
                    "bsonType": ["object", "null"],
                    "properties": {
                        "by": {"bsonType": "string"},
                        "at": {"bsonType": "date"},
                        "comment": {"bsonType": "string"},
                    },
                },
                "recipients": {"bsonType": "array", "items": {"bsonType": "string"}},
            },
        }
    },
}

INDEXES = {
    OBSERVATIONS: [
        IndexModel([("obs_id", ASCENDING)], unique=True, name="uq_obs_id"),
        IndexModel([("incident_id", ASCENDING)], name="idx_obs_incident"),
        IndexModel([("timestamp", DESCENDING)], name="idx_obs_time"),
        IndexModel([("location.gate_id", ASCENDING)], name="idx_obs_gate"),
    ],
    REPORT: [
        IndexModel([("report_id", ASCENDING)], unique=True, name="uq_report_id"),
        IndexModel([("incident_id", ASCENDING), ("timestamp", DESCENDING)],
                   name="idx_report_incident_time"),
        IndexModel([("description", TEXT)], name="txt_report_description"),
    ],
    ALERTS: [
        IndexModel([("alert_id", ASCENDING)], unique=True, name="uq_alert_id"),
        IndexModel([("ack_status", ASCENDING), ("alert_time", DESCENDING)],
                   name="idx_alert_status_time"),
        IndexModel([("incident_id", ASCENDING)], name="idx_alert_incident"),
    ],
}


def create_collections(db: Database, drop_existing: bool = False) -> None:
    existing = set(db.list_collection_names())
    for name, validator in VALIDATORS.items():
        if drop_existing and name in existing:
            db.drop_collection(name)
            existing.discard(name)
        if name in existing:
            db.command("collMod", name, validator=validator, validationLevel="strict")
        else:
            db.create_collection(name, validator=validator, validationLevel="strict")
        db[name].create_indexes(INDEXES[name])
