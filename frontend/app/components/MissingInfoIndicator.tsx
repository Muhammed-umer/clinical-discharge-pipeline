import React from 'react';

interface MissingInfoIndicatorProps {
  value: any;
  fallbackText?: string;
  type?: 'patient' | 'clinical';
}

export const MissingInfoIndicator: React.FC<MissingInfoIndicatorProps> = ({
  value,
  fallbackText,
  type = 'clinical'
}) => {
  const isMissing = (val: any) => {
    if (val === null || val === undefined) return true;
    const str = String(val).trim().toUpperCase();
    return str === 'NOT_DOCUMENTED' || str === 'NOT DOCUMENTED';
  };

  const renderMissing = () => {
    return (
      <span 
        className="relative group inline-flex items-center select-none font-mono text-amber-500 font-bold gap-1 cursor-help"
        title="Information was not found in source documents."
      >
        <span className="text-amber-500">⚠</span>
        <span>NOT_DOCUMENTED</span>
        
        {/* Custom Hover Tooltip */}
        <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 bg-slate-900 text-slate-100 text-[11px] font-sans font-normal p-2.5 rounded shadow-xl border border-slate-800 opacity-0 group-hover:opacity-100 transition-opacity z-50 text-center leading-normal whitespace-normal">
          Information was not found in source documents.
          {/* Tooltip arrow */}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-900"></span>
        </span>
      </span>
    );
  };

  if (isMissing(value)) {
    return renderMissing();
  }

  const strVal = String(value);
  
  if (strVal.includes('NOT_DOCUMENTED')) {
    const parts = strVal.split('NOT_DOCUMENTED');
    return (
      <>
        {parts.map((part, idx) => (
          <React.Fragment key={idx}>
            {part}
            {idx < parts.length - 1 && renderMissing()}
          </React.Fragment>
        ))}
      </>
    );
  }

  return <>{value}</>;
};

