export interface Incident {
  incident_id: number; scan_id: number; detected_time: string; severity: string; status: string;
  scan_time: string; access_result: string; gate_id: number; gate_name: string; location: string;
  card_no: string; emp_id: number; employee: string; department: string;
  observations?: number; reports?: number; pending_alerts?: number;
}

export interface Observation {
  obs_id: string; incident_id: number; method: string; observed_count: number; authorized_count: number;
  excess?: number; timestamp: string; location?: { gate_id: number; gate_name: string; scan_id: number };
  observed_by?: string; notes?: string; tags?: string[]; updated_by?: string; updated_at?: string;
}

export interface Attachment { file_name: string; file_type: string; note?: string }

export interface Report {
  report_id: string; incident_id: number; description: string;
  reported_by: { username: string; role: string }; attachments: Attachment[]; timestamp: string; updated_at?: string;
}

export interface Alert {
  alert_id: string; incident_id: number; alert_time: string; alert_type: string; severity?: string;
  message: string; ack_status: string; acknowledged: { by: string; at: string; comment?: string } | null; recipients?: string[];
}

export const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
export const INCIDENT_STATUSES = ["OPEN", "INVESTIGATING", "RESOLVED", "FALSE_ALARM"];
export const METHODS = ["MANUAL_HEADCOUNT", "GUARD_PATROL", "TURNSTILE_COUNTER", "SIMULATED"];
export const ALERT_TYPES = ["TAILGATING", "ESCALATION", "REPEAT_OFFENDER", "SYSTEM"];
