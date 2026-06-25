import React from 'react';
import { StayDetails } from './presets';

interface AdvancedTechnicalDetailsProps {
  stayDetails: StayDetails | null;
  isAdvancedOpen: boolean;
  setIsAdvancedOpen: (val: boolean) => void;
  handleExportJSON: () => void;
  handlePrintPDF: () => void;
  pipelineSimulationLogs: string[];
}

export const AdvancedTechnicalDetails: React.FC<AdvancedTechnicalDetailsProps> = ({
  stayDetails,
  isAdvancedOpen,
  setIsAdvancedOpen,
  handleExportJSON,
  handlePrintPDF,
  pipelineSimulationLogs
}) => {
  if (!stayDetails) return null;

  const final_summary = stayDetails.final_summary;
  if (!final_summary) return null;

  const groundingScore = final_summary.validation?.grounding_metrics?.grounding_score || 0;
  const verifiedCount = stayDetails.claims.filter(c => c.status === 'SUPPORTED').length;

  return (
    <>
      {/* ========================================================
          SECTION 8: DOWNLOAD PDF BANNER
          ======================================================== */}
      <section id="section-8" className="py-12 border-b border-slate-900">
        <div className="max-w-5xl mx-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-2xl">
            
            <div className="space-y-1 text-center md:text-left">
              <h3 className="text-sm font-bold text-slate-205 font-mono">
                Sealed Clinical Document
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                Grounding score: {Math.round(groundingScore * 100)}% &bull; Facts Verified: {verifiedCount}
              </p>
            </div>

            <button
              onClick={handlePrintPDF}
              className="w-full md:w-auto bg-teal-650 hover:bg-teal-500 text-slate-955 font-bold py-3.5 px-8 rounded-lg text-xs font-mono uppercase tracking-wider transition-all hover:scale-102"
            >
              Download PDF
            </button>

          </div>
        </div>
      </section>

      {/* ========================================================
          SECTION 9: ADVANCED TECHNICAL DETAILS
          ======================================================== */}
      <section id="advanced-section" className="py-12">
        <div className="max-w-5xl mx-auto border border-slate-900 rounded-xl bg-slate-900/20 overflow-hidden">
          
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="w-full p-4 flex justify-between items-center bg-slate-955 hover:bg-slate-900/60 font-mono font-bold text-slate-400 text-xs border-b border-slate-900"
          >
            <span>⚙ Advanced Technical Details</span>
            <span>{isAdvancedOpen ? "▲ Collapse" : "▼ Expand"}</span>
          </button>
          
          {isAdvancedOpen && (
            <div className="p-6 space-y-6 text-xs font-mono text-slate-400">
              
              {/* Metrics detail table */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-bold text-slate-300 uppercase mb-3">System Diagnostics</h4>
                  <div className="bg-slate-955 p-4 rounded-lg border border-slate-900 space-y-2">
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Internal Case DB ID:</span>
                      <span className="text-slate-205">{stayDetails.stay_id}</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Pipeline Version:</span>
                      <span className="text-slate-205">v1.2.0</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Grounding Judge Model:</span>
                      <span className="text-slate-205">gemini-2.5-pro</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Embedding Dimension:</span>
                      <span className="text-slate-205">768 (text-embedding-004)</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Average Confidence:</span>
                      <span className="text-teal-400">{Math.round((final_summary.validation?.confidence || 0) * 100)}%</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-bold text-slate-300 uppercase mb-3 font-mono">Factual Grounding Indexes</h4>
                  <div className="bg-slate-955 p-4 rounded-lg border border-slate-900 space-y-2">
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Evidence Coverage:</span>
                      <span className="text-teal-400">{Math.round((final_summary.validation?.grounding_metrics?.evidence_coverage || 0) * 100)}%</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span>Citation Completeness:</span>
                      <span className="text-teal-400">{Math.round((final_summary.validation?.grounding_metrics?.citation_completeness || 0) * 100)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Action:</span>
                      <button
                        onClick={handleExportJSON}
                        className="text-teal-400 font-bold hover:underline font-mono"
                      >
                        Export structured JSON summary
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Technical Stepper Logs */}
              <div>
                <h4 className="font-bold text-slate-300 uppercase mb-3">Technical Execution Logs</h4>
                <div className="bg-slate-955 p-4 rounded-lg border border-slate-900 max-h-56 overflow-y-auto text-[10px]">
                  {final_summary.validation?.notes.map((logMsg, logIdx) => (
                    <div key={logIdx} className="border-b border-slate-900 pb-1.5 last:border-0 last:pb-0 text-slate-400 flex justify-between gap-4">
                      <span>{logMsg}</span>
                      <span className="text-slate-650 shrink-0">Timestamp Audited</span>
                    </div>
                  ))}
                  {pipelineSimulationLogs.map((logMsg, logIdx) => (
                    <div key={`sim-${logIdx}`} className="border-b border-slate-900 pb-1.5 last:border-0 last:pb-0 text-blue-400/80 flex justify-between gap-4">
                      <span>{logMsg}</span>
                      <span>Simulation Trace</span>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}
          
        </div>
      </section>
    </>
  );
};
