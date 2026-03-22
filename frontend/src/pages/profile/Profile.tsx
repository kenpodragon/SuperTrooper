import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

// ─── Types ───────────────────────────────────────────────────────────────────

interface ProfileData {
  candidate_name: string | null;
  candidate_email: string | null;
  candidate_phone: string | null;
  candidate_location: string | null;
  target_roles: string[] | null;
  avoid_roles: string[] | null;
  target_locations: LocationEntry[] | null;
  work_mode: string | null;
  desired_salary_min: number | null;
  desired_salary_max: number | null;
  industry_preferences: string[] | null;
  industry_avoids: string[] | null;
  years_experience: number | null;
  visa_status: string | null;
  credentials: string[] | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  bio: string | null;
  job_search_status: string | null;
}

interface LocationEntry {
  name: string;
  work_mode: string;
  range_miles: number;
}

const EMPTY_PROFILE: ProfileData = {
  candidate_name: null,
  candidate_email: null,
  candidate_phone: null,
  candidate_location: null,
  target_roles: null,
  avoid_roles: null,
  target_locations: null,
  work_mode: null,
  desired_salary_min: null,
  desired_salary_max: null,
  industry_preferences: null,
  industry_avoids: null,
  years_experience: null,
  visa_status: null,
  credentials: null,
  linkedin_url: null,
  github_url: null,
  portfolio_url: null,
  bio: null,
  job_search_status: null,
};

// ─── Suggestion Lists ────────────────────────────────────────────────────────

const TARGET_ROLE_SUGGESTIONS = [
  'VP Engineering', 'CTO', 'Chief Technology Officer', 'Director of Engineering',
  'Head of Engineering', 'SVP Technology', 'Engineering Manager', 'Senior Engineering Manager',
  'Principal Engineer', 'Staff Engineer', 'Director of Product', 'VP Product',
  'Head of Platform', 'VP Infrastructure', 'Director of DevOps', 'Head of Data',
  'VP Data Engineering', 'Chief Data Officer', 'Director of AI/ML',
];

const AVOID_ROLE_SUGGESTIONS = [
  'Individual Contributor', 'Junior Developer', 'Intern', 'Contract', 'Freelance',
  'Part-time', 'Temporary', 'Associate', 'Entry Level', 'Analyst',
];

const LOCATION_SUGGESTIONS = [
  'Remote (Anywhere)', 'Melbourne, FL', 'Orlando, FL', 'Tampa, FL', 'Miami, FL',
  'Jacksonville, FL', 'Austin, TX', 'Denver, CO', 'Seattle, WA', 'San Francisco, CA',
  'New York, NY', 'Boston, MA', 'Chicago, IL', 'Atlanta, GA', 'Raleigh, NC',
  'Washington, DC', 'Los Angeles, CA', 'Portland, OR', 'Nashville, TN', 'Dallas, TX',
];

const INDUSTRY_PREF_SUGGESTIONS = [
  'Technology', 'FinTech', 'HealthTech', 'EdTech', 'Defense', 'Government',
  'SaaS', 'E-Commerce', 'AI/ML', 'Cybersecurity', 'Telecommunications',
  'Consulting', 'Aerospace', 'Automotive', 'Clean Energy', 'Biotech',
  'Insurance', 'Real Estate Tech', 'Supply Chain', 'Media & Entertainment',
];

const INDUSTRY_AVOID_SUGGESTIONS = [
  'Tobacco', 'Gambling', 'Adult Entertainment', 'Weapons Manufacturing',
  'Payday Lending', 'Cryptocurrency', 'Fast Fashion', 'Fossil Fuels',
  'Private Prisons', 'Surveillance Tech',
];

// ─── TagInput Component ──────────────────────────────────────────────────────

function TagInput({
  label,
  tags,
  onChange,
  suggestions,
  placeholder,
}: {
  label: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  suggestions: string[];
  placeholder?: string;
}) {
  const [input, setInput] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    if (!input.trim()) return suggestions.filter((s) => !tags.includes(s));
    const lower = input.toLowerCase();
    return suggestions
      .filter((s) => s.toLowerCase().includes(lower) && !tags.includes(s));
  }, [input, suggestions, tags]);

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput('');
    setShowDropdown(false);
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          setShowDropdown(true);
        }}
        onFocus={() => setShowDropdown(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            if (filtered.length > 0) {
              addTag(filtered[0]);
            } else if (input.trim()) {
              addTag(input);
            }
          }
        }}
        placeholder={placeholder || `Type to search or add...`}
      />
      {showDropdown && filtered.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {filtered.slice(0, 10).map((s) => (
            <button
              key={s}
              type="button"
              className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition"
              onClick={() => addTag(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm"
            >
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="text-blue-500 hover:text-blue-700 font-bold leading-none"
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Salary Slider ───────────────────────────────────────────────────────────

function SalaryRangeSlider({
  min,
  max,
  onChange,
}: {
  min: number;
  max: number;
  onChange: (min: number, max: number) => void;
}) {
  const RANGE_MIN = 50000;
  const RANGE_MAX = 500000;
  const STEP = 5000;

  const fmt = (n: number) =>
    '$' + n.toLocaleString('en-US');

  const minPct = ((min - RANGE_MIN) / (RANGE_MAX - RANGE_MIN)) * 100;
  const maxPct = ((max - RANGE_MIN) / (RANGE_MAX - RANGE_MIN)) * 100;

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">Desired Salary Range</label>
      <div className="flex items-center gap-3 mb-3">
        <div className="flex-1">
          <label className="block text-xs text-gray-400 mb-0.5">Min</label>
          <input
            type="text"
            className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={fmt(min)}
            onChange={(e) => {
              const v = parseInt(e.target.value.replace(/[^0-9]/g, ''));
              if (!isNaN(v) && v >= RANGE_MIN && v <= max) onChange(v, max);
            }}
          />
        </div>
        <span className="text-gray-400 mt-5">&mdash;</span>
        <div className="flex-1">
          <label className="block text-xs text-gray-400 mb-0.5">Max</label>
          <input
            type="text"
            className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            value={fmt(max)}
            onChange={(e) => {
              const v = parseInt(e.target.value.replace(/[^0-9]/g, ''));
              if (!isNaN(v) && v <= RANGE_MAX && v >= min) onChange(min, v);
            }}
          />
        </div>
      </div>
      {/* Dual range slider */}
      <div className="relative h-8">
        {/* Track background */}
        <div className="absolute top-3 left-0 right-0 h-2 bg-gray-200 rounded-full" />
        {/* Active track */}
        <div
          className="absolute top-3 h-2 rounded-full"
          style={{
            left: `${minPct}%`,
            width: `${maxPct - minPct}%`,
            backgroundColor: '#00FF41',
          }}
        />
        {/* Min thumb */}
        <input
          type="range"
          min={RANGE_MIN}
          max={RANGE_MAX}
          step={STEP}
          value={min}
          onChange={(e) => {
            const v = parseInt(e.target.value);
            if (v <= max) onChange(v, max);
          }}
          className="absolute top-0 left-0 w-full h-8 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-gray-900 [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white [&::-moz-range-thumb]:shadow [&::-moz-range-thumb]:cursor-pointer"
          style={{ zIndex: min > RANGE_MAX - STEP * 2 ? 5 : 3 }}
        />
        {/* Max thumb */}
        <input
          type="range"
          min={RANGE_MIN}
          max={RANGE_MAX}
          step={STEP}
          value={max}
          onChange={(e) => {
            const v = parseInt(e.target.value);
            if (v >= min) onChange(min, v);
          }}
          className="absolute top-0 left-0 w-full h-8 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-gray-900 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-gray-900 [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white [&::-moz-range-thumb]:shadow [&::-moz-range-thumb]:cursor-pointer"
          style={{ zIndex: 4 }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{fmt(RANGE_MIN)}</span>
        <span>{fmt(RANGE_MAX)}</span>
      </div>
    </div>
  );
}

// ─── Location Manager ────────────────────────────────────────────────────────

function LocationManager({
  locations,
  onChange,
}: {
  locations: LocationEntry[];
  onChange: (locs: LocationEntry[]) => void;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [newLoc, setNewLoc] = useState<LocationEntry>({ name: '', work_mode: 'Remote', range_miles: 50 });
  const [locInput, setLocInput] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const filteredSuggestions = useMemo(() => {
    if (!locInput.trim()) return LOCATION_SUGGESTIONS;
    const lower = locInput.toLowerCase();
    return LOCATION_SUGGESTIONS.filter((s) => s.toLowerCase().includes(lower));
  }, [locInput]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const addLocation = () => {
    const name = newLoc.name.trim() || locInput.trim();
    if (!name) return;
    onChange([...locations, { ...newLoc, name }]);
    setNewLoc({ name: '', work_mode: 'Remote', range_miles: 50 });
    setLocInput('');
    setShowAdd(false);
  };

  const removeLocation = (idx: number) => {
    onChange(locations.filter((_, i) => i !== idx));
  };

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-2">Target Locations</label>
      {locations.length > 0 && (
        <div className="space-y-2 mb-3">
          {locations.map((loc, idx) => (
            <div key={idx} className="flex items-center gap-3 bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
              <div className="flex-1">
                <span className="text-sm font-medium text-gray-900">{loc.name}</span>
              </div>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{loc.work_mode}</span>
              <span className="text-xs text-gray-500">{loc.range_miles} mi</span>
              <button
                type="button"
                onClick={() => removeLocation(idx)}
                className="text-gray-400 hover:text-red-500 font-bold"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}
      {showAdd ? (
        <div ref={wrapperRef} className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-3">
          <div className="relative">
            <label className="block text-xs text-gray-400 mb-0.5">Location</label>
            <input
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              value={locInput}
              onChange={(e) => {
                setLocInput(e.target.value);
                setNewLoc((p) => ({ ...p, name: e.target.value }));
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              placeholder="City, State or Remote"
            />
            {showSuggestions && filteredSuggestions.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                {filteredSuggestions.slice(0, 8).map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700"
                    onClick={() => {
                      setLocInput(s);
                      setNewLoc((p) => ({ ...p, name: s }));
                      setShowSuggestions(false);
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Work Mode</label>
              <select
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={newLoc.work_mode}
                onChange={(e) => setNewLoc((p) => ({ ...p, work_mode: e.target.value }))}
              >
                <option value="Remote">Remote</option>
                <option value="Onsite">Onsite</option>
                <option value="Hybrid">Hybrid</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Range (miles)</label>
              <input
                type="number"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={newLoc.range_miles}
                onChange={(e) => setNewLoc((p) => ({ ...p, range_miles: parseInt(e.target.value) || 0 }))}
                min={0}
                max={500}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={addLocation}
              className="px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setShowAdd(false)}
              className="px-4 py-1.5 text-gray-500 text-sm rounded border border-gray-200 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          + Add Location
        </button>
      )}
    </div>
  );
}

// ─── Main Profile Component ──────────────────────────────────────────────────

export default function Profile() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProfileData>(EMPTY_PROFILE);
  const [saveMsg, setSaveMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [loadingKb, setLoadingKb] = useState(false);

  const { data: profile, isLoading } = useQuery<ProfileData>({
    queryKey: ['profile'],
    queryFn: () => api.get<ProfileData>('/profile'),
  });

  useEffect(() => {
    if (profile) {
      setForm({ ...EMPTY_PROFILE, ...profile });
    }
  }, [profile]);

  const mutation = useMutation({
    mutationFn: (data: Partial<ProfileData>) =>
      api.put<{ profile: ProfileData; updated_fields: string[] }>('/profile', data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      const count = (res as any).updated_fields?.length ?? 0;
      setSaveMsg({ text: `Saved ${count} fields successfully`, type: 'success' });
      setTimeout(() => setSaveMsg(null), 4000);
    },
    onError: (err: Error) => {
      setSaveMsg({ text: `Error: ${err.message}`, type: 'error' });
      setTimeout(() => setSaveMsg(null), 5000);
    },
  });

  const handleSave = () => {
    const payload: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(form)) {
      if (value !== null && value !== undefined && value !== '') {
        payload[key] = value;
      }
    }
    mutation.mutate(payload as Partial<ProfileData>);
  };

  const handleLoadFromKb = async () => {
    setLoadingKb(true);
    try {
      const data = await api.get<Partial<ProfileData>>('/profile/from-kb');
      setForm((prev) => {
        const merged = { ...prev };
        for (const [key, value] of Object.entries(data)) {
          if (value !== null && value !== undefined) {
            (merged as any)[key] = value;
          }
        }
        return merged;
      });
      setSaveMsg({ text: 'Loaded data from knowledge base. Review and save.', type: 'success' });
      setTimeout(() => setSaveMsg(null), 5000);
    } catch (err: any) {
      setSaveMsg({ text: `Failed to load from KB: ${err.message}`, type: 'error' });
      setTimeout(() => setSaveMsg(null), 5000);
    } finally {
      setLoadingKb(false);
    }
  };

  const set = (field: keyof ProfileData, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Profile</h1>
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="pb-24">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
          <p className="text-sm text-gray-500 mt-1">Your candidate profile and job search preferences</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleLoadFromKb}
            disabled={loadingKb}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {loadingKb ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading...
              </>
            ) : (
              'Load from Knowledge Base'
            )}
          </button>
        </div>
      </div>

      {/* Toast */}
      {saveMsg && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${
          saveMsg.type === 'error'
            ? 'bg-red-50 text-red-700 border border-red-200'
            : 'bg-green-50 text-green-700 border border-green-200'
        }`}>
          {saveMsg.text}
        </div>
      )}

      <div className="space-y-6">

        {/* Section 1: Personal Info */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Personal Info</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Full Name</label>
              <input
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.candidate_name ?? ''}
                onChange={(e) => set('candidate_name', e.target.value)}
                placeholder="Stephen Salaka"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <input
                type="email"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.candidate_email ?? ''}
                onChange={(e) => set('candidate_email', e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Phone</label>
              <input
                type="tel"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.candidate_phone ?? ''}
                onChange={(e) => set('candidate_phone', e.target.value)}
                placeholder="(555) 123-4567"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Location</label>
              <input
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.candidate_location ?? ''}
                onChange={(e) => set('candidate_location', e.target.value)}
                placeholder="Melbourne, FL"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">LinkedIn URL</label>
              <input
                type="url"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.linkedin_url ?? ''}
                onChange={(e) => set('linkedin_url', e.target.value)}
                placeholder="https://linkedin.com/in/yourprofile"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">GitHub URL</label>
              <input
                type="url"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.github_url ?? ''}
                onChange={(e) => set('github_url', e.target.value)}
                placeholder="https://github.com/yourusername"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Portfolio URL</label>
              <input
                type="url"
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.portfolio_url ?? ''}
                onChange={(e) => set('portfolio_url', e.target.value)}
                placeholder="https://yourportfolio.com"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Job Search Status</label>
              <select
                className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={form.job_search_status ?? ''}
                onChange={(e) => set('job_search_status', e.target.value || null)}
              >
                <option value="">Select...</option>
                <option value="actively_looking">Actively Looking</option>
                <option value="open_to_opportunities">Open to Opportunities</option>
                <option value="casually_browsing">Casually Browsing</option>
                <option value="not_looking">Not Looking</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Target Roles */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Target Roles</h2>
          <div className="max-w-3xl">
            <TagInput
              label="Roles you want"
              tags={form.target_roles ?? []}
              onChange={(tags) => set('target_roles', tags.length ? tags : null)}
              suggestions={TARGET_ROLE_SUGGESTIONS}
              placeholder="Type a role title... (e.g., VP Engineering)"
            />
          </div>
        </div>

        {/* Section 3: Avoid Roles */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Avoid Roles</h2>
          <div className="max-w-3xl">
            <TagInput
              label="Roles to filter out"
              tags={form.avoid_roles ?? []}
              onChange={(tags) => set('avoid_roles', tags.length ? tags : null)}
              suggestions={AVOID_ROLE_SUGGESTIONS}
              placeholder="Type a role to exclude... (e.g., Individual Contributor)"
            />
          </div>
        </div>

        {/* Section 4: Locations */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Locations</h2>
          <div className="max-w-3xl">
            <LocationManager
              locations={form.target_locations ?? []}
              onChange={(locs) => set('target_locations', locs.length ? locs : null)}
            />
          </div>
        </div>

        {/* Section 5: Salary */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Salary</h2>
          <div className="max-w-xl">
            <SalaryRangeSlider
              min={form.desired_salary_min ?? 150000}
              max={form.desired_salary_max ?? 250000}
              onChange={(min, max) => {
                setForm((prev) => ({ ...prev, desired_salary_min: min, desired_salary_max: max }));
              }}
            />
          </div>
        </div>

        {/* Section 6: Industry Preferences */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Industry Preferences</h2>
          <div className="max-w-3xl">
            <TagInput
              label="Industries you want to work in"
              tags={form.industry_preferences ?? []}
              onChange={(tags) => set('industry_preferences', tags.length ? tags : null)}
              suggestions={INDUSTRY_PREF_SUGGESTIONS}
              placeholder="Type an industry... (e.g., FinTech)"
            />
          </div>
        </div>

        {/* Section 7: Industry Avoids */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Industry Avoids</h2>
          <div className="max-w-3xl">
            <TagInput
              label="Industries to filter out"
              tags={form.industry_avoids ?? []}
              onChange={(tags) => set('industry_avoids', tags.length ? tags : null)}
              suggestions={INDUSTRY_AVOID_SUGGESTIONS}
              placeholder="Type an industry to avoid... (e.g., Gambling)"
            />
          </div>
        </div>

        {/* Section 8: Bio */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Bio</h2>
          <div className="max-w-3xl">
            <label className="block text-xs text-gray-500 mb-1">Professional Bio / Elevator Pitch</label>
            <textarea
              className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 h-32 resize-y"
              value={form.bio ?? ''}
              onChange={(e) => set('bio', e.target.value || null)}
              placeholder="Senior technology executive with 20+ years building and scaling engineering teams..."
              maxLength={2000}
            />
            <div className="flex justify-end mt-1">
              <span className="text-xs text-gray-400">
                {(form.bio ?? '').length} / 2,000
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky Save Button */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-6 py-3 flex justify-end z-20">
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="px-6 py-2.5 bg-gray-900 text-white text-sm font-medium rounded hover:bg-gray-700 disabled:opacity-50 transition"
        >
          {mutation.isPending ? 'Saving...' : 'Save Profile'}
        </button>
      </div>
    </div>
  );
}
