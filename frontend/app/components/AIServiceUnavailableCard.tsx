import React, { useState } from 'react';
import { StayDetails } from './presets';

interface AIServiceUnavailableCardProps {
  stayDetails: StayDetails | null;
  onRetry: () => void;
  loading: boolean;
}

export const AIServiceUnavailableCard: React.FC<AIServiceUnavailableCardProps> = ({
  stayDetails,
  onRetry,
  loading
}) => {
  const [isViewNotesOpen, setIsViewNotesOpen] = useState(false);

  if (!stayDetails) return null;

  const failureDetails = stayDetails.final_summary as any;
  const reason = failureDetails?.reason || "Gemini API quota exceeded.";

  const handleDownloadNotes = () => {
    if (!stayDetails.notes || stayDetails.notes.length === 0) {
      alert("No clinical notes available to download.");
      return;
    }

    const textContent = stayDetails.notes
      .map(note => `==================================================\nCLINICIAN ROLE: ${note.author_role}\nRECORDED AT: ${note.recorded_at}\n==================================================\n\n${note.content}\n\n`)
      .join("\n");

    const dataStr = "data:text/plain;charset=utf-8," + encodeURIComponent(textContent);
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `clinical_notes_stay_${stayDetails.stay_id}.txt`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleDownloadTimeline = () => {
    if (!stayDetails.notes || stayDetails.notes.length === 0) {
      alert("No timeline data available to download.");
      return;
    }

    // Sort notes chronologically
    const sortedNotes = [...stayDetails.notes].sort(
      (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );

    const textContent = sortedNotes
      .map((note, idx) => `${idx + 1}. [${new Date(note.recorded_at).toLocaleString()}] ${note.author_role}\n--------------------------------------------------\n${note.content}\n\n`)
      .join("\n");

    const dataStr = "data:text/plain;charset=utf-8," + encodeURIComponent(textContent);
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `chronological_clinical_timeline_${stayDetails.stay_id}.txt`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <section id="section-status-card" className="py-12 border-b border-slate-900 bg-slate-950/40">
      <div className="max-w-5xl mx-auto">
        <div className="bg-slate-900 border border-blue-900/50 rounded-xl p-6 sm:p-10 shadow-[0_0_30px_rgba(59,130,246,0.1)] space-y-6">
          
          {/* Header */}
          <div className="flex items-start gap-4 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-blue-955/60 border border-blue-500/35 flex items-center justify-center text-xl text-blue-400 shrink-0 select-none animate-pulse">
              ⚠
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase tracking-wider text-blue-400">
                AI Extraction Service Temporarily Unavailable
              </h2>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                The uploaded clinical notes were successfully received and stored in our secure database. <br/>
                However, the AI extraction service is currently unavailable, so a discharge summary could not be safely generated.
              </p>
            </div>
          </div>

          {/* Safety checklist grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-955 p-5 rounded-lg border border-slate-800">
            <div>
              <h3 className="text-xs font-mono font-bold text-slate-305 uppercase tracking-wider mb-3">
                🛡️ Clinical Safety Audits
              </h3>
              <ul className="space-y-2 text-xs font-mono">
                <li className="flex items-center gap-2 text-blue-450">
                  <span className="font-bold text-emerald-400">✔</span> Uploaded documents preserved
                </li>
                <li className="flex items-center gap-2 text-blue-450">
                  <span className="font-bold text-emerald-400">✔</span> No hallucinated medical information
                </li>
                <li className="flex items-center gap-2 text-blue-450">
                  <span className="font-bold text-emerald-400">✔</span> No partial discharge summary generated
                </li>
                <li className="flex items-center gap-2 text-amber-500 font-bold">
                  <span className="font-bold text-amber-500">✔</span> Manual physician review recommended
                </li>
              </ul>
            </div>

            <div className="flex flex-col justify-between">
              <div>
                <h3 className="text-xs font-mono font-bold text-slate-305 uppercase tracking-wider mb-2">
                  ℹ️ Extraction Blocker Details
                </h3>
                <div className="text-xs bg-slate-900 border border-slate-800 rounded p-3 font-mono text-slate-300">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Service Reason:</div>
                  <div className="mt-1 font-bold text-amber-400">{reason}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Controls bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-800">
            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleDownloadNotes}
                className="bg-slate-805 hover:bg-slate-700 text-blue-400 border border-slate-700/60 font-mono text-[10px] uppercase font-bold px-4 py-2 rounded-lg transition-all"
              >
                📥 Download Uploaded Notes
              </button>
              <button
                onClick={handleDownloadTimeline}
                className="bg-slate-805 hover:bg-slate-700 text-blue-400 border border-slate-700/60 font-mono text-[10px] uppercase font-bold px-4 py-2 rounded-lg transition-all"
              >
                ⏳ Download Raw Timeline
              </button>
              <button
                onClick={() => setIsViewNotesOpen(!isViewNotesOpen)}
                className="bg-slate-805 hover:bg-slate-700 text-slate-300 border border-slate-700 font-mono text-[10px] uppercase font-bold px-4 py-2 rounded-lg transition-all"
              >
                {isViewNotesOpen ? "✕ Close Notes Viewer" : "👁 View Uploaded Documents"}
              </button>
            </div>

            <button
              onClick={onRetry}
              disabled={loading}
              className="bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:from-slate-800 disabled:to-slate-800 text-slate-950 font-bold px-6 py-2.5 rounded-lg text-xs font-mono uppercase tracking-wider transition-all disabled:text-slate-500 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(20,184,166,0.2)] animate-pulse"
            >
              {loading ? "Re-processing..." : "🔄 Retry Processing"}
            </button>
          </div>

          {/* Notes viewer panel */}
          {isViewNotesOpen && (
            <div className="pt-4 border-t border-slate-850 space-y-4">
              <h3 className="text-xs font-mono font-bold text-slate-305 uppercase">
                Clinical Documents List ({stayDetails.notes.length})
              </h3>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {stayDetails.notes.map((note) => (
                  <div key={note.id} className="bg-slate-955 border border-slate-800/80 rounded-lg p-4 space-y-2">
                    <div className="flex justify-between items-center text-[10px] font-mono text-slate-400 border-b border-slate-900 pb-1.5">
                      <span className="font-bold text-teal-400">{note.author_role}</span>
                      <span>{new Date(note.recorded_at).toLocaleString()}</span>
                    </div>
                    <pre className="text-xs font-mono text-slate-305 whitespace-pre-wrap leading-relaxed">
                      {note.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </section>
  );
};
