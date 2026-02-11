import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Map, Database, Bell, Settings, ShieldAlert } from 'lucide-react';

const Sidebar = () => {
  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard, path: '/' },
    { name: 'Risk Mapping', icon: Map, path: '/mapping' },
    { name: 'Data Modalities', icon: Database, path: '/modalities' },
    { name: 'Alert Logs', icon: Bell, path: '/alerts' },
  ];

  return (
    <div className="w-72 bg-[#0f172a] min-h-screen sticky top-0 text-slate-300 p-8 flex flex-col border-r border-slate-800 shadow-2xl">
      <div className="flex items-center gap-4 mb-14 px-2">
        <div className="bg-blue-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/40">
          <ShieldAlert size={28} className="text-white" />
        </div>
        <span className="font-black text-white text-2xl tracking-tighter uppercase">BioGuard AI</span>
      </div>
      
      <nav className="flex-1 space-y-3">
        {menuItems.map((item) => (
          <NavLink 
            to={item.path} 
            key={item.name} 
            className={({ isActive }) => `
              w-full flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-300 font-bold text-sm
              ${isActive 
                ? 'bg-blue-600 text-white shadow-xl shadow-blue-600/30 translate-x-2' 
                : 'hover:bg-slate-800 hover:text-white text-slate-400'}
            `}
          >
            <item.icon size={22} strokeWidth={2.5} />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto pt-6 border-t border-slate-800">
        <button className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl hover:bg-slate-800 transition-all text-slate-400 hover:text-white font-bold text-sm">
          <Settings size={22} />
          <span>Settings</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;