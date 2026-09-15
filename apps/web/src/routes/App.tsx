import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ProjectLibraryPage from "../features/projects/ProjectLibraryPage";
import ImportPage from "../features/import-media/ImportPage";
import WorkspacePage from "../features/workspace/WorkspacePage";
import SettingsPage from "../features/settings/SettingsPage";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>JLPT Listening Studio</strong>
          <small>Local-first listening practice</small>
        </div>
        <nav className="nav" aria-label="Điều hướng chính">
          <NavLink to="/projects">Projects</NavLink>
          <NavLink to="/settings">Model & Settings</NavLink>
        </nav>
        <div className="sidebar-footer">Audio · Transcript · Practice</div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/projects" element={<ProjectLibraryPage />} />
        <Route path="/projects/:projectId/import" element={<ImportPage />} />
        <Route path="/projects/:projectId/*" element={<WorkspacePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </Shell>
  );
}

