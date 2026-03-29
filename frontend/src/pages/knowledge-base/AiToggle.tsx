import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface SettingsData {
  ai_enabled: boolean;
  ai_provider: string;
}

export default function AiToggle() {
  const queryClient = useQueryClient();

  const { data: settings } = useQuery<SettingsData>({
    queryKey: ['settings'],
    queryFn: () => api.get<SettingsData>('/settings'),
  });

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.patch('/settings', { ai_enabled: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  const isOn = settings?.ai_enabled ?? false;

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-400">AI Assist</span>
      <button
        onClick={() => mutation.mutate(!isOn)}
        disabled={mutation.isPending}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          isOn ? 'bg-purple-600' : 'bg-gray-600'
        }`}
        title={isOn ? 'Disable AI features' : 'Enable AI features'}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            isOn ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}
