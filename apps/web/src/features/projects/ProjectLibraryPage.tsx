import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { formatDuration } from "../../lib/format";

export default function ProjectLibraryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<"upload" | "youtube">("upload");
  const [sourceUrl, setSourceUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const create = useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}/import`);
    },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "Không thể tạo project"),
  });
  const remove = useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Hãy đặt tên project trước.");
      return;
    }
    if (sourceType === "youtube" && !sourceUrl.trim()) {
      setError("Hãy nhập URL YouTube hoặc chọn Upload.");
      return;
    }
    create.mutate({ title: title.trim(), source_type: sourceType, source_url: sourceUrl.trim() || undefined });
  }

  return (
    <section className="page stack">
      <header className="page-header">
        <div>
          <h1>Thư viện luyện nghe</h1>
          <p className="muted">Import audio đề JLPT hoặc video YouTube, rồi biến chúng thành bài nghe có thể chỉnh sửa.</p>
        </div>
      </header>

      <form className="card card-pad grid two" onSubmit={submit}>
        <label className="label">
          Tên project
          <input className="input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: JLPT N4 聴解 - 2024" />
        </label>
        {sourceType === "youtube" ? <label className="label">YouTube URL<input className="input" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" /></label> : null}
        <label className="label">
          Nguồn đầu tiên
          <select className="select" value={sourceType} onChange={(event) => setSourceType(event.target.value as "upload" | "youtube") }>
            <option value="upload">Upload audio/file video</option>
            <option value="youtube">YouTube URL</option>
          </select>
        </label>
        <div className="row between" style={{ gridColumn: "1 / -1" }}>
          {error ? <span className="notice error">{error}</span> : <span className="muted small">Sau khi tạo, bạn sẽ import media và chọn preset chia đoạn.</span>}
          <button className="button primary" disabled={create.isPending}>{create.isPending ? "Đang tạo…" : "Tạo project"}</button>
        </div>
      </form>

      {projects.isLoading ? <div className="empty">Đang tải project…</div> : null}
      {projects.isError ? <div className="notice error">Không tải được thư viện. Hãy kiểm tra API local.</div> : null}
      {projects.data?.length === 0 ? <div className="card empty">Chưa có project nào. Tạo project đầu tiên ở phía trên.</div> : null}
      <div className="grid three">
        {projects.data?.map((project) => (
          <article className="card card-pad stack" key={project.id}>
            <div className="row between">
              <span className={`badge ${project.status === "ready" ? "ready" : ""}`}>{project.status}</span>
              <span className="muted small">{project.source_type}</span>
            </div>
            <div>
              <h2>{project.title}</h2>
              <p className="muted small">{project.chunk_count} chunks · {formatDuration(project.duration_ms)}</p>
            </div>
            <div className="row wrap">
              <Link className="button primary small" to={project.status === "draft" ? `/projects/${project.id}/import` : `/projects/${project.id}/editor`}>
                {project.status === "draft" ? "Import audio" : "Mở workspace"}
              </Link>
              <button
                className="button danger small"
                onClick={() => {
                  if (window.confirm(`Xóa project “${project.title}” và toàn bộ audio local?`)) remove.mutate(project.id);
                }}
              >
                Xóa
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
