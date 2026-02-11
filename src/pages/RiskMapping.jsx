import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl, useMap } from 'react-leaflet';
import { Activity, Radio, Zap, Loader2 } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

const MapController = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, 13, { duration: 2 });
  }, [center, map]);
  return null;
};

const RiskMapping = () => {
  const [riskZones, setRiskZones] = useState([]);
  const [activeZone, setActiveZone] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/risk-status');
        const data = await response.json();
        setRiskZones(data.zones);
        setActiveZone(data.zones[0]);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching map data:", error);
      }
    };
    fetchData();
  }, []);

  if (loading) return (
    <div className="h-full w-full flex items-center justify-center bg-[#020617] rounded-[2.5rem]">
      <Loader2 className="animate-spin text-blue-500" size={40} />
    </div>
  );

  return (
    <div className="h-full w-full relative flex flex-col md:flex-row overflow-hidden rounded-[2.5rem] border border-white/10 bg-[#020617] shadow-2xl">
      
      {/* 1. Tactical Sidebar */}
      <div className="w-full md:w-80 z-[1001] p-6 border-r border-white/5 bg-[#020617]/80 backdrop-blur-xl text-white flex flex-col gap-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Radio className="text-blue-400 animate-pulse" size={20} />
          </div>
          <div>
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-blue-400">Tactical Feed</h2>
            <p className="text-[9px] font-bold opacity-40 uppercase">Live AI Processing</p>
          </div>
        </div>
        
        <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar">
          {riskZones.map(zone => (
            <button 
              key={zone.id}
              onClick={() => setActiveZone(zone)}
              className={`w-full p-5 rounded-2xl border transition-all text-left relative overflow-hidden group ${
                activeZone?.id === zone.id 
                ? 'bg-blue-600/20 border-blue-500 text-white' 
                : 'bg-white/5 border-white/5 hover:border-white/20'
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className={`text-[10px] font-black uppercase tracking-widest ${activeZone?.id === zone.id ? 'text-blue-400' : 'opacity-40'}`}>
                  {zone.risk}
                </span>
                <Zap size={12} className={zone.score > 60 ? 'text-rose-500 animate-pulse' : 'text-emerald-500'} />
              </div>
              <h4 className="text-sm font-black uppercase tracking-tight">{zone.city}</h4>
              <div className="mt-3 flex items-end gap-2">
                <span className="text-2xl font-black italic">{zone.score}</span>
                <span className="text-[9px] font-bold opacity-30 uppercase mb-1.5">Risk Index</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 2. Map Interface */}
      <div className="flex-1 relative">
        <div className="absolute inset-0 z-[500] pointer-events-none overflow-hidden">
          <div className="scanner-line w-full h-[2px] bg-gradient-to-r from-transparent via-blue-500/50 to-transparent shadow-[0_0_20px_#3b82f6]" />
        </div>

        <MapContainer 
          center={activeZone?.center} 
          zoom={12} 
          zoomControl={false}
          className="h-full w-full z-0"
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <ZoomControl position="bottomright" />
          <MapController center={activeZone?.center} />

          {riskZones.map((zone) => (
            <React.Fragment key={zone.id}>
              <CircleMarker
                center={zone.center}
                radius={35}
                pathOptions={{ 
                  color: zone.color, 
                  fillColor: zone.color, 
                  fillOpacity: 0.05, 
                  weight: 1,
                  dashArray: "5, 10" 
                }}
              />
              <CircleMarker
                center={zone.center}
                radius={10}
                pathOptions={{
                  color: '#fff',
                  fillColor: zone.color,
                  fillOpacity: 1,
                  weight: 2
                }}
              >
                <Popup className="custom-map-popup">
                  <div className="p-3 min-w-[200px] font-sans">
                    <h3 className="text-sm font-black uppercase mb-1 text-slate-900">{zone.city}</h3>
                    <p className="text-[10px] text-slate-500 mb-2 uppercase font-bold">
                      Status: <span style={{color: zone.color}}>{zone.risk}</span>
                    </p>
                    <div className="border-t border-slate-100 pt-2 text-[9px] font-bold text-slate-400">
                        ANALYSIS: {zone.signal}
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            </React.Fragment>
          ))}
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