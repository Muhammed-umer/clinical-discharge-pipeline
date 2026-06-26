import React from 'react';
import { PendingDocument } from './presets';

// ==========================================
// DATABASE UNAVAILABLE CARD
// ==========================================
interface DatabaseUnavailableCardProps {
  onRetry: () => void;
  loading: boolean;
  notes?: PendingDocument[];
}

export const DatabaseUnavailableCard: React.FC<DatabaseUnavailableCardProps> = ({
  onRetry,
  loading,
  notes = []
}) => {
  const handleDownloadNotes = () => {
    if (notes.length === 0) {
      alert("No notes in queue to download.");
      return;
    }
    const textContent = notes
      .map(note => `==================================================\nCLINICIAN ROLE: ${note.authorRole}\n==================================================\n\n${note.content}\n\n`)
      .join("\n");

    const dataStr = "data:text/plain;charset=utf-8," + encodeURIComponent(textContent);
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "queued_clinical_notes.txt");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <section id="section-database-error" className="py-12 border-b border-slate-900 bg-slate-950/40">
      <div className="max-w-5xl mx-auto">
        <div className="bg-slate-900 border border-rose-900/50 rounded-xl p-6 sm:p-10 shadow-[0_0_30px_rgba(239,68,68,0.1)] space-y-6">
          
          <div className="flex items-start gap-4 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-rose-955/60 border border-rose-500/35 flex items-center justify-center text-xl text-rose-500 shrink-0 select-none">
              ⚠️
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase tracking-wider text-rose-500">
                Database Service Unavailable
              </h2>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                Clinical records cannot currently be accessed. The pipeline engine failed to query patient database records.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-955 p-5 rounded-lg border border-slate-800 text-xs font-mono">
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Happened</h4>
              <p className="text-slate-300 leading-relaxed">
                The application encountered a database connection failure, pool exhaustion, or database restart in the cloud registry.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Remains Safe</h4>
              <p className="text-slate-300 leading-relaxed">
                Any documents in your upload queue remain safe in browser cache memory. No patient note records have been lost.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What You Can Do Next</h4>
              <p className="text-slate-305 leading-relaxed">
                You can download your queued notes as a backup file, or trigger a retry connection request to reconnect to the database.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-800">
            <button
              onClick={handleDownloadNotes}
              disabled={notes.length === 0}
              className="bg-slate-805 hover:bg-slate-700 disabled:opacity-50 text-rose-400 border border-slate-700/60 font-mono text-[10px] uppercase font-bold px-4 py-2 rounded-lg transition-all"
            >
              📥 Download Queued Notes
            </button>

            <button
              onClick={onRetry}
              disabled={loading}
              className="bg-gradient-to-r from-rose-500 to-amber-500 hover:from-rose-400 hover:to-amber-400 disabled:from-slate-800 disabled:to-slate-800 text-slate-950 font-bold px-6 py-2.5 rounded-lg text-xs font-mono uppercase tracking-wider transition-all disabled:text-slate-500 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(239,68,68,0.2)]"
            >
              {loading ? "Connecting..." : "🔄 Retry Connection"}
            </button>
          </div>

        </div>
      </div>
    </section>
  );
};


// ==========================================
// UNSUPPORTED FILE CARD
// ==========================================
interface UnsupportedFileCardProps {
  onReturnToUpload: () => void;
  message?: string;
}

export const UnsupportedFileCard: React.FC<UnsupportedFileCardProps> = ({
  onReturnToUpload,
  message = "This demonstration currently supports UTF-8 encoded TXT clinical notes."
}) => {
  return (
    <section id="section-file-error" className="py-12 border-b border-slate-900 bg-slate-950/40">
      <div className="max-w-5xl mx-auto">
        <div className="bg-slate-900 border border-amber-950 rounded-xl p-6 sm:p-10 shadow-[0_0_30px_rgba(245,158,11,0.08)] space-y-6">
          
          <div className="flex items-start gap-4 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-amber-955/60 border border-amber-500/35 flex items-center justify-center text-xl text-amber-500 shrink-0 select-none">
              📄⚠️
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase tracking-wider text-amber-500">
                Unsupported File Format Rejected
              </h2>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                {message}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-955 p-5 rounded-lg border border-slate-800 text-xs font-mono">
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Happened</h4>
              <p className="text-slate-300 leading-relaxed">
                You selected a PDF, DOCX, image, or raw binary document that is unsupported by our current extraction parser.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Remains Safe</h4>
              <p className="text-slate-300 leading-relaxed">
                All valid notes already loaded in your files queue remain fully safe and untouched.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What You Can Do Next</h4>
              <p className="text-slate-305 leading-relaxed">
                Please convert the rejected notes to standard plain text (.txt) files encoded in UTF-8 format and re-upload.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 text-left">
            <button
              onClick={onReturnToUpload}
              className="bg-slate-805 hover:bg-slate-700 text-amber-500 border border-slate-700/60 font-mono text-[10px] uppercase font-bold px-5 py-2.5 rounded-lg transition-all"
            >
              ⬅ Return to Upload Screen
            </button>
          </div>

        </div>
      </div>
    </section>
  );
};


// ==========================================
// NO CLINICAL CONTENT CARD
// ==========================================
interface NoClinicalContentFoundCardProps {
  onReturnToUpload: () => void;
  message?: string;
}

export const NoClinicalContentFoundCard: React.FC<NoClinicalContentFoundCardProps> = ({
  onReturnToUpload,
  message = "No clinical content detected. Supported file type: UTF-8 TXT clinical notes."
}) => {
  return (
    <section id="section-content-error" className="py-12 border-b border-slate-900 bg-slate-950/40">
      <div className="max-w-5xl mx-auto">
        <div className="bg-slate-900 border border-amber-950 rounded-xl p-6 sm:p-10 shadow-[0_0_30px_rgba(245,158,11,0.08)] space-y-6">
          
          <div className="flex items-start gap-4 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-amber-955/60 border border-amber-500/35 flex items-center justify-center text-xl text-amber-550 shrink-0 select-none">
              🔍📄
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase tracking-wider text-amber-500">
                No Clinical Content Detected
              </h2>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                {message}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-955 p-5 rounded-lg border border-slate-800 text-xs font-mono">
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Happened</h4>
              <p className="text-slate-300 leading-relaxed">
                The uploaded text file was empty, contained only spaces/blank lines, or was a binary file disguised as text.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Remains Safe</h4>
              <p className="text-slate-300 leading-relaxed">
                No database records have been modified. No empty patient cases were registered.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What You Can Do Next</h4>
              <p className="text-slate-305 leading-relaxed">
                Check that the file contains actual note content, has not been corrupted, and is not a binary file renamed as txt.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 text-left">
            <button
              onClick={onReturnToUpload}
              className="bg-slate-805 hover:bg-slate-700 text-amber-550 border border-slate-700/60 font-mono text-[10px] uppercase font-bold px-5 py-2.5 rounded-lg transition-all"
            >
              ⬅ Return to Upload Screen
            </button>
          </div>

        </div>
      </div>
    </section>
  );
};


// ==========================================
// BACKEND STARTING CARD
// ==========================================
interface BackendStartingCardProps {
  onRetry: () => void;
  loading: boolean;
}

export const BackendStartingCard: React.FC<BackendStartingCardProps> = ({
  onRetry,
  loading
}) => {
  return (
    <section id="section-coldstart" className="py-12 border-b border-slate-900 bg-slate-950/40">
      <div className="max-w-5xl mx-auto">
        <div className="bg-slate-900 border border-teal-900/50 rounded-xl p-6 sm:p-10 shadow-[0_0_30px_rgba(20,184,166,0.1)] space-y-6">
          
          <div className="flex items-start gap-4 pb-4 border-b border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-teal-955/60 border border-teal-500/35 flex items-center justify-center text-xl text-teal-400 shrink-0 select-none animate-pulse">
              ⚡
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase tracking-wider text-teal-400">
                Clinical Engine Initializing
              </h2>
              <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                Backend is starting. This may take up to one minute on free hosting as the container wakes up.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-955 p-5 rounded-lg border border-slate-800 text-xs font-mono">
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Happened</h4>
              <p className="text-slate-300 leading-relaxed">
                The hosting container is starting up or provisioning memory resources for the pipeline engine.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What Remains Safe</h4>
              <p className="text-slate-300 leading-relaxed">
                All patient profiles and upload queues remain saved in your browser cache memory.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">What You Can Do Next</h4>
              <p className="text-slate-305 leading-relaxed">
                Please wait a few moments. The page will attempt to automatically connect to the engine, or you can retry manually.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 text-right">
            <button
              onClick={onRetry}
              disabled={loading}
              className="bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:from-slate-800 disabled:to-slate-800 text-slate-950 font-bold px-6 py-2.5 rounded-lg text-xs font-mono uppercase tracking-wider transition-all disabled:text-slate-500 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(20,184,166,0.2)]"
            >
              {loading ? "Connecting..." : "🔄 Reconnect to Engine"}
            </button>
          </div>

        </div>
      </div>
    </section>
  );
};
