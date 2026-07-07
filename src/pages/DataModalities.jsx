import React, { useState } from 'react';
import { 
  Share2, Wind, Activity, CheckCircle2, 
  Zap, BarChart3, Binary, Cpu, RefreshCcw 
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
        
        <button className="group flex items-center gap-3 px-8 py-4 bg-white/5 border border-white/10 rounded-2xl text-sm font-black text-white hover:bg-white/10 transition-all">
          <RefreshCcw size={18} className="group-hover:rotate-180 transition-transform duration-700" />
          SYNC ALL DATA PIPELINES
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
        <ModalityCard 
          icon={Share2}
          title="NLP BERT Engine"
          status="ACTIVE"
          color="bg-rose-600 shadow-rose-900/40"
          latency="84ms"
          throughput="1.2k req/s"
          details="Scanning social media for illness-related sentiment and symptomatic keyword clusters in Dhaka sectors."
        />
        <ModalityCard 
          icon={Activity}
          title="Mobility Hub"
          status="ACTIVE"
          color="bg-blue-600 shadow-blue-900/40"
          latency="112ms"
          throughput="8.4GB/hr"
          details="Anonymized GPS density tracking using Isolation Forest algorithms to detect abnormal campus clustering."
        />
        <ModalityCard 
          icon={Wind}
          title="Symptom Search Engine"
          status="SYNCING"
          color="bg-emerald-600 shadow-emerald-900/40"
          latency="2.1s"
          throughput="Batch: 24h"
          details="Google Trends symptom-search volume tracking as a proxy for disease activity, following Ginsberg et al. (Nature 2009)."
        />
      </div>

      <div className="mt-16 bg-white/5 border border-white/10 rounded-[4rem] p-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-1/2 h-full bg-blue-600/5 blur-3xl pointer-events-none" />
        <div className="relative z-10 grid grid-cols-1 xl:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-black text-white italic uppercase tracking-tighter mb-4">Fusion Pipeline Health</h2>
              <p className="text-slate-400 font-medium leading-relaxed max-w-xl">
                The Cross-Modality Validation engine cross-references social spikes against mobility patterns to filter out 99.8% of noise.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-8">
               <div className="p-6 bg-black/40 rounded-3xl border border-white/5">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Model Precision</p>
                  <p className="text-4xl font-black text-white italic">98.2<span className="text-blue-500">%</span></p>
               </div>
               <div className="p-6 bg-black/40 rounded-3xl border border-white/5">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Global Uptime</p>
                  <p className="text-4xl font-black text-white italic">99.9<span className="text-emerald-500">%</span></p>
               </div>
            </div>
        </div>
      </div>
    </div>
  );
};

export default DataModalities;