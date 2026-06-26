import React from 'react';
import { StayDetails } from './presets';

interface PipelineOverviewProps {
  loading: boolean;
  pipelineStateStep: number;
  pipelineSimulationLogs: string[];
  stayDetails: StayDetails | null;
}

const PIPELINE_STAGES = [
  { id: 'docs', name: 'Reading Notes', desc: 'Ingests clinical document note logs and specialist consultations.' },
  { id: 'extract', name: 'Extracting Facts', desc: 'Identifies structured medical statements and clinical values.' },
  { id: 'claims', name: 'Generating Claims', desc: 'Decomposes unstructured segments into individual fact assertions.' },
  { id: 'conflict', name: 'Conflict Detection', desc: 'Scans timelines for prescribing variations or treatment conflicts.' },
  { id: 'grounding', name: 'Grounding', desc: 'Evaluates claim consistency against supporting note context.' },
  { id: 'summary', name: 'Summary Generated', desc: 'Synthesizes verified structured findings into final discharge format.' },
  { id: 'approve', name: 'Physician Approved', desc: 'Attending physician signs and seals the clinical discharge record.' }
];

const SAFE_FAILURE_STAGES = [
  { id: 'start', name: 'Extraction Started', desc: 'Process initiated and notes fetched from timeline.' },
  { id: 'gemini', name: 'Gemini API Connection', desc: 'Attempting connection and structured document parsing.' },
  { id: 'retries', name: 'Retries Completed', desc: 'Exhausted maximum retry attempts under backoff protocol.' },
  { id: 'safestop', name: 'Safe Pipeline Stop', desc: 'Execution stopped cleanly to prevent clinical fabrication.' },
  { id: 'preserved', name: 'Documents Preserved', desc: 'All uploaded raw document notes safely stored in clinical DB.' },
  { id: 'manual', name: 'Manual Review Required', desc: 'Discharge summary generation delegated to human physician.' }
];

export const PipelineOverview: React.FC<PipelineOverviewProps> = ({
  loading,
  pipelineStateStep,
  pipelineSimulationLogs,
  stayDetails
}) => {
  const isSafeFailure = pipelineStateStep === -3 || stayDetails?.status === 'AI_SERVICE_UNAVAILABLE';
  const stages = isSafeFailure ? SAFE_FAILURE_STAGES : PIPELINE_STAGES;

  return (
    <section id="section-3" className="py-16 border-b border-slate-900 bg-slate-900/20">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-lg font-black font-mono uppercase tracking-widest text-teal-400">
            AI Pipeline
          </h2>
          <p className="text-slate-400 text-xs mt-1">
            Visual tracking of the clinical extraction and verification steps.
          </p>
        </div>

        <div className="max-w-xl mx-auto space-y-6">
          
          {/* The Vertical Stepper */}
          <div className="space-y-2 relative">
            <div className="absolute left-[27px] top-[24px] bottom-[24px] w-0.5 bg-slate-800 z-0"></div>

            {stages.map((stage, idx) => {
              let statusText = 'Pending';
              let cardClass = 'border-slate-855 bg-slate-955/40 text-slate-505 opacity-60';
              let iconClass = 'bg-slate-900 border-slate-800 text-slate-505';

              if (isSafeFailure) {
                if (idx < 5) {
                  statusText = (idx === 0) ? 'Success' : (idx === 1) ? 'Service Error' : (idx === 2) ? 'Retries Done' : (idx === 3) ? 'Safe Stop' : 'Preserved';
                  cardClass = 'border-blue-900/30 bg-blue-950/10 text-blue-300';
                  iconClass = 'bg-blue-950/40 border-blue-900 text-blue-400';
                } else {
                  statusText = 'Review Required';
                  cardClass = 'border-amber-900/60 bg-amber-950/10 text-amber-400 ring-1 ring-amber-500/25 animate-pulse';
                  iconClass = 'bg-amber-950 border-amber-800 text-amber-550 animate-pulse';
                }
              } else {
                if (pipelineStateStep === -2) {
                  statusText = 'Failed';
                  cardClass = 'border-rose-955/40 bg-rose-955/5 text-rose-350';
                  iconClass = 'bg-rose-955/20 border-rose-900 text-rose-455';
                } else if (pipelineStateStep === -1) {
                  if (stayDetails?.final_summary) {
                    if (idx === 6) {
                      // Physician Approved step
                      if (stayDetails.is_reconciled || stayDetails.status === 'COMPLETED') {
                        statusText = 'Completed';
                        cardClass = 'border-emerald-955 bg-emerald-955/5 text-emerald-400';
                        iconClass = 'bg-emerald-950/40 border-emerald-900 text-emerald-400';
                      } else if (stayDetails.status === 'READY_FOR_REVIEW') {
                        statusText = 'Review Required';
                        cardClass = 'border-amber-900/60 bg-amber-950/10 text-amber-400 ring-1 ring-amber-500/25 animate-pulse';
                        iconClass = 'bg-amber-950 border-amber-800 text-amber-550 animate-pulse';
                      } else {
                        statusText = 'Pending';
                        cardClass = 'border-slate-855 bg-slate-955/40 text-slate-505 opacity-60';
                        iconClass = 'bg-slate-900 border-slate-800 text-slate-505';
                      }
                    } else if (idx === 3 && (stayDetails.status === 'READY_FOR_REVIEW' || stayDetails.status === 'COMPLETED')) {
                      statusText = 'Conflict Resolved';
                      cardClass = 'border-emerald-955 bg-emerald-955/5 text-emerald-400';
                      iconClass = 'bg-emerald-950/40 border-emerald-900 text-emerald-400';
                    } else {
                      statusText = 'Completed';
                      cardClass = 'border-emerald-950 bg-emerald-955/5 text-slate-300';
                      iconClass = 'bg-emerald-950/40 border-emerald-900 text-emerald-400';
                    }
                  }
                } else {
                  if (idx < pipelineStateStep) {
                    statusText = 'Completed';
                    cardClass = 'border-emerald-955/60 bg-emerald-955/5 text-slate-355';
                    iconClass = 'bg-emerald-950/40 border-emerald-900 text-emerald-400';
                  } else if (idx === pipelineStateStep) {
                    statusText = 'Running';
                    cardClass = 'border-blue-500/50 bg-blue-955/10 text-slate-200 ring-1 ring-blue-500/20 scale-[1.01]';
                    iconClass = 'bg-blue-950 border-blue-500 text-blue-400 animate-pulse';
                  }
                }

                const isConflictDiscrepancyStep = idx === 3 && stayDetails?.status === 'NEEDS_RECONCILIATION' && pipelineStateStep === -1;
                if (isConflictDiscrepancyStep) {
                  statusText = 'Conflict Detected';
                  cardClass = 'border-rose-900/60 bg-rose-955/20 text-rose-300 animate-pulse';
                  iconClass = 'bg-rose-955/20 border-rose-900 text-rose-455';
                }
              }

              return (
                <div
                  key={stage.id}
                  className={`flex items-start gap-4 p-2.5 rounded-xl border transition-all duration-300 relative z-10 ${cardClass}`}
                >
                  <div className={`w-8 h-8 rounded-full border flex items-center justify-center font-mono text-xs font-bold shrink-0 ${iconClass}`}>
                    {statusText === 'Completed' || statusText === 'Success' || statusText === 'Preserved' || statusText === 'Safe Stop' || statusText === 'Retries Done'
                      ? '✓' 
                      : statusText === 'Running' 
                      ? '⚡' 
                      : statusText.includes('Conflict') || statusText === 'Review Required' 
                      ? '⚠️' 
                      : statusText === 'Service Error' 
                      ? '✕' 
                      : idx + 1}
                  </div>

                  <div className="space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-205">{stage.name}</span>
                      <span className={`px-2 py-0.2 rounded text-[8px] font-mono border uppercase tracking-wider ${
                        statusText === 'Completed'
                          ? 'bg-emerald-955/80 text-emerald-400 border-emerald-900/30'
                          : statusText === 'Running'
                          ? 'bg-blue-955/80 text-blue-400 border-blue-500/30 animate-pulse'
                          : statusText.includes('Conflict')
                          ? 'bg-rose-955/80 text-rose-400 border-rose-800/30'
                          : statusText === 'Service Error' || statusText === 'Retries Done' || statusText === 'Safe Stop' || statusText === 'Preserved' || statusText === 'Success'
                          ? 'bg-blue-955/80 text-blue-400 border-blue-500/30'
                          : statusText === 'Review Required'
                          ? 'bg-amber-955/80 text-amber-400 border-amber-800/30 animate-pulse'
                          : 'bg-slate-900 text-slate-505 border-slate-850'
                      }`}>
                        {statusText}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-sans leading-normal">{stage.desc}</p>
                  </div>
                </div>
              );
            })}

          </div>

          {/* Status Header flags */}
          <div className="flex flex-wrap gap-2.5 items-center justify-center pt-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-850 rounded-lg text-xs font-mono text-slate-400">
              <span className="text-emerald-500 font-bold">✓</span> Evidence Grounded
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-850 rounded-lg text-xs font-mono text-slate-400">
              <span className="text-emerald-500 font-bold">✓</span> Conflict Detection Enabled
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-850 rounded-lg text-xs font-mono text-slate-400">
              <span className="text-emerald-500 font-bold">✓</span> Physician Review Ready
            </span>
          </div>

          {/* Collapsible execution logs */}
          {(loading || pipelineSimulationLogs.length > 0) && (
            <details className="mt-4 bg-slate-900/60 border border-slate-850 rounded-xl overflow-hidden text-left" open={loading}>
              <summary className="p-3.5 font-mono text-xs font-bold text-slate-455 cursor-pointer hover:bg-slate-900/80 select-none flex justify-between items-center">
                <span>▼ View Technical Execution Log</span>
                <span className="text-[10px] text-slate-500 font-normal font-mono">{pipelineSimulationLogs.length} entries</span>
              </summary>
              <div className="p-4 bg-slate-955 max-h-40 overflow-y-auto text-[10px] font-mono text-blue-400/80 space-y-1.5 border-t border-slate-900">
                {pipelineSimulationLogs.map((logMsg, logIdx) => (
                  <div key={logIdx} className="truncate">
                    {logMsg}
                  </div>
                ))}
              </div>
            </details>
          )}

        </div>

      </div>
    </section>
  );
};
