import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Landing.css';

/* ---- Inline SVG: Indian Railways wheel ---- */
function IRWheelLogo({ size = 48 }) {
  const cx = 50;
  const cy = 50;
  const R = 44;
  const spokeCount = 24;
  const spokes = Array.from({ length: spokeCount }, (_, i) => {
    const angle = (i * 360) / spokeCount;
    const rad = (angle * Math.PI) / 180;
    return {
      x1: cx + 12 * Math.cos(rad),
      y1: cy + 12 * Math.sin(rad),
      x2: cx + R * Math.cos(rad),
      y2: cy + R * Math.sin(rad),
    };
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Indian Railways Wheel"
    >
      {/* Outer rim */}
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="#ffffff" strokeWidth="5" />
      {/* Inner hub */}
      <circle cx={cx} cy={cy} r={12} fill="#ffffff" />
      <circle cx={cx} cy={cy} r={6} fill="#1a3a6b" />
      {/* Spokes */}
      {spokes.map((s, i) => (
        <line
          key={i}
          x1={s.x1}
          y1={s.y1}
          x2={s.x2}
          y2={s.y2}
          stroke="#ffffff"
          strokeWidth="1.8"
        />
      ))}
    </svg>
  );
}

/* ---- Track Route Visual (CSS background pattern) ---- */
function TrackVisual() {
  return (
    <div className="track-visual" aria-hidden="true">
      {/* Two parallel rails */}
      <div className="rail rail-left" />
      <div className="rail rail-right" />
      {/* Sleepers */}
      {Array.from({ length: 9 }, (_, i) => (
        <div key={i} className="sleeper" style={{ top: `${i * 44 + 20}px` }} />
      ))}
    </div>
  );
}

/* ---- Stat Badge ---- */
function StatItem({ value, label }) {
  return (
    <div className="stat-item">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/* ---- Feature Box ---- */
function FeatureBox({ title, desc }) {
  return (
    <div className="feature-box">
      <div className="feature-box-indicator" />
      <p className="feature-box-title">{title}</p>
      <p className="feature-box-desc">{desc}</p>
    </div>
  );
}

/* ================================================================
   LANDING PAGE
   ================================================================ */
export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing-root">

      {/* ---- TOP HEADER ---- */}
      <header className="ir-header">
        <div className="ir-header-inner">
          <div className="ir-header-left">
            <div className="ir-header-logo">
              <IRWheelLogo size={52} />
            </div>
            <div className="ir-header-title">
              <h1>INDIAN RAILWAYS</h1>
              <p>Ministry of Railways, Government of India</p>
            </div>
          </div>
          <div className="ir-header-right">
            <h2>AI-POWERED BLOCK PLANNING SYSTEM</h2>
            <p>South Central Railway — Vijayawada Division</p>
          </div>
        </div>
      </header>

      {/* ---- ORANGE ACCENT STRIP ---- */}
      <div className="accent-strip" />

      {/* ---- HERO SECTION ---- */}
      <main className="hero-section">
        <div className="container hero-grid">

          {/* LEFT COLUMN */}
          <div className="hero-left">
            <div className="hero-badge">South Central Railway | Vijayawada Division</div>

            <h2 className="hero-heading">TrackMind AI</h2>
            <p className="hero-subheading">
              Intelligent Block Planning. Safer Rail Operations.
            </p>
            <p className="hero-body">
              A centralised platform for coordinating maintenance blocks, managing
              gang schedules, and ensuring safe track possession across divisions.
              Built for Controllers, Engineering staff, S&amp;T, TRD, and Locopilots.
            </p>

            {/* 2×2 Feature Grid */}
            <div className="feature-grid">
              <FeatureBox
                title="Optimized Block Planning"
                desc="AI-assisted scheduling minimises disruption to train operations."
              />
              <FeatureBox
                title="Enhanced Safety"
                desc="Rule-based conflict detection prevents overlapping possessions."
              />
              <FeatureBox
                title="Real-time Insights"
                desc="Live status of blocks, gangs, and section occupancy."
              />
              <FeatureBox
                title="AI Decision Support"
                desc="Data-driven recommendations for block window allocation."
              />
            </div>

            {/* CTA Buttons */}
            <div className="hero-actions">
              <button
                className="btn-outline"
                onClick={() => navigate('/complaint')}
              >
                Submit Public Complaint
              </button>
              <button
                className="btn-primary"
                onClick={() => navigate('/login')}
              >
                Staff Login
              </button>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div className="hero-right">
            <div className="info-card">
              <div className="info-card-header">
                <span className="info-card-label">NETWORK OVERVIEW</span>
                <span className="info-card-division">SCR — Vijayawada Division</span>
              </div>

              {/* Track visual */}
              <div className="info-card-visual">
                <TrackVisual />
                <div className="route-labels">
                  <span className="route-node">BZA</span>
                  <div className="route-line" />
                  <span className="route-node">GNT</span>
                  <div className="route-line" />
                  <span className="route-node">OGL</span>
                  <div className="route-line" />
                  <span className="route-node">RJY</span>
                </div>
              </div>

              {/* Stats */}
              <div className="stats-grid">
                <StatItem value="6,300+ KM" label="Network" />
                <StatItem value="140+" label="Trains / Day" />
                <StatItem value="4" label="Divisions Active" />
                <StatItem value="24 / 7" label="Operations" />
              </div>

              <div className="info-card-footer">
                <span>TrackMind AI — Prototype System</span>
                <span className="info-badge">LIVE</span>
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* ---- FOOTER ---- */}
      <footer className="landing-footer">
        <div className="container landing-footer-inner">
          <p>Towards a Smarter, Safer and More Efficient Indian Railways</p>
          <p className="footer-right">TrackMind AI &nbsp;|&nbsp; SIH 26027 &nbsp;|&nbsp; Prototype System</p>
        </div>
      </footer>

    </div>
  );
}
