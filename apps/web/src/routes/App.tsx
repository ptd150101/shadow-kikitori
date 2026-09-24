import { useLayoutEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ProjectLibraryPage from "../features/projects/ProjectLibraryPage";
import ImportPage from "../features/import-media/ImportPage";
import WorkspacePage from "../features/workspace/WorkspacePage";
import SettingsPage from "../features/settings/SettingsPage";
import DemoPreviewPage from "../features/preview/DemoPreviewPage";
import { api } from "../api/client";

const previewMode = import.meta.env.VITE_PREVIEW_MODE === "true";
const sampleRecent = [
  { id: "sample", title: "Hẹn nhau trước kỳ thi", isSample: true },
  { id: "sample2", title: "Hội thoại tại thư viện", isSample: true },
];

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try { return window.localStorage.getItem("jlpt-studio-theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; /* Storage can be disabled. */ }
  });
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem("jlpt-studio-theme", theme); } catch { /* Theme still works for this session. */ }
  }, [theme]);
  const recent = projects.data?.length
    ? projects.data.slice(0, 2).map((project) => ({ id: project.id, title: project.title, isSample: false }))
    : sampleRecent;
  const reviewTarget = recent[0]?.isSample ? "/preview" : "/projects/" + recent[0]?.id + "/practice";
  const pageTitle = location.pathname === "/settings" ? "Cài đặt" : location.pathname.startsWith("/projects/") ? "Không gian học" : "Thư viện";

  function toggleSidebar() {
    if (window.matchMedia("(max-width: 680px)").matches) setMobileMenuOpen((open) => !open);
    else setSidebarCollapsed((collapsed) => !collapsed);
  }
  function openCreateProject() {
    navigate("/projects?create=1");
    setMobileMenuOpen(false);
  }
  function toggleTheme() {
    setTheme((current) => current === "dark" ? "light" : "dark");
  }

  return (
    <div className={"app-shell" + (sidebarCollapsed ? " sidebar-collapsed" : "") + (mobileMenuOpen ? " mobile-menu-open" : "")}>
      <aside className="sidebar">
        <NavLink className="brand" to="/projects" aria-label="JLPT Listening Studio — thư viện">
          <span className="brand-mark" aria-hidden="true">字</span>
          <span className="brand-copy">
            <strong>LISTENING STUDIO</strong>
            <small>JAPANESE PRACTICE</small>
          </span>
        </NavLink>

        <div className="sidebar-group-label">KHÔNG GIAN HỌC</div>
        <nav className="nav" aria-label="Điều hướng chính">
          <NavLink className="nav-link" to="/projects">
            <span className="nav-icon" aria-hidden="true">▣</span><span className="nav-label">Thư viện</span>
          </NavLink>
          <NavLink className="nav-link" to={reviewTarget}>
            <span className="nav-icon" aria-hidden="true">↻</span><span className="nav-label">Ôn tập</span>{recent.length ? <span className="nav-count">{recent.length}</span> : null}
          </NavLink>
          <button className="nav-link sidebar-create" type="button" onClick={openCreateProject}>
            <span className="nav-icon" aria-hidden="true">+</span><span className="nav-label">Tạo bài học</span>
          </button>
        </nav>

        <div className="sidebar-group-label recent-label">GẦN ĐÂY</div>
        <nav className="nav recent-nav" aria-label="Bài học gần đây">
          {recent.map((item) => <NavLink className="recent-link" key={item.id} to={item.isSample ? "/preview" : "/projects/" + item.id + "/editor"}>
            <span className="recent-dot" aria-hidden="true" />
            <span className="recent-title">{item.title}</span>
          </NavLink>)}
        </nav>

        <div className="sidebar-footer">
          <NavLink className="nav-link" to="/settings"><span className="nav-icon" aria-hidden="true">⚙</span><span className="nav-label">Cài đặt</span></NavLink>
          <div className="sidebar-storage"><span className="storage-dot" /> Lưu trong trình duyệt</div>
          <small>DESIGN PREVIEW · 01</small>
        </div>
      </aside>
      <main className="main">
        <header className="studio-topbar">
          <div className="studio-breadcrumb">
            <button className="studio-menu-button" type="button" aria-label="Thu gọn hoặc mở điều hướng" onClick={toggleSidebar}>☰</button>
            <span>Không gian</span><span className="breadcrumb-separator">›</span><strong>{pageTitle}</strong>
          </div>
          <div className="studio-topbar-actions">
            <span className="studio-preview-badge">INTERACTIVE PREVIEW</span>
            <button className="studio-theme-button" type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"} aria-pressed={theme === "dark"} title={theme === "dark" ? "Giao diện sáng" : "Giao diện tối"}>
              <span aria-hidden="true">{theme === "dark" ? "☼" : "☾"}</span>
            </button>
            <NavLink className="studio-help-button" to="/preview" aria-label="Mở bản xem trước" title="Mở bản xem trước">?</NavLink>
          </div>
        </header>
        <div className="studio-content">{children}</div>
      </main>
    </div>
  );
}

export default function App() {
  const { pathname } = useLocation();
  if (pathname === "/preview") return <DemoPreviewPage />;

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/preview" replace />} />
        <Route path="/projects" element={<ProjectLibraryPage />} />
        <Route path="/projects/:projectId/import" element={<ImportPage />} />
        <Route path="/projects/:projectId/*" element={<WorkspacePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={previewMode ? <DemoPreviewPage /> : <Navigate to="/projects" replace />} />
      </Routes>
    </Shell>
  );
}
