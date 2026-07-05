import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl, useMap, GeoJSON } from 'react-leaflet';
import { Radio, Zap, Loader2, TrendingUp, TrendingDown, Minus, X, ChevronRight } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import MobilityBreakdown from '../components/MobilityBreakdown';
import MobilityTrend from '../components/MobilityTrend';
import MobilityRankings from '../components/MobilityRankings';

const MapController = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, 13, { duration: 2 });
  }, [center, map]);
  return null;
};

const SIGNAL_COLORS = {
  google_mobility: '#3b82f6',
  social_volume: '#f43f5e',
  osrm_routing: '#f59e0b',
  google_trends: '#8b5cf6',
};

const RISK_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  moderate: '#f59e0b',
  low: '#22c55e',
  minimal: '#6366f1',
};

const getWdzmiColor = (score) => {
  if (score >= 75) return '#ef4444';
  if (score >= 55) return '#f97316';
  if (score >= 35) return '#f59e0b';
  if (score >= 20) return '#22c55e';
  return '#6366f1';
};

const PopupContent = ({ zone, wdzmi }) => {
  if (!wdzmi) {
    return (
      <div style={{ fontFamily: 'system-ui', padding: 12, minWidth: 200 }}>
        <h3 style={{ fontSize: 13, fontWeight: 900, textTransform: 'uppercase', margin: '0 0 4px', color: '#1e293b' }}>{zone.city}</h3>
        <p style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 700, margin: 0 }}>
          Status: <span style={{ color: zone.color }}>{zone.risk}</span>
        </p>
      </div>
    );
  }

  const signals = wdzmi.signal_breakdown || {};
  const signalEntries = Object.entries(signals).filter(([, s]) => s && s.score !== undefined);
  const riskColor = RISK_COLORS[wdzmi.risk_level] || '#64748b';

  const topSignal = [...signalEntries].sort((a, b) => b[1].score - a[1].score)[0];
  const topLabel = topSignal ? topSignal[0].replace(/_/g, ' ') : 'unknown';
  const topScore = topSignal ? topSignal[1].score : 0;
  const isHigh = wdzmi.wdzmi_score >= 55;

  let assessmentText = '';
  if (isHigh && topScore > 70) {
    assessmentText = `${topLabel.charAt(0).toUpperCase() + topLabel.slice(1)} signal is elevated at ${topScore} — primary risk driver for this zone. Combined W-DZMI composite indicates elevated epidemic risk requiring monitoring.`;
  } else if (isHigh) {
    assessmentText = `Multiple signals contributing to elevated risk. W-DZMI composite score of ${wdzmi.wdzmi_score} suggests increased population mobility patterns in this zone.`;
  } else {
    assessmentText = `All signals within normal range. W-DZMI composite of ${wdzmi.wdzmi_score} indicates baseline activity. No immediate concern.`;
  }

  return (
    <div style={{ fontFamily: 'system-ui', padding: 14, minWidth: 260, maxWidth: 300, background: '#0f172a', borderRadius: 12, border: `1px solid ${riskColor}33`, color: '#e2e8f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <h3 style={{ fontSize: 12, fontWeight: 900, textTransform: 'uppercase', margin: 0, color: '#f1f5f9', letterSpacing: '0.05em' }}>
            {zone.city}
          </h3>
          <span style={{ fontSize: 8, color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>
            Zone {zone.id} | Dhaka, Bangladesh
          </span>
        </div>
        <span style={{
          fontSize: 8, fontWeight: 900, textTransform: 'uppercase',
          padding: '2px 8px', borderRadius: 6,
          background: `${riskColor}22`, color: riskColor,
          border: `1px solid ${riskColor}44`
        }}>
          {wdzmi.risk_level?.toUpperCase()}
        </span>
      </div>

      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontSize: 8, fontWeight: 800, textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.1em' }}>Composite Risk</span>
          <span style={{ fontSize: 10, fontWeight: 900, color: riskColor }}>{zone.score}</span>
        </div>
        <div style={{ height: 6, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${Math.min(zone.score, 100)}%`, height: '100%', background: `linear-gradient(90deg, ${riskColor}88, ${riskColor})`, borderRadius: 3, transition: 'width 0.5s' }} />
        </div>
      </div>

      <div style={{ borderTop: '1px solid #1e293b', paddingTop: 8, marginBottom: 8 }}>
        <div style={{ fontSize: 8, fontWeight: 800, textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.1em', marginBottom: 6 }}>
          Signal Decomposition
        </div>
        {signalEntries.map(([key, sig]) => {
          const color = SIGNAL_COLORS[key] || '#64748b';
          const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const isSpike = sig.score >= 75;
          return (
            <div key={key} style={{ marginBottom: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 5, height: 5, borderRadius: '50%', background: color }} />
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#cbd5e1' }}>{label}</span>
                  {isSpike && <span style={{ fontSize: 7, fontWeight: 900, color: '#f43f5e' }}>← SPIKE</span>}
                </div>
                <span style={{ fontSize: 9, fontWeight: 900, color }}>{sig.score}</span>
              </div>
              <div style={{ height: 3, background: '#1e293b', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(sig.score, 100)}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.5s' }} />
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ background: '#1e293b', borderRadius: 6, padding: '6px 8px', marginBottom: 8 }}>
        <div style={{ fontSize: 7, fontWeight: 800, textTransform: 'uppercase', color: '#64748b', letterSpacing: '0.1em', marginBottom: 3 }}>Fusion Formula</div>
        <div style={{ fontSize: 8, color: '#94a3b8', fontFamily: 'monospace' }}>
          NLP × 0.25 + Wastewater × 0.40 + W-DZMI × 0.35 = <span style={{ color: riskColor, fontWeight: 900 }}>{zone.score}</span>
        </div>
      </div>

      <MobilityTrend zoneId={zone.id} height={40} showLabels={false} />

      <div style={{ borderTop: '1px solid #1e293b', paddingTop: 8, marginTop: 8 }}>
        <div style={{ fontSize: 8, fontWeight: 800, textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.1em', marginBottom: 4 }}>
          AI Assessment
        </div>
        <p style={{ fontSize: 8, color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
          {assessmentText}
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, paddingTop: 6, borderTop: '1px solid #1e293b' }}>
        <span style={{ fontSize: 7, color: '#475569', fontWeight: 700 }}>Confidence: {wdzmi.confidence?.toFixed(0)}%</span>
        <span style={{ fontSize: 7, color: '#475569', fontWeight: 700 }}>Signals: {wdzmi.num_signals}/4</span>
      </div>
    </div>
  );
};

const ZoneDetailPanel = ({ zone, wdzmi, onClose }) => {
  if (!zone) return null;

  const signals = wdzmi?.signal_breakdown || {};
  const signalEntries = Object.entries(signals).filter(([, s]) => s && s.score !== undefined);
  const riskColor = wdzmi ? (RISK_COLORS[wdzmi.risk_level] || '#64748b') : '#64748b';

  const topSignal = [...signalEntries].sort((a, b) => b[1].score - a[1].score)[0];
  const topLabel = topSignal ? topSignal[0].replace(/_/g, ' ') : 'unknown';
  const topScore = topSignal ? topSignal[1].score : 0;

  let assessmentText = '';
  if (wdzmi) {
    if (wdzmi.wdzmi_score >= 55 && topScore > 70) {
      assessmentText = `${topLabel.charAt(0).toUpperCase() + topLabel.slice(1)} signal is elevated at ${topScore} — the primary risk driver for this zone. Social media activity and mobility patterns suggest increased population interaction, which combined with health signal data elevates the composite risk. This zone requires close monitoring and potential public health intervention.`;
    } else if (wdzmi.wdzmi_score >= 55) {
      assessmentText = `Multiple signals are contributing to moderately elevated risk. While no single signal has spiked, the combined W-DZMI composite of ${wdzmi.wdzmi_score} suggests shifting mobility patterns that warrant continued surveillance. Cross-referencing with NLP health signals and wastewater data recommended.`;
    } else {
      assessmentText = `All mobility signals are within normal operating range. The W-DZMI composite of ${wdzmi.wdzmi_score} indicates stable baseline population movement. No immediate public health concern detected from mobility data alone. Continue routine monitoring.`;
    }
  }

  const getTrendIcon = (trend) => {
    if (trend === 'rising') return <TrendingUp size={12} className="text-rose-400" />;
    if (trend === 'falling') return <TrendingDown size={12} className="text-emerald-400" />;
    return <Minus size={12} className="text-blue-400" />;
  };

  return (
    <div className="absolute top-4 right-4 z-[1000] w-[320px] max-h-[calc(100%-32px)] overflow-y-auto custom-scrollbar">
      <div className="bg-[#0f172a]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        <div className="p-4 border-b border-white/5">
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span style={{
                  fontSize: 8, fontWeight: 900, textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: 6,
                  background: `${riskColor}22`, color: riskColor,
                  border: `1px solid ${riskColor}44`
                }}>
                  {wdzmi?.risk_level?.toUpperCase() || zone.risk}
                </span>
                <span className="text-[8px] font-bold text-slate-600 uppercase">Zone {zone.id}</span>
              </div>
              <h3 className="text-sm font-black uppercase tracking-tight text-white">
                {zone.city}
              </h3>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-slate-500 hover:text-white"
            >
              <X size={14} />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2 mt-3">
            <div className="bg-white/5 rounded-xl p-2.5 text-center">
              <div className="text-[7px] font-black uppercase tracking-widest text-slate-500 mb-1">Risk Index</div>
              <div className="text-lg font-black text-white">{zone.score}</div>
            </div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center">
              <div className="text-[7px] font-black uppercase tracking-widest text-slate-500 mb-1">W-DZMI</div>
              <div className="text-lg font-black" style={{ color: wdzmi ? getWdzmiColor(wdzmi.wdzmi_score) : '#64748b' }}>
                {wdzmi?.wdzmi_score || '—'}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-2.5 text-center">
              <div className="text-[7px] font-black uppercase tracking-widest text-slate-500 mb-1">Confidence</div>
              <div className="text-lg font-black text-white">{wdzmi ? `${wdzmi.confidence.toFixed(0)}%` : '—'}</div>
            </div>
          </div>

          {wdzmi && (
            <div className="flex items-center justify-between mt-3 px-1">
              <div className="flex items-center gap-2">
                {getTrendIcon(wdzmi.trend)}
                <span className="text-[9px] font-black uppercase text-slate-300">{wdzmi.trend}</span>
              </div>
              <span className="text-[8px] font-bold text-slate-600">
                {wdzmi.num_signals}/4 signals active
              </span>
            </div>
          )}
        </div>

        {wdzmi && (
          <div className="p-4 border-b border-white/5">
            <div className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-500 mb-3">
              Signal Decomposition
            </div>
            <MobilityBreakdown signals={signals} />
          </div>
        )}

        <div className="px-4 pt-3 pb-2 border-b border-white/5">
          <div className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">
            Fusion Formula
          </div>
          <div className="bg-white/5 rounded-xl p-3">
            <div className="grid grid-cols-3 gap-2 mb-2">
              <div className="text-center">
                <div className="text-[7px] font-bold text-blue-400 uppercase">NLP</div>
                <div className="text-[10px] font-black text-slate-300">× 0.25</div>
              </div>
              <div className="text-center">
                <div className="text-[7px] font-bold text-emerald-400 uppercase">Wastewater</div>
                <div className="text-[10px] font-black text-slate-300">× 0.40</div>
              </div>
              <div className="text-center">
                <div className="text-[7px] font-bold text-amber-400 uppercase">W-DZMI</div>
                <div className="text-[10px] font-black text-slate-300">× 0.35</div>
              </div>
            </div>
            <div className="text-center pt-2 border-t border-white/5">
              <span className="text-[9px] font-black" style={{ color: riskColor }}>
                = {zone.score} / 100
              </span>
            </div>
          </div>
        </div>

        <div className="p-4 border-b border-white/5">
          <MobilityTrend zoneId={zone.id} height={80} showLabels={true} />
        </div>

        <div className="p-4">
          <div className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2">
            AI Assessment
          </div>
          <p className="text-[10px] text-slate-400 leading-relaxed">
            {assessmentText || 'Select a zone to view AI assessment.'}
          </p>
        </div>
      </div>
    </div>
  );
};

const RiskMapping = () => {
  const [riskZones, setRiskZones] = useState([]);
  const [wdzmiData, setWdzmiData] = useState({});
  const [activeZone, setActiveZone] = useState(null);
  const [selectedZone, setSelectedZone] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState(null);
  const [geoData, setGeoData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [riskRes, mobilityRes] = await Promise.all([
          fetch('http://localhost:5000/api/risk-status'),
          fetch('http://localhost:5000/api/mobility'),
        ]);

        const riskData = await riskRes.json();
        const mobilityData = await mobilityRes.json();

        setRiskZones(riskData.zones);

        if (mobilityData.success && mobilityData.data?.zones) {
          const zoneMap = {};
          mobilityData.data.zones.forEach(z => {
            zoneMap[z.zone_id] = z;
          });
          setWdzmiData(zoneMap);
          if (mobilityData.data.last_updated) {
            setLastSync(mobilityData.data.last_updated);
          }
        }

        if (riskData.zones.length > 0) {
          setActiveZone(riskData.zones[0]);
        }
        setLoading(false);
      } catch (error) {
        console.error("Error fetching map data:", error);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    fetch('/dhaka_zones.geojson')
      .then(res => res.json())
      .then(data => setGeoData(data))
      .catch(err => console.error("Error fetching GeoJSON:", err));
  }, []);

  const geoNameToZoneId = useMemo(() => {
    const lookup = {};
    riskZones.forEach(z => {
      lookup[z.city.toLowerCase()] = z.id;
      const firstWord = z.city.split(' ')[0].toLowerCase();
      if (!lookup[firstWord]) lookup[firstWord] = z.id;
    });
    return lookup;
  }, [riskZones]);

  const getTrendIcon = (trend) => {
    if (trend === 'rising') return <TrendingUp size={11} className="text-rose-400" />;
    if (trend === 'falling') return <TrendingDown size={11} className="text-emerald-400" />;
    return <Minus size={11} className="text-blue-400" />;
  };

  const geoStyle = (feature) => {
    const name = (feature.properties?.name || '').toLowerCase();
    let zoneId = geoNameToZoneId[name];

    if (!zoneId) {
      for (const [key, id] of Object.entries(geoNameToZoneId)) {
        if (name.includes(key) || key.includes(name)) {
          zoneId = id;
          break;
        }
      }
    }

    const wdzmi = zoneId ? wdzmiData[zoneId] : null;
    const score = wdzmi ? wdzmi.wdzmi_score : feature.properties?.risk_index || 20;
    const color = getWdzmiColor(score);

    return {
      fillColor: color,
      fillOpacity: 0.35,
      color: color,
      weight: 1.5,
      dashArray: '4, 6',
    };
  };

  if (loading) return (
    <div className="h-full w-full flex items-center justify-center bg-[#020617] rounded-[2.5rem]">
      <Loader2 className="animate-spin text-blue-500" size={40} />
    </div>
  );

  const formatTime = (ts) => {
    if (!ts) return '2 min ago';
    try {
      const d = new Date(ts);
      const now = new Date();
      const diffSec = Math.floor((now - d) / 1000);
      if (diffSec < 60) return `${diffSec}s ago`;
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
      return `${Math.floor(diffSec / 3600)}h ago`;
    } catch {
      return 'synced';
    }
  };

  return (
    <div className="h-full w-full relative flex flex-col md:flex-row overflow-hidden rounded-[2.5rem] border border-white/10 bg-[#020617] shadow-2xl">
      
      <div className="w-full md:w-80 z-[1001] p-6 border-r border-white/5 bg-[#020617]/80 backdrop-blur-xl text-white flex flex-col gap-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Radio className="text-blue-400 animate-pulse" size={20} />
            </div>
            <div>
              <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-blue-400">Tactical Feed</h2>
              <p className="text-[9px] font-bold opacity-40 uppercase">Live AI Processing | W-DZMI Active</p>
            </div>
          </div>
        </div>

        <div className="text-[8px] font-bold text-slate-600 uppercase tracking-widest text-right -mt-2">
          Last sync: {formatTime(lastSync)}
        </div>
        
        <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar">
          {riskZones.map(zone => {
            const wdzmi = wdzmiData[zone.id];
            const signals = wdzmi?.signal_breakdown || null;
            const isActive = activeZone?.id === zone.id;

            return (
              <button 
                key={zone.id}
                onClick={() => {
                  setActiveZone(zone);
                  setSelectedZone(zone);
                }}
                className={`w-full p-4 rounded-2xl border transition-all text-left relative overflow-hidden group ${
                  isActive 
                    ? 'bg-blue-600/20 border-blue-500 text-white' 
                    : 'bg-white/5 border-white/5 hover:border-white/20'
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className={`text-[10px] font-black uppercase tracking-widest ${isActive ? 'text-blue-400' : 'opacity-40'}`}>
                    {zone.risk}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {wdzmi && (
                      <span className="text-[7px] font-black uppercase px-1.5 py-0.5 rounded border"
                        style={{
                          color: getWdzmiColor(wdzmi.wdzmi_score),
                          borderColor: `${getWdzmiColor(wdzmi.wdzmi_score)}44`,
                          background: `${getWdzmiColor(wdzmi.wdzmi_score)}15`
                        }}>
                        {wdzmi.risk_level?.slice(0, 4)}
                      </span>
                    )}
                    <Zap size={12} className={zone.score > 60 ? 'text-rose-500 animate-pulse' : 'text-emerald-500'} />
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-black uppercase tracking-tight">{zone.city}</h4>
                  <ChevronRight size={14} className="text-slate-700 group-hover:text-slate-400 transition-colors" />
                </div>

                <div className="mt-2 flex items-end gap-2">
                  <span className="text-2xl font-black italic">{zone.score}</span>
                  <span className="text-[9px] font-bold opacity-30 uppercase mb-1.5">Risk</span>
                  {wdzmi && (
                    <span className="text-[9px] font-black uppercase mb-1.5 ml-auto" style={{ color: getWdzmiColor(wdzmi.wdzmi_score) }}>
                      W-DZMI {wdzmi.wdzmi_score}
                    </span>
                  )}
                </div>

                {isActive && signals && (
                  <div className="mt-3 pt-3 border-t border-white/5">
                    <div className="text-[8px] font-black uppercase tracking-widest text-slate-500 mb-2">
                      Mobility Breakdown
                    </div>
                    <MobilityBreakdown signals={signals} compact />
                  </div>
                )}

                {isActive && wdzmi && (
                  <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      {getTrendIcon(wdzmi.trend)}
                      <span className="text-[8px] font-black uppercase">
                        {wdzmi.trend}
                      </span>
                    </div>
                    <span className="text-[8px] font-bold text-slate-500">
                      {wdzmi.confidence.toFixed(0)}% ({wdzmi.num_signals}/4 signals)
                    </span>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 relative">
        <div className="absolute inset-0 z-[500] pointer-events-none overflow-hidden">
          <div className="scanner-line w-full h-[2px] bg-gradient-to-r from-transparent via-blue-500/50 to-transparent shadow-[0_0_20px_#3b82f6]" />
        </div>

        <MobilityRankings onZoneClick={(z) => {
          const match = riskZones.find(rz => rz.id === z.zone_id);
          if (match) {
            setActiveZone(match);
            setSelectedZone(match);
          }
        }} />

        {selectedZone && (
          <ZoneDetailPanel
            zone={selectedZone}
            wdzmi={wdzmiData[selectedZone.id]}
            onClose={() => setSelectedZone(null)}
          />
        )}

        <MapContainer 
          center={activeZone?.center} 
          zoom={12} 
          zoomControl={false}
          className="h-full w-full z-0"
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <ZoomControl position="bottomright" />
          <MapController center={activeZone?.center} />

          {geoData && (
            <GeoJSON 
              key={JSON.stringify(wdzmiData)}
              data={geoData} 
              style={geoStyle}
            />
          )}

          {riskZones.map((zone) => {
            const wdzmi = wdzmiData[zone.id] || null;
            const markerColor = wdzmi ? getWdzmiColor(wdzmi.wdzmi_score) : zone.color;
            return (
              <CircleMarker
                key={zone.id}
                center={zone.center}
                radius={10}
                pathOptions={{
                  color: '#fff',
                  fillColor: markerColor,
                  fillOpacity: 1,
                  weight: 2
                }}
              >
                <Popup className="custom-map-popup" maxWidth={320} minWidth={260}>
                  <PopupContent zone={zone} wdzmi={wdzmi} />
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      <style jsx>{`
        .scanner-line {
          position: absolute;
          top: -10%;
          animation: scan 4s linear infinite;
        }
        @keyframes scan {
          0% { top: -10%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 110%; opacity: 0; }
        }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
      `}</style>
    </div>
  );
};

export default RiskMapping;