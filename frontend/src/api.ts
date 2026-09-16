import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface KpiData {
  total_defects: number;
  open_defects: number;
  critical_defects: number;
  high_defects: number;
  scheduled_blocks: number;
  locked_overrides: number;
  health_score: number;
  active_trains_count: number;
  on_time_pct: number;
  capacity_utilization_pct: number;
}

export interface ScheduleItem {
  schedule_id: number;
  defect_id: string;
  slot_id: string;
  section_id: str;
  department: str;
  planned_start: string;
  planned_end: string;
  horizon: string;
  status: string;
  decided_by: string;
  defect_type?: string;
  severity?: string;
  priority_score?: number;
  estimated_duration_hours?: number;
}

export interface LiveTrain {
  train_id: string;
  train_number: string;
  train_name: string;
  current_km: number;
  speed_kmh: number;
  delay_minutes: number;
  status: string;
}

export interface NotificationItem {
  notif_id: number;
  recipient_role: string;
  category: string;
  audience: string;
  message: string;
  created_at: string;
  is_read: number;
}

export const fetchKpi = async (dept = 'All'): Promise<KpiData> => {
  const res = await api.get(`/kpi?department=${dept}`);
  return res.data;
};

export const fetchSchedules = async (horizon = 'weekly', dept = 'All'): Promise<ScheduleItem[]> => {
  const res = await api.get(`/schedules?horizon=${horizon}&department=${dept}`);
  return res.data.data;
};

export const fetchLiveTrains = async (): Promise<LiveTrain[]> => {
  const res = await api.get('/trains/live');
  return res.data.data;
};

export const fetchNotifications = async (): Promise<{ unread_count: number; data: NotificationItem[] }> => {
  const res = await api.get('/notifications');
  return res.data;
};

export const applyOverride = async (payload: {
  schedule_id: number;
  section_id: string;
  department: string;
  new_start: string;
  new_end: string;
  is_locked: boolean;
  is_emerg_force: boolean;
  override_reason: string;
  horizon?: string;
}) => {
  const res = await api.post('/schedules/override', payload);
  return res.data;
};

export const cancelBlock = async (schedule_id: number, reason = 'Controller Cancelled') => {
  const res = await api.post(`/schedules/cancel?schedule_id=${schedule_id}&reason=${encodeURIComponent(reason)}`);
  return res.data;
};

export const grantEmergencyBlock = async (payload: {
  department: string;
  section_id: string;
  defect_type: string;
  severity: string;
  duration_hours: number;
  reason: string;
}) => {
  const res = await api.post('/schedules/emergency', payload);
  return res.data;
};

export const markNotificationsRead = async (notif_id?: number, mark_all = false) => {
  const res = await api.post('/notifications/read', { notif_id, mark_all });
  return res.data;
};

export const fetchSetting = async (key: string): Promise<string> => {
  const res = await api.get(`/settings/${key}`);
  return res.data.value;
};

export const updateSetting = async (key: string, value: string) => {
  const res = await api.post('/settings', { key, value });
  return res.data;
};

export const advanceTelemetryStep = async (step_km = 3.0) => {
  const res = await api.post(`/trains/advance?step_km=${step_km}`);
  return res.data;
};
