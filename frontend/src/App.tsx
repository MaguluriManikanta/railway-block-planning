import React, { useState, useEffect } from 'react';
import {
  Bell, CheckCircle2, AlertTriangle, ShieldAlert, Train, Activity, Zap, Clock,
  Calendar, Lock, Settings, RefreshCw, Send, Radio, AlertOctagon, Layers, Filter
} from 'lucide-react';
import {
  fetchKpi, fetchSchedules, fetchLiveTrains, fetchNotifications,
  applyOverride, cancelBlock, grantEmergencyBlock, markNotificationsRead,
  fetchSetting, updateSetting, advanceTelemetryStep,
  KpiData, ScheduleItem, LiveTrain, NotificationItem
} from './api';

export default function App() {
  const [department, setDepartment] = useState('All');
  const [horizon, setHorizon] = useState('weekly');
  const [activeTab, setActiveTab] = useState('override');
  
  // Data State
  const [kpi, setKpi] = useState<KpiData | null>(null);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [liveTrains, setLiveTrains] = useState<LiveTrain[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const [autoLiveStream, setAutoLiveStream] = useState(false);
  
  // UI Controls State
  const [showNotifPopover, setShowNotifPopover] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'warning' | 'error'; text: string } | null>(null);
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [newStart, setNewStart] = useState('2026-09-16 08:00');
  const [newEnd, setNewEnd] = useState('2026-09-16 10:00');
  const [isLocked, setIsLocked] = useState(true);
  const [isEmergForce, setIsEmergForce] = useState(false);
  const [overrideReason, setOverrideReason] = useState('Sectional Congestion Adjustment');
  
  // Emergency Block Form
  const [emDept, setEmDept] = useState('Engineering');
  const [emSec, setEmSec] = useState('Vijayawada-SEC-01');
  const [emDefect, setEmDefect] = useState('Rail Fracture (Immediate Danger)');
  const [emDuration, setEmDuration] = useState(2.0);

  // Load Data
  const loadDashboardData = async () => {
    try {
      const kData = await fetchKpi(department);
      setKpi(kData);

      const sData = await fetchSchedules(horizon, department);
      setSchedules(sData);

      if (sData.length > 0 && selectedScheduleId === null) {
        setSelectedScheduleId(sData[0].schedule_id);
        setNewStart(sData[0].planned_start);
        setNewEnd(sData[0].planned_end);
      }

      const tData = await fetchLiveTrains();
      setLiveTrains(tData);

      const nData = await fetchNotifications();
      setNotifications(nData.data);
      setUnreadNotifCount(nData.unread_count);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  };

  useEffect(() => {
    loadDashboardData();
    fetchSetting('auto_live_stream').then(val => setAutoLiveStream(val === '1'));
  }, [department, horizon]);

  // Auto-stream telemetry interval loop (3 seconds)
  useEffect(() => {
    let interval: any = null;
    if (autoLiveStream) {
      interval = setInterval(async () => {
        await advanceTelemetryStep(3.0);
        const tData = await fetchLiveTrains();
        setLiveTrains(tData);
      }, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoLiveStream]);

  // Toast Auto-clear
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  const handleToggleAutoStream = async () => {
    const nextVal = !autoLiveStream;
    setAutoLiveStream(nextVal);
    await updateSetting('auto_live_stream', nextVal ? '1' : '0');
    setToastMessage({ type: 'success', text: `Live Auto-Feed ${nextVal ? 'Activated (3s)' : 'Deactivated'}` });
  };

  const handleApplyOverride = async () => {
    if (!selectedScheduleId) return;
    const currentItem = schedules.find(s => s.schedule_id === selectedScheduleId);
    if (!currentItem) return;

    try {
      const res = await applyOverride({
        schedule_id: selectedScheduleId,
        section_id: currentItem.section_id,
        department: currentItem.department,
        new_start: newStart,
        new_end: newEnd,
        is_locked: isLocked,
        is_emerg_force: isEmergForce,
        override_reason: overrideReason,
        horizon: horizon
      });

      if (res.success) {
        setToastMessage({ type: 'success', text: res.message });
        loadDashboardData();
      } else {
        setToastMessage({ type: 'error', text: res.reason });
      }
    } catch (err) {
      setToastMessage({ type: 'error', text: 'Failed to submit controller override' });
    }
  };

  const handleCancelBlock = async () => {
    if (!selectedScheduleId) return;
    try {
      const res = await cancelBlock(selectedScheduleId, overrideReason);
      if (res.success) {
        setToastMessage({ type: 'warning', text: res.message });
        loadDashboardData();
      }
    } catch (err) {
      setToastMessage({ type: 'error', text: 'Failed to cancel schedule block' });
    }
  };

  const handleGrantEmergency = async () => {
    try {
      const res = await grantEmergencyBlock({
        department: emDept,
        section_id: emSec,
        defect_type: emDefect,
        severity: 'Critical',
        duration_hours: emDuration,
        reason: 'G&SR Rule 4.09 Emergency Track Protection'
      });
      if (res.success) {
        setToastMessage({ type: 'success', text: res.message });
        loadDashboardData();
      }
    } catch (err) {
      setToastMessage({ type: 'error', text: 'Failed to grant emergency block' });
    }
  };

  const handleMarkAllRead = async () => {
    await markNotificationsRead(undefined, true);
    const nData = await fetchNotifications();
    setNotifications(nData.data);
    setUnreadNotifCount(nData.unread_count);
    setToastMessage({ type: 'success', text: 'All notifications marked as read!' });
  };

  const handleMarkSingleRead = async (notif_id: number) => {
    await markNotificationsRead(notif_id);
    const nData = await fetchNotifications();
    setNotifications(nData.data);
    setUnreadNotifCount(nData.unread_count);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-lg shadow-xl border text-sm font-semibold flex items-center gap-3 transition-all ${
          toastMessage.type === 'success' ? 'bg-emerald-950/90 border-emerald-500 text-emerald-200' :
          toastMessage.type === 'warning' ? 'bg-amber-950/90 border-amber-500 text-amber-200' :
          'bg-rose-950/90 border-rose-500 text-rose-200'
        }`}>
          {toastMessage.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
          {toastMessage.type === 'warning' && <AlertTriangle className="w-5 h-5 text-amber-400" />}
          {toastMessage.type === 'error' && <ShieldAlert className="w-5 h-5 text-rose-400" />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Top Navbar */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 text-xl font-bold">
            🎛️
          </div>
          <div>
            <h1 className="text-lg font-extrabold text-white tracking-tight leading-none">
              Indian Railways AI Block Planning & Operations Master Center
            </h1>
            <p className="text-xs text-blue-400 font-medium mt-1">
              Ministry of Railways &nbsp;|&nbsp; Vijayawada Division (BZA) &nbsp;|&nbsp; Zero-Lag FastAPI + React System
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Department Filter */}
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400 font-medium">Department:</span>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="bg-transparent text-white font-semibold outline-none cursor-pointer"
            >
              <option value="All">All Departments</option>
              <option value="Engineering">Engineering (TMS)</option>
              <option value="S&T">Signal & Telecom (SMMS)</option>
              <option value="TRD">Traction Distribution (TDMS)</option>
            </select>
          </div>

          {/* Notifications Popover */}
          <div className="relative">
            <button
              onClick={() => setShowNotifPopover(!showNotifPopover)}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition"
            >
              <Bell className="w-4 h-4 text-blue-400" />
              <span>Alerts ({unreadNotifCount})</span>
            </button>

            {showNotifPopover && (
              <div className="absolute right-0 mt-2 w-96 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-4 z-50 max-h-[480px] overflow-y-auto">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Bell className="w-4 h-4 text-blue-400" /> Unread Live Alerts ({unreadNotifCount})
                  </h3>
                  {unreadNotifCount > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      className="text-xs text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1"
                    >
                      ✓ Mark All Read
                    </button>
                  )}
                </div>

                <div className="space-y-2.5">
                  {notifications.length > 0 ? (
                    notifications.map((n) => (
                      <div
                        key={n.notif_id}
                        className={`p-3 rounded-lg border text-xs transition ${
                          n.is_read === 0
                            ? 'bg-rose-950/20 border-rose-800/40 text-slate-200'
                            : 'bg-slate-950 border-slate-800/60 text-slate-400'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            n.audience === 'public' ? 'bg-blue-900/60 text-blue-300' : 'bg-slate-800 text-slate-300'
                          }`}>
                            {n.audience === 'public' ? '📢 PUBLIC' : '🔒 STAFF'}
                          </span>
                          <span className="text-[10px] text-slate-500">{n.created_at}</span>
                        </div>
                        <p className="font-medium text-slate-300 leading-snug">{n.message}</p>
                        {n.is_read === 0 && (
                          <button
                            onClick={() => handleMarkSingleRead(n.notif_id)}
                            className="mt-2 text-[10px] bg-slate-800 hover:bg-slate-700 text-blue-300 px-2 py-1 rounded font-semibold transition"
                          >
                            ✓ Mark as Read
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 text-center py-4">No active notifications</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 px-6 py-5 max-w-[1700px] w-full mx-auto space-y-6">
        {/* KPI Strip */}
        {kpi && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">🚆 Active Trains</p>
                <p className="text-2xl font-extrabold text-white mt-1">{kpi.active_trains_count} Trains</p>
                <p className="text-xs text-emerald-400 font-semibold mt-1">🟢 {kpi.on_time_pct}% On-Time Punctuality</p>
              </div>
              <Train className="w-8 h-8 text-blue-400/80" />
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">⚙️ Operational Health</p>
                <p className="text-2xl font-extrabold text-sky-400 mt-1">{kpi.health_score}%</p>
                <p className="text-xs text-sky-400 font-semibold mt-1">✨ AI Optimized Matrix</p>
              </div>
              <Activity className="w-8 h-8 text-sky-400/80" />
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">⚡ Line Capacity</p>
                <p className="text-2xl font-extrabold text-amber-400 mt-1">{kpi.capacity_utilization_pct}%</p>
                <p className="text-xs text-amber-400 font-semibold mt-1">🤝 37.5% Downtime Saved</p>
              </div>
              <Zap className="w-8 h-8 text-amber-400/80" />
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">🚨 Backlog & Alerts</p>
                <p className="text-2xl font-extrabold text-rose-400 mt-1">{kpi.critical_defects + kpi.high_defects} Active</p>
                <p className="text-xs text-rose-400 font-semibold mt-1">🔴 {kpi.critical_defects} Critical | 🟠 {kpi.high_defects} High</p>
              </div>
              <ShieldAlert className="w-8 h-8 text-rose-400/80" />
            </div>
          </div>
        )}

        {/* Console & Override Tabs */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('override')}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                  activeTab === 'override' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                🛠️ Manual Controller Override Console
              </button>
              <button
                onClick={() => setActiveTab('emergency')}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                  activeTab === 'emergency' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                🚨 Grant Immediate Emergency Block
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-slate-400">Planning Horizon:</span>
              <button
                onClick={() => setHorizon('weekly')}
                className={`px-3 py-1 rounded text-xs font-bold ${horizon === 'weekly' ? 'bg-slate-800 text-blue-400 border border-blue-500/50' : 'text-slate-400'}`}
              >
                7-Day Weekly
              </button>
              <button
                onClick={() => setHorizon('monthly')}
                className={`px-3 py-1 rounded text-xs font-bold ${horizon === 'monthly' ? 'bg-slate-800 text-blue-400 border border-blue-500/50' : 'text-slate-400'}`}
              >
                30-Day Monthly
              </button>
            </div>
          </div>

          {/* TAB 1: MANUAL OVERRIDE */}
          {activeTab === 'override' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Select Block to Modify:</label>
                  <select
                    value={selectedScheduleId || ''}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setSelectedScheduleId(id);
                      const s = schedules.find(item => item.schedule_id === id);
                      if (s) {
                        setNewStart(s.planned_start);
                        setNewEnd(s.planned_end);
                      }
                    }}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  >
                    {schedules.map((s) => (
                      <option key={s.schedule_id} value={s.schedule_id}>
                        Schedule #{s.schedule_id} | {s.department} | {s.section_id} | {s.planned_start} ({s.defect_type || 'Block'})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Controller Justification / Reason:</label>
                  <input
                    type="text"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Planned Start (YYYY-MM-DD HH:MM):</label>
                  <input
                    type="text"
                    value={newStart}
                    onChange={(e) => setNewStart(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Planned End (YYYY-MM-DD HH:MM):</label>
                  <input
                    type="text"
                    value={newEnd}
                    onChange={(e) => setNewEnd(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-6 pt-2">
                <label className="flex items-center gap-2 text-xs font-bold text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isLocked}
                    onChange={(e) => setIsLocked(e.target.checked)}
                    className="rounded bg-slate-950 border-slate-800 text-blue-600 focus:ring-0"
                  />
                  <span>📌 Lock & Pin this Block (Prevent AI from moving)</span>
                </label>

                <label className="flex items-center gap-2 text-xs font-bold text-rose-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isEmergForce}
                    onChange={(e) => setIsEmergForce(e.target.checked)}
                    className="rounded bg-slate-950 border-slate-800 text-rose-600 focus:ring-0"
                  />
                  <span>🚨 Emergency Force Override (Bypass Non-Emergency Train Conflict)</span>
                </label>
              </div>

              <div className="flex items-center gap-4 pt-2">
                <button
                  onClick={handleApplyOverride}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg text-xs transition"
                >
                  💾 Apply Controller Override & Re-Optimize
                </button>
                <button
                  onClick={handleCancelBlock}
                  className="flex-1 bg-slate-800 hover:bg-rose-900/60 border border-slate-700 text-slate-300 hover:text-rose-200 font-bold py-2.5 rounded-lg text-xs transition"
                >
                  ❌ Cancel / Postpone Block (Release Slot)
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: EMERGENCY BLOCK */}
          {activeTab === 'emergency' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Department Requesting Emergency Block:</label>
                  <select
                    value={emDept}
                    onChange={(e) => setEmDept(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  >
                    <option value="Engineering">Engineering (TMS)</option>
                    <option value="S&T">Signal & Telecom (SMMS)</option>
                    <option value="TRD">Traction Distribution (TDMS)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Track Section:</label>
                  <select
                    value={emSec}
                    onChange={(e) => setEmSec(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  >
                    <option value="Vijayawada-SEC-01">Vijayawada-SEC-01</option>
                    <option value="Guntur-SEC-08">Guntur-SEC-08</option>
                    <option value="Hyderabad-SEC-02">Hyderabad-SEC-02</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Emergency Defect Nature:</label>
                  <input
                    type="text"
                    value={emDefect}
                    onChange={(e) => setEmDefect(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-white outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5">Required Block Duration (Hours): {emDuration} hrs</label>
                  <input
                    type="range"
                    min="0.5"
                    max="4.0"
                    step="0.5"
                    value={emDuration}
                    onChange={(e) => setEmDuration(Number(e.target.value))}
                    className="w-full cursor-pointer accent-rose-500"
                  />
                </div>
              </div>

              <button
                onClick={handleGrantEmergency}
                className="w-full bg-rose-600 hover:bg-rose-500 text-white font-extrabold py-3 rounded-lg text-xs transition uppercase tracking-wider"
              >
                🚨 Authorize & Impose Emergency Corridor Block (TSR 30 km/h Dispatched)
              </button>
            </div>
          )}
        </div>

        {/* Live Train Operational Cards & Auto-Feed Toggle */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-extrabold text-white flex items-center gap-2">
              <Train className="w-4 h-4 text-blue-400" /> Live Train Operational Status Cards
            </h2>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-xs font-bold text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoLiveStream}
                  onChange={handleToggleAutoStream}
                  className="rounded bg-slate-950 border-slate-800 text-blue-600 focus:ring-0"
                />
                <span>🔴 Live Auto-Feed (3s)</span>
              </label>
              <button
                onClick={async () => {
                  await advanceTelemetryStep(3.0);
                  const tData = await fetchLiveTrains();
                  setLiveTrains(tData);
                  setToastMessage({ type: 'success', text: 'Telemetry step advanced!' });
                }}
                className="bg-slate-800 hover:bg-slate-700 text-blue-400 border border-slate-700 px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Step Manual
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {liveTrains.map((tr) => (
              <div
                key={tr.train_id}
                className={`bg-slate-950 border-l-4 rounded-xl p-4 shadow-lg flex items-center justify-between ${
                  tr.delay_minutes === 0 ? 'border-l-emerald-500 border-slate-800' :
                  tr.delay_minutes <= 15 ? 'border-l-amber-500 border-slate-800' :
                  'border-l-rose-500 border-slate-800'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-extrabold text-white text-sm">🚆 {tr.train_number}</span>
                    <span className="text-xs text-slate-400 font-semibold">— {tr.train_name}</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                    <span>📍 KM {tr.current_km.toFixed(1)}</span>
                    <span>⚡ {tr.speed_kmh} km/h</span>
                  </div>
                  <p className="text-xs font-semibold mt-2 text-slate-300">{tr.status}</p>
                </div>

                <div className="text-right">
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-full inline-block ${
                    tr.delay_minutes === 0 ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                    tr.delay_minutes <= 15 ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                    'bg-rose-950 text-rose-300 border border-rose-800'
                  }`}>
                    {tr.delay_minutes === 0 ? '🟢 On Time' : `🔴 +${tr.delay_minutes}m Delay`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Schedule Matrix Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-extrabold text-white flex items-center gap-2">
            <Calendar className="w-4 h-4 text-blue-400" /> Active Maintenance Schedule Matrix ({horizon})
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300 border-collapse">
              <thead>
                <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
                  <th className="p-3 font-bold">ID</th>
                  <th className="p-3 font-bold">Dept</th>
                  <th className="p-3 font-bold">Section</th>
                  <th className="p-3 font-bold">Defect Type</th>
                  <th className="p-3 font-bold">Severity</th>
                  <th className="p-3 font-bold">Planned Window</th>
                  <th className="p-3 font-bold">Status</th>
                  <th className="p-3 font-bold">Authority</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {schedules.map((s) => (
                  <tr key={s.schedule_id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3 font-extrabold text-white">#{s.schedule_id}</td>
                    <td className="p-3 font-semibold text-blue-400">{s.department}</td>
                    <td className="p-3 font-semibold">{s.section_id}</td>
                    <td className="p-3">{s.defect_type || 'Corridor Block'}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        s.severity === 'Critical' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-amber-950 text-amber-300'
                      }`}>
                        {s.severity || 'High'}
                      </span>
                    </td>
                    <td className="p-3 font-medium text-slate-300">{s.planned_start} → {s.planned_end}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        s.status === 'locked' ? 'bg-purple-950 text-purple-300 border border-purple-800' : 'bg-blue-950 text-blue-300'
                      }`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="p-3 font-semibold text-slate-400">{s.decided_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 px-6 py-4 text-center text-xs text-slate-500">
        Indian Railways AI-Powered Automatic Block Planning System &nbsp;|&nbsp; Zero-Lag FastAPI + React Edition
      </footer>
    </div>
  );
}
