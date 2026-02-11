import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const riskZones = [
  { 
    id: 1, 
    name: "Bashundhara R/A (NSU Sector)", 
    coords: [23.8191, 90.4526], 
    riskScore: 88, 
    status: "CRITICAL", 
    color: '#ef4444',
    metrics: { mobility: "+14%", wastewater: "High", social_sent: "Anxious", density: "8.2k/km²" }
  },
  { 
    id: 2, 
    name: "Banani / Gulshan Hub", 
    coords: [23.7940, 90.4043], 
    riskScore: 54, 
    status: "MODERATE", 
    color: '#f59e0b',
    metrics: { mobility: "-2%", wastewater: "Low", social_sent: "Neutral", density: "12.5k/km²" }
  },
  { 
    id: 3, 
    name: "Uttara Sector 4", 
    coords: [23.8759, 90.3795], 
    riskScore: 22, 
    status: "STABLE", 
    color: '#10b981',
    metrics: { mobility: "-12%", wastewater: "Trace", social_sent: "Stable", density: "6.1k/km²" }
  },
];

const RiskMap = ({ isDark }) => {
  // Use professional Dark/Light themed tiles from CartoDB
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
        
        {riskZones.map(zone => (
          <React.Fragment key={zone.id}>
            {/* Outer Radar Pulse */}
            <CircleMarker
              center={zone.coords}
              radius={28}
              pathOptions={{ 
                color: zone.color, 
                fillColor: zone.color, 
                fillOpacity: 0.05, 
                weight: 1,
                dashArray: '5, 10'
              }}
            />

            {/* Core Data Point */}
            <CircleMarker 
              center={zone.coords} 
              radius={10} 
              pathOptions={{
                color: isDark ? '#ffffff' : zone.color,
                fillColor: zone.color,
                fillOpacity: 0.9,
                weight: 2
              }}
            >
              <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                <div className="px-2 py-1 bg-slate-900 text-white rounded text-[9px] font-black uppercase">
                  {zone.status}: {zone.riskScore}%
                </div>
              </Tooltip>

              <Popup minWidth={240}>
                <div className="font-sans">
                  <div className="flex justify-between items-center border-b border-slate-100 pb-2 mb-3">
                    <div className="flex flex-col">
                      <span className="text-[9px] font-black text-slate-400 uppercase leading-none mb-1">Sector ID #00{zone.id}</span>
                      <h4 className="font-black text-slate-900 text-sm uppercase m-0 leading-tight">{zone.name}</h4>
                    </div>
                    <div className="h-8 w-8 rounded-lg flex items-center justify-center text-white font-bold text-xs" style={{backgroundColor: zone.color}}>
                      {zone.riskScore}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                      <p className="text-[8px] font-black text-slate-400 uppercase mb-0.5">Mobility</p>
                      <p className="text-[11px] font-black text-slate-900 m-0">{zone.metrics.mobility}</p>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                      <p className="text-[8px] font-black text-slate-400 uppercase mb-0.5">Sentiment</p>
                      <p className="text-[11px] font-black text-slate-900 m-0">{zone.metrics.social_sent}</p>
                    </div>
                  </div>

                  <div className="space-y-1 mb-4">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-500 font-bold uppercase">Wastewater RNA</span>
                      <span className="font-black text-slate-900">{zone.metrics.wastewater}</span>
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-500 font-bold uppercase">Density</span>
                      <span className="font-black text-slate-900">{zone.metrics.density}</span>
                    </div>
                  </div>

                  <button className="w-full py-2 bg-slate-900 hover:bg-blue-600 text-white text-[9px] font-black uppercase rounded-lg tracking-widest transition-colors">
                    Deploy Sector Report
                  </button>
                </div>
              </Popup>
            </CircleMarker>
          </React.Fragment>
        ))}
      </MapContainer>

      {/* Floating Modern Legend */}
      <div className={`absolute bottom-6 right-6 z-[1000] p-5 rounded-[2rem] border backdrop-blur-xl shadow-2xl ${isDark ? 'bg-slate-950/80 border-white/5 text-white' : 'bg-white/80 border-slate-200 text-slate-900'}`}>
        <h5 className="text-[9px] font-black uppercase tracking-[0.3em] mb-4 opacity-40">Risk Hierarchy</h5>
        <div className="space-y-3">
          {[
            { label: 'Critical Threat', color: 'bg-red-500' },
            { label: 'Moderate Watch', color: 'bg-orange-500' },
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