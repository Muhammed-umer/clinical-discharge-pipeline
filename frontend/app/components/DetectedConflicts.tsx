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
  const conflicts = stayDetails?.final_summary?.validation?.conflicts;

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

        {/* Check for conflicts */}
        {!stayDetails || !conflicts || conflicts.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-900 border-dashed rounded-xl p-10 text-center text-slate-505 text-xs font-mono">
            No conflicts detected.
          </div>
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
                        "<MissingInfoIndicator value={val} />"
                      </p>
                    </div>
                  ))}
                </div>

                <div className="bg-slate-955 p-3 rounded-lg border border-slate-900 text-slate-300">
                  <span className="font-bold text-teal-400">Recommended Reconciliation:</span> <MissingInfoIndicator value={conf.recommended_action} />
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
                    Attending Physician Prescription Override
                  </h4>
                  
                  <div className="space-y-3">
                    {resolvedMeds.map((med, index) => (
                      <div key={index} className="grid grid-cols-1 md:grid-cols-4 gap-2.5 bg-slate-955 p-3 rounded-lg border border-slate-900">
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
                      </div>
                    ))}
                  </div>

                  <div className="flex justify-end gap-2.5">
                    <button
                      type="button"
                      onClick={() => setShowResolveEditor(false)}
                      className="bg-slate-800 hover:bg-slate-750 text-slate-350 py-2 px-4 rounded text-xs font-mono uppercase"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={loading}
                      className="bg-emerald-600 hover:bg-emerald-500 text-slate-955 font-bold py-2 px-5 rounded text-xs font-mono uppercase transition-all"
                    >
                      Apply Resolved Prescription
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
