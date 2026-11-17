// =====================================================================
// GateSentry - mongo_dml_demo.js   (MongoDB version of 06_dml_demo.sql)
//
// HOW TO RUN - MongoDB Compass:
//   1. Connect to mongodb://localhost:27017
//   2. Click "Open MongoDB shell" (or ">_ MONGOSH" at the bottom)
//   3. Copy ONE command at a time from this file, paste it, press Enter.
//      Every command is self-contained (no variables), so you can run any
//      of them in any order and as many times as you like.
//
//   1. how many collections         5. view the inserted documents
//   2. structure of each collection 6. UPDATE (one per collection)
//   3. view the data                7. DELETE (one per collection)
//   4. INSERT (one per collection)
//
// incident_id refers to incidents.incident_id in PostgreSQL (7 exists in the sample data).
// Whole numbers are written as NumberInt(..) because the collection validators
// require type "int" (a plain 4 in the shell is stored as a decimal number).
// =====================================================================


// ---------------------------------------------------------------------
// 0. SWITCH TO THE DATABASE  (run this first)
// ---------------------------------------------------------------------
use gatesentry


// =====================================================================
// 1. HOW MANY COLLECTIONS ARE THERE?
// =====================================================================
show collections

db.getCollectionNames().length

db.Observations.countDocuments()

db.Report.countDocuments()

db.Alerts.countDocuments()


// =====================================================================
// 2. STRUCTURE OF EACH COLLECTION (validator = required fields + types, and indexes)
// =====================================================================
db.getCollectionInfos({ name: "Observations" })[0].options.validator

db.getCollectionInfos({ name: "Report" })[0].options.validator

db.getCollectionInfos({ name: "Alerts" })[0].options.validator

db.Observations.getIndexes()

db.Report.getIndexes()

db.Alerts.getIndexes()


// =====================================================================
// 3. VIEW THE DATA OF EACH COLLECTION
// =====================================================================
db.Observations.find()

db.Report.find()

db.Alerts.find()


// =====================================================================
// 4. INSERT - ONE INSERT PER COLLECTION
// =====================================================================

// ---------------------------------------------------------------------
// 4.1 INSERT INTO Observations   (nested document "location" + array "tags")
// ---------------------------------------------------------------------
db.Observations.insertOne({
  obs_id: "OBS-DEMO-001",
  incident_id: NumberInt(7),
  method: "MANUAL_HEADCOUNT",
  observed_count: NumberInt(4),
  authorized_count: NumberInt(1),
  timestamp: new Date(),
  location: { gate_id: NumberInt(3), gate_name: "Server Room", scan_id: NumberInt(22) },
  observed_by: "guard",
  notes: "Three visitors followed one employee into the server room.",
  tags: ["tailgating", "high", "demo"]
})

// ---------------------------------------------------------------------
// 4.2 INSERT INTO Report   (nested document "reported_by" + array "attachments")
// ---------------------------------------------------------------------
db.Report.insertOne({
  report_id: "RPT-DEMO-001",
  incident_id: NumberInt(7),
  description: "Guard stopped three visitors without badges at the Server Room door and escorted them out.",
  reported_by: { username: "guard", role: "security" },
  attachments: [
    { file_name: "server_room_logbook.pdf", file_type: "application/pdf", note: "Guard logbook page" }
  ],
  timestamp: new Date()
})

// ---------------------------------------------------------------------
// 4.3 INSERT INTO Alerts
// ---------------------------------------------------------------------
db.Alerts.insertOne({
  alert_id: "ALT-DEMO-001",
  incident_id: NumberInt(7),
  alert_time: new Date(),
  alert_type: "ESCALATION",
  severity: "CRITICAL",
  message: "Repeated tailgating at Server Room - supervisor informed.",
  ack_status: "PENDING",
  acknowledged: null,
  recipients: ["security-desk", "facility-admin"]
})

// NOTE: running an insert a second time gives "E11000 duplicate key error"
// because obs_id / report_id / alert_id have UNIQUE indexes - that is the
// unique index working. Run section 7 (DELETE) first to insert again.

// (optional) the validator rejects a wrong document -> "Document failed validation"
db.Observations.insertOne({ obs_id: "OBS-BAD", incident_id: NumberInt(7), method: "CCTV", observed_count: NumberInt(-2), authorized_count: NumberInt(1), timestamp: new Date() })


// =====================================================================
// 5. VIEW THE INSERTED DOCUMENTS
// =====================================================================
db.Observations.find({ obs_id: "OBS-DEMO-001" })

db.Report.find({ report_id: "RPT-DEMO-001" })

db.Alerts.find({ alert_id: "ALT-DEMO-001" })

// everything for incident 7 in each collection
db.Observations.find({ incident_id: 7 })

db.Report.find({ incident_id: 7 })

db.Alerts.find({ incident_id: 7 })


// =====================================================================
// 6. UPDATE - ONE UPDATE PER COLLECTION
// =====================================================================

// 6.1 UPDATE Observations   ($set a value + $push into the tags array)
db.Observations.updateOne(
  { obs_id: "OBS-DEMO-001" },
  { $set: { observed_count: NumberInt(5), notes: "Recount: four visitors followed one employee." },
    $push: { tags: "recounted" } }
)

// 6.2 UPDATE Report   ($push a new attachment into the array)
db.Report.updateOne(
  { report_id: "RPT-DEMO-001" },
  { $push: { attachments: { file_name: "visitor_list.png", file_type: "image/png", note: "Visitor register" } },
    $set: { updated_at: new Date() } }
)

// 6.3 UPDATE Alerts   (acknowledge the alert - nested document)
db.Alerts.updateOne(
  { alert_id: "ALT-DEMO-001" },
  { $set: { ack_status: "ACKNOWLEDGED", acknowledged: { by: "guard", at: new Date(), comment: "Area secured" } } }
)

// view the updated documents
db.Observations.find({ obs_id: "OBS-DEMO-001" })

db.Report.find({ report_id: "RPT-DEMO-001" })

db.Alerts.find({ alert_id: "ALT-DEMO-001" })


// =====================================================================
// 7. DELETE - ONE DELETE PER COLLECTION
// =====================================================================

// 7.1 DELETE FROM Observations
db.Observations.deleteOne({ obs_id: "OBS-DEMO-001" })

// 7.2 DELETE FROM Report
db.Report.deleteOne({ report_id: "RPT-DEMO-001" })

// 7.3 DELETE FROM Alerts
db.Alerts.deleteOne({ alert_id: "ALT-DEMO-001" })

// counts are back to the starting numbers
db.Observations.countDocuments()

db.Report.countDocuments()

db.Alerts.countDocuments()


// =====================================================================
// EXTRA - filters, sorting, text search, aggregation
// =====================================================================
db.Observations.find({ "location.gate_name": "Server Room" }).sort({ observed_count: -1 })

db.Alerts.find({ ack_status: "PENDING" }).sort({ alert_time: -1 })

db.Report.find({ $text: { $search: "server room" } })

db.Observations.aggregate([
  { $project: { gate: "$location.gate_name", excess: { $subtract: ["$observed_count", "$authorized_count"] } } },
  { $group: { _id: "$gate", observations: { $sum: 1 }, unauthorised_people: { $sum: "$excess" } } },
  { $sort: { unauthorised_people: -1 } }
])

db.Alerts.aggregate([
  { $match: { ack_status: "PENDING" } },
  { $lookup: { from: "Observations", localField: "incident_id", foreignField: "incident_id", as: "observations" } },
  { $project: { _id: 0, alert_id: 1, incident_id: 1, severity: 1, observation_count: { $size: "$observations" } } }
])
