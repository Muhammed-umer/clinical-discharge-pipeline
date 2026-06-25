import React from 'react';
import { StayDetails } from './presets';
import { MissingInfoIndicator } from './MissingInfoIndicator';

interface ExtractedClaimsProps {
  stayDetails: StayDetails | null;
  expandedClaimId: string | null;
  toggleClaimExpand: (claimId: string) => void;
}

export const ExtractedClaims: React.FC<ExtractedClaimsProps> = ({
  stayDetails,
  expandedClaimId,
  toggleClaimExpand
}) => {
  const claims = stayDetails?.claims || [];

  return (
    <section id="section-4" className="py-16 border-b border-slate-900">
      <div className="max-w-5xl mx-auto">
        <div className="text-center md:text-left mb-6">
          <h2 className="text-lg font-black font-mono uppercase tracking-widest text-teal-400">
            Extracted Claims
          </h2>
          <p className="text-slate-400 text-xs mt-1">
            Clinical assertions extracted from document note entries.
          </p>
        </div>

        {claims.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-900 border-dashed rounded-xl p-10 text-center text-slate-505 text-xs font-mono">
            No claims extracted yet.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {claims.map((claim, idx) => (
              <div
                key={claim.id}
                className={`p-4 rounded-xl border text-xs font-mono bg-slate-900/40 transition-all ${
                  claim.status === 'SUPPORTED'
                    ? 'border-slate-855 hover:border-emerald-500/20'
                    : 'border-rose-955 hover:border-rose-500/20'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5">
                    <span className="px-2 py-0.5 bg-slate-955 border border-slate-805 text-[9px] rounded font-mono font-bold">
                      Claim {idx + 1}
                    </span>
                    <span className="px-2 py-0.5 bg-slate-955 text-teal-400 border border-slate-855 text-[9px] rounded font-bold uppercase">
                      {claim.category}
                    </span>
                  </div>
                  
                  <span className={`px-2 py-0.5 text-[9px] rounded font-bold uppercase border ${
                    claim.status === 'SUPPORTED'
                      ? 'bg-emerald-955/80 text-emerald-400 border-emerald-500/20'
                      : 'bg-rose-955/20 text-rose-455 border-rose-900/20'
                  }`}>
                    {claim.status === 'SUPPORTED' ? 'Verified Fact' : 'Discrepancy'}
                  </span>
                </div>

                <p className="text-slate-200 mb-3 bg-slate-950/60 p-2.5 rounded border border-slate-900 font-mono text-[11px] leading-relaxed">
                  <MissingInfoIndicator value={claim.value} />
                </p>

                <div className="flex justify-between items-center text-[10px] text-slate-505 border-t border-slate-900/60 pt-2.5">
                  <span>Citations: <span className="text-slate-355 font-bold">{claim.evidence.length} sources</span></span>
                  
                  <button
                    onClick={() => toggleClaimExpand(claim.id)}
                    className="text-teal-400 hover:text-teal-350 font-bold tracking-wide"
                  >
                    {expandedClaimId === claim.id ? "Hide Citations ▲" : "View Citations ▼"}
                  </button>
                </div>

                {/* Expandable Evidence View */}
                {expandedClaimId === claim.id && (
                  <div className="mt-3 bg-slate-955 border border-slate-900 p-3 rounded-lg text-[10px] space-y-2 text-slate-450">
                    {claim.evidence.map((ev, evIdx) => (
                      <div key={evIdx} className="border-b border-slate-900/60 pb-2 last:border-0 last:pb-0">
                        <div className="flex justify-between font-bold text-slate-355 text-[9px] mb-1">
                          <span>Source: {ev.source_document}</span>
                          <span className="text-teal-400">Author: {ev.author_role}</span>
                        </div>
                        <p className="italic text-slate-355 leading-relaxed bg-slate-900/30 p-2 rounded border border-slate-900">
                          "<MissingInfoIndicator value={ev.extracted_text} />"
                        </p>
                      </div>
                    ))}
                  </div>
                )}

              </div>
            ))}
          </div>
        )}

      </div>
    </section>
  );
};
