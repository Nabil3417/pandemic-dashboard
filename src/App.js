import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import RiskMapping from './pages/RiskMapping';
import DataModalities from './pages/DataModalities';
import AlertLogs from './pages/AlertLogs';
import SignalIntelligence from './pages/SignalIntelligence';
import PredictiveEngine from './pages/PredictiveEngine';

const PageLoader = () => (
  <div className="h-full w-full flex items-center justify-center bg-[#020617]">
    <div className="flex flex-col items-center gap-3">
      <div className="h-10 w-10 border-4 border-blue-600/20 border-t-blue-600 rounded-full animate-spin"></div>
      <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Neural Link Established...</p>
    </div>
  </div>
);

function App() {
  return (
    <Router>
      <div className="flex h-screen w-full bg-[#020617] font-sans antialiased overflow-hidden">
        <Toaster position="top-right" />
        <Sidebar />
        
        <main className="flex-1 h-full overflow-hidden bg-[#020617] relative border-l border-white/5">
          {/* Background Ambient FX */}
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-600/5 blur-[150px] rounded-full -z-10" />
          
          <Suspense fallback={<PageLoader />}>
            <div className="h-full w-full overflow-y-auto custom-scrollbar">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/mapping" element={<RiskMapping />} />
                <Route path="/intel" element={<SignalIntelligence />} />
                <Route path="/engine" element={<PredictiveEngine />} />
                <Route path="/modalities" element={<DataModalities />} />
                <Route path="/alerts" element={<AlertLogs />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          </Suspense>
        </main>
      </div>
    </Router>
  );
}

export default App;