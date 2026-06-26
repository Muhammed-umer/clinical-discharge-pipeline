import React from 'react';
import { StayDetails } from './presets';
import { MissingInfoIndicator } from './MissingInfoIndicator';

interface DetectedConflictsProps {
  stayDetails: StayDetails | null;
  showResolveEditor: boolean;
  setShowResolveEditor: (val: boolean) => void;
  resolvedMeds: Array<{ name: string; dosage: string; frequency: string; duration: string }>;
  handleReconcileConflict: (e: React.FormEvent) => void;
  handleMedResolutionChange: (index: number, field: string, value: string) => void;
  loading: boolean;
}

export const DetectedConflicts: React.FC<DetectedConflictsProps> = ({
  stayDetails,
  showResolveEditor,
  setShowResolveEditor,
  resolvedMeds,
  handleReconcileConflict,
  handleMedResolutionChange,
  loading
}) => {
  const conflicts = stayDetails?.final_summary?.validation?.conflicts || [];
  const historicalMeds = stayDetails?.final_summary?.validation?.historical_medications || [];
  const mergedDuplicates = stayDetails?.final_summary?.validation?.merged_duplicates || [];

  return (
    <section id="section-5" className="py-16 border-b border-slate-900 bg-slate-900/10">
      <div className="max-w-5xl mx-auto">
        <div className="text-center md:text-left mb-6">
          <h2 className="text-lg font-black font-mono uppercase tracking-widest text-teal-400">
            Detected Conflicts
          </h2>
          <p className="text-slate-400 text-xs mt-1">
            Scans notes timeline for prescribing variations or treatment conflicts.
          </p>
        </div>

        {/* Render automated resolution logs if any exist */}
        {(historicalMeds.length > 0 || mergedDuplicates.length > 0) && (
          <div className="mb-6 space-y-2.5">
            {mergedDuplicates.map((med, mIdx) => (
              <div key={`merged-${mIdx}`} className="bg-slate-900/40 border border-emerald-950/30 p-3.5 rounded-xl text-xs font-mono text-emerald-400 flex items-center gap-2">
                <span className="text-emerald-400 font-bold">✓</span>
                <div>
                  <span className="font-bold">Automatically merged duplicate medication:</span>{' '}
                  <span className="text-slate-200">{med.name} {med.dosage} {med.frequency}</span>
                  {med.duration && med.duration !== "NOT_DOCUMENTED" && (
                    <>
                      {' '}— kept documented duration: <span className="text-slate-200">{med.duration}</span>
                    </>
                  )}
                  <span className="text-slate-500 text-[10px] ml-2 block sm:inline">
                    (Evidence from: {med.evidence.map(e => e.author_role).join(', ')})
                  </span>
                </div>
              </div>
            ))}
            {historicalMeds.map((med, hIdx) => (
              <div key={`hist-${hIdx}`} className="bg-slate-900/40 border border-slate-800/40 p-3.5 rounded-xl text-xs font-mono text-slate-400 flex items-center gap-2">
                <span className="text-slate-400 font-bold">✓</span>
                <div>
                  <span className="font-bold text-slate-400">Historical inpatient medication excluded:</span>{' '}
                  <span className="text-slate-400/80">{med.name} {med.dosage} {med.frequency}</span>
                  {med.evidence && med.evidence.length > 0 && (
                    <span className="text-slate-600 text-[10px] ml-2 block sm:inline">
                      (Source: {med.evidence[0].author_role})
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Check for conflicts / Success State */}
        {stayDetails && (stayDetails.status === 'READY_FOR_REVIEW' || stayDetails.status === 'COMPLETED') ? (
          <div className="bg-emerald-950/10 border border-emerald-500/30 p-6 rounded-xl text-xs font-mono text-emerald-400 space-y-4">
            <h3 className="font-black text-emerald-400 text-sm uppercase tracking-wide flex items-center gap-2">
              ✓ Medication reconciliation completed
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-slate-300">
              <div>
                <span className="text-slate-500 text-[10px] block uppercase font-bold tracking-wider">Reviewed by</span>
                <span className="font-bold text-slate-200">Attending Physician</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block uppercase font-bold tracking-wider">Decision Time</span>
                <span className="font-bold text-slate-200">
                  {stayDetails.reviewed_at 
                    ? new Date(stayDetails.reviewed_at).toLocaleString() 
                    : new Date().toLocaleString()}
                </span>
              </div>
              <div className="md:col-span-2">
                <span className="text-slate-500 text-[10px] block uppercase font-bold tracking-wider">Final Medication</span>
                <div className="font-bold text-slate-100 space-y-1 mt-1">
                  {stayDetails.final_summary?.summary?.prescribed_medications.map((med, mIdx) => (
                    <div key={mIdx}>
                      {med.name} {med.dosage} {med.frequency}
                      {med.duration && med.duration !== 'NOT_DOCUMENTED' ? ` for ${med.duration}` : ''}
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block uppercase font-bold tracking-wider">Status</span>
                <span className="inline-block bg-emerald-500 text-slate-955 font-bold px-2 py-0.5 rounded text-[10px] uppercase mt-1">
                  Conflict Resolved
                </span>
              </div>
            </div>

            {/* Display Clinical Audit trail */}
            {stayDetails.final_summary?.validation?.clinical_audit && (
              <div className="border-t border-emerald-500/20 pt-4 mt-4 space-y-3">
                <h4 className="font-bold text-emerald-400 uppercase tracking-wider text-[11px]">
                  Clinical Audit
                </h4>
                <div className="bg-slate-950 p-4 rounded-xl border border-emerald-955/20 text-xs font-mono space-y-3">
                  <div className="flex flex-col md:flex-row md:items-center gap-2 text-slate-400">
                    <span className="font-bold uppercase text-[10px] text-slate-500">Original Recommendation:</span>
                    <div className="flex flex-wrap items-center gap-1.5 text-slate-350">
                      {stayDetails.final_summary.validation.clinical_audit.original_recommendations.map((rec: any, rIdx: number) => (
                        <React.Fragment key={rIdx}>
                          {rIdx > 0 && <span className="text-slate-500">↓</span>}
                          <span className="bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-[10px]">
                            <span className="text-slate-400 font-bold">{rec.role}:</span> {rec.value}
                          </span>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col md:flex-row md:items-center gap-2 text-slate-400">
                    <span className="font-bold uppercase text-[10px] text-slate-500">Physician Decision:</span>
                    <span className="text-emerald-400 font-bold">
                      {stayDetails.final_summary.validation.clinical_audit.physician_decision}
                    </span>
                  </div>
                  <div className="text-slate-400">
                    <span className="font-bold uppercase text-[10px] text-slate-500 block mb-1">Reason:</span>
                    <p className="italic text-slate-300 bg-slate-900/40 p-2.5 rounded border border-slate-900">
                      "{stayDetails.final_summary.validation.clinical_audit.reason}"
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : !stayDetails || conflicts.length === 0 ? (
          (historicalMeds.length === 0 && mergedDuplicates.length === 0) && (
            <div className="bg-slate-900/40 border border-slate-900 border-dashed rounded-xl p-10 text-center text-slate-505 text-xs font-mono">
              No conflicts detected.
            </div>
          )
        ) : (
          <div className="space-y-4">
            {conflicts.map((conf, cIdx) => (
              <div key={cIdx} className="bg-rose-955/10 border border-rose-900/50 p-5 rounded-xl text-xs font-mono relative">
                <div className="absolute top-4 right-4 text-[9px] font-mono font-bold bg-rose-500/10 text-rose-455 border border-rose-500/25 px-2.5 py-0.5 rounded uppercase">
                  Severity: {conf.severity}
                </div>

                <h3 className="font-bold text-rose-455 text-sm uppercase tracking-wide mb-3">
                  ⚠️ Clinical Conflict: {conf.field.toUpperCase()}
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  {conf.conflicting_values.map((val, vIdx) => (
                    <div key={vIdx} className="p-3 bg-slate-955 border border-slate-900 rounded-lg">
                      <div className="text-[9px] text-slate-500 mb-1">
                        Document: <span className="text-slate-355 font-bold">{conf.detected_from[vIdx]}</span>
                      </div>
                      <p className="text-slate-205 italic font-mono">
                        "{val}"
                      </p>
                    </div>
                  ))}
                </div>

                <div className="bg-slate-955 p-3 rounded-lg border border-slate-900 text-slate-300">
                  <span className="font-bold text-teal-400">Recommended Reconciliation:</span> {conf.recommended_action}
                </div>
              </div>
            ))}

            {/* Overwrite editor form */}
            <div className="mt-6 border-t border-slate-900 pt-6">
              {!showResolveEditor ? (
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowResolveEditor(true)}
                    className="bg-rose-700 hover:bg-rose-650 text-slate-100 font-bold py-2.5 px-6 rounded-lg text-xs font-mono uppercase tracking-wider transition-all"
                  >
                    Resolve Conflicts (Reconcile)
                  </button>
                </div>
              ) : (
                <form onSubmit={handleReconcileConflict} className="bg-slate-900/60 border border-slate-850 p-5 rounded-xl space-y-4">
                  <h4 className="text-xs font-mono font-bold text-slate-300 uppercase border-b border-slate-800 pb-2">
                    Final Discharge Prescription
                  </h4>
                  
                  <div className="space-y-3">
                    {resolvedMeds.map((med, index) => {
                      const matchingConflict = conflicts.find(c => 
                        c.field.toLowerCase().includes(med.name.toLowerCase())
                      );
                      const reasonForSelection = matchingConflict 
                        ? matchingConflict.recommended_action 
                        : "Standard discharge prescription.";

                      return (
                        <div key={index} className="grid grid-cols-1 md:grid-cols-5 gap-2.5 bg-slate-955 p-3 rounded-lg border border-slate-900">
                          <div>
                            <label className="block text-[9px] font-mono text-slate-500 uppercase mb-1">Medication</label>
                            <input
                              type="text"
                              value={med.name}
                              onChange={(e) => handleMedResolutionChange(index, "name", e.target.value)}
                              className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] font-mono text-slate-500 uppercase mb-1">Dosage</label>
                            <input
                              type="text"
                              value={med.dosage}
                              onChange={(e) => handleMedResolutionChange(index, "dosage", e.target.value)}
                              className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] font-mono text-slate-500 uppercase mb-1">Frequency</label>
                            <input
                              type="text"
                              value={med.frequency}
                              onChange={(e) => handleMedResolutionChange(index, "frequency", e.target.value)}
                              className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] font-mono text-slate-500 uppercase mb-1">Duration</label>
                            <input
                              type="text"
                              value={med.duration}
                              onChange={(e) => handleMedResolutionChange(index, "duration", e.target.value)}
                              className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[9px] font-mono text-slate-500 uppercase mb-1">Reason for selection</label>
                            <input
                              type="text"
                              readOnly
                              value={reasonForSelection}
                              className="w-full bg-slate-900/50 border border-slate-800/80 rounded p-1.5 text-xs text-slate-400 font-mono cursor-not-allowed"
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={() => setShowResolveEditor(false)}
                      className="bg-transparent border border-slate-700 hover:border-slate-500 text-slate-400 hover:text-slate-300 py-2 px-4 rounded text-xs font-mono uppercase transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={loading}
                      className="bg-emerald-500 hover:bg-emerald-400 text-slate-955 font-bold py-2 px-5 rounded text-xs font-mono uppercase transition-all flex items-center justify-center gap-2 min-w-[240px]"
                    >
                      {loading ? (
                        <>
                          <svg className="animate-spin h-3.5 w-3.5 text-slate-955" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span>Updating discharge summary...</span>
                        </>
                      ) : (
                        <span>✔ Apply & Regenerate Summary</span>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}

      </div>
    </section>
  );
};
