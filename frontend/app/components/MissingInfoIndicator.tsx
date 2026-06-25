import React from 'react';

interface MissingInfoIndicatorProps {
  value: any;
  fallbackText?: string;
}

export const MissingInfoIndicator: React.FC<MissingInfoIndicatorProps> = ({
  value,
  fallbackText = "NOT_DOCUMENTED"
}) => {
  if (value === null || value === undefined) {
    return (
      <span 
        className="inline-flex items-center text-amber-500 font-bold gap-1 cursor-help group relative select-none"
        title="Information was not found in source documents."
      >
        <span>⚠</span>
        <span className="uppercase tracking-wider font-mono">{fallbackText}</span>
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900 border border-slate-800 text-[10px] text-slate-300 font-mono rounded shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 text-center normal-case">
          Information was not found in source documents.
        </span>
      </span>
    );
  }

  const strVal = String(value);
  if (strVal.trim().toUpperCase() === 'NOT_DOCUMENTED' || strVal.trim().toUpperCase() === 'NOT DOCUMENTED') {
    return (
      <span 
        className="inline-flex items-center text-amber-500 font-bold gap-1 cursor-help group relative select-none"
        title="Information was not found in source documents."
      >
        <span>⚠</span>
        <span className="uppercase tracking-wider font-mono">{fallbackText}</span>
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900 border border-slate-800 text-[10px] text-slate-300 font-mono rounded shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 text-center normal-case">
          Information was not found in source documents.
        </span>
      </span>
    );
  }

  if (strVal.includes('NOT_DOCUMENTED')) {
    const parts = strVal.split('NOT_DOCUMENTED');
    return (
      <>
        {parts.map((part, idx) => (
          <React.Fragment key={idx}>
            {part}
            {idx < parts.length - 1 && (
              <span 
                className="inline-flex items-center text-amber-500 font-bold gap-1 cursor-help group relative select-none mx-1"
                title="Information was not found in source documents."
              >
                <span>⚠</span>
                <span className="uppercase tracking-wider font-mono">NOT_DOCUMENTED</span>
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-slate-900 border border-slate-800 text-[10px] text-slate-300 font-mono rounded shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 text-center normal-case">
                  Information was not found in source documents.
                </span>
              </span>
            )}
          </React.Fragment>
        ))}
      </>
    );
  }

  return <>{value}</>;
};
