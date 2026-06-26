import React from 'react';
import { StayDetails } from './presets';

interface AdvancedTechnicalDetailsProps {
  stayDetails: StayDetails | null;
  isAdvancedOpen: boolean;
  setIsAdvancedOpen: (val: boolean) => void;
  handleExportJSON: () => void;
  handlePrintPDF: () => void;
  pipelineSimulationLogs: string[];
  pdfStatus: 'idle' | 'generating' | 'success' | 'error';
}

export const AdvancedTechnicalDetails: React.FC<AdvancedTechnicalDetailsProps> = ({
  stayDetails,
  isAdvancedOpen,
  setIsAdvancedOpen,
  handleExportJSON,
  handlePrintPDF,
  pipelineSimulationLogs,
  pdfStatus
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
              disabled={pdfStatus !== 'idle'}
              className={`w-full md:w-auto font-bold py-3.5 px-8 rounded-lg text-xs font-mono uppercase tracking-wider transition-all min-w-[240px] flex items-center justify-center gap-2 ${
                pdfStatus === 'generating'
                  ? 'bg-slate-800 border border-slate-700 text-slate-400 cursor-not-allowed'
                  : pdfStatus === 'success'
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-slate-955'
                  : pdfStatus === 'error'
                  ? 'bg-rose-700 hover:bg-rose-650 text-slate-100'
                  : 'bg-teal-650 hover:bg-teal-500 text-slate-955 hover:scale-102'
              }`}
            >
              {pdfStatus === 'generating' && (
                <svg className="animate-spin h-3.5 w-3.5 text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
              <span>
                {pdfStatus === 'generating'
                  ? 'Generating PDF...'
                  : pdfStatus === 'success'
                  ? 'PDF downloaded successfully.'
                  : pdfStatus === 'error'
                  ? 'Unable to generate PDF.'
                  : 'Download PDF'}
              </span>
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
