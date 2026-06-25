import React from 'react';

interface HeroProps {
  onStartClick: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onStartClick }) => {
  return (
    <section id="section-1" className="min-h-[50vh] flex flex-col justify-center items-center text-center py-12 border-b border-slate-900 relative">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[350px] h-[350px] bg-teal-500/5 rounded-full filter blur-[80px] pointer-events-none"></div>
      
      <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight max-w-4xl text-slate-100 font-sans leading-tight">
        AI-Powered Hospital <br/>
        <span className="bg-gradient-to-r from-teal-400 via-emerald-450 to-teal-500 bg-clip-text text-transparent">Discharge Summary Pipeline</span>
      </h1>
      
      <p className="text-slate-400 text-sm sm:text-base max-w-2xl mt-5 font-medium leading-relaxed">
        Transform multiple unstructured clinical documents into one safe, evidence-grounded discharge summary.
      </p>

      <div className="flex flex-wrap justify-center gap-4 mt-8 text-xs font-mono text-slate-355">
        <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-900/50 border border-slate-855 rounded-lg">
          ✔ Evidence Grounded
        </span>
        <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-900/50 border border-slate-855 rounded-lg">
          ✔ Conflict Aware
        </span>
        <span className="flex items-center gap-1.5 px-3 py-1 bg-slate-900/50 border border-slate-855 rounded-lg">
          ✔ Human Verified
        </span>
      </div>

      <div className="mt-10 flex flex-col items-center gap-3">
        <button
          onClick={onStartClick}
          className="px-8 py-3.5 bg-teal-500 hover:bg-teal-400 text-slate-955 font-bold rounded-xl text-sm font-mono tracking-wider uppercase transition-all shadow-[0_0_20px_rgba(20,184,166,0.25)] hover:scale-105"
        >
          Upload Clinical Documents
        </button>
      </div>
    </section>
  );
};
