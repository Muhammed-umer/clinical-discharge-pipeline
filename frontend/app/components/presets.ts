export interface Note {
  id: number;
  author_role: string;
  recorded_at: string;
  content: string;
}

export interface Evidence {
  source_document: string;
  extracted_text: string;
  author_role: string;
  recorded_at?: string;
}

export interface Claim {
  id: string;
  category: string;
  value: string;
  confidence_score: number;
  confidence_level: string;
  evidence: Evidence[];
  author_role: string;
  recorded_at: string;
  status: string;
}

export interface Conflict {
  field: string;
  conflicting_values: string[];
  detected_from: string[];
  recommended_action: string;
  severity: string;
}

export interface MissingField {
  field_name: string;
  reason: string;
  requires_physician_review: boolean;
}

export interface ClinicalWarning {
  field: string;
  severity: string;
  message: string;
}

export interface GroundingMetrics {
  grounding_score: number;
  evidence_coverage: number;
  citation_completeness: number;
}

export interface StayDetails {
  stay_id: string;
  patient_name: string;
  status: string;
  notes: Note[];
  claims: Claim[];
  final_summary: {
    summary: {
      patient_details: {
        name: string;
        patient_id: string;
        age_sex: string;
        date_of_admission?: string;
        date_of_discharge?: string;
      };
      admission_details: {
        reason_for_admission: string;
        mode_of_admission: string;
      };
      diagnoses: Array<{
        diagnosis: string;
        confidence: { score: number; level: string };
        evidence: Evidence[];
        claim_id: string;
      }>;
      symptoms: Array<{
        observation: string;
        confidence: { score: number; level: string };
        evidence: Evidence[];
        claim_id: string;
      }>;
      clinical_summary: string;
      treatment_provided: string;
      investigations: Array<{
        investigation: string;
        result: string;
        confidence: { score: number; level: string };
        evidence: Evidence[];
        claim_id: string;
      }>;
      discharge_condition: string;
      prescribed_medications: Array<{
        name: string;
        dosage: string;
        frequency: string;
        duration: string;
        confidence: { score: number; level: string };
        evidence: Evidence[];
        claim_id: string;
      }>;
      follow_up_instructions: {
        recommended_follow_up: string;
        next_follow_up_date: string;
        lifestyle_dietary_instructions: string;
        claim_id?: string;
      };
      discharging_physician_name: string;
      missing_information: MissingField[];
    };
    validation: {
      grounded: boolean;
      confidence: number;
      unsupported_claims: string[];
      conflicts: Conflict[];
      notes: string[];
      grounding_metrics?: GroundingMetrics;
      warnings?: ClinicalWarning[];
    };
  } | null;
  is_reconciled: boolean;
  reviewed_by: string | null;
  reviewed_at: string | null;
  grounding_score: number;
}

export interface PendingDocument {
  id: string;
  filename: string;
  docType: string;
  authorRole: string;
  content: string;
  recorded_at: string;
  status: 'pending' | 'uploading' | 'success' | 'failed';
  error?: string;
}

export interface PresetNote {
  filename: string;
  docType: string;
  authorRole: string;
  content: string;
  recorded_at: string;
}

export interface PresetCase {
  id: string;
  name: string;
  title: string;
  desc: string;
  notes: PresetNote[];
}

export const SAMPLE_CASES: PresetCase[] = [
  {
    id: "CASE-PNEUMONIA-983",
    name: "Robert Harrison",
    title: "Sample Case 1: Pneumonia (Antibiotic Switch)",
    desc: "Consistent transition check from intravenous Ceftriaxone to oral Cefuroxime on discharge.",
    notes: [
      {
        filename: "resident_admission_log.txt",
        docType: "Resident Note",
        authorRole: "RESIDENT",
        content: "Patient Robert Harrison admitted with fever (102F), productive cough, and shortness of breath. Chest X-ray confirms right lower lobe lobar consolidation. Started on Ceftriaxone 1g IV daily. Discharging Physician: Dr. Robert Chen.",
        recorded_at: "2026-06-21T08:00:00"
      },
      {
        filename: "pulmonologist_consult.txt",
        docType: "Consultant Note",
        authorRole: "CONSULTANT",
        content: "Pulmonology consult: Patient responding well to Ceftriaxone IV. Right lower lobe pneumonia resolving. Recommend switching to oral Cefuroxime 500mg BID on discharge to complete a 5-day course. Outpatient pulmonary follow-up in 10 days.",
        recorded_at: "2026-06-22T14:30:00"
      },
      {
        filename: "nurse_ward_note.txt",
        docType: "Nurse Note",
        authorRole: "WARD_NURSE",
        content: "Patient completed Ceftriaxone IV course. Ambulatory and tolerating oral diet. Discharging Physician: Dr. Robert Chen. Patient education provided regarding oral Cefuroxime 500mg BID and clinic review.",
        recorded_at: "2026-06-23T09:15:00"
      }
    ]
  },
  {
    id: "CASE-DIABETES-402",
    name: "Muhammed Ahmed",
    title: "Sample Case 2: Diabetes (Medication Conflict)",
    desc: "Triggers prescribing discrepancy warning (Metformin 500mg BID vs daily) due to clinical contradictions.",
    notes: [
      {
        filename: "rmo_ward_log.txt",
        docType: "Resident Note",
        authorRole: "RESIDENT",
        content: "Patient Muhammed Ahmed admitted with diabetic foot ulcer. History of Type-2 Diabetes. Started Metformin 500mg BID. Prescribed Metformin 500mg BID for discharge review.",
        recorded_at: "2026-06-21T10:00:00"
      },
      {
        filename: "endocrinology_consult.txt",
        docType: "Consultant Note",
        authorRole: "CONSULTANT",
        content: "Endocrine consult: Patient has stable diabetic foot ulcer, but creatinine is slightly elevated. Metformin dosage should be adjusted to Metformin 500mg daily to avoid lactic acidosis risks. Discontinue NSAIDs.",
        recorded_at: "2026-06-22T11:00:00"
      },
      {
        filename: "attending_discharge_draft.txt",
        docType: "Discharge Draft",
        authorRole: "ATTENDING",
        content: "Discharge draft: Patient clinically stable, ulcer healing. Discharging on Metformin 500mg BD. Discharging Physician: Dr. Sarah Jenkins. Follow up in outpatient clinic in 14 days. Condition on discharge is stable.",
        recorded_at: "2026-06-23T16:00:00"
      }
    ]
  },
  {
    id: "CASE-CARDIOLOGY-117",
    name: "Eleanor Vance",
    title: "Sample Case 3: Cardiology (Aspirin Discrepancy)",
    desc: "Flags Aspirin discrepancy (75mg vs 150mg) between Specialist recommendation and Nurse discharge instructions.",
    notes: [
      {
        filename: "admission_notes.txt",
        docType: "Resident Note",
        authorRole: "RESIDENT",
        content: "Patient Eleanor Vance admitted with chest tightness. Diagnosed with unstable Angina. Started Aspirin 75mg daily. Discharging Physician: Dr. James Mercer.",
        recorded_at: "2026-06-21T09:00:00"
      },
      {
        filename: "cardiologist_evaluation.txt",
        docType: "Consultant Note",
        authorRole: "CONSULTANT",
        content: "Cardiology consult: EKG shows mild ischemia. Due to high thrombotic risk, recommend adjusting Aspirin to 150mg daily. Add Metoprolol 25mg BID.",
        recorded_at: "2026-06-22T13:45:00"
      },
      {
        filename: "ward_nurse_discharge_checklist.txt",
        docType: "Nurse Note",
        authorRole: "WARD_NURSE",
        content: "Discharge instructions: Continue Aspirin 75mg daily and Metoprolol 25mg BID. Follow up in outpatient clinic in 7 days.",
        recorded_at: "2026-06-23T10:30:00"
      }
    ]
  }
];
