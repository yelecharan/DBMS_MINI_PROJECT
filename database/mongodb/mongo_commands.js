// =====================================================================
// GateSentry - MongoDB commands (R6 Observations, R7 Report, R8 Alerts)
// Run in MongoDB Compass -> "MONGOSH" tab, or:  mongosh mongodb://localhost:27017 mongo_commands.js
// The same operations are executed by the FastAPI backend through PyMongo
// (backend/app/mongo_setup.py and backend/app/routers/{observations,reports,alerts}.py).
// incident_id is an application-level reference to incidents.incident_id in PostgreSQL.
// =====================================================================

// ---------- 1. Database creation ----------
use("gatesentry");

// ---------- 2. Collection creation with $jsonSchema validation ----------
// (skips collections that already exist, e.g. created by backend/scripts/init_db.py)
function ensureCollection(name, opts) {
  if (db.getCollectionNames().includes(name)) print(name + " already exists");
  else db.createCollection(name, opts);
}

ensureCollection("Observations", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["obs_id", "incident_id", "method", "observed_count", "authorized_count", "timestamp"],
    properties: {
      obs_id:           { bsonType: "string" },
      incident_id:      { bsonType: "int", minimum: 1 },
      method:           { enum: ["MANUAL_HEADCOUNT", "GUARD_PATROL", "TURNSTILE_COUNTER", "SIMULATED"] },
      observed_count:   { bsonType: "int", minimum: 0 },
      authorized_count: { bsonType: "int", minimum: 0 },
      timestamp:        { bsonType: "date" },
      location:         { bsonType: "object" },            // nested document
      tags:             { bsonType: "array", items: { bsonType: "string" } }
    }
  }}
});

ensureCollection("Report", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["report_id", "incident_id", "description", "reported_by", "timestamp"],
    properties: {
      report_id:   { bsonType: "string" },
      incident_id: { bsonType: "int", minimum: 1 },
      description: { bsonType: "string", minLength: 10 },
      reported_by: { bsonType: "object", required: ["username", "role"] },
      attachments: { bsonType: "array" },
      timestamp:   { bsonType: "date" }
    }
  }}
});

ensureCollection("Alerts", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["alert_id", "incident_id", "alert_time", "alert_type", "message", "ack_status"],
    properties: {
      alert_id:    { bsonType: "string" },
      incident_id: { bsonType: "int", minimum: 1 },
      alert_time:  { bsonType: "date" },
      alert_type:  { enum: ["TAILGATING", "ESCALATION", "REPEAT_OFFENDER", "SYSTEM"] },
      message:     { bsonType: "string" },
      ack_status:  { enum: ["PENDING", "ACKNOWLEDGED"] }
    }
  }}
});

// ---------- 3. Indexes ----------
db.Observations.createIndex({ obs_id: 1 }, { unique: true, name: "uq_obs_id" });
db.Observations.createIndex({ incident_id: 1 }, { name: "idx_obs_incident" });
db.Observations.createIndex({ timestamp: -1 }, { name: "idx_obs_time" });
db.Observations.createIndex({ "location.gate_id": 1 }, { name: "idx_obs_gate" });
db.Report.createIndex({ report_id: 1 }, { unique: true, name: "uq_report_id" });
db.Report.createIndex({ incident_id: 1, timestamp: -1 }, { name: "idx_report_incident_time" });
db.Report.createIndex({ description: "text" }, { name: "txt_report_description" });
db.Alerts.createIndex({ alert_id: 1 }, { unique: true, name: "uq_alert_id" });
db.Alerts.createIndex({ ack_status: 1, alert_time: -1 }, { name: "idx_alert_status_time" });
db.Alerts.createIndex({ incident_id: 1 }, { name: "idx_alert_incident" });

// ---------- 4. CREATE: insert documents (nested docs + arrays) ----------
db.Observations.insertOne({
  obs_id: "OBS-DEMO0001", incident_id: NumberInt(7), method: "MANUAL_HEADCOUNT",
  observed_count: NumberInt(6), authorized_count: NumberInt(1), timestamp: new Date(),
  location: { gate_id: NumberInt(3), gate_name: "Server Room", scan_id: NumberInt(22) },
  observed_by: "guard", notes: "Five people followed one card holder.",
  tags: ["tailgating", "critical"]
});

db.Report.insertOne({
  report_id: "RPT-DEMO0001", incident_id: NumberInt(7),
  description: "Group of five visitors entered the server room behind one employee.",
  reported_by: { username: "guard", role: "security" },
  attachments: [ { file_name: "server_room_log.pdf", file_type: "application/pdf", note: "Logbook" } ],
  timestamp: new Date()
});

db.Alerts.insertMany([
  { alert_id: "ALT-DEMO0001", incident_id: NumberInt(7), alert_time: new Date(),
    alert_type: "ESCALATION", severity: "CRITICAL",
    message: "CRITICAL tailgating suspected at Server Room.", ack_status: "PENDING",
    acknowledged: null, recipients: ["security-desk", "facility-admin"] },
  { alert_id: "ALT-DEMO0002", incident_id: NumberInt(8), alert_time: new Date(),
    alert_type: "TAILGATING", severity: "MEDIUM",
    message: "MEDIUM tailgating suspected at Server Room.", ack_status: "PENDING",
    acknowledged: null, recipients: ["security-desk"] }
]);

// Validation demo - rejected: observed_count must be an int >= 0, method must be in the enum
try {
  db.Observations.insertOne({ obs_id: "BAD", incident_id: NumberInt(1), method: "CCTV",
                              observed_count: -3, authorized_count: NumberInt(1), timestamp: new Date() });
} catch (e) { print("Validation rejected the document: " + e.message); }

// ---------- 5. READ: filtering, projection, sorting ----------
db.Observations.find({ incident_id: 7 }, { _id: 0 }).sort({ timestamp: -1 });
db.Observations.find({ "location.gate_name": "Server Room" }, { _id: 0, obs_id: 1, observed_count: 1 });
db.Observations.find({ $expr: { $gte: [ { $subtract: ["$observed_count", "$authorized_count"] }, 3 ] } });
db.Observations.find({ tags: "critical" });                         // query inside an array
db.Report.find({ $text: { $search: "server room" } }, { _id: 0, report_id: 1, description: 1 });
db.Alerts.find({ ack_status: "PENDING", severity: { $in: ["HIGH", "CRITICAL"] } }).sort({ alert_time: -1 });
db.Alerts.countDocuments({ ack_status: "PENDING" });

// ---------- 6. UPDATE ----------
db.Alerts.updateOne(                                                  // acknowledge an alert
  { alert_id: "ALT-DEMO0001", ack_status: "PENDING" },
  { $set: { ack_status: "ACKNOWLEDGED",
            acknowledged: { by: "guard", at: new Date(), comment: "Area secured" } } });
db.Report.updateOne(                                                  // push into an array
  { report_id: "RPT-DEMO0001" },
  { $push: { attachments: { file_name: "visitor_badges.jpg", file_type: "image/jpeg", note: "Badges" } },
    $set:  { updated_at: new Date() } });
db.Report.updateOne(                                                  // pull from an array
  { report_id: "RPT-DEMO0001" }, { $pull: { attachments: { file_name: "visitor_badges.jpg" } } });
db.Observations.updateMany({ method: "SIMULATED" }, { $addToSet: { tags: "simulated" } });

// ---------- 7. DELETE ----------
db.Alerts.deleteOne({ alert_id: "ALT-DEMO0002" });
db.Observations.deleteMany({ obs_id: { $regex: "^OBS-DEMO" } });
db.Report.deleteOne({ report_id: "RPT-DEMO0001" });
db.Alerts.deleteMany({ alert_id: { $regex: "^ALT-DEMO" } });

// ---------- 8. Aggregation pipelines ----------
// unauthorised people per gate
db.Observations.aggregate([
  { $project: { gate: "$location.gate_name",
                excess: { $subtract: ["$observed_count", "$authorized_count"] } } },
  { $group: { _id: "$gate", observations: { $sum: 1 }, unauthorised: { $sum: "$excess" } } },
  { $sort: { unauthorised: -1 } }
]);

// alerts by status and type
db.Alerts.aggregate([
  { $group: { _id: { status: "$ack_status", type: "$alert_type" }, count: { $sum: 1 } } },
  { $sort: { count: -1 } }
]);

// pending alerts joined with their observations ($lookup)
db.Alerts.aggregate([
  { $match: { ack_status: "PENDING" } },
  { $lookup: { from: "Observations", localField: "incident_id",
               foreignField: "incident_id", as: "observations" } },
  { $project: { _id: 0, alert_id: 1, incident_id: 1, severity: 1,
                observation_count: { $size: "$observations" } } }
]);

// attachments per file type ($unwind)
db.Report.aggregate([
  { $unwind: "$attachments" },
  { $group: { _id: "$attachments.file_type", count: { $sum: 1 } } }
]);

// observations per day
db.Observations.aggregate([
  { $group: { _id: { $dateToString: { format: "%Y-%m-%d", date: "$timestamp", timezone: "Asia/Kolkata" } },
              observations: { $sum: 1 } } },
  { $sort: { _id: 1 } }
]);

// index list
db.Observations.getIndexes();
