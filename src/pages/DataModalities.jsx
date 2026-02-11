import React, { useState } from 'react';
import { 
  Database, Share2, Wind, Activity, 
  CheckCircle2, Zap, BarChart3, Binary, 
  ShieldCheck, Cpu, RefreshCcw
} from 'lucide-react';

const ModalityCard = ({ icon: Icon, title, status, details, color, latency, throughput }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div 
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="bg-white p-8 rounded-[3rem] border border-slate-100 shadow-sm hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 group relative overflow-hidden"
    >
      {/* Decorative Neural Background Pattern */}
      <div className={`absolute -right-4 -top-4 opacity-[0.03] transition-opacity duration-500 ${isHovered ? 'opacity-[0.08]' : ''}`}>
        <Binary size={120} />
      </div>

      <div className="relative z-10 text-left">
        <div className={`w-16 h-16 rounded-[1.5rem] flex items-center justify-center mb-8 shadow-lg transition-transform duration-700 group-hover:rotate-[360deg] ${color}`}>
          <Icon className="text-white" size={32} />
        </div>

        <div className="flex justify-between items-start mb-4">
          <h3 className="text-2xl font-black text-slate-900 tracking-tight">{title}</h3>
          <span className="flex items-center gap-1.5 text-[10px] font-black bg-emerald-50 text-emerald-600 px-3 py-1.5 rounded-full border border-emerald-100">
            <CheckCircle2 size={12} /> {status}
          </span>
        </div>

        <p className="text-slate-500 text-sm leading-relaxed mb-8 font-medium">
          {details}
        </p>

        {/* Real-time Telemetry Mini-Grid */}
        <div className="grid grid-cols-2 gap-4 pt-6 border-t border-slate-50">
          <div>
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Latency</p>
            <p className="text-sm font-bold text-slate-700 flex items-center gap-1">
              <Zap size={12} className="text-amber-500" /> {latency}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Throughput</p>
            <p className="text-sm font-bold text-slate-700 flex items-center gap-1">
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
    <div className="p-8 lg:p-12 animate-in fade-in slide-in-from-bottom-6 duration-1000">
      
      {/* 1. Technical Header */}
      <header className="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-16 gap-8 text-left">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-600 rounded-lg">
              <Cpu size={18} className="text-white" />
            </div>
            <span className="text-[11px] font-black text-blue-600 uppercase tracking-[0.3em]">Neural Fusion Engine v2.0</span>
          </div>
          <h1 className="text-6xl font-black text-slate-900 tracking-tighter">
            Data <span className="text-blue-600">Modalities</span>
          </h1>
          <p className="text-slate-500 font-medium mt-4 text-lg max-w-2xl leading-relaxed">
            Managing the heterogeneous multi-source data pipeline. Our system fuses NLP, geospatial mobility, and biological markers for peak predictive accuracy.
          </p>
        </div>
        
        <button className="group flex items-center gap-3 px-8 py-4 bg-white border border-slate-200 rounded-2xl text-sm font-black text-slate-900 hover:bg-slate-50 transition-all shadow-sm">
          <RefreshCcw size={18} className="group-hover:rotate-180 transition-transform duration-700" />
          RE-SYNC ALL PIPELINES
        </button>
      </header>

      {/* 2. Modality Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-10">
        <ModalityCard 
          icon={Share2}
          title="NLP Social Engine"
          status="ACTIVE"
          color="bg-rose-500 shadow-rose-200"
          latency="84ms"
          throughput="1.2k req/s"
          details="BERT-based sentiment classifier scanning X (Twitter) and regional health forums for symptomatic keyword clusters."
        />
        <ModalityCard 
          icon={Activity}
          title="Mobility Tracker"
          status="ACTIVE"
          color="bg-blue-600 shadow-blue-200"
          latency="112ms"
          throughput="8.4GB/hr"
          details="Anonymized telco-grade GPS pings processed via Isolation Forest algorithms to detect abnormal density shifts."
        />
        <ModalityCard 
          icon={Wind}
          title="Wastewater Bio-Feed"
          status="SYNCING"
          color="bg-emerald-500 shadow-emerald-200"
          latency="2.1s"
          throughput="Batch: 24h"
          details="Digital twin of viral RNA concentration levels integrated from the Dhaka Water Supply & Sewerage Authority (DWASA)."
        />
      </div>

      {/* 3. Fusion Pipeline Visualization */}
      <div className="mt-16 bg-[#0f172a] rounded-[4rem] p-12 text-white relative overflow-hidden text-left shadow-2xl shadow-slate-900/50">
        {/* Abstract Background Design */}
        <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-blue-600/20 to-transparent pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-emerald-500/10 blur-[100px] rounded-full" />

        <div className="relative z-10">
          <div className="flex items-center gap-4 mb-8">
            <div className="h-12 w-12 bg-white/10 rounded-2xl flex items-center justify-center backdrop-blur-md">
              <ShieldCheck className="text-blue-400" size={24} />
            </div>
            <h2 className="text-3xl font-black tracking-tight">Fusion Pipeline Health</h2>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-12">
            <div className="xl:col-span-2">
              <p className="text-slate-400 font-medium leading-relaxed max-w-xl mb-10">
                Our proprietary **Cross-Modality Validation** engine cross-references social media spikes against mobility patterns to filter out 99.8% of noise.
              </p>
              
              {/* Pro Status Indicators */}
              <div className="flex flex-wrap gap-8">
                <div className="space-y-2">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Model Precision</p>
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-black text-white">98.2</span>
                    <span className="text-blue-400 font-bold mb-1">%</span>
                  </div>
                </div>
                <div className="w-[1px] h-12 bg-slate-800 hidden md:block" />
                <div className="space-y-2">
                  <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Global Uptime</p>
                  <div className="flex items-end gap-2">
                    <span className="text-4xl font-black text-white">99.99</span>
                    <span className="text-emerald-400 font-bold mb-1">%</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-slate-800/50 backdrop-blur-sm p-8 rounded-[2.5rem] border border-slate-700/50">
              <h4 className="text-sm font-black text-blue-400 uppercase tracking-widest mb-6 flex items-center gap-2">
                <Binary size={16} /> Data Flow Health
              </h4>
              <div className="space-y-4">
                {[
                  { label: "Normalization", status: 100 },
                  { label: "Weighting", status: 85 },
                  { label: "Inference", status: 92 },
                ].map((item, idx) => (
                  <div key={idx} className="space-y-2">
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider">
                      <span className="text-slate-400">{item.label}</span>
                      <span className="text-slate-200">{item.status}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500 rounded-full" 
                        style={{ width: `${item.status}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataModalities;