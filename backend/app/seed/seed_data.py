import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.database.session import SessionLocal, activate_database_role
from app.models.models import (
    User, Employee, Site, Zone, Gate, Camera, AccessCredential,
    AccessEvent, GateSession, CameraObservation, Incident,
    IncidentAction, EvidenceAsset, AuditLog, DetectionRule
)
from app.core.security import hash_password
from app.services.outbox_service import enqueue_incident_vector_event
import logging

logger = logging.getLogger("gatesentry.seed")

def seed_database(db: Session = None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        activate_database_role(db, "ADMIN")
        existing_data = any(
            db.query(model).first()
            for model in (User, Employee, Site, Gate, Incident)
        )
        if existing_data:
            raise RuntimeError("Demo seed data can only be loaded into an empty database.")

        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. USERS (3 distinct roles)
        # -------------------------------------------------------------
        admin_user = User(
            id=str(uuid.uuid4()),
            full_name="Alex Mercer (Chief Admin)",
            email="admin@gatesentry.internal",
            password_hash=hash_password("AdminPassword2026!"),
            role="ADMIN",
            is_active=True,
            created_at=now - timedelta(days=60)
        )
        security_user = User(
            id=str(uuid.uuid4()),
            full_name="Sarah Jenkins (Security Lead)",
            email="security@gatesentry.internal",
            password_hash=hash_password("SecurityPassword2026!"),
            role="SECURITY_OFFICER",
            is_active=True,
            created_at=now - timedelta(days=60)
        )
        auditor_user = User(
            id=str(uuid.uuid4()),
            full_name="David Vance (Compliance Auditor)",
            email="auditor@gatesentry.internal",
            password_hash=hash_password("AuditorPassword2026!"),
            role="AUDITOR",
            is_active=True,
            created_at=now - timedelta(days=60)
        )
        db.add_all([admin_user, security_user, auditor_user])
        db.flush()

        # -------------------------------------------------------------
        # 2. SITES (2 physical sites)
        # -------------------------------------------------------------
        site_blr = Site(
            id=str(uuid.uuid4()),
            site_name="Bengaluru Tech Park - Headquarters",
            address="Plot 14, Electronic City Phase 1, Hosur Road, Bengaluru 560100",
            created_at=now - timedelta(days=90)
        )
        site_hyd = Site(
            id=str(uuid.uuid4()),
            site_name="Hyderabad Development Center",
            address="Building 4, HITEC City, Madhapur, Hyderabad 500081",
            created_at=now - timedelta(days=90)
        )
        db.add_all([site_blr, site_hyd])
        db.flush()

        # -------------------------------------------------------------
        # 3. ZONES (6 hierarchical zones)
        # -------------------------------------------------------------
        # Level 1: Ground Floor
        zone_gf = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=None,
            zone_name="Ground Floor Reception & Concourse",
            zone_type="PUBLIC_RECEPTION",
            sensitivity_level=5,
            created_at=now - timedelta(days=90)
        )
        db.add(zone_gf)
        db.flush()

        # Level 2 Children of GF
        zone_north_lobby = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=zone_gf.id,
            zone_name="North Turnstile Portal",
            zone_type="PERIMETER_ACCESS",
            sensitivity_level=10,
            created_at=now - timedelta(days=90)
        )
        zone_south_lobby = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=zone_gf.id,
            zone_name="South Turnstile Portal",
            zone_type="PERIMETER_ACCESS",
            sensitivity_level=10,
            created_at=now - timedelta(days=90)
        )
        
        # Level 1: First Floor
        zone_f1 = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=None,
            zone_name="First Floor Engineering Wing",
            zone_type="INTERNAL_OFFICE",
            sensitivity_level=15,
            created_at=now - timedelta(days=90)
        )
        db.add_all([zone_north_lobby, zone_south_lobby, zone_f1])
        db.flush()

        # Child of F1: Server Room (High security)
        zone_server_room = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=zone_f1.id,
            zone_name="Secure Server Room Data Vault",
            zone_type="RESTRICTED_INFRASTRUCTURE",
            sensitivity_level=30,
            created_at=now - timedelta(days=90)
        )
        # Child of F1: Executive Wing
        zone_exec = Zone(
            id=str(uuid.uuid4()),
            site_id=site_blr.id,
            parent_zone_id=zone_f1.id,
            zone_name="Executive Leadership Suite",
            zone_type="RESTRICTED_EXECUTIVE",
            sensitivity_level=20,
            created_at=now - timedelta(days=90)
        )
        db.add_all([zone_server_room, zone_exec])
        db.flush()

        # -------------------------------------------------------------
        # 4. GATES (4 portals)
        # -------------------------------------------------------------
        gate_north = Gate(
            id=str(uuid.uuid4()),
            zone_id=zone_north_lobby.id,
            gate_code="GATE-BLR-N01",
            gate_name="North Lobby Speedlane Turnstile",
            direction="ENTRY",
            is_active=True,
            session_window_seconds=8,
            minimum_detection_confidence=0.65
        )
        gate_south = Gate(
            id=str(uuid.uuid4()),
            zone_id=zone_south_lobby.id,
            gate_code="GATE-BLR-S01",
            gate_name="South Lobby Fastgate",
            direction="ENTRY",
            is_active=True,
            session_window_seconds=8,
            minimum_detection_confidence=0.65
        )
        gate_server = Gate(
            id=str(uuid.uuid4()),
            zone_id=zone_server_room.id,
            gate_code="GATE-BLR-SR01",
            gate_name="Data Center Vault Airlock",
            direction="ENTRY",
            is_active=True,
            session_window_seconds=6,
            minimum_detection_confidence=0.75
        )
        gate_exec = Gate(
            id=str(uuid.uuid4()),
            zone_id=zone_exec.id,
            gate_code="GATE-BLR-EX01",
            gate_name="Executive Suite Biometric Portal",
            direction="BIDIRECTIONAL",
            is_active=True,
            session_window_seconds=7,
            minimum_detection_confidence=0.70
        )
        gates = [gate_north, gate_south, gate_server, gate_exec]
        db.add_all(gates)
        db.flush()

        # -------------------------------------------------------------
        # 5. CAMERAS (4 optical tracking sensors)
        # -------------------------------------------------------------
        cam_north = Camera(
            id=str(uuid.uuid4()),
            gate_id=gate_north.id,
            camera_code="CAM-N01-OVERHEAD",
            camera_name="North Turnstile Overhead Tracker (Sony 4K)",
            status="ACTIVE"
        )
        cam_south = Camera(
            id=str(uuid.uuid4()),
            gate_id=gate_south.id,
            camera_code="CAM-S01-OVERHEAD",
            camera_name="South Turnstile Overhead Tracker (Axis 4K)",
            status="ACTIVE"
        )
        cam_server = Camera(
            id=str(uuid.uuid4()),
            gate_id=gate_server.id,
            camera_code="CAM-SR01-OPTIC",
            camera_name="Server Room Ceiling Optical Tracker",
            status="ACTIVE"
        )
        cam_exec = Camera(
            id=str(uuid.uuid4()),
            gate_id=gate_exec.id,
            camera_code="CAM-EX01-FRONT",
            camera_name="Executive Entrance Overhead Sensor",
            status="ACTIVE"
        )
        db.add_all([cam_north, cam_south, cam_server, cam_exec])
        db.flush()

        # -------------------------------------------------------------
        # 6. EMPLOYEES & CREDENTIALS (16 synthetic employees across departments)
        # -------------------------------------------------------------
        employee_data = [
            ("EMP-1001", "Rohan Sharma", "rohan.sharma@nexuscorp.internal", "Software Engineering"),
            ("EMP-1002", "Priya Nair", "priya.nair@nexuscorp.internal", "Software Engineering"),
            ("EMP-1003", "Ananya Deshmukh", "ananya.deshmukh@nexuscorp.internal", "Data & AI"),
            ("EMP-1004", "Vikramaditya Iyer", "vikram.iyer@nexuscorp.internal", "Cloud DevOps"),
            ("EMP-1005", "Neha Singhania", "neha.singhania@nexuscorp.internal", "Product Management"),
            ("EMP-1006", "Karthik Raja", "karthik.raja@nexuscorp.internal", "Cybersecurity"),
            ("EMP-1007", "Tanvi Bhatt", "tanvi.bhatt@nexuscorp.internal", "Human Resources"),
            ("EMP-1008", "Sameer Qureshi", "sameer.qureshi@nexuscorp.internal", "Finance & Accounts"),
            ("EMP-1009", "Deepak Verma", "deepak.verma@nexuscorp.internal", "Operations"),
            ("EMP-1010", "Sneha Kulkarni", "sneha.kulkarni@nexuscorp.internal", "Quality Assurance"),
            ("EMP-1011", "Arjun Sen", "arjun.sen@nexuscorp.internal", "Infrastructure"),
            ("EMP-1012", "Meera Pillai", "meera.pillai@nexuscorp.internal", "Legal & Compliance"),
            ("EMP-1013", "Rajeshwari Rao", "rajeshwari.rao@nexuscorp.internal", "Executive Staff"),
            ("EMP-1014", "Gautam Malhotra", "gautam.malhotra@nexuscorp.internal", "Software Engineering"),
            ("EMP-1015", "Ishaan Roy", "ishaan.roy@nexuscorp.internal", "Data & AI"),
            ("EMP-1016", "Pooja Hegde", "pooja.hegde@nexuscorp.internal", "Cloud DevOps")
        ]

        employees = []
        credentials = []
        for code, name, email, dept in employee_data:
            emp = Employee(
                id=str(uuid.uuid4()),
                employee_code=code,
                full_name=name,
                email=email,
                department=dept,
                is_active=True,
                created_at=now - timedelta(days=60)
            )
            employees.append(emp)
            db.add(emp)
            db.flush()

            # Create credential hash
            cred_hash = f"cred_hash_{code.lower()}_{uuid.uuid4().hex[:12]}"
            cred = AccessCredential(
                id=str(uuid.uuid4()),
                employee_id=emp.id,
                credential_hash=cred_hash,
                status="ACTIVE",
                valid_from=now - timedelta(days=60),
                valid_until=now + timedelta(days=365)
            )
            credentials.append(cred)
            db.add(cred)

        db.flush()

        # -------------------------------------------------------------
        # 7. ACCESS EVENTS (24 access events)
        # -------------------------------------------------------------
        access_events = []
        for i in range(24):
            c = credentials[i % len(credentials)]
            g = [gate_north, gate_south, gate_server, gate_exec][i % 4]
            t_offset = timedelta(hours=i * 2, minutes=i * 3)
            decision = "DENIED" if (i == 7 or i == 19) else "GRANTED"
            reason = "Revoked badge identifier" if decision == "DENIED" else None

            ev = AccessEvent(
                id=str(uuid.uuid4()),
                gate_id=g.id,
                credential_id=c.id,
                event_timestamp=now - t_offset,
                direction="ENTRY",
                decision=decision,
                denial_reason=reason,
                external_event_id=f"ext_rfid_evt_{i}_{uuid.uuid4().hex[:6]}"
            )
            access_events.append(ev)
            db.add(ev)

        db.flush()

        # -------------------------------------------------------------
        # 8. CAMERA OBSERVATIONS (36 person crossings)
        # -------------------------------------------------------------
        for j in range(36):
            g = [gate_north, gate_south, gate_server, gate_exec][j % 4]
            c = [cam_north, cam_south, cam_server, cam_exec][j % 4]
            t_offset = timedelta(hours=j * 1.5, minutes=j * 4)
            conf = 0.85 + ((j % 15) * 0.01)

            obs = CameraObservation(
                id=str(uuid.uuid4()),
                gate_id=g.id,
                camera_id=c.id,
                gate_session_id=None,
                tracker_id=f"bytetrack_id_{100 + j}",
                observed_at=now - t_offset,
                direction="ENTRY",
                confidence=round(conf, 3),
                evidence_reference=f"frame_evidence_cam{j%4}_{100+j}.jpg",
                external_event_id=f"ext_cv_obs_{j}_{uuid.uuid4().hex[:6]}"
            )
            db.add(obs)

        db.flush()

        # -------------------------------------------------------------
        # 9. REALISTIC INCIDENTS (11 incidents with varied severities, statuses)
        # -------------------------------------------------------------
        sample_incidents = [
            (
                gate_north, "TAILGATING", 1, 2, 1, 0.94, 63.8, "HIGH", "UNDER_INVESTIGATION",
                "Two individuals observed entering through North Turnstile Portal following one successful badge authorization. One crossing was unmatched. Detection confidence was 0.94.",
                security_user.id
            ),
            (
                gate_server, "TAILGATING", 1, 3, 2, 0.96, 94.2, "CRITICAL", "NEW",
                "Severe security discrepancy at Secure Server Room Data Vault. Three individuals entered following one authorized access credential. Two crossings were unmatched.",
                None
            ),
            (
                gate_south, "UNAUTHORIZED_ENTRY", 0, 1, 1, 0.89, 52.8, "MEDIUM", "ACKNOWLEDGED",
                "Unauthorized entry detected at South Lobby Fastgate. 1 individual crossed without any corresponding badge authorization.",
                security_user.id
            ),
            (
                gate_exec, "TAILGATING", 1, 2, 1, 0.91, 58.2, "MEDIUM", "RESOLVED",
                "Tailgating flagged at Executive Suite. Secondary follower observed without independent swipe.",
                security_user.id
            ),
            (
                gate_north, "TAILGATING", 2, 4, 2, 0.93, 78.6, "HIGH", "RESOLVED",
                "Multi-person tailgating detected at North Lobby. Four individuals entered following two valid authorizations. Two crossings unmatched.",
                admin_user.id
            ),
            (
                gate_north, "TAILGATING", 1, 2, 1, 0.88, 42.6, "MEDIUM", "FALSE_POSITIVE",
                "Tailgating flagged at North Turnstile. Investigation revealed visitor escort protocol followed with physical badge delay.",
                security_user.id
            ),
            (
                gate_server, "UNAUTHORIZED_ENTRY", 0, 1, 1, 0.95, 84.0, "CRITICAL", "UNDER_INVESTIGATION",
                "Unauthorized breach attempt at Data Center Vault Airlock. Physical door pushed open without RFID scan.",
                security_user.id
            ),
            (
                gate_south, "TAILGATING", 1, 2, 1, 0.92, 53.4, "MEDIUM", "NEW",
                "Tailgating observed at South Turnstile Portal. One unmatched follower crossed close behind authorized employee.",
                None
            ),
            (
                gate_north, "TAILGATING", 1, 3, 2, 0.95, 74.0, "HIGH", "ACKNOWLEDGED",
                "Three individuals crossed North Lobby speedlane after single card scan. Two unmatched crossings.",
                security_user.id
            ),
            (
                gate_exec, "UNAUTHORIZED_ENTRY", 0, 1, 1, 0.78, 45.6, "MEDIUM", "NEW",
                "Unmatched crossing observed at Executive Leadership Suite without badge event.",
                None
            ),
            (
                gate_south, "TAILGATING", 2, 3, 1, 0.87, 47.4, "MEDIUM", "RESOLVED",
                "Single unmatched crossing following two valid badge swipes at South Lobby Fastgate.",
                security_user.id
            )
        ]

        incidents = []
        for idx, (gt, itype, auth_c, obs_c, unmatch_c, conf, rscore, sev, stat, summary, assignee) in enumerate(sample_incidents):
            inc_time = now - timedelta(days=idx * 2, hours=idx * 3)
            inc = Incident(
                id=str(uuid.uuid4()),
                gate_id=gt.id,
                gate_session_id=None,
                incident_type=itype,
                authorized_count=auth_c,
                observed_count=obs_c,
                unmatched_count=unmatch_c,
                average_confidence=conf,
                risk_score=rscore,
                severity=sev,
                status=stat,
                summary=summary,
                assigned_to=assignee,
                resolution_notes="Investigation closed and confirmed by security staff." if stat == "RESOLVED" else None,
                created_at=inc_time,
                updated_at=inc_time + timedelta(hours=1)
            )
            incidents.append(inc)
            db.add(inc)
            db.flush()

            # Actions
            action = IncidentAction(
                id=str(uuid.uuid4()),
                incident_id=inc.id,
                actor_id=security_user.id if assignee else admin_user.id,
                action_type="STATUS_CHANGE",
                description=f"Incident initialized with status {stat}",
                created_at=inc_time
            )
            db.add(action)

            # Evidence Asset
            evidence = EvidenceAsset(
                id=str(uuid.uuid4()),
                incident_id=inc.id,
                object_reference=f"cctv_frame_crop_{gt.gate_code}_{idx+1}.jpg",
                media_type="IMAGE_CROPPED",
                checksum=uuid.uuid4().hex,
                is_redacted=True,
                created_at=inc_time
            )
            db.add(evidence)

            # Audit Log
            log = AuditLog(
                id=str(uuid.uuid4()),
                actor_user_id=None,
                entity_type="INCIDENT",
                entity_id=inc.id,
                action="CREATE",
                old_values=None,
                new_values={"incident_type": inc.incident_type, "severity": inc.severity, "risk_score": inc.risk_score},
                occurred_at=inc_time
            )
            db.add(log)

            enqueue_incident_vector_event(db, inc, event_type="INCIDENT_CREATED")

        db.commit()
        logger.info(
            "Database seeded with %s employees, %s gates, %s incidents; "
            "vector synchronization is queued in the transactional outbox.",
            len(employees),
            len(gates),
            len(incidents),
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding error: {e}")
        raise
    finally:
        if should_close:
            db.close()

if __name__ == "__main__":
    seed_database()
