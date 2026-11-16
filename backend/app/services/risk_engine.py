from typing import Dict, Any

class RiskScoreResult:
    def __init__(
        self,
        final_score: float,
        severity: str,
        unmatched_component: float,
        confidence_component: float,
        zone_sensitivity_bonus: float,
        repeat_incident_bonus: float,
        explanation: str
    ):
        self.final_score = final_score
        self.severity = severity
        self.unmatched_component = unmatched_component
        self.confidence_component = confidence_component
        self.zone_sensitivity_bonus = zone_sensitivity_bonus
        self.repeat_incident_bonus = repeat_incident_bonus
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": self.final_score,
            "severity": self.severity,
            "components": {
                "unmatched_component": self.unmatched_component,
                "confidence_component": self.confidence_component,
                "zone_sensitivity_bonus": self.zone_sensitivity_bonus,
                "repeat_incident_bonus": self.repeat_incident_bonus,
            },
            "explanation": self.explanation
        }

def calculate_risk_score(
    unmatched_count: int,
    average_confidence: float,
    zone_sensitivity_bonus: int = 5,
    repeat_incident_count: int = 0
) -> RiskScoreResult:
    """
    Deterministic explainable risk score heuristic:
    Risk = (25 * unmatched_count) + (20 * avg_confidence) + zone_sensitivity + min(15, 5 * repeat_incidents)
    Clamped strictly between 0 and 100.
    """
    unmatched = max(0, unmatched_count)
    conf = max(0.0, min(1.0, average_confidence))
    
    unmatched_comp = round(25.0 * unmatched, 2)
    conf_comp = round(20.0 * conf, 2)
    zone_bonus = float(zone_sensitivity_bonus)
    repeat_bonus = min(15.0, 5.0 * repeat_incident_count)
    
    raw_score = unmatched_comp + conf_comp + zone_bonus + repeat_bonus
    final_score = round(max(0.0, min(100.0, raw_score)), 2)
    
    if final_score >= 80.0:
        severity = "CRITICAL"
    elif final_score >= 60.0:
        severity = "HIGH"
    elif final_score >= 35.0:
        severity = "MEDIUM"
    else:
        severity = "LOW"
        
    explanation = (
        f"Base penalty of {unmatched_comp:.1f} for {unmatched} unmatched crossing(s), "
        f"{conf_comp:.1f} detection confidence factor ({conf:.2f}), "
        f"{zone_bonus:.1f} zone sensitivity bonus, and {repeat_bonus:.1f} repeat-incident weight."
    )
    
    return RiskScoreResult(
        final_score=final_score,
        severity=severity,
        unmatched_component=unmatched_comp,
        confidence_component=conf_comp,
        zone_sensitivity_bonus=zone_bonus,
        repeat_incident_bonus=repeat_bonus,
        explanation=explanation
    )
