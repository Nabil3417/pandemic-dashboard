import React, { useState, useEffect } from 'react';
import { Target, BrainCircuit, Activity, Loader2, TrendingUp, BarChart3, Grid3X3, Crosshair } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const PredictiveEngine = () => {
  const [forecasts, setForecasts] = useState([]);
  const [evalResults, setEvalResults] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('http://localhost:5000/api/forecast').then(res => res.json()),
      fetch('http://localhost:5000/api/evaluation-results').then(res => res.json())
    ])
      .then(([forecastData, evalData]) => {
        setForecasts(forecastData);
        setEvalResults(evalData);
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching data:", err);
        setLoading(false);
      });
  }, []);

  const cm = evalResults?.combined_model || {};
  const confusionMatrix = [
    { label: 'True Positive', value: cm.tp || 0, sub: 'Correctly predicted outbreak', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
    { label: 'False Positive', value: cm.fp || 0, sub: 'False alarm raised', color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' },
    { label: 'True Negative', value: cm.tn || 0, sub: 'Correctly predicted normal', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
    { label: 'False Negative', value: cm.fn || 0, sub: 'Missed outbreak', color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/20' },
  ];

  const metricCards = [
    { label: 'F1 Score', value: cm.f1_score !== undefined ? (cm.f1_score * 100).toFixed(1) + '%' : 'N/A', icon: <Target className="text-blue-400" />, accent: 'border-blue-500/30' },
    { label: 'Precision', value: cm.precision !== undefined ? (cm.precision * 100).toFixed(1) + '%' : 'N/A', icon: <Crosshair className="text-amber-400" />, accent: 'border-amber-500/30' },
    { label: 'Recall', value: cm.recall !== undefined ? (cm.recall * 100).toFixed(1) + '%' : 'N/A', icon: <Activity className="text-emerald-400" />, accent: 'border-emerald-500/30' },
    { label: 'ROC-AUC', value: cm.roc_auc !== undefined ? (cm.roc_auc * 100).toFixed(1) + '%' : 'N/A', icon: <TrendingUp className="text-purple-400" />, accent: 'border-purple-500/30' },
  ];

  const modalityBarData = evalResults ? [
    {
      name: 'NLP',
      F1: +(evalResults.per_modality.nlp_only.f1_score * 100).toFixed(1),
      Precision: +(evalResults.per_modality.nlp_only.precision * 100).toFixed(1),
      Recall: +(evalResults.per_modality.nlp_only.recall * 100).toFixed(1),
      AUC: +(evalResults.per_modality.nlp_only.roc_auc * 100).toFixed(1),
    },
    {
      name: 'Mobility',
      F1: +(evalResults.per_modality.mobility_only.f1_score * 100).toFixed(1),
      Precision: +(evalResults.per_modality.mobility_only.precision * 100).toFixed(1),
      Recall: +(evalResults.per_modality.mobility_only.recall * 100).toFixed(1),
      AUC: +(evalResults.per_modality.mobility_only.roc_auc * 100).toFixed(1),
    },
    {
      name: 'Wastewater',
      F1: +(evalResults.per_modality.wastewater_only.f1_score * 100).toFixed(1),
      Precision: +(evalResults.per_modality.wastewater_only.precision * 100).toFixed(1),
      Recall: +(evalResults.per_modality.wastewater_only.recall * 100).toFixed(1),
      AUC: +(evalResults.per_modality.wastewater_only.roc_auc * 100).toFixed(1),
    },
    {
      name: 'Combined',
      F1: +(evalResults.combined_model.f1_score * 100).toFixed(1),
      Precision: +(evalResults.combined_model.precision * 100).toFixed(1),
      Recall: +(evalResults.combined_model.recall * 100).toFixed(1),
      AUC: +(evalResults.combined_model.roc_auc * 100).toFixed(1),
    },
  ] : [];

  const metricColors = { F1: '#3b82f6', Precision: '#f59e0b', Recall: '#22c55e', AUC: '#a855f7' };

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
      </div>

      {/* Projection Charts */}
      <div className="grid grid-cols-1 gap-8 mb-16">
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
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} label={{ value: 'Predicted Risk Score (0–100)', angle: -90, position: 'insideLeft', fill: '#475569', fontSize: 9, fontWeight: '900' }} />
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
            <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mt-4 text-center">
              Forecast generated using ARIMA on historical mobility and symptom-search data
            </p>
          </div>
        ))}
      </div>

      {/* ===== MODEL EVALUATION METRICS ===== */}
      {evalResults && !evalResults.error && (
        <div className="mt-4">
          {/* Section Header */}
          <div className="flex items-center gap-3 mb-10">
            <div className="p-2.5 bg-purple-500/20 rounded-xl border border-purple-500/20">
              <BarChart3 size={20} className="text-purple-400" />
            </div>
            <div>
              <h2 className="text-3xl font-black uppercase italic tracking-tighter">
                Model <span className="text-purple-500">Evaluation</span> Metrics
              </h2>
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mt-1">
                Zone {evalResults.eval_zone} &middot; {evalResults.total_weeks} Weeks Evaluated &middot; Threshold {evalResults.threshold}
              </p>
            </div>
          </div>

          {/* 4 Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            {metricCards.map((m, i) => (
              <div key={i} className={`bg-white/5 border ${m.accent} p-6 rounded-[2rem] hover:bg-white/[0.07] transition-colors`}>
                <div className="bg-white/5 w-10 h-10 rounded-xl flex items-center justify-center mb-4">{m.icon}</div>
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{m.label}</p>
                <h4 className="text-2xl font-black italic mt-1">{m.value}</h4>
              </div>
            ))}
          </div>

          {/* Confusion Matrix + Bar Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
            
            {/* Confusion Matrix */}
            <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
              <div className="flex items-center gap-2 mb-6">
                <Grid3X3 size={16} className="text-blue-400" />
                <h3 className="text-sm font-black uppercase tracking-wider">Confusion Matrix</h3>
                <span className="text-[9px] font-bold text-slate-500 uppercase ml-auto">Combined Model</span>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-3 pl-[120px]">
                <p className="text-[9px] font-black text-slate-500 uppercase text-center tracking-widest">Predicted Positive</p>
                <p className="text-[9px] font-black text-slate-500 uppercase text-center tracking-widest">Predicted Negative</p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-4">
                  <div className="w-[104px] shrink-0">
                    <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Actual Positive</p>
                  </div>
                  <div className={`flex-1 p-5 rounded-2xl border text-center ${confusionMatrix[0].bg}`}>
                    <p className="text-3xl font-black italic">{confusionMatrix[0].value}</p>
                    <p className={`text-[10px] font-black uppercase ${confusionMatrix[0].color} mt-1`}>{confusionMatrix[0].label}</p>
                    <p className="text-[9px] text-slate-500 mt-1">{confusionMatrix[0].sub}</p>
                  </div>
                  <div className={`flex-1 p-5 rounded-2xl border text-center ${confusionMatrix[3].bg}`}>
                    <p className="text-3xl font-black italic">{confusionMatrix[3].value}</p>
                    <p className={`text-[10px] font-black uppercase ${confusionMatrix[3].color} mt-1`}>{confusionMatrix[3].label}</p>
                    <p className="text-[9px] text-slate-500 mt-1">{confusionMatrix[3].sub}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-[104px] shrink-0">
                    <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Actual Negative</p>
                  </div>
                  <div className={`flex-1 p-5 rounded-2xl border text-center ${confusionMatrix[1].bg}`}>
                    <p className="text-3xl font-black italic">{confusionMatrix[1].value}</p>
                    <p className={`text-[10px] font-black uppercase ${confusionMatrix[1].color} mt-1`}>{confusionMatrix[1].label}</p>
                    <p className="text-[9px] text-slate-500 mt-1">{confusionMatrix[1].sub}</p>
                  </div>
                  <div className={`flex-1 p-5 rounded-2xl border text-center ${confusionMatrix[2].bg}`}>
                    <p className="text-3xl font-black italic">{confusionMatrix[2].value}</p>
                    <p className={`text-[10px] font-black uppercase ${confusionMatrix[2].color} mt-1`}>{confusionMatrix[2].label}</p>
                    <p className="text-[9px] text-slate-500 mt-1">{confusionMatrix[2].sub}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Per-Modality Bar Chart */}
            <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
              <div className="flex items-center gap-2 mb-6">
                <BarChart3 size={16} className="text-amber-400" />
                <h3 className="text-sm font-black uppercase tracking-wider">Per-Modality Comparison</h3>
                <span className="text-[9px] font-bold text-slate-500 uppercase ml-auto">F1 / Precision / Recall / AUC</span>
              </div>

              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={modalityBarData} barGap={4} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                    <XAxis 
                      dataKey="name" 
                      stroke="#475569" 
                      fontSize={10} 
                      tickLine={false} 
                      axisLine={false}
                      tick={{ fontWeight: '900', textTransform: 'uppercase' }}
                    />
                    <YAxis 
                      stroke="#475569" 
                      fontSize={10} 
                      tickLine={false} 
                      axisLine={false}
                      domain={[0, 100]}
                      tickFormatter={(v) => v + '%'}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#020617', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', fontSize: '11px' }}
                      itemStyle={{ fontWeight: '900', textTransform: 'uppercase' }}
                      formatter={(value) => [value + '%']}
                    />
                    <Legend 
                      wrapperStyle={{ fontSize: '10px', fontWeight: '800', textTransform: 'uppercase', paddingTop: '8px' }}
                      iconType="circle"
                      iconSize={8}
                    />
                    <Bar dataKey="F1" fill={metricColors.F1} radius={[4, 4, 0, 0]} barSize={14} />
                    <Bar dataKey="Precision" fill={metricColors.Precision} radius={[4, 4, 0, 0]} barSize={14} />
                    <Bar dataKey="Recall" fill={metricColors.Recall} radius={[4, 4, 0, 0]} barSize={14} />
                    <Bar dataKey="AUC" fill={metricColors.AUC} radius={[4, 4, 0, 0]} barSize={14} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Fusion Weights */}
          <div className="bg-white/5 border border-white/10 rounded-[2rem] p-6">
            <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.3em] mb-3">Fusion Weights</p>
            <div className="flex flex-wrap gap-6">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                <span className="text-[11px] font-black uppercase">NLP: {(evalResults.fusion_weights.nlp * 100).toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-[11px] font-black uppercase">Wastewater: {(evalResults.fusion_weights.wastewater * 100).toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="text-[11px] font-black uppercase">Mobility: {(evalResults.fusion_weights.mobility * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {evalResults?.error && (
        <div className="mt-8 bg-rose-500/10 border border-rose-500/20 rounded-[2rem] p-8 text-center">
          <p className="text-sm font-bold text-rose-400">{evalResults.error}</p>
        </div>
      )}
    </div>
  );
};

export default PredictiveEngine;