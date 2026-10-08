import { Link, Route, Routes, useLocation } from "react-router-dom";

import DashboardPage from "./pages/Dashboard";
import ResultsPage from "./pages/Results";
import { API_BASE } from "./services/api";

function Header() {
  const location = useLocation();
  const onHome = location.pathname === "/";

  return (
    <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Link to="/" className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-indigo-500 font-bold text-white">
            G
          </span>
          <span>
            <span className="block text-sm font-semibold leading-tight text-white sm:text-base">
              Geospatial File Measurement API
            </span>
            <span className="block text-xs text-slate-400">
              Measure KML &amp; Shapefile features
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2">
          {!onHome && (
            <Link to="/" className="btn-ghost hidden sm:inline-flex">
              Dashboard
            </Link>
          )}
          <a
            className="btn-ghost"
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            API docs
          </a>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-800 py-5">
      <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <span>Geospatial File Measurement API — FastAPI + React + PostgreSQL</span>
        <span>
          <a className="hover:text-slate-300" href={`${API_BASE}/openapi.json`}>
            OpenAPI spec
          </a>
          <span className="mx-2">·</span>
          <a className="hover:text-slate-300" href={`${API_BASE}/health`}>
            Health
          </a>
        </span>
      </div>
    </footer>
  );
}

function NotFound() {
  return (
    <div className="panel mx-auto max-w-lg p-10 text-center">
      <p className="text-3xl font-semibold text-white">404</p>
      <p className="mt-2 text-sm text-slate-400">That page does not exist.</p>
      <Link to="/" className="btn-primary mt-6">
        Back to dashboard
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/files/:fileId" element={<ResultsPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
