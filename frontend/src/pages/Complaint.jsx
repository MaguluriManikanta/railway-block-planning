import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './Complaint.css';

/* ---- SVG Wheel ---- */
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

const REPORTER_TYPES = ['Patrolman', 'Loco Inspector', 'Station Master', 'Citizen', 'Other'];
const SEVERITY_LEVELS = ['Low', 'Medium', 'High', 'Critical'];
const DEPARTMENTS = [
  'Engineering (Track)',
  'S&T (Signalling)',
  'TRD (OHE/Electrical)',
  'Not Sure',
];

const INITIAL_FORM = {
  reporterType: '',
  reporterName: '',
  contact: '',
  location: '',
  department: '',
  defectType: '',
  severity: '',
  description: '',
  observedAt: '',
};

/* ---- Radio Button Group ---- */
function RadioGroup({ name, options, value, onChange }) {
  return (
    <div className="radio-group" role="group">
      {options.map(opt => (
        <label key={opt} className="radio-label">
          <input
            type="radio"
            name={name}
            value={opt}
            checked={value === opt}
            onChange={() => onChange(opt)}
          />
          <span>{opt}</span>
        </label>
      ))}
    </div>
  );
}

/* ================================================================
   COMPLAINT PAGE
   ================================================================ */
export default function Complaint() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INITIAL_FORM);
  const [charCount, setCharCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);   /* { refId } */
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  /* ---- Helpers ---- */
  function setField(key, val) {
    setForm(prev => ({ ...prev, [key]: val }));
    if (fieldErrors[key]) setFieldErrors(prev => ({ ...prev, [key]: '' }));
  }

  function handleDescChange(e) {
    const val = e.target.value.slice(0, 500);
    setField('description', val);
    setCharCount(val.length);
  }

  /* ---- Validation ---- */
  function validate() {
    const errs = {};
    if (!form.reporterType) errs.reporterType = 'Select reporter type.';
    if (!form.location.trim()) errs.location = 'Section / location is required.';
    if (!form.department) errs.department = 'Select department concerned.';
    if (!form.defectType.trim()) errs.defectType = 'Describe the defect observed.';
    if (!form.severity) errs.severity = 'Select severity level.';
    if (!form.description.trim()) errs.description = 'Description is required.';
    if (!form.observedAt) errs.observedAt = 'Observed date and time is required.';
    return errs;
  }

  /* ---- Submit ---- */
  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setLoading(true);
    try {
      const res = await axios.post('/api/complaint', form);
      const refId = res.data?.ref_id || res.data?.id || 'N/A';
      setSuccess({ refId });
      setForm(INITIAL_FORM);
      setCharCount(0);
      setFieldErrors({});
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Submission failed. Please try again or contact the nearest station.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  /* ================================================================
     RENDER
     ================================================================ */
  return (
    <div className="complaint-root">

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
            <h2>INFRASTRUCTURE DEFECT REPORTING</h2>
            <p>Public Safety Report Portal</p>
          </div>
        </div>
      </header>

      <div className="complaint-body">
        <div className="complaint-container">

          {/* PAGE TITLE */}
          <div className="complaint-title-block">
            <h2>Submit Infrastructure Defect / Safety Report</h2>
            <p>
              Anyone observing a track defect, signal failure, or safety hazard can report here.
              No account required.
            </p>
            <div className="complaint-info-bar">
              Reports are forwarded to the concerned department within 4 hours.
              For emergencies, contact the nearest station or dial 139.
            </div>
          </div>

          {/* SUCCESS STATE */}
          {success && (
            <div className="alert-success" style={{ marginBottom: '24px' }} role="status">
              <strong>Report Submitted Successfully.</strong>
              <br />
              Reference ID: <strong>{success.refId}</strong>. The concerned department has been
              notified. Please keep this reference for follow-up.
              <div style={{ marginTop: '12px' }}>
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => { setSuccess(null); }}
                >
                  Submit Another Report
                </button>
                &nbsp;
                <button
                  type="button"
                  className="link-btn"
                  style={{ marginLeft: '12px' }}
                  onClick={() => navigate('/')}
                >
                  Return to Home
                </button>
              </div>
            </div>
          )}

          {/* FORM */}
          {!success && (
            <form className="complaint-form" onSubmit={handleSubmit} noValidate>

              {/* Row 1: Reporter Type */}
              <div className="form-section">
                <div className="form-section-title">Reporter Information</div>
                <div className="form-group">
                  <label className="form-label">Reporter Type <span className="required">*</span></label>
                  <RadioGroup
                    name="reporterType"
                    options={REPORTER_TYPES}
                    value={form.reporterType}
                    onChange={val => setField('reporterType', val)}
                  />
                  {fieldErrors.reporterType && (
                    <span className="field-error">{fieldErrors.reporterType}</span>
                  )}
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="reporter-name">Reporter Name <span className="optional">(optional)</span></label>
                    <input
                      id="reporter-name"
                      type="text"
                      className="form-input"
                      placeholder="Full name"
                      value={form.reporterName}
                      onChange={e => setField('reporterName', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="contact">Contact Number <span className="optional">(optional)</span></label>
                    <input
                      id="contact"
                      type="tel"
                      className="form-input"
                      placeholder="10-digit mobile number"
                      value={form.contact}
                      onChange={e => setField('contact', e.target.value)}
                      maxLength={10}
                    />
                  </div>
                </div>
              </div>

              {/* Row 2: Defect Details */}
              <div className="form-section">
                <div className="form-section-title">Defect Details</div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="location">
                      Section / Location <span className="required">*</span>
                    </label>
                    <input
                      id="location"
                      type="text"
                      className={`form-input${fieldErrors.location ? ' input-error' : ''}`}
                      placeholder="e.g. BZA–GNT section, KM 45"
                      value={form.location}
                      onChange={e => setField('location', e.target.value)}
                    />
                    {fieldErrors.location && (
                      <span className="field-error">{fieldErrors.location}</span>
                    )}
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="department">
                      Department Concerned <span className="required">*</span>
                    </label>
                    <select
                      id="department"
                      className={`form-select${fieldErrors.department ? ' input-error' : ''}`}
                      value={form.department}
                      onChange={e => setField('department', e.target.value)}
                    >
                      <option value="">-- Select department --</option>
                      {DEPARTMENTS.map(d => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                    {fieldErrors.department && (
                      <span className="field-error">{fieldErrors.department}</span>
                    )}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="defect-type">
                    Defect Type / What Was Observed <span className="required">*</span>
                  </label>
                  <input
                    id="defect-type"
                    type="text"
                    className={`form-input${fieldErrors.defectType ? ' input-error' : ''}`}
                    placeholder="e.g. Cracked rail fish-plate, signal at Danger without train"
                    value={form.defectType}
                    onChange={e => setField('defectType', e.target.value)}
                  />
                  {fieldErrors.defectType && (
                    <span className="field-error">{fieldErrors.defectType}</span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Severity <span className="required">*</span>
                  </label>
                  <div className="severity-group" role="group">
                    {SEVERITY_LEVELS.map(level => (
                      <label
                        key={level}
                        className={`severity-chip${form.severity === level ? ` severity-chip--${level.toLowerCase()}` : ''}`}
                      >
                        <input
                          type="radio"
                          name="severity"
                          value={level}
                          checked={form.severity === level}
                          onChange={() => setField('severity', level)}
                        />
                        {level}
                      </label>
                    ))}
                  </div>
                  {fieldErrors.severity && (
                    <span className="field-error">{fieldErrors.severity}</span>
                  )}
                </div>
              </div>

              {/* Row 3: Description & Date */}
              <div className="form-section">
                <div className="form-section-title">Additional Information</div>

                <div className="form-group">
                  <label className="form-label" htmlFor="description">
                    Description <span className="required">*</span>
                    <span className="char-count">{charCount}/500</span>
                  </label>
                  <textarea
                    id="description"
                    className={`form-textarea${fieldErrors.description ? ' input-error' : ''}`}
                    placeholder="Provide a detailed description of the defect or hazard observed. Include any visible damage, sounds, or conditions."
                    value={form.description}
                    onChange={handleDescChange}
                    rows={5}
                  />
                  {fieldErrors.description && (
                    <span className="field-error">{fieldErrors.description}</span>
                  )}
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="observed-at">
                      Observed Date and Time <span className="required">*</span>
                    </label>
                    <input
                      id="observed-at"
                      type="datetime-local"
                      className={`form-input${fieldErrors.observedAt ? ' input-error' : ''}`}
                      value={form.observedAt}
                      onChange={e => setField('observedAt', e.target.value)}
                      max={new Date().toISOString().slice(0, 16)}
                    />
                    {fieldErrors.observedAt && (
                      <span className="field-error">{fieldErrors.observedAt}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Server error */}
              {error && (
                <div className="alert-error" style={{ marginBottom: '16px' }} role="alert">
                  {error}
                </div>
              )}

              {/* Submit */}
              <div className="form-actions">
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => navigate('/')}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? 'Submitting...' : 'Submit Report'}
                </button>
              </div>

            </form>
          )}

        </div>
      </div>

      <footer className="complaint-footer">
        <div className="container">
          <p>TrackMind AI &nbsp;|&nbsp; SIH 26027 &nbsp;|&nbsp; For emergencies call 139</p>
        </div>
      </footer>

    </div>
  );
}
