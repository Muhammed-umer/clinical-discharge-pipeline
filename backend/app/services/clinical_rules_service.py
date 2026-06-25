"""
Clinical Rule Engine — Priority 5

A lightweight, data-driven clinical safety rule engine that evaluates the merged
discharge summary against a set of structured clinical rules and appends
ClinicalWarningSchema entries to the validation report.

Design principles:
- Rules are defined as structured data (RuleDefinition dataclasses), not ad-hoc
  conditional branches scattered through the arbitration service.
- Adding new rules does not require touching the arbitration or validation layers.
- The engine is stateless — it reads the summary and returns an updated copy.
- No external dependencies beyond the project's own schema module.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Callable

from app.models.schemas import FinalDischargeSummary, ClinicalWarningSchema

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Rule definition structure
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClinicalRule:
    """
    Represents a single clinical safety rule.

    Attributes:
        rule_id:     Unique identifier (used in logs for traceability).
        description: Human-readable description of the rule.
        field:       The summary field this rule targets (used in the warning).
        severity:    Warning severity level: CRITICAL, HIGH, MEDIUM, LOW.
        condition:   A callable that returns True if the rule is violated.
                     Receives the FinalDischargeSummary as argument.
        message:     The actionable warning message emitted when violated.
    """
    rule_id: str
    description: str
    field: str
    severity: str
    condition: Callable[[FinalDischargeSummary], bool]
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Rule registry
# ─────────────────────────────────────────────────────────────────────────────

def _has_metformin(summary: FinalDischargeSummary) -> bool:
    """Returns True if any prescribed medication contains Metformin."""
    for med in summary.summary.prescribed_medications:
        if "metformin" in med.name.lower():
            return True
    return False


def _has_elevated_creatinine(summary: FinalDischargeSummary) -> bool:
    """Returns True if any investigation references elevated creatinine."""
    for inv in summary.summary.investigations:
        if "creatinine" in inv.investigation.lower():
            result_lower = inv.result.lower()
            if any(kw in result_lower for kw in ["elevat", "high", "raised", "abnormal", "above"]):
                return True
    # Also check diagnoses for creatinine-related entries
    for diag in summary.summary.diagnoses:
        if "creatinine" in diag.diagnosis.lower():
            return True
    return False


def _no_discharge_condition(summary: FinalDischargeSummary) -> bool:
    """Returns True if discharge condition is undocumented."""
    return summary.summary.discharge_condition == "NOT_DOCUMENTED"


def _no_follow_up_date(summary: FinalDischargeSummary) -> bool:
    """Returns True if follow-up date is undocumented."""
    fi = summary.summary.follow_up_instructions
    return fi is None or fi.next_follow_up_date == "NOT_DOCUMENTED"


def _no_medications(summary: FinalDischargeSummary) -> bool:
    """Returns True if no discharge medications were prescribed."""
    return len(summary.summary.prescribed_medications) == 0


def _no_follow_up(summary: FinalDischargeSummary) -> bool:
    """Returns True if follow-up instructions are entirely undocumented."""
    fi = summary.summary.follow_up_instructions
    return fi is None or fi.recommended_follow_up == "NOT_DOCUMENTED"


# The rule registry — add new rules here without touching any other service
CLINICAL_RULES: List[ClinicalRule] = [
    ClinicalRule(
        rule_id="RULE_001",
        description="Metformin prescribed with elevated creatinine",
        field="medication.Metformin",
        severity="CRITICAL",
        # Rule fires when BOTH conditions are true simultaneously
        condition=lambda s: _has_metformin(s) and _has_elevated_creatinine(s),
        message=(
            "CRITICAL: Metformin is prescribed while elevated creatinine is documented. "
            "Risk of lactic acidosis. Attending physician must review and confirm dosage "
            "or substitute an alternative hypoglycaemic agent. "
            "eGFR must be checked before continuing Metformin."
        ),
    ),
    ClinicalRule(
        rule_id="RULE_002",
        description="Discharge condition not documented",
        field="discharge_condition",
        severity="HIGH",
        condition=_no_discharge_condition,
        message=(
            "Discharge condition is NOT_DOCUMENTED. NABH standards require the patient's "
            "clinical condition at discharge to be explicitly recorded. "
            "Physician review required before finalising the discharge summary."
        ),
    ),
    ClinicalRule(
        rule_id="RULE_003",
        description="Follow-up date not documented",
        field="follow_up_instructions.next_follow_up_date",
        severity="MEDIUM",
        condition=_no_follow_up_date,
        message=(
            "Follow-up appointment date is NOT_DOCUMENTED. Patients must be given a "
            "specific date or timeframe for their next clinical review. "
            "Add follow-up details before discharge."
        ),
    ),
    ClinicalRule(
        rule_id="RULE_004",
        description="No discharge medications prescribed",
        field="prescribed_medications",
        severity="HIGH",
        condition=_no_medications,
        message=(
            "No discharge medications are documented. If the patient was on active "
            "treatment during the stay, discharge prescriptions must be recorded. "
            "Physician review required."
        ),
    ),
    ClinicalRule(
        rule_id="RULE_005",
        description="Follow-up instructions not documented",
        field="follow_up_instructions",
        severity="MEDIUM",
        condition=_no_follow_up,
        message=(
            "Follow-up instructions are NOT_DOCUMENTED. NABH discharge summaries require "
            "explicit outpatient follow-up guidance to be provided to the patient."
        ),
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Rule engine
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalRulesEngine:
    """
    Evaluates the merged FinalDischargeSummary against all registered clinical
    rules. Appends ClinicalWarningSchema entries to the validation report for
    every violated rule.

    Usage:
        engine = ClinicalRulesEngine()
        finalized_summary = engine.evaluate_rules(finalized_summary)
    """

    def evaluate_rules(
        self, summary: FinalDischargeSummary
    ) -> FinalDischargeSummary:
        """
        Runs all registered clinical rules against the summary and appends
        warnings for any violations to the validation report.

        Returns the updated FinalDischargeSummary (mutates in-place and returns).
        """
        if summary.validation.warnings is None:
            summary.validation.warnings = []

        triggered_count = 0
        for rule in CLINICAL_RULES:
            try:
                if rule.condition(summary):
                    logger.warning(
                        f"Clinical rule violated [{rule.rule_id}]: {rule.description}"
                    )
                    warning = ClinicalWarningSchema(
                        field=rule.field,
                        severity=rule.severity,
                        message=f"[{rule.rule_id}] {rule.message}",
                    )
                    summary.validation.warnings.append(warning)
                    triggered_count += 1
                else:
                    logger.debug(f"Rule [{rule.rule_id}] passed: {rule.description}")
            except Exception as e:
                # A rule evaluation error must not crash the pipeline.
                # Log and continue.
                logger.error(
                    f"Error evaluating clinical rule [{rule.rule_id}]: {str(e)}"
                )

        logger.info(
            f"Clinical rule evaluation complete. "
            f"{triggered_count}/{len(CLINICAL_RULES)} rules triggered."
        )
        return summary
