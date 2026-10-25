import { useState } from 'react';
import { NavLink, Routes, Route, useLocation } from 'react-router-dom';
import {
  CalendarDays,
  CircleHelp,
  Gauge,
  LayoutDashboard,
  Menu,
  RefreshCw,
  SlidersHorizontal,
  Table2,
  Wind,
  X
} from 'lucide-react';

import OverviewPage from './pages/OverviewPage';
import ForecastExplorerPage from './pages/ForecastExplorerPage';
import SimulatorPage from './pages/SimulatorPage';
import AccuracyPage from './pages/AccuracyPage';
import DataExplorerPage from './pages/DataExplorerPage';
import MethodologyPage from './pages/MethodologyPage';

const navItems = [
  ['Overview', '/', LayoutDashboard],
  ['Decision Simulator', '/simulator', SlidersHorizontal],
  ['Forecast Explorer', '/forecasts', Wind],
  ['Accuracy Analysis', '/accuracy', Gauge],
  ['Data Explorer', '/data', Table2],
  ['Methodology & Data', '/methodology', CircleHelp]
] as const;

function Sidebar({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand">
        <div className="brand-mark">
          <Wind size={18} />
        </div>
        <div>
          <strong>
            Aether<span>Grid</span>
          </strong>
          <small>TRADING INTELLIGENCE</small>
        </div>
        <button className="close-nav" onClick={() => setOpen(false)} aria-label="Close navigation">
          <X size={17} />
        </button>
      </div>

      <div className="period">
        <span className="live-dot" /> ANALYSIS PERIOD
        <strong>JAN 2026</strong>
      </div>

      <nav>
        {navItems.map(([label, path, Icon]) => (
          <NavLink
            key={path}
            to={path}
            onClick={() => setOpen(false)}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="source-label">DATA SOURCE</div>
        <div className="source">
          <span className="source-status" />
          Elexon BMRS
          <small>STREAM API</small>
        </div>
        <div className="sidebar-rule" />
        <div className="user">
          <div className="avatar">AG</div>
          <div>
            <strong>Analyst Desk</strong>
            <small>Day-Ahead Procurement</small>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const activeLabel = navItems.find((n) => n[1] === loc.pathname)?.[0] || 'Overview';

  return (
    <div className="app-shell">
      <Sidebar open={open} setOpen={setOpen} />
      <main className="main">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            <span>PORTFOLIO</span>
            <i>/</i>
            <strong>{activeLabel.toUpperCase()}</strong>
          </div>
          <div className="top-actions">
            <div className="date-control">
              <CalendarDays size={15} />
              01 Jan — 31 Jan 2026
            </div>
            <button
              className="refresh-btn"
              onClick={() => window.location.reload()}
              type="button"
            >
              <RefreshCw size={14} />
              Reload
            </button>
          </div>
        </header>

        <div className="content">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/simulator" element={<SimulatorPage />} />
            <Route path="/forecasts" element={<ForecastExplorerPage />} />
            <Route path="/accuracy" element={<AccuracyPage />} />
            <Route path="/data" element={<DataExplorerPage />} />
            <Route path="/methodology" element={<MethodologyPage />} />
          </Routes>

          <footer>
            <span>
              AetherGrid v1.0 / Day-ahead electricity procurement decision support. Not a trading execution engine.
            </span>
            <span>
              Official Source:{' '}
              <a
                href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream"
                target="_blank"
                rel="noopener noreferrer"
              >
                Elexon BMRS API
              </a>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
