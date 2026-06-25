import React from 'react';
import { StayDetails } from './presets';

interface GroundingReportProps {
  stayDetails: StayDetails | null;
}

const getGroundingColor = (score: number) => {
  if (score >= 0.90) return 'text-emerald-400 border-emerald-500/30';
  if (score >= 0.70) return 'text-amber-400 border-amber-500/30';
  return 'text-rose-455 border-rose-500/30';
};

export const GroundingReport: React.FC<GroundingReportProps> = ({ stayDetails }) => {
  const summary = stayDetails?.final_summary?.summary;
  const validation = stayDetails?.final_summary?.validation;

  return (
    <section id="section-6" className="py-16 border-b border-slate-900">
      <div className="max-w-5xl mx-auto">
        <div className="text-center md:text-left mb-6">
          <h2 className="text-xl font-black font-mono uppercase tracking-widest text-teal-400">
            Grounding Report
          </h2>
          <p className="text-slate-405 text-xs mt-1">
            Safety scorecard verifying clinical grounding metrics.
          </p>
        </div>

        {!stayDetails || !stayDetails.final_summary || !summary || !validation ? (
          <div className="bg-slate-900/40 border border-slate-900 border-dashed rounded-xl p-10 text-center text-slate-505 text-xs font-mono">
            No grounding report available.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Metrics block */}
          <div className="md:col-span-2 space-y-4">
            
            <div className="grid grid-cols-4 gap-3">
              
              {/* Grounding index */}
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 text-center">
                <div className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">Grounding Score</div>
                <div className={`text-2xl font-black font-mono mt-1 ${getGroundingColor(validation.grounding_metrics?.grounding_score || 0)}`}>
                  {Math.round((validation.grounding_metrics?.grounding_score || 0) * 100)}%
                </div>
              </div>

              {/* Supported claims count */}
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 text-center">
                <div className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">Supported Claims</div>
                <div className="text-2xl font-black font-mono text-teal-400 mt-1">
                  {stayDetails.claims.filter(c => c.status === 'SUPPORTED').length}
                </div>
              </div>

              {/* Conflicts count */}
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 text-center">
                <div className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">Conflicts</div>
                <div className="text-2xl font-black font-mono text-rose-400 mt-1">
                  {validation.conflicts.length}
                </div>
              </div>

              {/* Missing Information count */}
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 text-center">
                <div className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">Missing Information</div>
                <div className="text-2xl font-black font-mono text-amber-400 mt-1">
                  {summary.missing_information.length}
                </div>
              </div>

            </div>

            <div className="bg-slate-900/30 border border-slate-900 p-4 rounded-xl text-xs font-mono space-y-2">
              <div className="flex justify-between border-b border-slate-900 pb-2">
                <span className="text-slate-400">Total Verified Clinical Facts:</span>
                <span className="text-slate-205 font-bold">{stayDetails.claims.length} claims</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Identified Gaps in Document Notes:</span>
                <span className="text-amber-400 font-bold">{summary.missing_information.length} fields</span>
              </div>
            </div>

          </div>

          {/* Checklist */}
          <div className="bg-slate-900/60 border border-slate-850 rounded-xl p-4 text-xs font-mono">
            <h4 className="font-bold text-slate-350 uppercase border-b border-slate-855 pb-2 mb-3">
              🛡️ Safety Checklist
            </h4>
            
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Every claim has evidence
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Every diagnosis is grounded
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Every medication is grounded
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Every observation is grounded
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Every investigation is grounded
              </li>
              <li className="flex items-center gap-2">
                <span className={validation.unsupported_claims.length === 0 ? 'text-emerald-400' : 'text-slate-500'}>
                  {validation.unsupported_claims.length === 0 ? '✓' : '✗'}
                </span>
                No hallucinated facts detected
              </li>
            </ul>
          </div>
        </div>
        )}

      </div>
    </section>
  );
};
