import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const MobilityTrend = ({ zoneId, height = 60, showLabels = true }) => {
  const [history, setHistory] = useState([]);
  const [trend, setTrend] = useState('stable');

  useEffect(() => {
    if (!zoneId) return;
    fetch(`http://localhost:5000/api/mobility/history/${zoneId}?days=7`)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.data) {
          const h = data.data.history || [];
          setHistory(h);
          // Derive trend from first vs last
          if (h.length >= 2) {
            const first = h[0].wdzmi_score;
            const last = h[h.length - 1].wdzmi_score;
            if (last - first > 5) setTrend('rising');
            else if (first - last > 5) setTrend('falling');
            else setTrend('stable');
          }
        }
      })
      .catch(() => {});
  }, [zoneId]);

  if (history.length < 2) {
    return (
      <div className="flex items-center justify-center text-slate-600 text-[9px] font-bold uppercase tracking-widest"
        style={{ height }}>
        Awaiting data...
      </div>
    );
  }

  const scores = history.map(h => h.wdzmi_score);
  const min = Math.min(...scores) - 5;
  const max = Math.max(...scores) + 5;
  const range = max - min || 1;

  const points = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * 100;
    const y = 100 - ((s - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  // Area fill
  const areaPoints = `0,100 ${points} 100,100`;

  const strokeColor = trend === 'rising' ? '#f43f5e' : trend === 'falling' ? '#10b981' : '#3b82f6';
  const fillColor = trend === 'rising' ? '#f43f5e' : trend === 'falling' ? '#10b981' : '#3b82f6';

  const TrendIcon = trend === 'rising' ? TrendingUp : trend === 'falling' ? TrendingDown : Minus;
  const trendColor = trend === 'rising' ? 'text-rose-400' : trend === 'falling' ? 'text-emerald-400' : 'text-blue-400';

  return (
    <div>
      {showLabels && (
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[8px] font-black uppercase tracking-widest text-slate-500">
            W-DZMI Trend (7d)
          </span>
          <div className="flex items-center gap-1">
            <TrendIcon size={10} className={trendColor} />
            <span className={`text-[8px] font-black uppercase ${trendColor}`}>
              {trend}
            </span>
          </div>
        </div>
      )}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ height, width: '100%' }}>
        <defs>
          <linearGradient id={`trend-grad-${zoneId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor} stopOpacity={0.3} />
            <stop offset="100%" stopColor={fillColor} stopOpacity={0} />
          </linearGradient>
        </defs>
        <polygon
          points={areaPoints}
          fill={`url(#trend-grad-${zoneId})`}
        />
        <polyline
          points={points}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Current point dot */}
        {scores.length > 0 && (
          <circle
            cx={100}
            cy={100 - ((scores[scores.length - 1] - min) / range) * 100}
            r="2.5"
            fill={strokeColor}
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      {showLabels && (
        <div className="flex justify-between mt-1">
          <span className="text-[7px] text-slate-600 font-bold">
            {history[0]?.timestamp ? new Date(history[0].timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
          </span>
          <span className="text-[7px] text-slate-600 font-bold">
            {scores[scores.length - 1]}
          </span>
        </div>
      )}
    </div>
  );
};

export default MobilityTrend;