import React, { useState, useEffect } from 'react';
import { Target, BrainCircuit, Activity, Loader2, TrendingUp, BarChart3, Grid3X3, Crosshair, Languages, ArrowRight, Sparkles, AlertCircle, Zap } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const PredictiveEngine = () => {
  const [forecasts, setForecasts] = useState([]);
  const [evalResults, setEvalResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nlpData, setNlpData] = useState(null);
  const [nlpLoading, setNlpLoading] = useState(true);
  const [fusionInfo, setFusionInfo] = useState(null); // T-08: fusion classifier info

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

  // T-08: Fetch fusion classifier info
  useEffect(() => {
    fetch('http://localhost:5000/api/fusion-info')
      .then(res => res.json())
      .then(data => {
        setFusionInfo(data);
      })
      .catch(err => {
        console.error("Error fetching fusion info:", err);
      });
  }, []);

  useEffect(() => {
    fetch('http://localhost:5000/api/nlp-evaluation')
      .then(res => res.json())
      .then(data => {
        setNlpData(data);
        setNlpLoading(false);
      })
      .catch(err => {
        console.error("Error fetching NLP evaluation:", err);
        setNlpLoading(false);
      });
  }, []);

  const languageMeta = {
    en: { name: 'English', emoji: '\u{1F1EC}\u{1F1E7}' },
    bn: { name: 'Bangla', emoji: '\u{1F1E7}\u{1F1E9}' },
    banglish: { name: 'Banglish', emoji: '\u{1F4F1}' },
    hi: { name: 'Hindi', emoji: '\u{1F1EE}\u{1F1F3}' },
    ur: { name: 'Urdu', emoji: '\u{1F1F5}\u{1F1F0}' },
    ar: { name: 'Arabic', emoji: '\u{1F1F8}\u{1F1E6}' },
    zh: { name: 'Chinese', emoji: '\u{1F1E8}\u{1F1F3}' },
    es: { name: 'Spanish', emoji: '\u{1F1EA}\u{1F1F8}' },
    fr: { name: 'French', emoji: '\u{1F1EB}\u{1F1F7}' },
    pt: { name: 'Portuguese', emoji: '\u{1F1F5}\u{1F1F9}' },
    ja: { name: 'Japanese', emoji: '\u{1F1EF}\u{1F1F5}' },
  };

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
      name: 'Symptom Search',
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

  // T-08: Build fusion comparison data for the model comparison table
  const fusionEval = evalResults?.fusion_classifier;
  const fusionCompData = fusionInfo?.model_comparison || [];

  // T-08: Feature importance bar chart data
  const featureImpData = fusionInfo?.feature_importances ? [
    { name: 'NLP', importance: +(fusionInfo.feature_importances.nlp_proxy * 100).toFixed(1), fill: '#3b82f6' },
    { name: 'Symptom Search', importance: +(fusionInfo.feature_importances.wastewater_proxy * 100).toFixed(1), fill: '#22c55e' },
    { name: 'Mobility', importance: +(fusionInfo.feature_importances.mobility_score * 100).toFixed(1), fill: '#f59e0b' },
  ] : [];

  const metricColors = { F1: '#3b82f6', Precision: '#f59e0b', Recall: '#22c55e', AUC: '#a855f7' };

  const getF1Color = (f1) => {
    if (f1 > 0.70) return { bar: 'bg-emerald-500', text: 'text-emerald-400' };
    if (f1 >= 0.50) return { bar: 'bg-amber-500', text: 'text-amber-400' };
    return { bar: 'bg-rose-500', text: 'text-rose-400' };
  };

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
        {fusionInfo?.active && (
          <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-full">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">GB Fusion Active</span>
          </div>
        )}
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
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} label={{ value: 'Predicted Risk Score (0\u2013100)', angle: -90, position: 'insideLeft', fill: '#475569', fontSize: 9, fontWeight: '900' }} />
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

          {/* ===== T-08: FUSION CLASSIFIER PANEL ===== */}
          <div className="mb-10">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 bg-emerald-500/20 rounded-xl border border-emerald-500/20">
                <Zap size={20} className="text-emerald-400" />
              </div>
              <div>
                <h2 className="text-3xl font-black uppercase italic tracking-tighter">
                  Fusion <span className="text-emerald-400">Classifier</span>
                </h2>
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mt-1">
                  T-08: GradientBoosting vs Fixed-Weight Baseline
                </p>
              </div>
            </div>

            {fusionInfo?.active ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Feature Importances Bar Chart */}
                <div className="lg:col-span-1 bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
                  <div className="flex items-center gap-2 mb-6">
                    <BarChart3 size={16} className="text-emerald-400" />
                    <h3 className="text-sm font-black uppercase tracking-wider">Signal Importance</h3>
                  </div>
                  <div className="h-[200px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={featureImpData} layout="vertical" barCategoryGap="20%">
                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                        <XAxis type="number" stroke="#475569" fontSize={9} tickLine={false} axisLine={false} tickFormatter={(v) => v + '%'} domain={[0, 'auto']} />
                        <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} width={100} tick={{ fontWeight: '900', textTransform: 'uppercase' }} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#020617', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', fontSize: '11px' }}
                          formatter={(value) => [value + '%', 'Importance']}
                        />
                        <Bar dataKey="importance" radius={[0, 6, 6, 0]} barSize={20}>
                          {featureImpData.map((entry, index) => (
                            <rect key={index} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-[9px] font-bold text-slate-500 text-center mt-4 uppercase tracking-widest">
                    Learned from {evalResults.total_weeks} weeks of data
                  </p>
                </div>

                {/* GB vs Baseline Comparison + Status */}
                <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
                  <div className="flex items-center gap-2 mb-6">
                    <Sparkles size={16} className="text-emerald-400" />
                    <h3 className="text-sm font-black uppercase tracking-wider">Classifier Comparison</h3>
                    <span className="text-[9px] font-bold text-emerald-400 uppercase ml-auto bg-emerald-500/10 px-2 py-0.5 rounded-full">
                      {fusionInfo.model_name || 'GradientBoosting'}
                    </span>
                  </div>

                  {/* Comparison Table */}
                  {fusionCompData.length > 0 && (
                    <div className="mb-6 overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="border-b border-white/5">
                            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest pb-3">Model</th>
                            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest pb-3 text-right">Mean F1</th>
                            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest pb-3 text-right">F1 SD</th>
                            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest pb-3 text-right">Mean AUC</th>
                            <th className="text-[9px] font-black text-slate-500 uppercase tracking-widest pb-3 text-right">AUC SD</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fusionCompData.map((m, i) => (
                            <tr key={i} className={`border-b border-white/5 ${m.name === 'Fixed Weights (baseline)' ? 'opacity-50' : ''} ${m.name === (fusionInfo.model_name || 'gradient_boosting') ? 'bg-emerald-500/5' : ''}`}>
                              <td className="py-3 text-[11px] font-black uppercase">
                                {m.name === (fusionInfo.model_name || 'gradient_boosting') && (
                                  <span className="text-emerald-400 mr-1">&#9650;</span>
                                )}
                                {m.name}
                              </td>
                              <td className="py-3 text-[11px] font-black text-right">{(m.cv_f1_mean * 100).toFixed(1)}%</td>
                              <td className="py-3 text-[11px] font-bold text-slate-400 text-right">{(m.cv_f1_sd * 100).toFixed(1)}%</td>
                              <td className="py-3 text-[11px] font-black text-right">{(m.cv_auc_mean * 100).toFixed(1)}%</td>
                              <td className="py-3 text-[11px] font-bold text-slate-400 text-right">{(m.cv_auc_sd * 100).toFixed(1)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="text-[8px] font-bold text-slate-600 mt-2 uppercase">5-fold Stratified Cross-Validation</p>
                    </div>
                  )}

                  {/* Improvement Summary */}
                  {fusionInfo.f1_improvement_over_baseline != null && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-2xl p-5 text-center">
                        <p className="text-[9px] font-black text-emerald-400 uppercase tracking-widest mb-2">F1 Improvement</p>
                        <p className="text-3xl font-black italic text-emerald-400">
                          +{(fusionInfo.f1_improvement_over_baseline * 100).toFixed(1)}%
                        </p>
                        <p className="text-[9px] text-slate-500 mt-1">vs Fixed-Weight Baseline</p>
                      </div>
                      <div className="bg-purple-500/5 border border-purple-500/10 rounded-2xl p-5 text-center">
                        <p className="text-[9px] font-black text-purple-400 uppercase tracking-widest mb-2">GB CV F1</p>
                        <p className="text-3xl font-black italic text-purple-400">
                          {(fusionInfo.cv_f1_mean * 100).toFixed(1)}%
                        </p>
                        <p className="text-[9px] text-slate-500 mt-1">SD: {(fusionInfo.cv_f1_sd * 100).toFixed(1)}%</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
                <div className="flex items-center gap-4">
                  <AlertCircle size={20} className="text-slate-500" />
                  <div>
                    <p className="text-sm font-bold text-slate-400">Fusion classifier not yet trained.</p>
                    <p className="text-[11px] text-slate-500 mt-1">Run <span className="text-emerald-400 font-mono">python train_fusion.py</span> in the backend directory to train the GradientBoosting classifier.</p>
                  </div>
                </div>

                {/* Still show legacy weights */}
                {evalResults.fusion_weights && (
                  <div className="mt-6 pt-6 border-t border-white/5">
                    <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.3em] mb-3">Current Fusion Weights (Manual)</p>
                    <div className="flex flex-wrap gap-6">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                        <span className="text-[11px] font-black uppercase">NLP: {(evalResults.fusion_weights.nlp * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                        <span className="text-[11px] font-black uppercase">Symptom Search: {(evalResults.fusion_weights.wastewater * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                        <span className="text-[11px] font-black uppercase">Mobility: {(evalResults.fusion_weights.mobility * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Legacy Fusion Weights — shown below classifier when active */}
          {fusionInfo?.active && evalResults.fusion_weights && (
            <div className="bg-white/[0.02] border border-white/5 rounded-[2rem] p-5 mb-10">
              <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em] mb-3">Legacy Fusion Weights (Replaced by Classifier)</p>
              <div className="flex flex-wrap gap-6 opacity-40">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <span className="text-[10px] font-black uppercase text-slate-400">NLP: {(evalResults.fusion_weights.nlp * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-[10px] font-black uppercase text-slate-400">Symptom Search: {(evalResults.fusion_weights.wastewater * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-[10px] font-black uppercase text-slate-400">Mobility: {(evalResults.fusion_weights.mobility * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}

          {/* T-08: Fusion Classifier Evaluation from evaluate.py */}
          {fusionEval?.active && (
            <div className="bg-white/5 border border-white/10 rounded-[2rem] p-6 mb-10">
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.3em] mb-3">Historical Evaluation (156 Weeks)</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-[9px] font-black text-slate-500 uppercase">GB F1</p>
                  <p className="text-xl font-black italic text-emerald-400">{(fusionEval.metrics.f1_score * 100).toFixed(1)}%</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-black text-slate-500 uppercase">Baseline F1</p>
                  <p className="text-xl font-black italic text-slate-300">{(fusionEval.baseline_metrics.f1_score * 100).toFixed(1)}%</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-black text-slate-500 uppercase">GB AUC</p>
                  <p className="text-xl font-black italic text-purple-400">{(fusionEval.metrics.roc_auc * 100).toFixed(1)}%</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] font-black text-slate-500 uppercase">Baseline AUC</p>
                  <p className="text-xl font-black italic text-slate-300">{(fusionEval.baseline_metrics.roc_auc * 100).toFixed(1)}%</p>
                </div>
              </div>
            </div>
          )}

        </div>
      )}

      {evalResults?.error && (
        <div className="mt-8 bg-rose-500/10 border border-rose-500/20 rounded-[2rem] p-8 text-center">
          <p className="text-sm font-bold text-rose-400">{evalResults.error}</p>
        </div>
      )}

      {/* ===== MULTILINGUAL NLP PERFORMANCE ===== */}
      <div className="mt-16">
        {/* Section Header */}
        <div className="flex items-center gap-3 mb-10">
          <div className="p-2.5 bg-cyan-500/20 rounded-xl border border-cyan-500/20">
            <Languages size={20} className="text-cyan-400" />
          </div>
          <div>
            <h2 className="text-3xl font-black uppercase italic tracking-tighter">
              Multilingual <span className="text-cyan-400">NLP</span> Performance
            </h2>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mt-1">
              11-language evaluation
            </p>
          </div>
        </div>

        {nlpLoading && (
          <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-12 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="animate-spin text-cyan-500" size={32} />
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">Loading NLP Evaluation...</p>
            </div>
          </div>
        )}

        {!nlpLoading && nlpData?.status === 'not_evaluated' && (
          <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-12 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-center">
              <AlertCircle className="text-slate-500" size={32} />
              <p className="text-sm font-bold text-slate-400">NLP evaluation not yet run.</p>
              <p className="text-[11px] text-slate-500">Please run <span className="text-cyan-400 font-mono">python evaluate_nlp.py</span> first.</p>
            </div>
          </div>
        )}

        {!nlpLoading && nlpData?.status === 'evaluated' && (
          <>
            {/* Overall NLP Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                { label: 'NLP F1', value: (nlpData.nlp_evaluation.overall.f1 * 100).toFixed(1) + '%', color: 'border-cyan-500/30', icon: <Target className="text-cyan-400" /> },
                { label: 'Precision', value: (nlpData.nlp_evaluation.overall.precision * 100).toFixed(1) + '%', color: 'border-amber-500/30', icon: <Crosshair className="text-amber-400" /> },
                { label: 'Recall', value: (nlpData.nlp_evaluation.overall.recall * 100).toFixed(1) + '%', color: 'border-emerald-500/30', icon: <Activity className="text-emerald-400" /> },
                { label: 'ROC-AUC', value: (nlpData.nlp_evaluation.overall.roc_auc * 100).toFixed(1) + '%', color: 'border-purple-500/30', icon: <TrendingUp className="text-purple-400" /> },
              ].map((m, i) => (
                <div key={i} className={`bg-white/5 border ${m.color} p-6 rounded-[2rem] hover:bg-white/[0.07] transition-colors`}>
                  <div className="bg-white/5 w-10 h-10 rounded-xl flex items-center justify-center mb-4">{m.icon}</div>
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{m.label}</p>
                  <h4 className="text-2xl font-black italic mt-1">{m.value}</h4>
                </div>
              ))}
            </div>

            {/* Language Cards */}
            <div className="flex flex-wrap gap-4 mb-8">
              {Object.entries(nlpData.nlp_evaluation.per_language)
                .filter(([, data]) => data.n_samples >= 5)
                .sort((a, b) => b[1].f1 - a[1].f1)
                .map(([lang, data]) => {
                  const meta = languageMeta[lang] || { name: lang, emoji: '' };
                  const colors = getF1Color(data.f1);
                  return (
                    <div key={lang} className="bg-white/5 border border-white/10 rounded-[2rem] p-5 w-[200px] relative overflow-hidden hover:bg-white/[0.07] transition-colors group">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{meta.emoji}</span>
                          <span className="text-[11px] font-black uppercase tracking-wider">{meta.name}</span>
                        </div>
                        <span className="text-[8px] font-bold text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">
                          n={data.n_samples}
                        </span>
                      </div>
                      <p className={`text-[2rem] font-black italic ${colors.text} leading-none`}>
                        {(data.f1 * 100).toFixed(1)}
                        <span className="text-sm opacity-40">%</span>
                      </p>
                      <p className="text-[9px] font-bold text-slate-500 mt-2">
                        Precision: {data.precision.toFixed(3)} &middot; Recall: {data.recall.toFixed(3)}
                      </p>
                      <div className={`absolute bottom-0 left-0 right-0 h-1 ${colors.bar}`} />
                    </div>
                  );
                })}
            </div>

            {/* Fine-Tuning Results + Banglish Ablation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Fine-Tuning Results */}
              {nlpData.finetuning_results && (
                <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
                  <div className="flex items-center gap-2 mb-6">
                    <Sparkles size={16} className="text-cyan-400" />
                    <h3 className="text-sm font-black uppercase tracking-wider">Fine-Tuning Impact</h3>
                  </div>
                  <div className="space-y-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Base XLM-RoBERTa</p>
                        <p className="text-2xl font-black italic text-slate-400 mt-1">
                          {(nlpData.finetuning_results.base_model.overall.f1 * 100).toFixed(1)}%
                        </p>
                      </div>
                      <ArrowRight size={20} className="text-slate-600" />
                      <div>
                        <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Fine-Tuned</p>
                        <p className="text-2xl font-black italic text-cyan-400 mt-1">
                          {(nlpData.finetuning_results.finetuned_model.overall.f1 * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                    <div className="h-3 w-full bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-cyan-600 to-emerald-500 rounded-full transition-all duration-1000"
                        style={{ width: `${nlpData.finetuning_results.finetuned_model.overall.f1 * 100}%` }}
                      />
                    </div>
                    <div className="flex items-center gap-2 justify-center">
                      <span className="text-[10px] font-black text-emerald-400 uppercase">F1 Improvement:</span>
                      <span className="text-lg font-black text-emerald-400">
                        +{(nlpData.finetuning_results.improvement.overall_f1_delta * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2 justify-center">
                      <span className="text-[10px] font-black text-purple-400 uppercase">AUC:</span>
                      <span className="text-[11px] font-black text-slate-300">
                        {(nlpData.finetuning_results.base_model.overall.roc_auc * 100).toFixed(1)}%
                      </span>
                      <ArrowRight size={12} className="text-slate-600" />
                      <span className="text-[11px] font-black text-purple-400">
                        {(nlpData.finetuning_results.finetuned_model.overall.roc_auc * 100).toFixed(1)}%
                      </span>
                      <span className="text-[10px] font-black text-emerald-400">
                        (+{(nlpData.finetuning_results.improvement.auc_delta * 100).toFixed(1)}%)
                      </span>
                    </div>
                    <p className="text-[9px] font-bold text-slate-500 text-center">
                      {nlpData.finetuning_results.training_config.train_samples} train &middot; {nlpData.finetuning_results.training_config.val_samples} val &middot; {nlpData.finetuning_results.training_config.test_samples} test &middot; {nlpData.finetuning_results.training_config.epochs} epochs
                    </p>
                  </div>
                </div>
              )}

              {/* Banglish Ablation */}
              {nlpData.banglish_ablation && (
                <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
                  <div className="flex items-center gap-2 mb-6">
                    <Languages size={16} className="text-amber-400" />
                    <h3 className="text-sm font-black uppercase tracking-wider">Banglish Detection Ablation</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-6 mb-6">
                    <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-2xl p-5 text-center">
                      <p className="text-[9px] font-black text-emerald-400 uppercase tracking-widest mb-2">With Detection</p>
                      <p className="text-3xl font-black italic text-emerald-400">
                        {(nlpData.banglish_ablation.with_detection.f1 * 100).toFixed(1)}%
                      </p>
                      <p className="text-[9px] text-slate-500 mt-2">
                        P: {nlpData.banglish_ablation.with_detection.precision.toFixed(3)} &middot; R: {nlpData.banglish_ablation.with_detection.recall.toFixed(3)}
                      </p>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center">
                      <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Without Detection</p>
                      <p className="text-3xl font-black italic text-slate-300">
                        {(nlpData.banglish_ablation.without_detection.f1 * 100).toFixed(1)}%
                      </p>
                      <p className="text-[9px] text-slate-500 mt-2">
                        P: {nlpData.banglish_ablation.without_detection.precision.toFixed(3)} &middot; R: {nlpData.banglish_ablation.without_detection.recall.toFixed(3)}
                      </p>
                    </div>
                  </div>
                  <div className="text-center">
                    {nlpData.banglish_ablation.f1_improvement > 0 ? (
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-[10px] font-black text-emerald-400 uppercase">F1 Improvement:</span>
                        <span className="text-lg font-black text-emerald-400">
                          +{(nlpData.banglish_ablation.f1_improvement * 100).toFixed(1)}%
                        </span>
                      </div>
                    ) : (
                      <p className="text-[10px] font-bold text-slate-500">
                        Baseline comparable (ablation delta: {nlpData.banglish_ablation.f1_improvement.toFixed(3)})
                      </p>
                    )}
                  </div>
                  <p className="text-[9px] font-bold text-amber-400/70 text-center mt-4 italic">
                    Novel contribution: First Banglish health signal detector for epidemic surveillance
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PredictiveEngine;