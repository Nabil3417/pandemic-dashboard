import React, { useState, useEffect } from 'react';

const DataFeed = () => {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchData = () => {
      fetch('http://localhost:5000/api/signals')
        .then(res => res.json())
        .then(setSignals)
        .catch(err => console.error(err));

      fetch('http://localhost:5000/api/db-stats')
        .then(res => res.json())
        .then(setStats)
        .catch(err => console.error(err));
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 lg:p-12 bg-[#020617] min-h-screen text-left">
      <header className="mb-12">
        <div className="flex items-center gap-3 mb-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[11px] font-black text-green-500 uppercase tracking-[0.2em]">Live Collection</span>
        </div>
        <h1 className="text-6xl font-black text-white tracking-tighter uppercase italic">
          Data <span className="text-blue-600">Feed</span>
        </h1>
      </header>

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {[
            { label: 'Total Posts', value: stats.total_posts },
            { label: 'Real Posts', value: stats.real_posts },
            { label: 'Simulated', value: stats.simulated_posts },
            { label: 'Processed', value: stats.processed_posts },
          ].map((s, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-6">
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">{s.label}</p>
              <p className="text-3xl font-black text-white">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-4">
        {signals.map((post, i) => (
          <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col lg:flex-row gap-4 items-start lg:items-center">
            <div className="min-w-[120px]">
              <span className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase ${
                post.type === 'Telegram' ? 'bg-blue-600 text-white' :
                post.type === 'Reddit' ? 'bg-orange-500 text-white' :
                'bg-slate-600 text-white'
              }`}>
                {post.type}
              </span>
            </div>
            <div className="flex-1">
              <p className="text-white font-bold text-sm leading-relaxed">{post.text}</p>
              <p className="text-slate-500 text-[10px] mt-1">{post.city} • {post.timestamp}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-black text-slate-500 uppercase">BERT Score</p>
              <p className={`text-xl font-black ${
                parseInt(post.ai_score) > 75 ? 'text-red-400' :
                parseInt(post.ai_score) > 50 ? 'text-amber-400' : 'text-green-400'
              }`}>{post.ai_score}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DataFeed;