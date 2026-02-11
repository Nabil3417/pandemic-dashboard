import React, { useState, useEffect } from 'react';
import { Target, BrainCircuit, ShieldCheck, Activity, Loader2, TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const PredictiveEngine = () => {
  const [forecasts, setForecasts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:5000/api/forecast')
      .then(res => res.json())
      .then(data => {
        setForecasts(data);
        setLoading(false);
      });
  }, []);

  if (loading) return (
    <div className="h-full w-full flex items-center justify-center bg-[#020617]">
      <Loader2 className="animate-spin text-blue-500" size={40} />
    </div>
  );

  return (
    <div className="p-8 bg-[#020617] min-h-screen text-white text-left overflow-y-auto">
      <div className="mb-10 flex justify-between items-end">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <BrainCircuit size={18} className="text-blue-500 animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500">Neural Projection Engine</span>
          </div>
          <h2 className="text-5xl font-black uppercase italic tracking-tighter">AI <span className="text-blue-600">Forecast</span></h2>
        </div>
        <div className="bg-white/5 px-6 py-3 rounded-2xl border border-white/10 text-right">
            <p className="text-[9px] font-black text-slate-500 uppercase">Confidence Interval</p>
            <p className="text-xl font-black text-emerald-500 italic">94.8%</p>
        </div>
      </div>

      {/* Accuracy Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
        {[
          { label: "Accuracy", val: "92.4%", icon: <Target className="text-emerald-400" /> },
          { label: "Recall", val: "88.1%", icon: <Activity className="text-blue-400" /> },
          { label: "Lead Time", val: "4.2 Days", icon: <ShieldCheck className="text-purple-400" /> },
          { label: "F1 Score", val: "0.89", icon: <TrendingUp className="text-amber-400" /> }
        ].map((stat, i) => (
          <div key={i} className="bg-white/5 border border-white/10 p-6 rounded-[2.5rem] hover:border-blue-500/50 transition-colors">
            <div className="bg-white/5 w-10 h-10 rounded-xl flex items-center justify-center mb-4">{stat.icon}</div>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{stat.label}</p>
            <h4 className="text-2xl font-black italic mt-1">{stat.val}</h4>
          </div>
        ))}
      </div>

      {/* Projection Charts */}
      <div className="grid grid-cols-1 gap-8">
        {forecasts.map((forecast, i) => (
          <div key={i} className="bg-white/5 border border-white/10 rounded-[3.5rem] p-10 relative overflow-hidden group">
            <div className="flex justify-between items-center mb-8 relative z-10">
              <div>
                <h3 className="text-2xl font-black italic uppercase">{forecast.city}</h3>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">14-Day Outbreak Probability Projection</p>
              </div>
              <div className="h-12 w-12 rounded-2xl bg-white/5 flex items-center justify-center border border-white/10">
                 <TrendingUp size={20} style={{ color: forecast.color }} />
              </div>
            </div>

            <div className="h-[300px] w-full relative z-10">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={forecast.data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                  <XAxis dataKey="day" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#020617', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', fontSize: '12px' }}
                    itemStyle={{ fontWeight: '900', textTransform: 'uppercase' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="val" 
                    stroke={forecast.color} 
                    strokeWidth={4} 
                    dot={{ fill: forecast.color, r: 4, strokeWidth: 2, stroke: '#020617' }} 
                    activeDot={{ r: 8, strokeWidth: 0 }}
                    animationDuration={2000}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PredictiveEngine;