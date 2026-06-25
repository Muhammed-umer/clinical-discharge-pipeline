import React from 'react';
import { SAMPLE_CASES, PendingDocument } from './presets';

interface UploadSectionProps {
  selectedCaseId: string;
  onSelectSampleCase: (idx: number) => void;
  patientName: string;
  setPatientName: (name: string) => void;
  dragOver: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  customFilename: string;
  setCustomFilename: (val: string) => void;
  customDocType: string;
  setCustomDocType: (val: string) => void;
  customAuthorRole: string;
  setCustomAuthorRole: (val: string) => void;
  customDocContent: string;
  setCustomDocContent: (val: string) => void;
  onAddCustomDoc: (e: React.FormEvent) => void;
  pendingDocuments: PendingDocument[];
  onRemovePendingDoc: (id: string) => void;
  onGenerateSummary: () => void;
  loading: boolean;
  hasSummary?: boolean;
}

export const UploadSection: React.FC<UploadSectionProps> = ({
  selectedCaseId,
  onSelectSampleCase,
  patientName,
  setPatientName,
  dragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileSelect,
  customFilename,
  setCustomFilename,
  customDocType,
  setCustomDocType,
  customAuthorRole,
  setCustomAuthorRole,
  customDocContent,
  setCustomDocContent,
  onAddCustomDoc,
  pendingDocuments,
  onRemovePendingDoc,
  onGenerateSummary,
  loading,
  hasSummary = false
}) => {
  return (
    <section id="section-2" className="py-16 border-b border-slate-900">
      <div className="max-w-5xl mx-auto">
        
        <div className="text-center md:text-left mb-6">
          <h2 className="text-lg font-black font-mono uppercase tracking-widest text-teal-400">
            Upload Clinical Documents
          </h2>
          <p className="text-slate-405 text-xs mt-1">
            Select a sample case or drag and drop clinical documents.
          </p>
        </div>

        {/* Quick Case Presets */}
        <div className="bg-slate-900/40 border border-slate-900 rounded-xl p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {SAMPLE_CASES.map((sc, scIdx) => (
              <button
                key={scIdx}
                onClick={() => onSelectSampleCase(scIdx)}
                className={`bg-slate-955 border text-left p-3.5 rounded-lg transition-all hover:border-slate-700 ${
                  selectedCaseId === sc.id
                    ? 'border-teal-500 bg-teal-955/10'
                    : 'border-slate-805'
                }`}
              >
                <div className="font-mono font-bold text-[11px] text-teal-400 mb-1">
                  {sc.title}
                </div>
                <p className="text-[10px] text-slate-400 line-clamp-2 leading-relaxed">
                  {sc.desc}
                </p>
                <span className="inline-block text-[9px] bg-slate-900 text-slate-505 border border-slate-805 px-1.5 py-0.5 rounded font-mono mt-2">
                  {sc.notes.length} Notes Ingested
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Form Inputs & DragDrop */}
          <div className="lg:col-span-2 space-y-4">
            
            <div>
              <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">Patient Full Name</label>
              <input
                type="text"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                className="w-full bg-slate-955 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-205 focus:border-teal-500 outline-none"
                placeholder="Patient Name"
              />
            </div>

            {/* Dropzone area */}
            <div
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                dragOver
                  ? 'border-teal-500 bg-teal-955/15'
                  : 'border-slate-805 bg-slate-900/20 hover:border-slate-800'
              }`}
            >
              <input
                type="file"
                id="clinical-file-input"
                multiple
                onChange={onFileSelect}
                className="hidden"
              />
              
              <svg className="w-8 h-8 text-slate-505 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>

              <div className="text-xs text-slate-350 font-medium">
                Drag and drop files here or{' '}
                <label htmlFor="clinical-file-input" className="text-teal-400 font-bold hover:underline cursor-pointer">
                  Browse local files
                </label>
              </div>
              
              <p className="text-[10px] text-slate-500 font-mono mt-2 leading-relaxed">
                Doctor Note &bull; Consultant Note &bull; Resident Note &bull; Nurse Note &bull; Ward Progress Note &bull; Lab Report &bull; Radiology Report &bull; Prescription &bull; Discharge Draft
              </p>
            </div>

            {/* Custom note form */}
            <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-4">
              <h4 className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2">
                ➕ Paste Custom Note Text
              </h4>
              <form onSubmit={onAddCustomDoc} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                  <div>
                    <input
                      type="text"
                      value={customFilename}
                      onChange={(e) => setCustomFilename(e.target.value)}
                      className="w-full bg-slate-955 border border-slate-800 rounded p-1.5 text-xs text-slate-300 font-mono"
                      placeholder="filename.txt"
                      required
                    />
                  </div>
                  <div>
                    <select
                      value={customDocType}
                      onChange={(e) => setCustomDocType(e.target.value)}
                      className="w-full bg-slate-955 border border-slate-800 rounded p-1.5 text-xs text-slate-300 font-mono"
                    >
                      <option value="Doctor Note">Doctor Note</option>
                      <option value="Consultant Note">Consultant Note</option>
                      <option value="Resident Note">Resident Note</option>
                      <option value="Nurse Note">Nurse Note</option>
                      <option value="Ward Progress Note">Ward Progress Note</option>
                      <option value="Lab Report">Lab Report</option>
                      <option value="Radiology Report">Radiology Report</option>
                      <option value="Prescription">Prescription</option>
                      <option value="Discharge Draft">Discharge Draft</option>
                    </select>
                  </div>
                  <div>
                    <select
                      value={customAuthorRole}
                      onChange={(e) => setCustomAuthorRole(e.target.value)}
                      className="w-full bg-slate-955 border border-slate-800 rounded p-1.5 text-xs text-slate-300 font-mono"
                    >
                      <option value="RESIDENT">Resident Medical Officer</option>
                      <option value="CONSULTANT">Consultant Specialist</option>
                      <option value="ATTENDING">Attending Physician</option>
                      <option value="WARD_NURSE">Ward Nurse</option>
                    </select>
                  </div>
                </div>
                
                <textarea
                  rows={2}
                  value={customDocContent}
                  onChange={(e) => setCustomDocContent(e.target.value)}
                  placeholder="Type or paste note details..."
                  className="w-full bg-slate-955 border border-slate-800 rounded p-2 text-xs text-slate-300 font-mono focus:border-teal-500 outline-none resize-none"
                />

                <button
                  type="submit"
                  className="px-4 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-750 font-mono text-[10px] uppercase rounded font-bold"
                >
                  Add Document Note
                </button>
              </form>
            </div>

          </div>

          {/* Document Queue Sidebar */}
          <div className="bg-slate-900/60 border border-slate-850 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <h3 className="text-xs font-mono font-bold text-slate-300 uppercase border-b border-slate-855 pb-2 mb-3 flex justify-between items-center">
                <span>📂 Uploaded Files</span>
                <span className="text-[10px] text-teal-400 bg-slate-955 px-2 py-0.5 border border-slate-900 rounded font-normal">
                  {pendingDocuments.length} files
                </span>
              </h3>

              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {pendingDocuments.length === 0 ? (
                  <div className="py-12 text-center text-[10px] text-slate-500 font-mono italic">
                    No clinical notes ingested yet. Click a case preset above or drop text documents.
                  </div>
                ) : (
                  pendingDocuments.map((doc) => (
                    <div key={doc.id} className="bg-slate-955 border border-slate-855 rounded-lg p-2.5 text-xs relative">
                      <button
                        type="button"
                        onClick={() => onRemovePendingDoc(doc.id)}
                        className="absolute top-2 right-2 text-slate-505 hover:text-rose-455"
                        title="Remove file"
                      >
                        ✕
                      </button>
                      
                      <div className="font-mono text-[10px] text-slate-200 font-bold truncate pr-4">
                        {doc.filename}
                      </div>
                      
                      <div className="grid grid-cols-2 gap-2 mt-1 text-[9px] text-slate-405 font-mono">
                        <div>Type: <span className="text-slate-305 font-bold">{doc.docType}</span></div>
                        <div>Role: <span className="text-slate-305 font-bold">{doc.authorRole}</span></div>
                      </div>

                      <div className="mt-2 flex justify-between items-center text-[9px] font-mono">
                        <span className="text-slate-505 font-medium" suppressHydrationWarning={true}>
                          {new Date(doc.recorded_at).toLocaleTimeString()}
                        </span>
                        
                        <span className={`px-1.5 py-0.2 rounded border ${
                          doc.status === 'success'
                            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/30'
                            : doc.status === 'uploading'
                            ? 'bg-blue-955 text-blue-400 border-blue-900/30 animate-pulse'
                            : doc.status === 'failed'
                            ? 'bg-rose-955/20 text-rose-455 border-rose-900/30'
                            : 'bg-slate-900 text-slate-400 border-slate-850'
                        }`}>
                          {doc.status === 'success' && '✓ Ingested'}
                          {doc.status === 'uploading' && '⚡ Ingesting'}
                          {doc.status === 'failed' && '❌ Failed'}
                          {doc.status === 'pending' && '⏳ In Queue'}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {pendingDocuments.length > 0 && (
              <div className="mt-4 border-t border-slate-850 pt-3">
                <button
                  type="button"
                  onClick={onGenerateSummary}
                  disabled={loading || (hasSummary && !loading)}
                  className={`w-full bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-black py-3.5 px-6 border border-teal-400 rounded-xl text-xs font-mono uppercase tracking-wider transition-all shadow-[0_0_15px_rgba(20,184,166,0.3)] hover:shadow-[0_0_20px_rgba(20,184,166,0.5)] flex items-center justify-center gap-2 disabled:bg-none disabled:bg-slate-800 disabled:border-slate-700 disabled:text-slate-500 disabled:shadow-none disabled:cursor-not-allowed`}
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin h-4 w-4 text-slate-955" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Generating Clinical Summary...</span>
                    </>
                  ) : hasSummary ? (
                    <>
                      <span>✓ Summary Generated</span>
                    </>
                  ) : (
                    <>
                      <span>🧠 GENERATE SAFE DISCHARGE SUMMARY</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>

      </div>
    </section>
  );
};
