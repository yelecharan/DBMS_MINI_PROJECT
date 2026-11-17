// =====================================================================
// GateSentry - mongo_dml_demo.js
// Demo script for the viva / report:
//   1. how many collections exist        4. INSERT into every collection
//   2. structure (validator + indexes)   5. UPDATE and DELETE
//   3. view the data of every collection 6. view the data again
//
// HOW TO RUN
//   MongoDB Compass: connect to mongodb://localhost:27017, click ">_ MONGOSH" at the bottom,
//                    paste this whole file (or one numbered block) and press Enter.
//   mongosh:         mongosh mongodb://localhost:27017 mongo_dml_demo.js
// The script can be run again: every inserted document gets a new unique id.
// incident_id values refer to rows in PostgreSQL table incidents (7 and 8 exist in the sample data).
// Whole numbers use NumberInt(...) because the collection validators require bsonType "int".
// =====================================================================

db = db.getSiblingDB("gatesentry");
const RUN = Date.now().toString(36).toUpperCase();      // makes ids unique for every run
const OBS_ID = "OBS-DEMO-" + RUN, RPT_ID = "RPT-DEMO-" + RUN;
const ALT_ID1 = "ALT-DEMO-" + RUN + "-1", ALT_ID2 = "ALT-DEMO-" + RUN + "-2";

function title(t) { print("\n==================== " + t + " ===================="); }
function counts() {
  ["Observations", "Report", "Alerts"].forEach(c =>
    print(c.padEnd(14) + db.getCollection(c).countDocuments({}) + " documents"));
}

// =====================================================================
// 1. HOW MANY COLLECTIONS ARE THERE?
// =====================================================================
title("1. Collections in database 'gatesentry'");
const names = db.getCollectionNames().sort();
printjson(names);
print("Total collections: " + names.length);
counts();

// =====================================================================
// 2. STRUCTURE: $jsonSchema validator (required fields + types) and indexes
// =====================================================================
title("2. Structure of each collection");
db.getCollectionInfos({ name: { $in: ["Observations", "Report", "Alerts"] } }).forEach(info => {
  const schema = info.options.validator.$jsonSchema;
  print("\n--- " + info.name + " ---");
  print("required fields: " + schema.required.join(", "));
  print("all fields:      " + Object.keys(schema.properties).join(", "));
  print("indexes:         " + db.getCollection(info.name).getIndexes().map(i => i.name).join(", "));
});

// =====================================================================
// 3. VIEW THE DATA OF EVERY COLLECTION
// =====================================================================
title("3a. Observations");
db.Observations.find({}, { _id: 0 }).sort({ timestamp: -1 }).forEach(printjson);

title("3b. Report");
db.Report.find({}, { _id: 0 }).sort({ timestamp: -1 }).forEach(printjson);

title("3c. Alerts");
db.Alerts.find({}, { _id: 0 }).sort({ alert_time: -1 }).forEach(printjson);

// =====================================================================
// 4. INSERT INTO EVERY COLLECTION
// =====================================================================
title("4. INSERT");

// 4.1 Observations - insertOne with a nested document and an array
printjson(db.Observations.insertOne({
  obs_id: OBS_ID,
  incident_id: NumberInt(7),
  method: "MANUAL_HEADCOUNT",
  observed_count: NumberInt(4),
  authorized_count: NumberInt(1),
  timestamp: new Date(),
  location: { gate_id: NumberInt(3), gate_name: "Server Room", scan_id: NumberInt(22) },   // nested
  observed_by: "guard",
  notes: "Three visitors followed one employee into the server room.",
  tags: ["tailgating", "high", "demo"]                                                        // array
}));

// 4.2 Report - nested reported_by document + array of attachment documents
printjson(db.Report.insertOne({
  report_id: RPT_ID,
  incident_id: NumberInt(7),
  description: "Guard stopped three visitors without badges at the Server Room door and escorted them out.",
  reported_by: { username: "guard", role: "security" },
  attachments: [
    { file_name: "server_room_logbook.pdf", file_type: "application/pdf", note: "Guard logbook page" },
    { file_name: "visitor_list.png",        file_type: "image/png",       note: "Visitor register" }
  ],
  timestamp: new Date()
}));

// 4.3 Alerts - insertMany (two documents at once)
printjson(db.Alerts.insertMany([
  { alert_id: ALT_ID1, incident_id: NumberInt(7), alert_time: new Date(), alert_type: "ESCALATION",
    severity: "CRITICAL", message: "Repeated tailgating at Server Room - supervisor informed.",
    ack_status: "PENDING", acknowledged: null, recipients: ["security-desk", "facility-admin"] },
  { alert_id: ALT_ID2, incident_id: NumberInt(8), alert_time: new Date(), alert_type: "TAILGATING",
    severity: "MEDIUM", message: "Possible tailgating at Server Room (demo alert).",
    ack_status: "PENDING", acknowledged: null, recipients: ["security-desk"] }
]));

// 4.4 the validator rejects an invalid document (wrong method, negative count, double instead of int)
try {
  db.Observations.insertOne({ obs_id: "OBS-BAD-" + RUN, incident_id: NumberInt(7), method: "CCTV",
                              observed_count: -2, authorized_count: NumberInt(1), timestamp: new Date() });
} catch (e) {
  print("Validator rejected the invalid document: " + e.message);
}

// =====================================================================
// 5. UPDATE AND DELETE
// =====================================================================
title("5. UPDATE and DELETE");

// $set a field and $push into an array
printjson(db.Observations.updateOne({ obs_id: OBS_ID },
  { $set: { observed_count: NumberInt(5), notes: "Recount: four visitors followed one employee." },
    $push: { tags: "recounted" } }));

// $push / $pull on the attachments array
printjson(db.Report.updateOne({ report_id: RPT_ID },
  { $push: { attachments: { file_name: "door_sensor.txt", file_type: "text/plain", note: "Door log" } },
    $set: { updated_at: new Date() } }));
printjson(db.Report.updateOne({ report_id: RPT_ID },
  { $pull: { attachments: { file_name: "visitor_list.png" } } }));

// acknowledge an alert (nested document)
printjson(db.Alerts.updateOne({ alert_id: ALT_ID1, ack_status: "PENDING" },
  { $set: { ack_status: "ACKNOWLEDGED",
            acknowledged: { by: "guard", at: new Date(), comment: "Area secured" } } }));

// updateMany: add a tag to every observation made by the demo method
printjson(db.Observations.updateMany({ obs_id: OBS_ID }, { $addToSet: { tags: "reviewed" } }));

// deleteOne: remove the second demo alert
printjson(db.Alerts.deleteOne({ alert_id: ALT_ID2 }));

// =====================================================================
// 6. VIEW THE DATA AGAIN
// =====================================================================
title("6a. Inserted / updated documents");
printjson(db.Observations.findOne({ obs_id: OBS_ID }, { _id: 0 }));
printjson(db.Report.findOne({ report_id: RPT_ID }, { _id: 0 }));
printjson(db.Alerts.findOne({ alert_id: ALT_ID1 }, { _id: 0 }));

title("6b. Filters and sorting");
print("Observations at the Server Room (nested field filter):");
db.Observations.find({ "location.gate_name": "Server Room" },
                     { _id: 0, obs_id: 1, incident_id: 1, observed_count: 1, authorized_count: 1 })
  .sort({ observed_count: -1 }).forEach(printjson);
print("Pending alerts, newest first:");
db.Alerts.find({ ack_status: "PENDING" }, { _id: 0, alert_id: 1, incident_id: 1, severity: 1, message: 1 })
  .sort({ alert_time: -1 }).forEach(printjson);
print("Reports containing the word 'visitors' (text index):");
db.Report.find({ $text: { $search: "visitors" } }, { _id: 0, report_id: 1, incident_id: 1 }).forEach(printjson);

title("6c. Everything linked to incident 7 (aggregation with $lookup)");
db.Observations.aggregate([
  { $match: { incident_id: 7 } },
  { $group: { _id: "$incident_id", observations: { $sum: 1 }, max_observed: { $max: "$observed_count" } } },
  { $lookup: { from: "Report", localField: "_id", foreignField: "incident_id", as: "reports" } },
  { $lookup: { from: "Alerts", localField: "_id", foreignField: "incident_id", as: "alerts" } },
  { $project: { _id: 0, incident_id: "$_id", observations: 1, max_observed: 1,
                reports: { $size: "$reports" }, alerts: { $size: "$alerts" } } }
]).forEach(printjson);

title("Document counts after the inserts");
counts();

// To remove only the demo documents:
//   db.Observations.deleteMany({ obs_id: /^OBS-DEMO-/ });
//   db.Report.deleteMany({ report_id: /^RPT-DEMO-/ });
//   db.Alerts.deleteMany({ alert_id: /^ALT-DEMO-/ });
// To go back to the original sample data:  cd backend && .venv\Scripts\python -m scripts.init_db
