import React, { useState, useEffect } from 'react';
import RiskCard from '../components/RiskCard';
import RiskMap from '../components/RiskMap';
import RiskChart from '../components/RiskChart';
import { 
  Radio, ShieldCheck, Globe, Activity, ListFilter, TrendingUp, Moon, Sun 
} from 'lucide-react';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    fetch('http://localhost:5000/api/risk-status')
      .then(response => response.json())
      .then(json => setData(json))
      .catch(error => {
        console.error("Data Error:", error);
        // Fallback mock data to prevent crash
        setData({ mobility_anomaly: 12.4, wastewater_load: 45.2, social_index: 8.4 });
      });
  }, []);

  const toggleTheme = () => setIsDark(!isDark);

  if (!data) return (
    <div className="h-screen w-full flex items-center justify-center bg-[#020617]">
      <div className="h-16 w-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );

  return (
    <div className={`${isDark ? 'bg-[#020617] text-white' : 'bg-slate-50 text-slate-900'} min-h-screen p-6 lg:p-10 transition-colors duration-500 font-sans`}>
      
      {/* 1. Balanced Header Section */}
      <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-10 gap-8">
        <div className="text-left">
          <div className="flex items-center gap-3 mb-3">
            <div className={`flex items-center gap-2 ${isDark ? 'bg-white/5' : 'bg-slate-900'} px-3 py-1.5 rounded-xl border border-white/10`}>
              <Globe className="text-blue-400" size={14} />
              <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Sector: DHAKA_01</span>
            </div>
            <div className={`h-1 w-8 ${isDark ? 'bg-slate-800' : 'bg-slate-200'} rounded-full`}></div>
            <span className="text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center gap-1">
              <Activity size={12} /> Engine Nominal
            </span>
          </div>
          {/* Balanced Typography */}
          <h1 className="text-4xl font-black tracking-tight leading-none mb-2">
            BioGuard <span className="text-blue-600 italic">Intelligence</span>
          </h1>
          <p className={`${isDark ? 'text-slate-400' : 'text-slate-500'} font-bold text-sm uppercase tracking-wider`}>
            Multi-Modal Fusion Analysis • Regional Risk Assessment
          </p>
        </div>

        {/* Theme Toggle & Status */}
        <div className="flex items-center gap-4">
          <button 
            onClick={toggleTheme}
            className={`p-4 rounded-2xl border transition-all ${isDark ? 'bg-white/5 border-white/10 text-yellow-400' : 'bg-white border-slate-200 text-slate-900 shadow-sm'}`}
          >
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          
          <div className={`flex items-center gap-6 ${isDark ? 'bg-white/5' : 'bg-white'} p-3 pr-6 rounded-3xl border ${isDark ? 'border-white/10' : 'border-slate-100 shadow-sm'}`}>
            <div className="h-14 w-14 rounded-2xl bg-rose-600 flex flex-col items-center justify-center text-white shadow-lg shadow-rose-500/20">
               <span className="text-[8px] font-black uppercase opacity-80">Risk</span>
               <span className="text-xl font-black italic">8.4</span>
            </div>
            <div className="text-left">
              <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Status</p>
              <h4 className="text-lg font-black text-rose-500 uppercase italic leading-none">Elevated</h4>
            </div>
          </div>
        </div>
      </header>

      {/* 2. KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <RiskCard isDark={isDark} title="Mobility Anomaly" value={data.mobility_anomaly} color="blue" description="Predictive tracking of population patterns." />
        <RiskCard isDark={isDark} title="Wastewater Load" value={data.wastewater_load} color="emerald" description="Biological signal processing from runoff." />
        <RiskCard isDark={isDark} title="Social Index" value={data.social_index} color="rose" description="Neural BERT classification of social data." />
      </div>

      {/* 3. Main Intelligence Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        
        {/* Left Section: Chart & Feed */}
        <div className="xl:col-span-7 space-y-8">
          <div className={`${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-slate-100'} p-8 rounded-[3rem] shadow-xl border h-[500px] flex flex-col text-left relative overflow-hidden`}>
             <div className="flex items-center justify-between mb-8 relative z-10">
                <div>
                  <h3 className="font-black text-2xl tracking-tighter">Outbreak <span className="text-blue-500">Forecast</span></h3>
                  <p className="text-slate-400 text-[10px] font-black uppercase tracking-widest mt-1 italic">Neural Projection Window</p>
                </div>
                <TrendingUp className="text-blue-500" size={24} />
             </div>
             <div className="flex-1">
               <RiskChart isDark={isDark} />
             </div>
          </div>

          {/* Tactical Feed with Improved Legibility */}
          <div className={`${isDark ? 'bg-blue-600/10 border-blue-500/20' : 'bg-[#0f172a] border-white/5'} p-8 rounded-[3rem] text-white shadow-2xl relative border`}>
            <div className="flex items-center justify-between mb-6">
               <h3 className="font-black flex items-center gap-3 text-sm uppercase tracking-[0.2em]">
                 <Radio size={18} className="text-blue-400 animate-pulse" /> Signal Intelligence Feed
               </h3>
               <ListFilter size={18} className="text-slate-500" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
               {[
                 { type: "MOBILITY", msg: "Anomalous cluster Dhaka Sector 4", color: "text-blue-400", time: "14:24" },
                 { type: "WASTEWATER", msg: "RNA markers stabilized in Zone 2", color: "text-emerald-400", time: "11:05" },
                 { type: "SOCIAL", msg: "BERT detected fever keyword spike", color: "text-rose-400", time: "09:12" }
               ].map((log, i) => (
                 <div key={i} className="p-5 bg-white/5 rounded-2xl border border-white/10 hover:bg-white/20 transition-all text-left group">
                    <div className="flex justify-between mb-2">
                      <span className={`text-[10px] font-black uppercase tracking-widest ${log.color}`}>{log.type}</span>
                      <span className="text-[10px] text-slate-500 font-bold">{log.time}</span>
                    </div>
                    {/* Fixed Text Size (13px) */}
                    <p className="text-[13px] font-bold text-slate-200 leading-snug group-hover:text-white">{log.msg}</p>
                 </div>
               ))}
            </div>
          </div>
        </div>
        
        {/* Right Section: The Risk Map */}
        <div className="xl:col-span-5 h-full">
          <div className={`${isDark ? 'bg-white/5 border-white/10' : 'bg-white border-slate-100'} p-3 rounded-[3rem] shadow-xl border h-full min-h-[600px] relative overflow-hidden group`}>
            <div className="absolute top-8 left-8 z-[50]">
              <div className={`${isDark ? 'bg-blue-600 text-white' : 'bg-slate-900 text-white'} px-5 py-2.5 rounded-2xl shadow-2xl flex items-center gap-3`}>
                 <ShieldCheck size={16} />
                 <span className="text-[11px] font-black uppercase tracking-widest">Geospatial Matrix</span>
              </div>
            </div>
            
            {/* The Map Component */}
            <div className={`h-full w-full overflow-hidden rounded-[2.5rem] transition-all duration-1000 ${isDark ? 'grayscale-[0.5] invert-[0.05]' : ''}`}>
               <RiskMap isDark={isDark} />
            </div>

            {/* Overlay Stats with balanced font size */}
            <div className="absolute bottom-8 left-8 right-8 z-[50] grid grid-cols-2 gap-4">
               <div className={`${isDark ? 'bg-slate-900/90 border-white/10' : 'bg-white/90 border-white'} backdrop-blur-md p-5 rounded-3xl shadow-lg border`}>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Active Hotspots</p>
                  <p className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>12 Sectors</p>
               </div>
               <div className={`${isDark ? 'bg-slate-900/90 border-white/10' : 'bg-white/90 border-white'} backdrop-blur-md p-5 rounded-3xl shadow-lg border`}>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Scanning Nodes</p>
                  <p className={`text-2xl font-black ${isDark ? 'text-white' : 'text-slate-900'}`}>1,402 Units</p>
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;