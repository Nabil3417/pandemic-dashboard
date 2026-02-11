import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, ZoomControl, useMap } from 'react-leaflet';
import { ShieldAlert, Activity, Globe, Zap, Radio } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

const riskZones = [
  { id: 1, center: [23.8191, 90.4526], city: "Bashundhara R/A", risk: "CRITICAL", score: 88, color: "#ef4444", trending: "up" },
  { id: 2, center: [23.7940, 90.4043], city: "Banani Hub", risk: "MODERATE", score: 54, color: "#f59e0b", trending: "stable" },
  { id: 3, center: [23.8759, 90.3795], city: "Uttara Sector 4", risk: "LOW", score: 22, color: "#10b981", trending: "down" }
];

const MapController = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, 12, { duration: 2 });
  }, [center, map]);
  return null;
};

const RiskMapping = () => {
  const [activeZone, setActiveZone] = useState(riskZones[0]);

  return (
    <div className="h-full w-full relative flex flex-col md:flex-row overflow-hidden rounded-[2.5rem] border border-white/10 bg-[#020617] shadow-2xl shadow-blue-900/20">
      
      {/* 1. Tactical Intelligence Sidebar (Fixed Dark) */}
      <div className="w-full md:w-80 z-[1001] p-6 border-r border-white/5 bg-[#020617]/80 backdrop-blur-xl text-white flex flex-col gap-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Radio className="text-blue-400 animate-pulse" size={20} />
          </div>
          <div>
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-blue-400">Tactical Feed</h2>
            <p className="text-[9px] font-bold opacity-40 uppercase">Satellite Sweep Active</p>
          </div>
        </div>
        
        <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar">
          {riskZones.map(zone => (
            <button 
              key={zone.id}
              onClick={() => setActiveZone(zone)}
              className={`w-full p-5 rounded-2xl border transition-all text-left relative overflow-hidden group ${
                activeZone.id === zone.id 
                ? 'bg-blue-600/20 border-blue-500 text-white' 
                : 'bg-white/5 border-white/5 hover:border-white/20'
              }`}
            >
              {activeZone.id === zone.id && (
                <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 shadow-[0_0_15px_#3b82f6]" />
              )}
              <div className="flex justify-between items-start mb-1">
                <span className={`text-[10px] font-black uppercase tracking-widest ${activeZone.id === zone.id ? 'text-blue-400' : 'opacity-40'}`}>
                  {zone.risk}
                </span>
                <Zap size={12} className={zone.score > 70 ? 'text-rose-500 animate-pulse' : 'text-emerald-500'} />
              </div>
              <h4 className="text-sm font-black leading-tight uppercase tracking-tight">{zone.city}</h4>
              <div className="mt-3 flex items-end gap-2">
                <span className="text-2xl font-black italic">{zone.score}</span>
                <span className="text-[9px] font-bold opacity-30 uppercase mb-1.5">Index Rating</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 2. Map Interface Section */}
      <div className="flex-1 relative">
        
        {/* SCANNER LINE ANIMATION */}
        <div className="absolute inset-0 z-[500] pointer-events-none overflow-hidden">
          <div className="scanner-line w-full h-[2px] bg-gradient-to-r from-transparent via-blue-500/50 to-transparent shadow-[0_0_20px_#3b82f6]" />
        </div>

        {/* Floating HUD */}
        <div className="absolute top-8 left-8 z-[1000] flex flex-col gap-2">
          <div className="bg-slate-900/90 backdrop-blur-xl px-4 py-2.5 rounded-xl border border-white/10 flex items-center gap-3 shadow-2xl">
            <Activity size={14} className="text-emerald-500" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white">Live Vector Stream</span>
          </div>
        </div>

        <MapContainer 
          center={activeZone.center} 
          zoom={12} 
          zoomControl={false}
          scrollWheelZoom={true}
          className="h-full w-full z-0 grayscale-[0.8] invert-[0.9] opacity-60 transition-all duration-1000 hover:opacity-100 hover:grayscale-0 hover:invert-0"
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <ZoomControl position="bottomright" />
          <MapController center={activeZone.center} />

          {riskZones.map((zone) => (
            <React.Fragment key={zone.id}>
              {/* Outer Pulse Heat-Ring */}
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
                <Popup>
                  <div className="p-3 min-w-[200px] font-sans bg-slate-950 text-white rounded-xl border border-white/10">
                    <h3 className="text-sm font-black uppercase mb-1">{zone.city}</h3>
                    <p className="text-[10px] text-slate-400 mb-4">Threat Level: <span style={{color: zone.color}} className="font-black">{zone.risk}</span></p>
                    <div className="space-y-1 border-t border-white/10 pt-3">
                      <div className="flex justify-between text-[9px] font-bold opacity-60">
                        <span>BIOSIGNAL</span>
                        <span className="text-white">STABLE</span>
                      </div>
                      <div className="flex justify-between text-[9px] font-bold opacity-60">
                        <span>CONFIDENCE</span>
                        <span className="text-white">98.4%</span>
                      </div>
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

        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 10px;
        }
      `}</style>
    </div>
  );
};

export default RiskMapping;