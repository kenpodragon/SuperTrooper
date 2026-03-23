import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';

interface Notification {
  id: number;
  title: string;
  message: string;
  type: string;
  read: boolean;
  created_at?: string;
  entity_type?: string;
  entity_id?: number;
  severity?: string;
}

const ENTITY_ROUTES: Record<string, string> = {
  application: '/applications',
  interview: '/interviews',
  contact: '/contacts',
  saved_job: '/saved-jobs',
  fresh_job: '/fresh-jobs',
  company: '/companies',
};

interface NotificationActionResponse {
  id: number;
  read?: boolean;
}

interface MarkAllReadResponse {
  updated: number;
}

const TYPE_COLORS: Record<string, string> = {
  info: 'bg-blue-100 text-blue-800',
  warning: 'bg-yellow-100 text-yellow-800',
  action_required: 'bg-red-100 text-red-800',
  success: 'bg-green-100 text-green-800',
};

export default function Notifications() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [tab, setTab] = useState<'all' | 'unread' | 'action_required'>('all');

  const { data, isLoading } = useQuery({
    queryKey: ['notifications', tab],
    queryFn: () => {
      const params = tab === 'unread' ? '?read=false' : tab === 'action_required' ? '?type=action_required' : '';
      return api.get<Notification[]>(`/notifications${params}`);
    },
  });

  const markRead = useMutation({
    mutationFn: (id: number) => api.put<NotificationActionResponse>(`/notifications/${id}/read`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
    onError: (error: Error) => {
      console.error('Failed to mark notification as read:', error.message);
    },
  });

  const dismiss = useMutation({
    mutationFn: (id: number) => api.del<void>(`/notifications/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
    onError: (error: Error) => {
      console.error('Failed to dismiss notification:', error.message);
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => api.post<MarkAllReadResponse>('/notifications/mark-all-read', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
    onError: (error: Error) => {
      console.error('Failed to mark all notifications as read:', error.message);
    },
  });

  const notifications = data ?? [];
  const unreadCount = notifications.filter((n: Notification) => !n.read).length;

  const tabs = [
    { key: 'all', label: 'All' },
    { key: 'unread', label: 'Unread' },
    { key: 'action_required', label: 'Action Required' },
  ] as const;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
        {unreadCount > 0 && (
          <button
            onClick={() => markAllRead.mutate()}
            className="text-sm text-blue-600 hover:underline"
          >
            Mark all read ({unreadCount})
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="flex gap-2 p-4 border-b border-gray-200">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 text-sm rounded-md ${tab === t.key ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {isLoading && <p className="text-sm text-gray-400 p-4">Loading...</p>}
        {!isLoading && notifications.length === 0 && (
          <p className="text-sm text-gray-400 p-4">No notifications.</p>
        )}

        {notifications.map((n: Notification) => {
          const entityRoute = n.entity_type ? ENTITY_ROUTES[n.entity_type] : null;
          const canNavigate = entityRoute != null;
          return (
            <div
              key={n.id}
              className={`flex items-start gap-3 p-4 border-b border-gray-100 last:border-0 ${!n.read ? 'bg-blue-50' : ''} ${canNavigate ? 'cursor-pointer hover:bg-gray-50' : ''}`}
              onClick={() => {
                if (canNavigate) {
                  if (!n.read) markRead.mutate(n.id);
                  navigate(entityRoute);
                }
              }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-sm font-medium text-gray-900">{n.title}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${TYPE_COLORS[n.type] ?? 'bg-gray-100 text-gray-700'}`}>
                    {n.type?.replace('_', ' ')}
                  </span>
                  {n.severity && n.severity !== 'info' && (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      n.severity === 'critical' ? 'bg-red-100 text-red-700' :
                      n.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                      'bg-yellow-100 text-yellow-700'
                    }`}>
                      {n.severity}
                    </span>
                  )}
                  {!n.read && <span className="w-2 h-2 bg-blue-500 rounded-full inline-block" />}
                </div>
                <p className="text-sm text-gray-600">{n.message}</p>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-xs text-gray-400">
                    {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                  </p>
                  {n.entity_type && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                      {n.entity_type.replace('_', ' ')}
                      {n.entity_id ? ` #${n.entity_id}` : ''}
                    </span>
                  )}
                  {canNavigate && (
                    <span className="text-xs text-blue-500">View &rarr;</span>
                  )}
                </div>
              </div>
              <div className="flex gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                {!n.read && (
                  <button
                    onClick={() => markRead.mutate(n.id)}
                    className="text-xs px-2 py-1 border border-blue-300 text-blue-700 rounded hover:bg-blue-50"
                  >
                    Mark Read
                  </button>
                )}
                <button
                  onClick={() => dismiss.mutate(n.id)}
                  className="text-xs px-2 py-1 border border-gray-300 text-gray-500 rounded hover:bg-gray-50"
                >
                  Dismiss
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
