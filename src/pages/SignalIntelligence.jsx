import React, { useState, useEffect } from 'react';
import { MessageSquare, Cpu, Radio, ShieldAlert, Loader2, Share2 } from 'lucide-react';

const SignalIntelligence = () => {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modality weights usually come from your model's attention layers or configuration
  const modalities = [
    { label: "Social Media (NLP/BERT)", val: 45, color: "bg-blue-500", icon: <MessageSquare size={14}/> },
    { label: "Wastewater Load", val: 35, color: "bg-emerald-500", icon: <Radio size={14}/> },
    { label: "Social Mobility", val: 20, color: "bg-amber-500", icon: <Cpu size={14}/> }
  ];

  useEffect(() => {
    const fetchIntel = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/signals');
        const data = await response.json();
        setSignals(data);
        setLoading(false);
      } catch (error) {
        console.error("Connection to Intelligence Server failed", error);
      }
    };
    fetchIntel();
  }, []);

  if (loading) return (
    <div className="h-full w-full flex items-center justify-center bg-[#020617]">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="animate-spin text-blue-500" size={40} />
        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500">Intercepting Signals...</p>
      </div>
    </div>
  );

  return (
    <div className="p-8 bg-[#020617] min-h-screen text-white text-left overflow-y-auto">
      {/* Tactical Header */}
      <div className="mb-10 flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-black uppercase tracking-tighter italic">Signal <span className="text-blue-500">Intelligence</span></h2>
          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.4em] mt-2">Neural Evidence & BERT Classification Feed</p>
        </div>
        <div className="hidden md:block text-right">
           <div className="px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-xl">
              <span className="text-[9px] font-black text-blue-400 uppercase animate-pulse">● System Live</span>
           </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* BERT NLP Feed (Dynamic) */}
        <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-[2.5rem] p-8 relative overflow-hidden">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <MessageSquare className="text-blue-400" size={20} />
              <h3 className="font-black uppercase tracking-widest text-sm italic">BERT Classification Stream</h3>
            </div>
            <span className="text-[10px] font-black text-slate-500 uppercase">n = {signals.length} intercepted</span>
          </div>

          <div className="space-y-4">
            {signals.map((signal, index) => (
              <div 
                key={signal.id} 
                className="p-6 bg-black/40 border border-white/5 rounded-3xl flex flex-col md:flex-row justify-between items-start md:items-center group hover:border-blue-500/50 transition-all gap-4"
              >
                <div className="max-w-full md:max-w-[75%]">
                  <p className="text-base font-bold leading-relaxed text-slate-200">"{signal.text}"</p>
                  <div className="flex flex-wrap gap-4 mt-4">
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                      <span className="text-[10px] font-black text-blue-400 uppercase">{signal.type}</span>
                    </div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">Loc: {signal.city}</span>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">Received: {signal.timestamp}</span>
                  </div>
                </div>
                
                <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end">
                  <div className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase border ${
                    signal.impact === 'Critical' 
                      ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' 
                      : 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                  }`}>
                    {signal.impact}
                  </div>
                  <Share2 size={14} className="text-slate-600 hover:text-white cursor-pointer transition-colors" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Modality Influence & AI Status */}
        <div className="space-y-8">
          <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8">
            <div className="flex items-center gap-3 mb-8">
               <ShieldAlert className="text-amber-500" size={20}/>
               <h3 className="font-black uppercase tracking-widest text-sm italic">Modality Influence</h3>
            </div>
            <div className="space-y-8">
              {modalities.map((m, i) => (
                <div key={i} className="group">
                  <div className="flex justify-between text-[10px] font-black uppercase mb-3">
                    <div className="flex items-center gap-2">
                      <span className="opacity-40">{m.icon}</span>
                      <span className="group-hover:text-blue-400 transition-colors">{m.label}</span>
                    </div>
                    <span className="opacity-50 italic">{m.val}%</span>
                  </div>
                  <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden p-[1px] border border-white/5">
                    <div 
                      className={`h-full ${m.color} rounded-full transition-all duration-1000 shadow-[0_0_10px_rgba(59,130,246,0.5)]`} 
                      style={{ width: `${m.val}%` }} 
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Research Training Logic Visualization Overlay */}
          <div className="bg-gradient-to-br from-blue-600/20 to-emerald-600/20 border border-white/10 rounded-[2.5rem] p-8">
             <h4 className="text-[10px] font-black uppercase tracking-[0.2em] mb-4 text-blue-400">Model Status</h4>
             <div className="space-y-2">
                <p className="text-2xl font-black italic">Active Inference</p>
                <p className="text-[11px] font-bold text-slate-400 leading-relaxed">
                  BERT-v3 is currently processing unstructured textual modality signals using multi-head attention to identify epidemic clusters.
                </p>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalIntelligence;