import React from 'react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { Activity } from 'lucide-react';

const RiskCard = ({ title, value, color, description, isDark }) => {
  const trendData = [{ v: 20 }, { v: 35 }, { v: 30 }, { v: 55 }, { v: 45 }, { v: 70 }, { v: 65 }];

  const config = {
    blue: { text: 'text-blue-500', bg: 'bg-blue-500/10', stroke: '#3b82f6' },
    emerald: { text: 'text-emerald-500', bg: 'bg-emerald-500/10', stroke: '#10b981' },
    rose: { text: 'text-rose-500', bg: 'bg-rose-500/10', stroke: '#f43f5e' }
  }[color];

  return (
    <div className={`relative p-8 rounded-[3rem] border transition-all duration-500 group text-left overflow-hidden ${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-slate-100 shadow-xl shadow-slate-200/50'}`}>
      <div className="flex justify-between items-start mb-6 relative z-10">
        <div className={`h-12 w-12 rounded-2xl ${config.bg} flex items-center justify-center ${config.text}`}>
          <Activity size={24} />
        </div>
        <span className={`px-4 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-current ${config.text}`}>
          {title}
        </span>
      </div>

      <div className="flex items-end justify-between relative z-10">
        <h2 className={`text-5xl font-black tracking-tighter ${isDark ? 'text-white' : 'text-slate-900'}`}>
          {value}<span className="text-lg opacity-30 italic">.4</span>
        </h2>
        <div className="h-16 w-32">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData}>
              <Area type="monotone" dataKey="v" stroke={config.stroke} strokeWidth={3} fill={config.stroke} fillOpacity={0.1} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Increased text size for description: 13px */}
      <p className={`mt-6 text-[13px] font-bold leading-relaxed border-t pt-4 ${isDark ? 'text-slate-400 border-white/5' : 'text-slate-500 border-slate-50'}`}>
        {description}
      </p>
    </div>
  );
};

export default RiskCard;