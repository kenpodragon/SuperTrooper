import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useTheme } from '../../context/ThemeContext';

export default function AppLayout() {
  const { theme } = useTheme();

  return (
    <div className={`flex min-h-screen ${theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-gray-50'}`}>
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
