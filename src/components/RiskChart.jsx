import React, { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { Loader2 } from 'lucide-react';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#0f172a] p-4 rounded-2xl border border-slate-700 shadow-2xl text-left backdrop-blur-md">
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">{label}</p>
        <div className="space-y-2">
          {payload.find(p => p.dataKey === 'fused') && (
            <div className="flex flex-col">
              <span className="text-[10px] text-rose-400 font-bold uppercase">Fused Forecast</span>
              <span className="text-lg font-black text-white">{payload.find(p => p.dataKey === 'fused').value}</span>
            </div>
          )}
          {payload.find(p => p.dataKey === 'wastewater_pred') && (
            <div className="flex flex-col border-t border-slate-800 pt-2">
              <span className="text-[10px] text-emerald-400 font-bold uppercase">Symptom (Wastewater)</span>
              <span className="text-md font-black text-slate-300">{payload.find(p => p.dataKey === 'wastewater_pred').value}</span>
            </div>
          )}
          {payload.find(p => p.dataKey === 'mobility_pred') && (
            <div className="flex flex-col border-t border-slate-800 pt-2">
              <span className="text-[10px] text-blue-400 font-bold uppercase">Mobility</span>
              <span className="text-md font-black text-slate-300">{payload.find(p => p.dataKey === 'mobility_pred').value}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
  return null;
};

const RiskChart = ({ isDark, zoneId = 11 }) => {
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`http://localhost:5000/api/forecast`)
      .then(res => res.json())
      .then(zones => {
        const zone = zones.find(z => z.zone_id === zoneId) || zones[0];
        if (zone && zone.data) {
          setChartData(zone.data.map(d => ({
            day: d.day,
            fused: d.val,
            wastewater_pred: d.wastewater_pred,
            mobility_pred: d.mobility_pred,
          })));
        }
      })
      .catch(err => console.error('Forecast fetch error:', err))
      .finally(() => setLoading(false));
  }, [zoneId]);

  if (loading) {
    return (
      <div className="w-full h-full min-h-[250px] flex items-center justify-center">
        <Loader2 className="animate-spin text-blue-500" size={28} />
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="w-full h-full min-h-[250px] flex items-center justify-center">
        <p className="text-slate-500 text-sm font-bold">No forecast data available</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[250px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -30, bottom: 0 }}>
          <defs>
            <linearGradient id="colorFused" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorWastewater" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.15}/>
              <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorMobility" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15}/>
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
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

          {/* Wastewater / Symptom Search line */}
          <Area
            type="monotone"
            dataKey="wastewater_pred"
            stroke="#10b981"
            strokeWidth={2}
            fill="url(#colorWastewater)"
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />

          {/* Mobility line */}
          <Area
            type="monotone"
            dataKey="mobility_pred"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#colorMobility)"
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />

          {/* Fused forecast line (on top, dashed red) */}
          <Area
            type="monotone"
            dataKey="fused"
            stroke="#ef4444"
            strokeWidth={3}
            strokeDasharray="6 6"
            fill="url(#colorFused)"
            dot={{ r: 3, fill: '#ef4444', strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RiskChart;