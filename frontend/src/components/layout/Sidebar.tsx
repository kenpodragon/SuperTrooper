import { NavLink } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';

const nav = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/profile', label: 'Profile', icon: '👤' },
  { to: '/applications', label: 'Applications', icon: '📋' },
  { to: '/jobs', label: 'Saved Jobs', icon: '🔍' },
  { to: '/resumes', label: 'Resumes', icon: '📄' },
  { to: '/contacts', label: 'Contacts', icon: '👥' },
  { to: '/interviews', label: 'Interviews', icon: '🎯' },
  { to: '/companies', label: 'Companies', icon: '🏢' },
  { to: '/fresh-jobs', label: 'Fresh Jobs', icon: '📥' },
  { to: '/notifications', label: 'Notifications', icon: '🔔' },
  { to: '/analytics', label: 'Analytics', icon: '📈' },
  { to: '/mock-interviews', label: 'Mock Interviews', icon: '🎤' },
  { to: '/networking', label: 'Networking', icon: '🤝' },
  { to: '/market', label: 'Market Intel', icon: '🌐' },
  { to: '/linkedin', label: 'LinkedIn Hub', icon: '💼' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function Sidebar() {
  const { theme, toggle } = useTheme();
  const isDark = theme === 'dark';

  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col h-screen sticky top-0">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">SuperTroopers</h1>
        <p className="text-xs text-gray-500">Hiring Command Center</p>
      </div>
      <nav className="flex-1 py-2 overflow-y-auto">
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
      <div className="p-4 border-t border-gray-700 shrink-0">
        <button
          onClick={toggle}
          className="flex items-center justify-between w-full px-1 py-1 rounded text-sm text-gray-400 hover:text-white transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs">{isDark ? '\u2600' : '\u263E'}</span>
            <span className="text-xs">{isDark ? 'Light' : 'Dark'}</span>
          </div>
          <div className={`relative w-9 h-5 rounded-full transition-colors ${isDark ? 'bg-blue-500' : 'bg-gray-600'}`}>
            <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${isDark ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </div>
        </button>
        <p className="text-xs text-gray-600 mt-2">v0.1.0</p>
      </div>
    </aside>
  );
}
