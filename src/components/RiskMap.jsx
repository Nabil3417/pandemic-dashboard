import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';


const RiskMap = ({ isDark }) => {
  const [zones, setZones] = useState([]);
  const [geoData, setGeoData] = useState(null);
  const [mobilityData, setMobilityData] = useState({});

  useEffect(() => {
    fetch('http://localhost:5000/api/risk-status')
      .then(res => res.json())
      .then(data => setZones(data.zones || []))
      .catch(err => console.error(err));

    fetch('http://localhost:5000/api/mobility')
      .then(res => res.json())
      .then(data => {
        if (data.success && data.data) {
          const map = {};
          (data.data.zones || []).forEach(z => {
            map[z.zone_id] = z;
          });
          setMobilityData(map);
        }
      })
      .catch(err => console.error('W-DZMI fetch failed:', err));

    fetch('/dhaka_zones.geojson')
      .then(res => res.json())
      .then(data => setGeoData(data))
      .catch(err => console.error(err));
  }, []);

  const getRiskColor = (score) => {
    if (score >= 75) return '#ef4444';
    if (score >= 55) return '#f97316';
    if (score >= 35) return '#f59e0b';
    if (score >= 20) return '#10b981';
    return '#6366f1';
  };

  const getTopFactor = (zone) => {
    if (!zone) return 'Baseline Activity';
    if (zone.score > 70) return 'Critical: Multi-signal Alert';
    if (zone.score > 40) return 'Elevated Wastewater / Mobility';
    return 'Baseline Activity';
  };

  const styleFeature = (feature) => {
    const zoneName = feature.properties.name;
    const matchedZone = zones.find(z =>
      z.city.toLowerCase().includes(zoneName.toLowerCase()) ||
      zoneName.toLowerCase().includes(z.city.toLowerCase().split(' ')[0])
    );
    const score = matchedZone ? matchedZone.score : feature.properties.risk_index || 20;
    const color = getRiskColor(score);

    return {
      fillColor: color,
      fillOpacity: 0.5,
      color: color,
      weight: 2,
      opacity: 0.8,
    };
  };

  const onEachFeature = (feature, layer) => {
    const zoneName = feature.properties.name;
    const matchedZone = zones.find(z =>
      z.city.toLowerCase().includes(zoneName.toLowerCase()) ||
      zoneName.toLowerCase().includes(z.city.toLowerCase().split(' ')[0])
    );
    const score = matchedZone ? matchedZone.score : feature.properties.risk_index || 20;
    const risk = matchedZone ? matchedZone.risk : feature.properties.risk_level || 'LOW';
    const topFactor = getTopFactor(matchedZone);
    const wdzmi = mobilityData[matchedZone?.id] || null;

    let signalRows = '';
    if (wdzmi && wdzmi.signal_breakdown) {
      const signals = wdzmi.signal_breakdown;
      signalRows = `
        <div style="border-top:1px solid #334155;margin-top:6px;padding-top:6px">
          <div style="font-size:8px;color:#94a3b8;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">W-DZMI Signal Breakdown</div>
          ${Object.entries(signals).map(([key, sig]) => {
            if (!sig) return '';
            const barWidth = Math.min(sig.contribution, 40);
            const barColor = sig.contribution > 15 ? '#f59e0b' : sig.contribution > 8 ? '#3b82f6' : '#64748b';
            return `<div style="display:flex;align-items:center;gap:4px;margin:2px 0">
              <span style="font-size:9px;color:#94a3b8;width:70px">${key}</span>
              <div style="width:40px;height:4px;background:#1e293b;border-radius:2px;overflow:hidden">
                <div style="width:${barWidth}px;height:100%;background:${barColor};border-radius:2px"></div>
              </div>
              <span style="font-size:9px;color:#e2e8f0;font-weight:700">${sig.contribution}</span>
            </div>`;
          }).join('')}
        </div>
      `;
    }

    const wdzmiRow = wdzmi
      ? `<div style="font-size:10px;color:#64748b;text-transform:uppercase">W-DZMI: <b style="color:${getRiskColor(wdzmi.wdzmi_score)}">${wdzmi.wdzmi_score}</b> <span style="font-size:8px;opacity:0.6">(${wdzmi.trend}, ${wdzmi.num_signals}/4 signals)</span></div>`
      : '';

    layer.bindTooltip(`
      <div style="font-family:sans-serif;padding:10px;min-width:200px;max-width:260px;background:#0f172a;border-radius:12px;border:1px solid #1e293b">
        <div style="font-weight:900;font-size:12px;text-transform:uppercase;margin-bottom:6px;color:#f1f5f9">${zoneName}</div>
        <div style="font-size:10px;color:#64748b;text-transform:uppercase">Fused Risk: <b style="color:${getRiskColor(score)}">${score}</b> &middot; ${risk}</div>
        ${wdzmiRow}
        <div style="font-size:9px;color:#475569;margin-top:4px">${topFactor}</div>
        ${signalRows}
      </div>
    `, {
      sticky: true,
      className: 'bioguard-tooltip',
      direction: 'top',
      offset: [0, -10],
    });

    layer.on({
      mouseover: (e) => {
        e.target.setStyle({ fillOpacity: 0.8, weight: 3 });
      },
      mouseout: (e) => {
        e.target.setStyle({ fillOpacity: 0.5, weight: 2 });
      }
    });
  };

  const mapStyle = isDark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  return (
    <div className="h-full w-full relative">
      <MapContainer
        center={[23.8103, 90.4125]}
        zoom={12}
        scrollWheelZoom={true}
        className="h-full w-full outline-none"
        zoomControl={false}
      >
        <TileLayer url={mapStyle} attribution='&copy; CARTO' />
        <ZoomControl position="topright" />

        {geoData && (
          <GeoJSON
            key={zones.length}
            data={geoData}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />
        )}
      </MapContainer>

      <div className={`absolute bottom-6 right-6 z-[1000] p-5 rounded-[2rem] border backdrop-blur-xl shadow-2xl ${isDark ? 'bg-slate-950/80 border-white/5 text-white' : 'bg-white/80 border-slate-200 text-slate-900'}`}>
        <h5 className="text-[9px] font-black uppercase tracking-[0.3em] mb-4 opacity-40">Risk Hierarchy</h5>
        <div className="space-y-3">
          {[
            { label: 'Critical (>=75)', color: 'bg-red-500' },
            { label: 'High (55-74)', color: 'bg-orange-500' },
            { label: 'Moderate (35-54)', color: 'bg-amber-500' },
            { label: 'Low (20-34)', color: 'bg-emerald-500' },
            { label: 'Minimal (<20)', color: 'bg-indigo-500' }
          ].map((item, idx) => (
            <div key={idx} className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${item.color}`} />
              <span className="text-[10px] font-black uppercase tracking-tighter">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default RiskMap;