import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, Clock, ArrowUpRight, Download, MapPin
} from 'lucide-react';

const AlertLogs = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');
  const [dynamicLogs, setDynamicLogs] = useState([]); // NEW: Real-time data

  // Fetch real-time alerts from backend
  const fetchAlerts = () => {
    fetch('http://localhost:5000/api/risk-status')
      .then(res => res.json())
      .then(data => {
        setDynamicLogs(data.alerts || []);
      })
      .catch(err => console.error("Alert Fetch Error", err));
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs = useMemo(() => {
    return dynamicLogs.filter(log => 
      (log.message.toLowerCase().includes(searchTerm.toLowerCase()) || log.city.toLowerCase().includes(searchTerm.toLowerCase())) &&
      (activeFilter === 'All' || log.severity.includes(activeFilter.toUpperCase()))
    );
  }, [searchTerm, activeFilter, dynamicLogs]);

  return (
    <div className="p-8 lg:p-12 bg-[#020617] min-h-screen text-left">
      <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-12 gap-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-2 w-2 rounded-full bg-red-600 animate-pulse" />
            <span className="text-[11px] font-black text-red-500 uppercase tracking-[0.2em]">Live Threat Audit</span>
          </div>
          <h1 className="text-6xl font-black text-white tracking-tighter uppercase italic">Alert <span className="text-blue-600">Logs</span></h1>
        </div>

        <div className="flex flex-wrap gap-4 w-full xl:w-auto">
          <div className="relative flex-1 xl:flex-none">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
            <input 
              type="text" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search tactical summaries..." 
              className="pl-12 pr-6 py-4 bg-white/5 border border-white/10 rounded-2xl text-sm font-bold text-white focus:outline-none focus:border-blue-500 w-full xl:w-80 transition-all"
            />
          </div>
          <button 
  onClick={() => {
    if (!dynamicLogs.length) return;
    const headers = ['ID', 'City', 'Severity', 'Message', 'Timestamp'];
    const rows = dynamicLogs.map(a => [
      a.id, a.city, a.severity, a.message, new Date().toISOString()
    ]);
    const csvContent = [headers, ...rows]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `bioguard_alerts_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }}
  className="flex items-center gap-3 px-8 py-4 bg-blue-600 text-white rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-blue-700 transition-all shadow-xl shadow-blue-900/20">
  <Download size={18} /> Export Results
</button>
        </div>
      </header>

      <div className="flex gap-4 mb-8 overflow-x-auto pb-2">
        {['All', 'Critical', 'Moderate'].map((type) => (
          <button
            key={type}
            onClick={() => setActiveFilter(type)}
            className={`px-6 py-2 rounded-xl text-[10px] font-black transition-all border shrink-0 ${
              activeFilter === type 
              ? 'bg-blue-600 text-white border-blue-600' 
              : 'bg-white/5 text-slate-500 border-white/10 hover:border-white/20'
            }`}
          >
            {type.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {filteredLogs.length > 0 ? filteredLogs.map((log) => (
          <div key={log.id} className="group relative bg-white/5 border border-white/10 rounded-[2.5rem] p-8 flex flex-col lg:flex-row items-start lg:items-center gap-8 transition-all hover:bg-white/[0.07] hover:border-white/20">
            <div className="min-w-[140px]">
              <p className="text-[10px] font-black text-blue-500 mb-1 uppercase tracking-widest">{log.id}</p>
              <div className="flex items-center gap-2 text-white font-black text-sm italic">
                <Clock size={14} className="text-slate-500" /> Just Now
              </div>
            </div>

            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase ${
                  log.severity === 'CRITICAL' ? 'bg-red-600 text-white' : 'bg-amber-500 text-black'
                }`}>
                  {log.severity}
                </span>
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1">
                  <MapPin size={10} /> {log.city}
                </span>
              </div>
              <h4 className="text-xl font-bold text-white leading-tight tracking-tight italic uppercase">
                {log.message}
              </h4>
            </div>

            <div className="flex items-center gap-8 border-t lg:border-t-0 border-white/10 pt-6 lg:pt-0 w-full lg:w-auto">
              <div className="text-right ml-auto">
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">AI Status</p>
                <p className="text-xl font-black text-blue-400 italic">LIVE FEED</p>
              </div>
              <button className="h-14 w-14 rounded-2xl bg-white/5 flex items-center justify-center text-white hover:bg-blue-600 transition-all">
                <ArrowUpRight size={24} />
              </button>
            </div>
          </div>
        )) : (
          <div className="text-center py-20 bg-white/5 rounded-[3rem] border border-white/5">
             <p className="text-slate-500 font-black uppercase tracking-[0.3em] italic">No Critical Anomalies Detected</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AlertLogs;