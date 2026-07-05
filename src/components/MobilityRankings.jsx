import React, { useState, useEffect } from 'react';
import { TrendingUp, Minus, TrendingDown, BarChart3 } from 'lucide-react';

const MobilityRankings = ({ onZoneClick }) => {
  const [zones, setZones] = useState([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    fetch('http://localhost:5000/api/mobility/ranking?n=15')
      .then(res => res.json())
      .then(data => {
        if (data.success && data.data) {
          setZones(data.data.top_zones || []);
        }
      })
      .catch(() => {});
  }, []);

  const getTrendIcon = (trend) => {
    if (trend === 'rising') return <TrendingUp size={10} className="text-rose-400" />;
    if (trend === 'falling') return <TrendingDown size={10} className="text-emerald-400" />;
    return <Minus size={10} className="text-blue-400" />;
  };

  const getRiskBadge = (risk) => {
    const colors = {
      critical: 'bg-red-500/20 text-red-400 border-red-500/30',
      high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      moderate: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      low: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      minimal: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    };
    return colors[risk] || colors.low;
  };

  if (zones.length === 0) return null;

  return (
    <div className="absolute top-4 left-4 z-[1000] w-[240px]">
      <div className="bg-[#0f172a]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-2">
            <BarChart3 size={14} className="text-blue-400" />
            <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white">
              W-DZMI Rankings
            </span>
          </div>
          <span className="text-[8px] font-bold text-slate-500">
            {collapsed ? '+' : '-'}
          </span>
        </button>

        {!collapsed && (
          <div className="px-2 pb-2 max-h-[400px] overflow-y-auto custom-scrollbar">
            <div className="grid grid-cols-[24px_1fr_40px_36px] gap-1 items-center px-1 mb-1">
              <span className="text-[7px] font-black text-slate-600 uppercase">#</span>
              <span className="text-[7px] font-black text-slate-600 uppercase">Zone</span>
              <span className="text-[7px] font-black text-slate-600 uppercase text-right">Score</span>
              <span className="text-[7px] font-black text-slate-600 uppercase text-right">Risk</span>
            </div>

            {zones.map((zone, idx) => (
              <button
                key={zone.zone_id}
                onClick={() => onZoneClick && onZoneClick(zone)}
                className="w-full grid grid-cols-[24px_1fr_40px_36px] gap-1 items-center px-1 py-1.5 rounded-lg hover:bg-white/5 transition-colors text-left"
              >
                <span className={`text-[10px] font-black ${idx < 3 ? 'text-rose-400' : 'text-slate-500'}`}>
                  {idx + 1}
                </span>
                <span className="text-[9px] font-bold text-slate-300 truncate">
                  {zone.zone_name}
                </span>
                <div className="flex items-center justify-end gap-1">
                  <span className="text-[10px] font-black text-white">
                    {zone.wdzmi_score}
                  </span>
                  {getTrendIcon(zone.trend)}
                </div>
                <span className={`text-[7px] font-black uppercase px-1.5 py-0.5 rounded border text-center truncate ${getRiskBadge(zone.risk_level)}`}>
                  {zone.risk_level?.slice(0, 4)}
                </span>
              </button>
            ))}

            <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-center gap-3">
              <div className="flex items-center gap-1">
                <TrendingUp size={8} className="text-rose-400" />
                <span className="text-[7px] text-slate-500 font-bold">Rising</span>
              </div>
              <div className="flex items-center gap-1">
                <Minus size={8} className="text-blue-400" />
                <span className="text-[7px] text-slate-500 font-bold">Stable</span>
              </div>
              <div className="flex items-center gap-1">
                <TrendingDown size={8} className="text-emerald-400" />
                <span className="text-[7px] text-slate-500 font-bold">Falling</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MobilityRankings;