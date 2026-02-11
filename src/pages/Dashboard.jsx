import React, { useState, useEffect } from 'react';
import RiskCard from '../components/RiskCard';
import RiskMap from '../components/RiskMap';
import RiskChart from '../components/RiskChart';
import { 
  Radio, Globe, Activity, TrendingUp, AlertTriangle, Zap, ShieldAlert
} from 'lucide-react';
import { toast, Toaster } from 'react-hot-toast';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [isCrisis, setIsCrisis] = useState(false);

  const fetchData = () => {
    fetch('http://localhost:5000/api/risk-status')
      .then(res => res.json())
      .then(json => {
        setData(json);
        setIsCrisis(json.crisis_active);
      })
      .catch(err => console.error("Data Sync Error", err));
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Auto-refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const handleSimulate = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/simulate-crisis', { method: 'POST' });
      const status = await res.json();
      if (status.status === "active") {
        toast.error("CRITICAL: Outbreak Simulation Initiated!", { duration: 4000 });
      } else {
        toast.success("Simulation Terminated. Systems Nominal.");
      }
      fetchData();
    } catch (e) {
      toast.error("Simulation Server Offline");
    }
  };

  if (!data) return <div className="bg-[#020617] h-screen" />;

  return (
    <div className={`transition-colors duration-700 ${isCrisis ? 'bg-[#1a0505]' : 'bg-[#020617]'} text-white min-h-screen p-6 lg:p-10 overflow-x-hidden relative`}>
      <Toaster position="top-right" />
      
      {/* Background Alerts Overlay when Crisis is Active */}
      {isCrisis && (
        <div className="absolute inset-0 pointer-events-none border-[10px] border-rose-600/20 animate-pulse z-[100]" />
      )}

      {/* 1. Tactical Header */}
      <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-10 gap-8">
        <div className="text-left">
          <div className="flex items-center gap-3 mb-3">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border ${isCrisis ? 'bg-rose-600/20 border-rose-500' : 'bg-white/5 border-white/10'}`}>
              <Globe className={isCrisis ? "text-rose-500" : "text-blue-400"} size={14} />
              <span className="text-[10px] font-black uppercase tracking-widest">Sector: DHAKA_METRO</span>
            </div>
            <button 
              onClick={handleSimulate}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${
                isCrisis ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/40' : 'bg-white/5 border border-white/20 text-slate-400 hover:bg-rose-600 hover:text-white'
              }`}
            >
              {isCrisis ? <Zap size={12} fill="white"/> : <Zap size={12}/>}
              {isCrisis ? "Deactivate Crisis" : "Simulate Outbreak"}
            </button>
          </div>
          <h1 className="text-5xl font-black tracking-tighter italic uppercase leading-none">
            Command <span className={isCrisis ? "text-rose-600" : "text-blue-600"}>Center</span>
          </h1>
        </div>

        <div className={`flex items-center gap-6 p-3 pr-8 rounded-[2rem] border transition-all shadow-2xl ${
          isCrisis ? 'bg-rose-950/40 border-rose-500' : 'bg-white/5 border-white/10'
        }`}>
          <div className={`h-16 w-16 rounded-2xl flex flex-col items-center justify-center text-white shadow-lg transform -rotate-3 transition-colors ${
            isCrisis ? 'bg-rose-600 shadow-rose-900/50' : 'bg-blue-600 shadow-blue-900/40'
          }`}>
             <span className="text-[8px] font-black uppercase opacity-80">Index</span>
             <span className="text-2xl font-black italic">{data.social_index}</span>
          </div>
          <div className="text-left">
            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Aggregate Threat</p>
            <h4 className={`text-xl font-black uppercase italic leading-none ${isCrisis ? 'text-rose-500' : 'text-blue-500'}`}>
              {isCrisis ? 'CRITICAL' : 'ELEVATED'}
            </h4>
          </div>
        </div>
      </header>

      {/* 2. KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <RiskCard isDark={true} title="Mobility Anomaly" value={data.mobility_anomaly} color={isCrisis ? "rose" : "blue"} />
        <RiskCard isDark={true} title="Wastewater Load" value={data.wastewater_load} color={isCrisis ? "rose" : "emerald"} />
        <RiskCard isDark={true} title="Social Sentiment" value={data.social_index} color="rose" />
      </div>

      {/* 3. Main Workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        {/* Forecast & Feed */}
        <div className="xl:col-span-6 space-y-8">
          <div className="bg-white/5 border border-white/10 p-8 rounded-[3.5rem] shadow-xl h-[520px] flex flex-col relative overflow-hidden group">
              <div className="flex items-center justify-between mb-8 relative z-10">
                <h3 className="font-black text-3xl tracking-tighter italic uppercase">
                  Outbreak <span className={isCrisis ? "text-rose-500" : "text-blue-500"}>Forecast</span>
                </h3>
                <TrendingUp className={isCrisis ? "text-rose-500" : "text-blue-500"} size={24} />
              </div>
              <div className="flex-1 relative z-10">
                <RiskChart isDark={true} />
              </div>
          </div>

          <div className={`${isCrisis ? 'bg-rose-600/10 border-rose-500/20' : 'bg-blue-600/5 border-blue-500/10'} p-8 rounded-[3rem] text-white shadow-2xl relative border overflow-hidden`}>
            <h3 className="font-black flex items-center gap-3 text-xs uppercase tracking-[0.3em] italic mb-6">
              <Radio size={18} className={`${isCrisis ? 'text-rose-500' : 'text-blue-400'} animate-pulse`} /> 
              Signal Intelligence Feed
            </h3>
            <div className="space-y-3">
               <div className="p-4 bg-black/40 rounded-2xl border border-white/5 flex justify-between items-center group hover:border-blue-500/50 transition-all">
                  <p className="text-[13px] font-bold text-slate-300 italic uppercase">
                    {isCrisis ? "Neural Outbreak Classification Active" : "Satellite Sweep Active"}
                  </p>
                  <span className={`text-[10px] font-black uppercase tracking-widest ${isCrisis ? 'text-rose-500' : 'text-blue-400'}`}>
                    {isCrisis ? 'EMERGENCY' : 'STABLE'}
                  </span>
               </div>
            </div>
          </div>
        </div>
        
        {/* Map Section */}
        <div className="xl:col-span-6 h-full min-h-[600px]">
          <div className={`border-2 p-2 rounded-[3.5rem] shadow-2xl h-full relative overflow-hidden transition-colors ${
            isCrisis ? 'border-rose-500/50 bg-[#2a0f0f]' : 'border-white/20 bg-[#0f172a]'
          }`}>
            <div className={`scanner-line absolute left-0 w-full h-[2px] z-[60] shadow-[0_0_20px] ${
              isCrisis ? 'bg-rose-500 shadow-rose-500' : 'bg-blue-500 shadow-blue-500'
            }`}></div>
            
            <div className="absolute top-8 left-8 z-[70] pointer-events-none">
              <div className="bg-slate-900/90 backdrop-blur-xl px-5 py-3 rounded-2xl border border-white/10 flex items-center gap-3 shadow-2xl">
                 <ShieldAlert size={16} className={isCrisis ? "text-rose-500" : "text-emerald-500"} />
                 <span className="text-[11px] font-black uppercase tracking-[0.2em] text-white">
                    {isCrisis ? 'CRISIS VECTOR STREAM' : 'LIVE VECTOR STREAM'}
                 </span>
              </div>
            </div>

            <div className="h-full w-full overflow-hidden rounded-[3rem] relative z-[50] bg-[#020617]">
              <div className={`h-full w-full transition-all duration-700 ${isCrisis ? 'saturate-[2] brightness-[0.8]' : 'saturate-[1.4] brightness-[1.25]'}`}>
                <RiskMap isDark={true} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes scan {
          0% { top: -5%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 105%; opacity: 0; }
        }
        .scanner-line {
          animation: scan 4s linear infinite;
        }
      `}</style>
    </div>
  );
};

export default Dashboard;