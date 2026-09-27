import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './Login.css';

/* ---- SVG Wheel (reused from Landing) ---- */
function IRWheelLogo({ size = 40 }) {
  const cx = 50, cy = 50, R = 44;
  const spokeCount = 24;
  const spokes = Array.from({ length: spokeCount }, (_, i) => {
    const rad = (i * 360 / spokeCount) * Math.PI / 180;
    return {
      x1: cx + 12 * Math.cos(rad), y1: cy + 12 * Math.sin(rad),
      x2: cx + R * Math.cos(rad),  y2: cy + R * Math.sin(rad),
    };
  });
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="#fff" strokeWidth="5" />
      <circle cx={cx} cy={cy} r={12} fill="#fff" />
      <circle cx={cx} cy={cy} r={6} fill="#1a3a6b" />
      {spokes.map((s, i) => (
        <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke="#fff" strokeWidth="1.8" />
      ))}
    </svg>
  );
}

/* ---- Role definitions ---- */
const ROLES = [
  {
    id: 'controller',
    title: 'Controller',
    desc: 'Central block management',
    icon: 'C',
  },
  {
    id: 'engineering',
    title: 'Engineering',
    desc: 'Track & P-Way maintenance',
    icon: 'E',
  },
  {
    id: 'snt',
    title: 'S&T',
    desc: 'Signalling & Telecom',
    icon: 'S',
  },
  {
    id: 'trd',
    title: 'TRD',
    desc: 'Traction & OHE',
    icon: 'T',
  },
  {
    id: 'locopilot',
    title: 'Locopilot',
    desc: 'Train operation',
    icon: 'L',
  },
];

const LOCOPILOT_ID = 'locopilot';

/* ---- Password field with show/hide ---- */
function PasswordInput({ value, onChange, id }) {
  const [show, setShow] = useState(false);
  return (
    <div className="password-wrap">
      <input
        id={id}
        type={show ? 'text' : 'password'}
        className="form-input"
        value={value}
        onChange={onChange}
        autoComplete="current-password"
      />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setShow(s => !s)}
        aria-label={show ? 'Hide password' : 'Show password'}
        tabIndex={-1}
      >
        {show ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  );
}

/* ================================================================
   LOGIN PAGE
   ================================================================ */
export default function Login() {
  const navigate = useNavigate();

  /* Step: 'role' | 'credentials' */
  const [step, setStep] = useState('role');
  const [selectedRole, setSelectedRole] = useState(null);

  /* Staff credentials */
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  /* Locopilot fields */
  const [trainNo, setTrainNo] = useState('');
  const [trainName, setTrainName] = useState('');
  const [fromStation, setFromStation] = useState('');
  const [toStation, setToStation] = useState('');
  const [opDate, setOpDate] = useState(() => new Date().toISOString().slice(0, 10));

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  /* ---- Handlers ---- */
  function handleRoleSelect(role) {
    setSelectedRole(role);
    setError('');
  }

  function handleRoleProceed() {
    if (!selectedRole) return;
    setStep('credentials');
    setError('');
  }

  function handleBack() {
    setStep('role');
    setUsername('');
    setPassword('');
    setTrainNo('');
    setTrainName('');
    setFromStation('');
    setToStation('');
    setError('');
  }

  async function handleStaffLogin(e) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Username and password are required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/login', {
        username: username.trim(),
        password,
        role: selectedRole.id,
      });
      const data = res.data;
      sessionStorage.setItem(
        'trackmind_user',
        JSON.stringify({ username: data.username || username, role: selectedRole.id, token: data.token || '' })
      );
      window.location.href = 'http://localhost:8501';
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Login failed. Please check your credentials.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleLocopilotLogin(e) {
    e.preventDefault();
    if (!trainNo.trim()) {
      setError('Train number is required.');
      return;
    }
    if (!fromStation.trim() || !toStation.trim()) {
      setError('Running section (From and To) is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await axios.post('/api/login', {
        role: 'locopilot',
        train_no: trainNo.trim(),
        train_name: trainName.trim(),
        from_station: fromStation.trim(),
        to_station: toStation.trim(),
        date: opDate,
      });
      const data = res.data;
      sessionStorage.setItem(
        'trackmind_user',
        JSON.stringify({ role: 'locopilot', train_no: trainNo.trim(), token: data.token || '' })
      );
      const params = new URLSearchParams({ role: 'locopilot', train_no: trainNo.trim() });
      window.location.href = `http://localhost:8501?${params.toString()}`;
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Verification failed. Check train details and try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  /* ================================================================
     RENDER
     ================================================================ */
  return (
    <div className="login-root">

      {/* HEADER */}
      <header className="ir-header">
        <div className="ir-header-inner">
          <div className="ir-header-left">
            <div className="ir-header-logo">
              <IRWheelLogo size={44} />
            </div>
            <div className="ir-header-title">
              <h1>INDIAN RAILWAYS</h1>
              <p>Ministry of Railways, Government of India</p>
            </div>
          </div>
          <div className="ir-header-right">
            <h2>TRACKMIND AI — STAFF LOGIN</h2>
            <p>Authorised Personnel Only</p>
          </div>
        </div>
      </header>

      <div className="login-page-body">
        <div className="login-container">

          {/* ---- STEP 1: ROLE SELECTION ---- */}
          {step === 'role' && (
            <div className="login-card">
              <div className="login-card-header">
                <h2>Select Your Role</h2>
                <p>Choose the role that corresponds to your department before signing in.</p>
              </div>

              <div className="role-grid">
                {ROLES.map(role => (
                  <button
                    key={role.id}
                    type="button"
                    className={`role-card${selectedRole?.id === role.id ? ' role-card--selected' : ''}`}
                    onClick={() => handleRoleSelect(role)}
                    aria-pressed={selectedRole?.id === role.id}
                  >
                    <span className="role-icon" aria-hidden="true">{role.icon}</span>
                    <span className="role-title">{role.title}</span>
                    <span className="role-desc">{role.desc}</span>
                  </button>
                ))}
              </div>

              <div className="login-card-footer">
                <button
                  className="btn-primary"
                  style={{ width: '100%' }}
                  disabled={!selectedRole}
                  onClick={handleRoleProceed}
                >
                  Continue
                </button>
              </div>

              <div className="login-back-link">
                <button type="button" className="link-btn" onClick={() => navigate('/')}>
                  Back to Home
                </button>
              </div>
            </div>
          )}

          {/* ---- STEP 2a: STAFF CREDENTIALS ---- */}
          {step === 'credentials' && selectedRole?.id !== LOCOPILOT_ID && (
            <div className="login-card">
              <div className="login-card-header">
                <h2>Sign In</h2>
                <p>
                  Role: <strong>{selectedRole?.title}</strong> — Enter your credentials to access the system.
                </p>
              </div>

              <form onSubmit={handleStaffLogin} noValidate>
                <div className="form-group">
                  <label className="form-label" htmlFor="username">Username</label>
                  <input
                    id="username"
                    type="text"
                    className="form-input"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    autoComplete="username"
                    autoFocus
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="password">Password</label>
                  <PasswordInput
                    id="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                  />
                </div>

                {error && (
                  <div className="alert-error" style={{ marginBottom: '16px' }} role="alert">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: '100%' }}
                  disabled={loading}
                >
                  {loading ? 'Verifying...' : 'Sign In'}
                </button>
              </form>

              <div className="login-back-link">
                <button type="button" className="link-btn" onClick={handleBack}>
                  Back to role selection
                </button>
              </div>
            </div>
          )}

          {/* ---- STEP 2b: LOCOPILOT FORM ---- */}
          {step === 'credentials' && selectedRole?.id === LOCOPILOT_ID && (
            <div className="login-card">
              <div className="login-card-header">
                <h2>Locopilot Access</h2>
                <p>Enter your train details to access the operational view.</p>
              </div>

              <div className="loco-notice">
                No password required. Train details are verified against active schedules.
              </div>

              <form onSubmit={handleLocopilotLogin} noValidate>
                <div className="form-row-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="train-no">Train Number</label>
                    <input
                      id="train-no"
                      type="text"
                      className="form-input"
                      placeholder="e.g. 12760"
                      value={trainNo}
                      onChange={e => setTrainNo(e.target.value)}
                      autoFocus
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="train-name">Train Name</label>
                    <input
                      id="train-name"
                      type="text"
                      className="form-input"
                      placeholder="e.g. Charminar Express"
                      value={trainName}
                      onChange={e => setTrainName(e.target.value)}
                    />
                  </div>
                </div>

                <fieldset className="form-fieldset">
                  <legend className="form-legend">Running Section</legend>
                  <div className="form-row-2">
                    <div className="form-group">
                      <label className="form-label" htmlFor="from-stn">From Station</label>
                      <input
                        id="from-stn"
                        type="text"
                        className="form-input"
                        placeholder="e.g. BZA"
                        value={fromStation}
                        onChange={e => setFromStation(e.target.value)}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="to-stn">To Station</label>
                      <input
                        id="to-stn"
                        type="text"
                        className="form-input"
                        placeholder="e.g. SC"
                        value={toStation}
                        onChange={e => setToStation(e.target.value)}
                      />
                    </div>
                  </div>
                </fieldset>

                <div className="form-group">
                  <label className="form-label" htmlFor="op-date">Date of Operation</label>
                  <input
                    id="op-date"
                    type="date"
                    className="form-input"
                    value={opDate}
                    onChange={e => setOpDate(e.target.value)}
                  />
                </div>

                {error && (
                  <div className="alert-error" style={{ marginBottom: '16px' }} role="alert">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: '100%' }}
                  disabled={loading}
                >
                  {loading ? 'Verifying...' : 'Proceed'}
                </button>
              </form>

              <div className="login-back-link">
                <button type="button" className="link-btn" onClick={handleBack}>
                  Back to role selection
                </button>
              </div>
            </div>
          )}

        </div>
      </div>

      <footer className="login-footer">
        <p>TrackMind AI &nbsp;|&nbsp; SIH 26027 &nbsp;|&nbsp; Authorised use only</p>
      </footer>
    </div>
  );
}
