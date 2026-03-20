import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/dashboard/Dashboard';
import Applications from './pages/applications/Applications';
import SavedJobs from './pages/jobs/SavedJobs';
import Resumes from './pages/resumes/Resumes';
import Contacts from './pages/contacts/Contacts';
import Interviews from './pages/interviews/Interviews';
import Companies from './pages/settings/Companies';
import Settings from './pages/settings/Settings';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="applications" element={<Applications />} />
            <Route path="jobs" element={<SavedJobs />} />
            <Route path="resumes" element={<Resumes />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="interviews" element={<Interviews />} />
            <Route path="companies" element={<Companies />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
