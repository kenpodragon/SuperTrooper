import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './context/ThemeContext';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/dashboard/Dashboard';
import Applications from './pages/applications/Applications';
import SavedJobs from './pages/jobs/SavedJobs';
import Resumes from './pages/resumes/Resumes';
import Contacts from './pages/contacts/Contacts';
import Interviews from './pages/interviews/Interviews';
import Companies from './pages/settings/Companies';
import Settings from './pages/settings/Settings';
import FreshJobs from './pages/fresh-jobs/FreshJobs';
import Notifications from './pages/notifications/Notifications';
import Analytics from './pages/analytics/Analytics';
import MockInterviews from './pages/mock-interviews/MockInterviews';
import Networking from './pages/networking/Networking';
import MarketIntel from './pages/market/MarketIntel';
import LinkedInHub from './pages/linkedin/LinkedInHub';
import Profile from './pages/profile/Profile';
import BulletBrowser from './pages/bullets/BulletBrowser';
import KnowledgeBase from './pages/knowledge-base/KnowledgeBase';
import ResumeBuilder from './pages/resume-builder/ResumeBuilder';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="applications" element={<Applications />} />
            <Route path="jobs" element={<SavedJobs />} />
            <Route path="resumes" element={<Resumes />} />
            <Route path="resume-builder" element={<ResumeBuilder />} />
            <Route path="resume-builder/:id" element={<ResumeBuilder />} />
            <Route path="bullets" element={<BulletBrowser />} />
            <Route path="knowledge-base" element={<KnowledgeBase />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="interviews" element={<Interviews />} />
            <Route path="companies" element={<Companies />} />
            <Route path="settings" element={<Settings />} />
            <Route path="fresh-jobs" element={<FreshJobs />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="mock-interviews" element={<MockInterviews />} />
            <Route path="networking" element={<Networking />} />
            <Route path="market" element={<MarketIntel />} />
            <Route path="linkedin" element={<LinkedInHub />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
    </ThemeProvider>
  );
}
