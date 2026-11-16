export type UserRole = 'ADMIN' | 'SECURITY_OFFICER' | 'AUDITOR';

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Employee {
  id: string;
  employee_code: string;
  full_name: string;
  email: string;
  department: string;
  is_active: boolean;
  created_at: string;
}

export interface Gate {
  id: string;
  zone_id: string;
  gate_code: string;
  gate_name: string;
  direction: string;
  is_active: boolean;
  session_window_seconds: number;
  minimum_detection_confidence: number;
  created_at: string;
  zone_name?: string;
  site_name?: string;
}

export interface IncidentAction {
  id: string;
  incident_id: string;
  actor_id: string;
  actor_name?: string;
  action_type: string;
  description: string;
  created_at: string;
}

export interface EvidenceAsset {
  id: string;
  incident_id: string;
  object_reference: string;
  media_type: string;
  checksum: string;
  is_redacted: boolean;
  created_at: string;
}

export interface Incident {
  id: string;
  gate_id: string;
  gate_name?: string;
  zone_name?: string;
  site_name?: string;
  incident_type: 'TAILGATING' | 'UNAUTHORIZED_ENTRY' | string;
  authorized_count: number;
  observed_count: number;
  unmatched_count: number;
  average_confidence: number;
  risk_score: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'NEW' | 'ACKNOWLEDGED' | 'UNDER_INVESTIGATION' | 'RESOLVED' | 'FALSE_POSITIVE';
  summary: string;
  assigned_to?: string | null;
  assigned_officer_name?: string | null;
  resolution_notes?: string | null;
  created_at: string;
  updated_at: string;
  actions?: IncidentAction[];
  evidence?: EvidenceAsset[];
  score_breakdown?: {
    final_score: number;
    severity: string;
    components: {
      unmatched_component: number;
      confidence_component: number;
      zone_sensitivity_bonus: number;
      repeat_incident_bonus: number;
    };
    explanation: string;
  };
}

export interface VectorSearchResult {
  incident_id: string;
  similarity_score: number;
  gate_name?: string;
  site_name?: string;
  incident_type: string;
  severity: string;
  status: string;
  risk_score: number;
  created_at?: string;
  summary: string;
}

export interface OverviewStats {
  total_access_events: number;
  successful_entries: number;
  denied_entries: number;
  total_observed_crossings: number;
  tailgating_incidents: number;
  unauthorized_entry_incidents: number;
  critical_incidents: number;
  high_incidents: number;
  medium_incidents: number;
  low_incidents: number;
  average_risk_score: number;
  average_resolution_hours: number;
}

export interface TrendPoint {
  date: string;
  incidents_count: number;
  tailgating_count: number;
  unauthorized_count: number;
}

export interface GateStat {
  gate_id: string;
  gate_name: string;
  gate_code: string;
  site_name: string;
  incident_count: number;
  avg_risk: number;
}

export interface SeverityBreakdown {
  low: number;
  medium: number;
  high: number;
  critical: number;
}

export interface LiveGateStatus {
  gate_id: string;
  gate_code: string;
  gate_name: string;
  direction: string;
  is_active: boolean;
  zone_name?: string;
  site_name?: string;
  camera_count: number;
  camera_status: string;
  session_active: boolean;
  session_id?: string;
  authorized_count: number;
  observed_count: number;
  last_access_time?: string;
  last_access_decision?: string;
  last_incident_severity?: string;
  last_incident_time?: string;
  last_incident_summary?: string;
}

export interface AuditLog {
  id: string;
  actor_user_id?: string;
  actor_name?: string;
  entity_type: string;
  entity_id: string;
  action: string;
  old_values?: any;
  new_values?: any;
  occurred_at: string;
}
