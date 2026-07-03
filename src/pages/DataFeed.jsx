import React, { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, Database, Clock, Zap, Filter, 
  ChevronLeft, ChevronRight, ExternalLink
} from 'lucide-react';
import { toast, Toaster } from 'react-hot-toast';

const PLATFORM_STYLES = {
  Telegram:  { bg: 'bg-blue-600',     text: 'text-white' },
  RSS_NEWS:  { bg: 'bg-amber-600',    text: 'text-white' },
  YouTube:   { bg: 'bg-red-600',      text: 'text-white' },
  Bluesky:   { bg: 'bg-sky-500',      text: 'text-white' },
  Mastodon:  { bg: 'bg-purple-600',   text: 'text-white' },
  SYSTEM:    { bg: 'bg-slate-600',    text: 'text-white' },
};

const PLATFORM_ICONS = {
  Telegram:  '📱',
  RSS_NEWS:  '📰',
  YouTube:   '▶️',
  Bluesky:   '🐦',
  Mastodon:  '🐘',
  SYSTEM:    '⚙️',
};

const DataFeed = () => {
  const [posts, setPosts] = useState([]);
  const [total, setTotal] = useState(0);
  const [collectionStatus, setCollectionStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [activePlatform, setActivePlatform] = useState('ALL');
  const [page, setPage] = useState(0);
  const [isCollecting, setIsCollecting] = useState(false);
  const limit = 30;

  const fetchPosts = useCallback(() => {
    const platform = activePlatform === 'ALL' ? '' : `&platform=${activePlatform}`;
    fetch(`http://localhost:5000/api/posts?limit=${limit}&offset=${page * limit}${platform}`)
      .then(res => res.json())
      .then(data => {
        setPosts(data.posts);
        setTotal(data.total);
      })
      .catch(err => console.error(err));
  }, [activePlatform, page]);

  const fetchStatus = useCallback(() => {
    fetch('http://localhost:5000/api/collection-status')
      .then(res => res.json())
      .then(setCollectionStatus)
      .catch(err => console.error(err));

    fetch('http://localhost:5000/api/db-stats')
      .then(res => res.json())
      .then(setStats)
      .catch(err => console.error(err));
  }, []);

  useEffect(() => {
    fetchPosts();
  }, [fetchPosts]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleTriggerCollection = async () => {
    setIsCollecting(true);
    toast('Collection started in background...', { icon: '🔄' });
    try {
      await fetch('http://localhost:5000/api/trigger-collection', { method: 'POST' });
      toast.success('Collectors running! Results in ~5 min.');
    } catch {
      toast.error('Failed to trigger collection');
    }
    // Refresh status after 10 seconds
    setTimeout(() => {
      fetchStatus();
      fetchPosts();
      setIsCollecting(false);
    }, 10000);
  };

  const handlePlatformChange = (platform) => {
    setActivePlatform(platform);
    setPage(0);
  };

  const totalPages = Math.ceil(total / limit);
  const platformList = collectionStatus?.platforms
    ? Object.entries(collectionStatus.platforms).sort((a, b) => b[1] - a[1])
    : [];

  const formatLastRun = (iso) => {
    if (!iso) return 'Never';
    const d = new Date(iso);
    return d.toLocaleString('en-US', { 
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="p-8 lg:p-12 bg-[#020617] min-h-screen text-left">
      <Toaster position="top-right" />

      {/* Header */}
      <header className="mb-10">
        <div className="flex items-center gap-3 mb-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[11px] font-black text-green-500 uppercase tracking-[0.2em]">Live Feed</span>
        </div>
        <h1 className="text-6xl font-black text-white tracking-tighter uppercase italic">
          Data <span className="text-blue-600">Feed</span>
        </h1>
      </header>

      {/* Collection Status Bar */}
      {collectionStatus && (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 mb-8">
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-slate-500" />
                <span className="text-[10px] font-black text-slate-500 uppercase">Last Run</span>
                <span className="text-sm font-bold text-white">{formatLastRun(collectionStatus.last_run)}</span>
              </div>
              <div className="flex items-center gap-2">
                <Database size={14} className="text-slate-500" />
                <span className="text-[10px] font-black text-slate-500 uppercase">Total Posts</span>
                <span className="text-sm font-bold text-white">{collectionStatus.total_posts?.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Zap size={14} className="text-amber-400" />
                <span className="text-[10px] font-black text-slate-500 uppercase">New (24h)</span>
                <span className="text-sm font-bold text-amber-400">{collectionStatus.recent_24h}</span>
              </div>
            </div>
            <button
              onClick={handleTriggerCollection}
              disabled={isCollecting}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                isCollecting
                  ? 'bg-amber-600/20 text-amber-400 border border-amber-500/30 cursor-wait'
                  : 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-900/40'
              }`}
            >
              <RefreshCw size={12} className={isCollecting ? 'animate-spin' : ''} />
              {isCollecting ? 'Collecting...' : 'Trigger Collection'}
            </button>
          </div>
        </div>
      )}

      {/* Platform Breakdown Cards */}
      {collectionStatus?.platforms && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
          {platformList.map(([name, count]) => (
            <button
              key={name}
              onClick={() => handlePlatformChange(name)}
              className={`relative p-4 rounded-xl border transition-all text-left ${
                activePlatform === name
                  ? 'bg-white/10 border-white/30 scale-[1.02]'
                  : 'bg-white/5 border-white/10 hover:bg-white/8 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-lg">{PLATFORM_ICONS[name] || '📄'}</span>
                {activePlatform === name && (
                  <Filter size={12} className="text-blue-400" />
                )}
              </div>
              <p className="text-2xl font-black text-white mt-2">{count.toLocaleString()}</p>
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
                {name === 'RSS_NEWS' ? 'RSS News' : name}
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
        <button
          onClick={() => handlePlatformChange('ALL')}
          className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${
            activePlatform === 'ALL'
              ? 'bg-white text-black'
              : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'
          }`}
        >
          All Platforms ({collectionStatus?.total_posts || 0})
        </button>
        {Object.keys(PLATFORM_STYLES).filter(p => p !== 'SYSTEM').map(p => {
          const count = collectionStatus?.platforms?.[p] || 0;
          if (count === 0) return null;
          return (
            <button
              key={p}
              onClick={() => handlePlatformChange(p)}
              className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all whitespace-nowrap ${
                activePlatform === p
                  ? `${PLATFORM_STYLES[p].bg} ${PLATFORM_STYLES[p].text}`
                  : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'
              }`}
            >
              {p === 'RSS_NEWS' ? 'RSS' : p} ({count})
            </button>
          );
        })}
      </div>

      {/* Posts List */}
      <div className="space-y-3">
        {posts.map((post) => {
          const style = PLATFORM_STYLES[post.platform] || PLATFORM_STYLES.SYSTEM;
          const icon = PLATFORM_ICONS[post.platform] || '📄';
          const displayName = post.platform === 'RSS_NEWS' ? 'RSS' : post.platform;
          const scoreColor = post.bert_score
            ? (post.bert_score > 75 ? 'text-red-400' : post.bert_score > 50 ? 'text-amber-400' : 'text-green-400')
            : 'text-slate-600';

          return (
            <div key={post.id} className="bg-white/5 border border-white/10 rounded-2xl p-5 flex flex-col lg:flex-row gap-4 items-start lg:items-center hover:bg-white/8 transition-all">
              {/* Platform Badge */}
              <div className="min-w-[100px] flex items-center gap-2">
                <span className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase ${style.bg} ${style.text} flex items-center gap-1.5`}>
                  <span>{icon}</span> {displayName}
                </span>
              </div>

              {/* Post Content */}
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm leading-relaxed">{post.text}</p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-slate-500 text-[10px]">{post.location_name || `Zone ${post.zone_id}`}</span>
                  <span className="text-slate-700">•</span>
                  <span className="text-slate-500 text-[10px]">{post.channel}</span>
                  <span className="text-slate-700">•</span>
                  <span className="text-slate-500 text-[10px]">{post.timestamp}</span>
                </div>
              </div>

              {/* Score + Link */}
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <p className="text-[9px] font-black text-slate-600 uppercase">Risk Score</p>
                  <p className={`text-lg font-black ${scoreColor}`}>
                    {post.bert_score ? `${post.bert_score}` : '—'}
                  </p>
                </div>
                {post.source_url && (
                  <a
                    href={post.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-600 hover:text-blue-400 transition-colors"
                  >
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 text-[10px] font-black uppercase tracking-widest hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={12} /> Previous
          </button>
          <span className="text-slate-500 text-xs font-bold">
            Page {page + 1} of {totalPages} ({total} posts)
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 text-[10px] font-black uppercase tracking-widest hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next <ChevronRight size={12} />
          </button>
        </div>
      )}
    </div>
  );
};

export default DataFeed;