import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  ReferenceLine
} from 'recharts';

// Data specifically structured for the 7-day forecast
const predictionData = [
  { day: 'Mon', reported: 120, ai_forecast: 125, range: [110, 140] },
  { day: 'Tue', reported: 150, ai_forecast: 155, range: [140, 170] },
  { day: 'Wed', reported: 180, ai_forecast: 190, range: [170, 210] },
  { day: 'Thu', reported: 210, ai_forecast: 240, range: [210, 270] },
  { day: 'Fri', reported: 250, ai_forecast: 310, range: [260, 360] },
  { day: 'Sat', reported: null, ai_forecast: 420, range: [350, 490] }, 
  { day: 'Sun', reported: null, ai_forecast: 550, range: [450, 650] },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#0f172a] p-4 rounded-2xl border border-slate-700 shadow-2xl text-left backdrop-blur-md">
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">{label}</p>
        <div className="space-y-2">
          {payload.find(p => p.dataKey === 'ai_forecast') && (
            <div className="flex flex-col">
              <span className="text-[10px] text-rose-400 font-bold uppercase">AI Forecast</span>
              <span className="text-lg font-black text-white">{payload.find(p => p.dataKey === 'ai_forecast').value}</span>
            </div>
          )}
          {payload.find(p => p.dataKey === 'reported')?.value && (
            <div className="flex flex-col border-t border-slate-800 pt-2">
              <span className="text-[10px] text-blue-400 font-bold uppercase">Clinical Reported</span>
              <span className="text-md font-black text-slate-300">{payload.find(p => p.dataKey === 'reported').value}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
  return null;
};

const RiskChart = () => {
  return (
    <div className="w-full h-full min-h-[250px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={predictionData} margin={{ top: 10, right: 10, left: -30, bottom: 0 }}>
          <defs>
            <linearGradient id="colorReported" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          
          <XAxis 
            dataKey="day" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 10, fontWeight: 800, fill: '#94a3b8' }} 
            dy={10}
          />
          
          <YAxis 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 10, fontWeight: 800, fill: '#94a3b8' }}
          />

          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#e2e8f0', strokeWidth: 2 }} />

          {/* 1. Range / Confidence (The grey area) */}
          <Area
            type="monotone"
            dataKey="range"
            stroke="none"
            fill="#f1f5f9"
            fillOpacity={0.6}
            connectNulls
          />

          {/* 2. Reported Cases Line (Solid Blue) */}
          <Area
            type="monotone"
            dataKey="reported"
            stroke="#3b82f6"
            strokeWidth={3}
            fill="url(#colorReported)"
            dot={{ r: 4, fill: '#3b82f6', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />

          {/* 3. AI Forecast Line (Dashed Red) */}
          <Area
            type="monotone"
            dataKey="ai_forecast"
            stroke="#ef4444"
            strokeWidth={3}
            strokeDasharray="6 6"
            fill="url(#colorForecast)"
            dot={false}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />

          <ReferenceLine x="Fri" stroke="#cbd5e1" strokeDasharray="3 3" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RiskChart;