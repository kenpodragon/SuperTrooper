/**
 * NotificationBell.tsx — Notification indicator with expandable list in popup.
 * Popup component (React functional component).
 */

import { useState, useEffect, useCallback } from "react";

interface Notification {
  id: number;
  message: string;
  type: string;
  read: boolean;
  created_at: string;
}

async function fetchNotifications(): Promise<Notification[]> {
  try {
    const res = await fetch("http://localhost:8055/api/notifications?limit=20", {
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.notifications || data || [];
  } catch {
    return [];
  }
}

async function markRead(id: number): Promise<void> {
  try {
    await fetch(`http://localhost:8055/api/notifications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read: true }),
    });
  } catch {
    // non-critical
  }
}

async function dismissNotification(id: number): Promise<void> {
  try {
    await fetch(`http://localhost:8055/api/notifications/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    // non-critical
  }
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const unread = notifications.filter((n) => !n.read).length;

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchNotifications();
    setNotifications(data);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleOpen = () => {
    setOpen((prev) => !prev);
    if (!open) load();
  };

  const handleClick = async (n: Notification) => {
    if (!n.read) {
      await markRead(n.id);
      setNotifications((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
      );
    }
  };

  const handleDismiss = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    await dismissNotification(id);
    setNotifications((prev) => prev.filter((x) => x.id !== id));
  };

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className="relative p-1 text-st-muted hover:text-st-green transition"
        title="Notifications"
      >
        <span className="text-sm font-mono">&#9679;</span>
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 text-[9px] font-bold bg-st-green text-st-bg rounded-full w-3.5 h-3.5 flex items-center justify-center font-mono">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-7 w-64 bg-st-surface border border-st-border rounded shadow-lg z-50 max-h-72 overflow-y-auto">
          <div className="px-3 py-2 border-b border-st-border flex items-center justify-between">
            <span className="text-[10px] font-mono text-st-green tracking-wider uppercase">
              Notifications
            </span>
            <button
              onClick={() => setOpen(false)}
              className="text-st-muted hover:text-st-text text-xs"
            >
              x
            </button>
          </div>

          {loading && (
            <div className="p-3 text-center text-st-muted text-xs animate-pulse">
              Loading...
            </div>
          )}

          {!loading && notifications.length === 0 && (
            <div className="p-3 text-center text-st-muted text-xs">
              No notifications
            </div>
          )}

          {!loading &&
            notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => handleClick(n)}
                className={`px-3 py-2 border-b border-st-border cursor-pointer hover:bg-st-bg transition flex items-start gap-2 ${
                  n.read ? "opacity-50" : ""
                }`}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-st-text leading-snug">{n.message}</p>
                  <p className="text-[9px] text-st-muted mt-0.5">{timeAgo(n.created_at)}</p>
                </div>
                <button
                  onClick={(e) => handleDismiss(e, n.id)}
                  className="text-st-muted hover:text-red-400 text-[10px] flex-shrink-0 mt-0.5"
                  title="Dismiss"
                >
                  x
                </button>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
