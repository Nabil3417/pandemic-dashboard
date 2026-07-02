import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';


const RiskMap = ({ isDark }) => {
 const [zones, setZones] = useState([]);
 const [geoData, setGeoData] = useState(null);

 useEffect(() => {
    fetch('http://localhost:5000/api/risk-status')
      .then(res => res.json())
      .then(data => setZones(data.zones || []))
      .catch(err => console.error(err));

    fetch('/dhaka_zones.geojson')
      .then(res => res.json())
      .then(data => setGeoData(data))
      .catch(err => console.error(err));
  }, []);

  const getRiskColor = (score) => {
    if (score > 70) return '#ef4444';
    if (score >= 40) return '#f59e0b';
    return '#10b981';
  };

  const getTopFactor = (zone) => {
    if (!zone) return 'N/A';
    if (zone.score > 70) return 'Critical NLP Signal';
    if (zone.score > 40) return 'Elevated Wastewater';
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

    layer.bindTooltip(`
      <div style="font-family:sans-serif;padding:8px;min-width:160px">
        <div style="font-weight:900;font-size:11px;text-transform:uppercase;margin-bottom:4px">${zoneName}</div>
        <div style="font-size:10px;color:#64748b;text-transform:uppercase">Risk Score: <b style="color:${getRiskColor(score)}">${score}</b></div>
        <div style="font-size:10px;color:#64748b;text-transform:uppercase">Status: <b>${risk}</b></div>
        <div style="font-size:10px;color:#64748b;text-transform:uppercase">Factor: <b>${topFactor}</b></div>
      </div>
    `, { sticky: true });

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

      {/* Legend */}
      <div className={`absolute bottom-6 right-6 z-[1000] p-5 rounded-[2rem] border backdrop-blur-xl shadow-2xl ${isDark ? 'bg-slate-950/80 border-white/5 text-white' : 'bg-white/80 border-slate-200 text-slate-900'}`}>
        <h5 className="text-[9px] font-black uppercase tracking-[0.3em] mb-4 opacity-40">Risk Hierarchy</h5>
        <div className="space-y-3">
          {[
            { label: 'Critical Threat', color: 'bg-red-500' },
            { label: 'Moderate Watch', color: 'bg-amber-500' },
            { label: 'Baseline Signal', color: 'bg-emerald-500' }
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