import React from 'react';
import { StayDetails } from './presets';
import { MissingInfoIndicator } from './MissingInfoIndicator';

interface DischargeSummaryCardProps {
  stayDetails: StayDetails | null;
  loading: boolean;
  handlePhysicianApprove: () => void;
}

export const DischargeSummaryCard: React.FC<DischargeSummaryCardProps> = ({
  stayDetails,
  loading,
  handlePhysicianApprove
}) => {
  const summary = stayDetails?.final_summary?.summary;

  const isMedConflicting = (medName: string) => {
    if (!stayDetails?.final_summary?.validation?.conflicts) return false;
    return stayDetails.final_summary.validation.conflicts.some(c => 
      c.field.toLowerCase().includes(medName.toLowerCase())
    );
  };

  return (
    <section id="section-7" className="py-16 border-b border-slate-900 bg-slate-900/20">
      <div className="max-w-5xl mx-auto">
        
        <div className="text-center md:text-left mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-black font-mono uppercase tracking-widest text-teal-400">
              Generated Discharge Summary
            </h2>
            <p className="text-slate-400 text-xs mt-1">
              NABH Compliant Structured Record with verification signatures.
            </p>
          </div>

          {/* Attending Seal Button Gate */}
          {stayDetails && summary && (
            <div>
              <button
                onClick={handlePhysicianApprove}
                disabled={loading || stayDetails.status === 'NEEDS_RECONCILIATION' || stayDetails.is_reconciled}
                className={`px-6 py-2.5 rounded-lg text-xs font-bold font-mono uppercase border transition-all ${
                  stayDetails.is_reconciled
                    ? 'bg-slate-900 border-emerald-900 text-emerald-400 cursor-not-allowed'
                    : stayDetails.status === 'NEEDS_RECONCILIATION'
                    ? 'bg-slate-955 border-rose-955 text-rose-500 cursor-not-allowed'
                    : 'bg-teal-500 border-teal-600 hover:bg-teal-400 text-slate-955 shadow-lg hover:scale-102'
                }`}
              >
                {stayDetails.is_reconciled
                  ? "✓ Case Review Sealed"
                  : stayDetails.status === 'NEEDS_RECONCILIATION'
                  ? "Physician Review Required"
                  : "Finalize Summary"}
              </button>
            </div>
          )}
        </div>

        {!stayDetails || !stayDetails.final_summary || !summary ? (
          <div className="bg-slate-900/40 border border-slate-900 border-dashed rounded-xl p-10 text-center text-slate-505 text-xs font-mono">
            No discharge summary generated.
          </div>
        ) : (
          /* The Printable Medical paper layout */
          <div id="printable-discharge-report" className="bg-slate-900 border border-slate-800 rounded-xl p-6 sm:p-10 shadow-2xl space-y-8 text-slate-300 font-mono text-xs">
          
          {/* Header Letterhead */}
          <div className="border-b-2 border-slate-800 pb-5 text-center sm:text-left flex flex-col sm:flex-row justify-between items-center gap-4">
            <div>
              <h2 className="text-base font-black text-slate-100 uppercase tracking-widest font-sans">
                METROPOLITAN CLINICAL MEDICAL CENTER
              </h2>
              <p className="text-[10px] text-slate-500 font-bold uppercase mt-0.5">
                Department of Internal Medicine | Electronic Health Records Index
              </p>
            </div>
            <div className="text-right font-mono text-[10px] text-slate-505">
              <div>NABH STANDARD FORMAT</div>
            </div>
          </div>

          {/* Demographics Box */}
          <div className="space-y-4 bg-slate-950 p-6 rounded-xl border border-slate-800">
            {/* Row 1 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-b border-slate-850 pb-4">
              <div>
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Patient Name</div>
                <div className="font-black text-slate-100 text-sm mt-1">
                  <MissingInfoIndicator value={summary.patient_details.name} />
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Age / Gender</div>
                <div className="font-bold text-slate-200 mt-1">
                  <MissingInfoIndicator value={summary.patient_details.age_sex} />
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Discharging Physician</div>
                <div className="font-bold text-teal-400 mt-1">
                  <MissingInfoIndicator value={summary.discharging_physician_name} />
                </div>
              </div>
            </div>
            {/* Row 2 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Date of Admission</div>
                <div className="font-bold text-slate-300 mt-1" suppressHydrationWarning={true}>
                  {summary.patient_details.date_of_admission 
                    ? <MissingInfoIndicator value={new Date(summary.patient_details.date_of_admission).toLocaleDateString()} />
                    : <MissingInfoIndicator value="NOT_DOCUMENTED" />}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Date of Discharge</div>
                <div className="font-bold text-slate-300 mt-1" suppressHydrationWarning={true}>
                  {summary.patient_details.date_of_discharge 
                    ? <MissingInfoIndicator value={new Date(summary.patient_details.date_of_discharge).toLocaleDateString()} />
                    : <MissingInfoIndicator value="NOT_DOCUMENTED" />}
                </div>
              </div>
            </div>
          </div>

          {/* 1. Reason for Admission */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>1. Admission Reason & Chief Presentation</span>
            </h4>
            <p className="text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-900 leading-relaxed">
              <MissingInfoIndicator value={summary.admission_details.reason_for_admission} /> (Admission Mode: <MissingInfoIndicator value={summary.admission_details.mode_of_admission} />)
            </p>
          </div>

          {/* 2. Reconciled Diagnoses */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>2. Reconciled Diagnoses</span>
            </h4>
            <div className="space-y-3">
              {summary.diagnoses.map((diag, i) => (
                <div key={i} className="bg-slate-950 p-4 rounded-xl border border-slate-900">
                  <div className="flex justify-between items-start gap-2 mb-1">
                    <span className="font-bold text-slate-100"><MissingInfoIndicator value={diag.diagnosis} /></span>
                  </div>
                  
                  {diag.evidence.length > 0 && (
                    <div className="text-[10px] text-slate-400 border-t border-slate-900/60 pt-2 mt-2 font-medium">
                      Citations:
                      {diag.evidence.map((ev, eIdx) => (
                        <span key={eIdx} className="block mt-1 italic text-slate-400 pl-2">
                          - "{ev.extracted_text}" (<MissingInfoIndicator value={ev.source_document} />)
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 3. Hospital Course */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>3. Hospital Course Narrative</span>
            </h4>
            <p className="text-slate-300 bg-slate-955 p-4 rounded-xl border border-slate-900 leading-relaxed whitespace-pre-line">
              <MissingInfoIndicator value={summary.clinical_summary} />
            </p>
          </div>

          {/* 4. Investigations */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>4. Investigations & Clinical Findings</span>
            </h4>
            <div className="space-y-3">
              {summary.investigations.map((inv, i) => (
                <div key={i} className="bg-slate-950 p-4 rounded-xl border border-slate-900">
                  <span className="font-bold text-slate-200"><MissingInfoIndicator value={inv.investigation} /></span>
                  <p className="text-slate-300 mt-1">Result: <span className="font-bold text-slate-100"><MissingInfoIndicator value={inv.result} /></span></p>
                </div>
              ))}
            </div>
          </div>

          {/* 5. Treatment Provided */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>5. Clinical Treatment & Interventions</span>
            </h4>
            <p className="text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-900 leading-relaxed">
              <MissingInfoIndicator value={summary.treatment_provided} />
            </p>
          </div>

          {/* 6. Medication on Discharge */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>6. Prescribed Medications on Discharge</span>
            </h4>
            <div className="overflow-x-auto max-h-96 border border-slate-900 rounded-xl">
              <table className="w-full text-left text-xs bg-slate-955 rounded-xl overflow-hidden">
                <thead className="sticky top-0 bg-slate-900 text-slate-400 border-b border-slate-800 z-10">
                  <tr>
                    <th className="p-3 text-[10px] font-bold uppercase tracking-wider">Medication Name</th>
                    <th className="p-3 text-[10px] font-bold uppercase tracking-wider">Dosage</th>
                    <th className="p-3 text-[10px] font-bold uppercase tracking-wider">Frequency</th>
                    <th className="p-3 text-[10px] font-bold uppercase tracking-wider">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900 text-slate-300">
                  {summary.prescribed_medications.map((med, i) => {
                    const isConflicting = isMedConflicting(med.name);
                    return (
                      <tr key={i} className={`hover:bg-slate-800/40 transition-colors ${i % 2 === 0 ? 'bg-slate-950' : 'bg-slate-900/30'} ${isConflicting ? 'border-l-[4px] border-l-rose-500 bg-rose-500/5 hover:bg-rose-500/10' : ''}`}>
                        <td className="p-3 font-bold text-slate-200">
                          <div className="flex flex-col gap-1">
                            <span><MissingInfoIndicator value={med.name} /></span>
                            {isConflicting && (
                              <span className="inline-flex items-center gap-1 self-start bg-rose-500/10 text-rose-455 border border-rose-500/25 px-1.5 py-0.5 rounded text-[8px] font-mono uppercase tracking-wider font-bold">
                                ⚠️ Physician Review Required
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-3 text-slate-300"><MissingInfoIndicator value={med.dosage} /></td>
                        <td className="p-3 text-slate-300"><MissingInfoIndicator value={med.frequency} /></td>
                        <td className="p-3 text-slate-300"><MissingInfoIndicator value={med.duration} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 7. Discharge Condition */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>7. Condition at Discharge Window</span>
            </h4>
            <p className="text-slate-300 bg-slate-955 p-4 rounded-xl border border-slate-900 leading-relaxed">
              <MissingInfoIndicator value={summary.discharge_condition} />
            </p>
          </div>

          {/* 8. Follow-up Instructions */}
          <div className="space-y-2">
            <h4 className="font-bold text-teal-400 border-b border-slate-800 pb-2 flex justify-between items-center text-xs uppercase tracking-widest font-sans">
              <span>8. Outpatient Follow-up Instructions</span>
            </h4>
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-900 space-y-3">
              <div>
                <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Recommended Consultations</span>
                <span className="text-slate-200 font-bold mt-1 block"><MissingInfoIndicator value={summary.follow_up_instructions.recommended_follow_up} /></span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Target Timeline</span>
                <span className="text-slate-200 font-bold mt-1 block"><MissingInfoIndicator value={summary.follow_up_instructions.next_follow_up_date} /></span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Dietary & lifestyle Advice</span>
                <span className="text-slate-300 leading-relaxed mt-1 block"><MissingInfoIndicator value={summary.follow_up_instructions.lifestyle_dietary_instructions} /></span>
              </div>
            </div>
          </div>

          {/* Human reviewed stamp seal */}
          <div className="border-t border-slate-800 pt-6 mt-8 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div className="text-[10px] text-slate-500">
              Summary generated chronologically from raw electronic clinical records.
            </div>
            
            <div className="text-center sm:text-right relative">
              {stayDetails.is_reconciled ? (
                <div className="inline-block border-4 border-emerald-500/60 bg-emerald-500/5 text-emerald-400 px-6 py-3 rounded-md font-mono uppercase tracking-wider relative select-none transform rotate-[-2deg] border-double shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                  <div className="absolute -top-3 -left-3 bg-emerald-500 text-slate-955 font-sans font-black text-[9px] px-1.5 py-0.5 rounded shadow">
                    APPROVED
                  </div>
                  <div className="text-xs font-black tracking-widest flex items-center justify-center gap-1">
                    ✓ REVIEW SEAL ACTIVE
                  </div>
                  <div className="font-bold text-xs mt-1 text-slate-100">
                    Dr. Sarah Jenkins
                  </div>
                  <div className="text-[9px] opacity-80 mt-0.5" suppressHydrationWarning={true}>
                    SIGNED: {new Date(stayDetails.reviewed_at || '').toLocaleString()}
                  </div>
                </div>
              ) : (
                <div className="inline-block border-4 border-rose-500/60 bg-rose-500/5 text-rose-500 px-6 py-3 rounded-md font-mono uppercase tracking-wider relative select-none transform rotate-[-2deg] border-double shadow-[0_0_15px_rgba(244,63,94,0.1)] animate-pulse">
                  <div className="absolute -top-3 -left-3 bg-rose-500 text-slate-955 font-sans font-black text-[9px] px-1.5 py-0.5 rounded shadow">
                    PENDING
                  </div>
                  <div className="text-xs font-black tracking-widest flex items-center justify-center gap-1">
                    ⚠ PENDING REVIEW
                  </div>
                  <div className="font-bold text-xs mt-1 text-slate-150">
                    Physician Review Required
                  </div>
                  <div className="text-[9px] opacity-80 mt-0.5">
                    Awaiting Attending Signature
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
        )}

      </div>
    </section>
  );
};
