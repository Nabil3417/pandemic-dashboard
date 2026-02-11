import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

// Layout Components
import Sidebar from './components/Sidebar';

// Page Sectors 
import Dashboard from './pages/Dashboard';
import RiskMapping from './pages/RiskMapping';
import DataModalities from './pages/DataModalities';
import AlertLogs from './pages/AlertLogs';

// Pro Loading Spinner for Route Transitions
const PageLoader = () => (
  <div className="h-full w-full flex items-center justify-center bg-slate-50/50">
    <div className="flex flex-col items-center gap-3">
      <div className="h-10 w-10 border-4 border-blue-600/20 border-t-blue-600 rounded-full animate-spin"></div>
      <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Loading Sector...</p>
    </div>
  </div>
);

function App() {
  return (
    <Router>
      <div className="flex h-screen w-full bg-[#F8FAFC] font-sans antialiased overflow-hidden">
        
        {/* Global Toast Provider - Handles AI Notifications */}
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 6000,
            style: {
              background: 'transparent',
              boxShadow: 'none',
              border: 'none',
              padding: 0
            },
          }}
        />

        {/* 1. Permanent Navigation Rail */}
        <Sidebar />

        {/* 2. Intelligence Viewport (Right Side) */}
        <main className="flex-1 h-full overflow-y-auto bg-slate-50/50 relative scroll-smooth">
          
          {/* Futuristic background glow */}
          <div className="hidden lg:block absolute top-0 right-0 w-[600px] h-[600px] bg-blue-200/20 blur-[150px] rounded-full -z-10 pointer-events-none transition-all duration-1000"></div>
          
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/mapping" element={<RiskMapping />} />
              <Route path="/modalities" element={<DataModalities />} />
              <Route path="/alerts" element={<AlertLogs />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>

      </div>
    </Router>
  );
}

export default App;