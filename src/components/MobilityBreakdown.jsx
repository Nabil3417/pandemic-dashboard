import React from 'react';

const SIGNAL_CONFIG = {
  google_mobility: { label: 'Google Mobility', color: '#3b82f6', bg: 'bg-blue-500' },
  social_volume:   { label: 'Social Volume',   color: '#f43f5e', bg: 'bg-rose-500' },
  osrm_routing:    { label: 'OSRM Routing',    color: '#f59e0b', bg: 'bg-amber-500' },
  google_trends:   { label: 'Google Trends',   color: '#8b5cf6', bg: 'bg-violet-500' },
};

const MobilityBreakdown = ({ signals, compact = false }) => {
  if (!signals || Object.keys(signals).length === 0) return null;

  const entries = Object.entries(signals).filter(([, sig]) => sig && sig.score !== undefined);
  if (entries.length === 0) return null;

  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-2.5'}>
      {entries.map(([key, sig]) => {
        const config = SIGNAL_CONFIG[key] || { label: key, color: '#64748b', bg: 'bg-slate-500' };
        const pct = Math.min(sig.score, 100);

        if (compact) {
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[8px] font-black uppercase tracking-wider text-slate-500 w-[62px] shrink-0 truncate">
                {config.label.split(' ')[0]}
              </span>
              <div className="flex-1 h-[3px] bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${pct}%`, background: config.color }}
                />
              </div>
              <span className="text-[9px] font-black text-slate-300 w-[28px] text-right">
                {sig.score}
              </span>
            </div>
          );
        }

        return (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${config.bg}`} />
                <span className="text-[9px] font-black uppercase tracking-widest text-slate-400">
                  {config.label}
                </span>
                <span className="text-[8px] font-bold text-slate-600">
                  (w={sig.weight})
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black" style={{ color: config.color }}>
                  {sig.score}
                </span>
                <span className="text-[8px] font-bold text-slate-600">
                  {sig.contribution > 15 ? '← SPIKE' : ''}
                </span>
              </div>
            </div>
            <div className="h-[5px] bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${config.color}66, ${config.color})`,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default MobilityBreakdown;