import React, { useState, useMemo } from 'react';
import { 
  Search, Filter, ShieldAlert, Activity, 
  Database, MessageSquare, MapPin, Clock, 
  ChevronRight, ArrowUpRight, Download
} from 'lucide-react';
import { Parser } from 'json2csv';

const AlertLogs = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');

  const logs = [
    { id: "AL-902", time: "02:14 PM", date: "Feb 11, 2026", sector: "Bashundhara", type: "Mobility", severity: "Critical", msg: "Anomalous crowd clustering detected near NSU Gate 1.", status: "Unresolved", confidence: "94%" },
    { id: "AL-895", time: "09:40 AM", date: "Feb 11, 2026", sector: "Dhaka North", type: "NLP BERT", severity: "High", msg: "Spike in 'respiratory distress' keywords in regional feeds.", status: "Reviewing", confidence: "88%" },
    { id: "AL-899", time: "11:05 AM", date: "Feb 10, 2026", sector: "Urban Drainage", type: "Wastewater", severity: "Info", msg: "RNA baseline synchronized. Minimal pathogen detected.", status: "Logged", confidence: "99%" },
    { id: "AL-882", time: "06:12 PM", date: "Feb 09, 2026", sector: "Mirpur", type: "Mobility", severity: "Medium", msg: "Evening transit patterns deviated from 7-day average.", status: "Resolved", confidence: "82%" },
  ];

  // --- LOGIC: Real-time Filtering & Search ---
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesSearch = 
        log.msg.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.sector.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.id.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesFilter = activeFilter === 'All' || log.type.includes(activeFilter);
      
      return matchesSearch && matchesFilter;
    });
  }, [searchTerm, activeFilter]);

  // --- LOGIC: Export to CSV ---
  const handleExport = () => {
    try {
      const parser = new Parser();
      const csv = parser.parse(filteredLogs);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `BioGuard_Intelligence_Log_${new Date().toISOString()}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error(err);
    }
  };

  const getSeverityConfig = (level) => {
    switch (level) {
      case 'Critical': return { bg: 'bg-rose-500', text: 'text-rose-500', light: 'bg-rose-50', border: 'border-rose-200', glow: 'shadow-rose-500/20', icon: <ShieldAlert size={18} /> };
      case 'High': return { bg: 'bg-orange-500', text: 'text-orange-500', light: 'bg-orange-50', border: 'border-orange-200', glow: 'shadow-orange-500/20', icon: <Activity size={18} /> };
      case 'Medium': return { bg: 'bg-amber-500', text: 'text-amber-500', light: 'bg-amber-50', border: 'border-amber-200', glow: 'shadow-amber-500/20', icon: <ChevronRight size={18} /> };
      default: return { bg: 'bg-blue-500', text: 'text-blue-500', light: 'bg-blue-50', border: 'border-blue-200', glow: 'shadow-blue-500/20', icon: <Database size={18} /> };
    }
  };

  return (
    <div className="p-8 lg:p-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <header className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-12 gap-8 text-left">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
            <span className="text-[11px] font-black text-blue-600 uppercase tracking-[0.2em]">Audit Intelligence</span>
          </div>
          <h1 className="text-5xl font-black text-slate-900 tracking-tight">Security <span className="text-blue-600">Logs</span></h1>
        </div>

        <div className="flex flex-wrap gap-4 w-full xl:w-auto">
          {/* Real-time Search Input */}
          <div className="relative flex-1 xl:flex-none">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              type="text" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by ID, Sector, or Keyword..." 
              className="pl-12 pr-6 py-4 bg-white border border-slate-200 rounded-2xl text-sm focus:outline-none focus:ring-4 focus:ring-blue-500/10 w-full xl:w-80 shadow-sm transition-all"
            />
          </div>
          
          {/* Export Button */}
          <button 
            onClick={handleExport}
            className="flex items-center gap-3 px-6 py-4 bg-slate-900 text-white rounded-2xl text-sm font-bold hover:bg-slate-800 transition-all shadow-xl shadow-slate-900/20"
          >
            <Download size={18} /> Export CSV
          </button>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className="flex gap-4 mb-8">
        {['All', 'Mobility', 'NLP', 'Wastewater'].map((type) => (
          <button
            key={type}
            onClick={() => setActiveFilter(type)}
            className={`px-6 py-2 rounded-xl text-xs font-black transition-all border ${
              activeFilter === type 
              ? 'bg-blue-600 text-white border-blue-600 shadow-lg shadow-blue-600/20' 
              : 'bg-white text-slate-400 border-slate-100 hover:border-slate-300'
            }`}
          >
            {type.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Main Logs Feed */}
      <div className="space-y-4">
        {filteredLogs.length > 0 ? filteredLogs.map((log) => {
          const config = getSeverityConfig(log.severity);
          return (
            <div key={log.id} className={`group relative bg-white border ${config.border} rounded-[2rem] p-6 transition-all hover:shadow-2xl flex flex-col lg:flex-row items-start lg:items-center gap-6 overflow-hidden text-left`}>
              <div className={`absolute left-0 top-0 bottom-0 w-2 ${config.bg}`} />
              <div className="min-w-[120px]">
                <p className="text-[10px] font-black text-slate-400 mb-1">{log.id}</p>
                <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
                  <Clock size={14} className="text-slate-400" /> {log.time}
                </div>
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`px-3 py-1 rounded-lg text-[10px] font-black uppercase border ${config.light} ${config.text} ${config.border}`}>
                    {log.severity}
                  </span>
                  <span className="text-[10px] font-bold text-blue-600 uppercase bg-blue-50 px-2 py-1 rounded-md">{log.sector}</span>
                </div>
                <p className="text-slate-700 font-semibold leading-relaxed">{log.msg}</p>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Confidence</p>
                  <p className="text-sm font-black text-slate-900">{log.confidence}</p>
                </div>
                <button className="h-12 w-12 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-400 hover:bg-blue-600 hover:text-white transition-all">
                  <ArrowUpRight size={20} />
                </button>
              </div>
            </div>
          );
        }) : (
          <div className="p-20 text-center bg-white rounded-[3rem] border border-dashed border-slate-200">
             <p className="text-slate-400 font-bold">No logs found matching your criteria.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AlertLogs;