import React, { useState, useEffect } from 'react';
import {
  Share2, Wind, Activity, CheckCircle2,
  Zap, BarChart3, Binary, Cpu, RefreshCcw, AlertCircle
} from 'lucide-react';

const ModalityCard = ({ icon: Icon, title, status, details, color, latency, throughput }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="bg-white/5 p-8 rounded-[3rem] border border-white/10 hover:border-blue-500/50 transition-all duration-500 group relative overflow-hidden text-left"
    >
      <div className={`absolute -right-4 -top-4 opacity-[0.05] transition-opacity duration-500 ${isHovered ? 'opacity-[0.1]' : ''}`}>
        <Binary size={120} className="text-white" />
      </div>

      <div className="relative z-10">
        <div className={`w-16 h-16 rounded-[1.5rem] flex items-center justify-center mb-8 shadow-lg transition-transform duration-700 group-hover:rotate-[360deg] ${color}`}>
          <Icon className="text-white" size={32} />
        </div>

        <div className="flex justify-between items-start mb-4">
          <h3 className="text-2xl font-black text-white tracking-tight italic uppercase">{title}</h3>
          <span className="flex items-center gap-1.5 text-[10px] font-black bg-blue-500/20 text-blue-400 px-3 py-1.5 rounded-full border border-blue-500/30">
            <CheckCircle2 size={12} /> {status}
          </span>
        </div>

        <p className="text-slate-400 text-sm leading-relaxed mb-8 font-medium">
          {details}
        </p>

        <div className="grid grid-cols-2 gap-4 pt-6 border-t border-white/10">
          <div>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Latency</p>
            <p className="text-sm font-bold text-white flex items-center gap-1">
              <Zap size={12} className="text-amber-500" /> {latency}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Throughput</p>
            <p className="text-sm font-bold text-white flex items-center gap-1">
              <BarChart3 size={12} className="text-blue-500" /> {throughput}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

const DataModalities = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/system-summary');
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const fmtPct = (val) => {
    if (val === null || val === undefined) return '--';
    return (val * 100).toFixed(1);
  };

  if (loading) {
    return (
      <div className="p-8 lg:p-12 bg-[#020617] min-h-screen flex items-center justify-center">
        <RefreshCcw className="animate-spin text-blue-500" size={40} />
      </div>
    );
  }

  return (
    <div className="p-8 lg:p-12 bg-[#020617] min-h-screen text-left">
      <header className="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-16 gap-8">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-600 rounded-lg">
              <Cpu size={18} className="text-white" />
            </div>
            <span className="text-[11px] font-black text-blue-500 uppercase tracking-[0.3em]">Multi-Modal Integration</span>
          </div>
          <h1 className="text-6xl font-black text-white tracking-tighter uppercase italic">
            Data <span className="text-blue-600">Modalities</span>
          </h1>
        </div>

        <button
          onClick={fetchSummary}
          disabled={loading}
          className="group flex items-center gap-3 px-8 py-4 bg-white/5 border border-white/10 rounded-2xl text-sm font-black text-white hover:bg-white/10 transition-all disabled:opacity-50"
        >
          <RefreshCcw size={18} className={`transition-transform duration-700 ${loading ? 'animate-spin' : 'group-hover:rotate-180'}`} />
          SYNC ALL DATA PIPELINES
        </button>
      </header>

      {error && (
        <div className="mb-8 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-2xl text-red-400 text-sm font-medium">
          <AlertCircle size={18} />
          Failed to connect to backend: {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
        <ModalityCard
          icon={Share2}
          title="NLP BERT Engine"
          status={summary ? 'ACTIVE' : 'OFFLINE'}
          color="bg-rose-600 shadow-rose-900/40"
          latency={summary ? `${fmtPct(summary.nlp_finetuned_f1)}% F1` : '--'}
          throughput={summary ? `${summary.languages_tested} languages` : '--'}
          details="Fine-tuned XLM-RoBERTa scanning social media for illness-related sentiment and symptomatic keyword clusters across 11 languages."
        />
        <ModalityCard
          icon={Activity}
          title="Mobility Hub"
          status={summary ? 'ACTIVE' : 'OFFLINE'}
          color="bg-blue-600 shadow-blue-900/40"
          latency={summary ? `${fmtPct(summary.combined_f1)}% F1` : '--'}
          throughput={summary ? `AUC ${summary.combined_auc ? fmtPct(summary.combined_auc) : '--'}%` : '--'}
          details="Anonymized GPS density tracking using Isolation Forest algorithms fused with NLP and wastewater signals for outbreak detection."
        />
        <ModalityCard
          icon={Wind}
          title="Symptom Search Engine"
          status={summary ? 'SYNCING' : 'OFFLINE'}
          color="bg-emerald-600 shadow-emerald-900/40"
          latency={summary ? `${summary.early_warning_avg_weeks ?? '--'} wks lead` : '--'}
          throughput={summary ? `${summary.total_eval_weeks ?? '--'} weeks data` : '--'}
          details="Google Trends symptom-search volume tracking as a proxy for disease activity, following Ginsberg et al. (Nature 2009)."
        />
      </div>

      <div className="mt-16 bg-white/5 border border-white/10 rounded-[4rem] p-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-1/2 h-full bg-blue-600/5 blur-3xl pointer-events-none" />
        <div className="relative z-10 grid grid-cols-1 xl:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl font-black text-white italic uppercase tracking-tighter mb-4">Fusion Pipeline Health</h2>
            <p className="text-slate-400 font-medium leading-relaxed max-w-xl">
              Cross-Modality Validation engine cross-references social spikes against mobility patterns.
              Fusion method: {summary ? (summary.fusion_method || 'N/A') : '--'}.
              {summary && summary.fusion_improvement_over_baseline != null
                ? ` F1 improvement over baseline: +${(summary.fusion_improvement_over_baseline * 100).toFixed(1)}%.`
                : ''}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8">
            <div className="p-6 bg-black/40 rounded-3xl border border-white/5">
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">NLP Fine-tuned F1</p>
              <p className="text-4xl font-black text-white italic">
                {summary ? fmtPct(summary.nlp_finetuned_f1) : '--'}<span className="text-blue-500">%</span>
              </p>
            </div>
            <div className="p-6 bg-black/40 rounded-3xl border border-white/5">
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Combined F1</p>
              <p className="text-4xl font-black text-white italic">
                {summary ? fmtPct(summary.combined_f1) : '--'}<span className="text-emerald-500">%</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataModalities;