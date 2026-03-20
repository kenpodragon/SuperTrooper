import { NavLink } from 'react-router-dom';

const nav = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/applications', label: 'Applications', icon: '📋' },
  { to: '/jobs', label: 'Saved Jobs', icon: '🔍' },
  { to: '/resumes', label: 'Resumes', icon: '📄' },
  { to: '/contacts', label: 'Contacts', icon: '👥' },
  { to: '/interviews', label: 'Interviews', icon: '🎯' },
  { to: '/companies', label: 'Companies', icon: '🏢' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">SuperTroopers</h1>
        <p className="text-xs text-gray-500">Hiring Command Center</p>
      </div>
      <nav className="flex-1 py-2">
        {nav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-gray-800 text-white border-r-2 border-blue-400'
                  : 'hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <span>{n.icon}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
        v0.1.0
      </div>
    </aside>
  );
}
