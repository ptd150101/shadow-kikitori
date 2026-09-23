import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { formatDuration } from "../../lib/format";
import ProjectLibraryView, { type LibraryItem } from "./ProjectLibraryView";

const sampleItems: LibraryItem[] = [
  {
    id: "sample",
    title: "Hẹn nhau trước kỳ thi",
    japanese: "試験の前に",
    level: "N4",
    type: "audio",
    status: "ready",
    durationLabel: "1:06",
    chunkCount: 9,
    progress: 0,
    currentChunk: 3,
    lastOpenedAt: 2,
    isSample: true,
  },
  {
    id: "sample2",
    title: "Hội thoại tại thư viện",
    japanese: "図書館で勉強しましょう",
    level: "N4",
    type: "audio",
    status: "ready",
    durationLabel: "0:28",
    chunkCount: 3,
    progress: 0,
    currentChunk: 1,
    lastOpenedAt: 1,
    isSample: true,
  },
];

export default function ProjectLibraryPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<"upload" | "youtube">("upload");
  const [sourceUrl, setSourceUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const mediaQueries = useQueries({
    queries: (projects.data ?? []).map((project) => ({
      queryKey: ["media", project.id],
      queryFn: () => api.listMedia(project.id),
      enabled: project.status !== "draft",
    })),
  });

  useEffect(() => {
    if (searchParams.get("create") !== "1") return;
    setError(null);
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete("create");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const items: LibraryItem[] = projects.data?.length
    ? projects.data.map((project, index) => {
        const sourceAsset = mediaQueries[index]?.data?.find((asset) => asset.kind === "source");
        const mimeType = sourceAsset?.mime_type?.toLowerCase() ?? "";
        const fileName = sourceAsset?.original_name ?? "";
        const isVideo = mimeType.startsWith("video/") || (!mimeType.startsWith("audio/") && /\.(mp4|webm|mov|mkv|avi)$/i.test(fileName));
        const level = project.title.match(/\bN[1-5]\b/i)?.[0]?.toUpperCase() ?? "JLPT";
        return {
          id: project.id,
          title: project.title,
          japanese: "日本語のリスニング",
          level,
          type: isVideo ? "video" : "audio",
          status: project.status,
          durationLabel: formatDuration(project.duration_ms),
          chunkCount: project.chunk_count,
          progress: 0,
          currentChunk: 1,
          lastOpenedAt: project.last_opened_at ? Date.parse(project.last_opened_at) : Date.parse(project.updated_at),
          isSample: false,
        };
      })
    : sampleItems;

  const sampleMode = !projects.data?.length;
  const create = useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate("/projects/" + project.id + "/import");
    },
    onError: (reason) => setError(reason instanceof ApiError ? reason.message : "Không thể tạo bài học."),
  });
  const remove = useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["projects"] }); },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Hãy đặt tên bài học trước.");
      return;
    }
    if (sourceType === "youtube" && !sourceUrl.trim()) {
      setError("Hãy nhập URL YouTube hoặc chọn tải file.");
      return;
    }
    create.mutate({ title: title.trim(), source_type: sourceType, source_url: sourceUrl.trim() || undefined });
  }

  function openItem(item: LibraryItem) {
    if (item.isSample) {
      navigate("/preview");
      return;
    }
    navigate("/projects/" + item.id + (item.status === "draft" ? "/import" : "/editor"));
  }

  function removeItem(item: LibraryItem) {
    if (window.confirm("Xóa bài học “" + item.title + "” và toàn bộ audio local?")) {
      remove.mutate(item.id);
    }
  }

  const statusNote = projects.isError
    ? "Đang xem bài mẫu · API local chưa kết nối"
    : projects.isLoading
      ? "Đang đồng bộ thư viện của bạn…"
      : sampleMode
        ? "Bài mẫu từ bản xem trước · Dữ liệu học sẽ hiện ở đây khi bạn tạo bài"
        : null;

  return (
    <>
      <ProjectLibraryView
        items={items}
        sampleMode={sampleMode}
        statusNote={statusNote}
        onCreate={() => { setError(null); setCreateOpen(true); }}
        onOpen={openItem}
        onRemove={removeItem}
      />
      {createOpen ? (
        <div className="library-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setCreateOpen(false); }}>
          <form className="card library-create-dialog" role="dialog" aria-modal="true" aria-labelledby="create-title" onSubmit={submit}>
            <div className="library-dialog-head">
              <div>
                <p className="library-eyebrow">BẮT ĐẦU TỪ MỘT ĐOẠN NGHE</p>
                <h2 id="create-title">Tạo bài học mới</h2>
              </div>
              <button className="button small" type="button" onClick={() => setCreateOpen(false)}>Đóng</button>
            </div>
            <label className="label">
              Tên bài học
              <input className="input" autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: JLPT N4 聴解 - 2024" />
            </label>
            <label className="label">
              Nguồn đầu tiên
              <select className="select" value={sourceType} onChange={(event) => setSourceType(event.target.value as "upload" | "youtube")}>
                <option value="upload">Tải audio hoặc video</option>
                <option value="youtube">YouTube URL</option>
              </select>
            </label>
            {sourceType === "youtube" ? (
              <label className="label">
                YouTube URL
                <input className="input" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" />
              </label>
            ) : null}
            {error ? <p className="notice error" role="alert">{error}</p> : <p className="muted small">Bạn sẽ tải media và chọn cách chia đoạn ở bước tiếp theo.</p>}
            <div className="library-dialog-actions">
              <button className="button" type="button" onClick={() => setCreateOpen(false)}>Hủy</button>
              <button className="button primary" type="submit" disabled={create.isPending}>{create.isPending ? "Đang tạo…" : "Tạo bài học"}</button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
