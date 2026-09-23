import { useMemo, useState } from "react";

export type LibraryItem = {
  id: string;
  title: string;
  japanese: string;
  level: string;
  type: "audio" | "video";
  status: string;
  durationLabel: string;
  chunkCount: number;
  progress: number;
  currentChunk: number;
  lastOpenedAt: number;
  isSample: boolean;
};

export default function ProjectLibraryView({
  items,
  sampleMode,
  statusNote,
  onCreate,
  onOpen,
  onRemove,
}: {
  items: LibraryItem[];
  sampleMode: boolean;
  statusNote: string | null;
  onCreate: () => void;
  onOpen: (item: LibraryItem) => void;
  onRemove: (item: LibraryItem) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "audio" | "video">("all");
  const [sort, setSort] = useState<"recent" | "name">("recent");

  const filtered = useMemo(() => {
    const search = query.trim().toLocaleLowerCase("vi");
    const result = items.filter((item) => {
      const matchesSearch = !search || (item.title + " " + item.japanese).toLocaleLowerCase("vi").includes(search);
      const matchesType = filter === "all" || item.type === filter;
      return matchesSearch && matchesType;
    });
    return result.sort((a, b) => sort === "name"
      ? a.title.localeCompare(b.title, "vi")
      : b.lastOpenedAt - a.lastOpenedAt);
  }, [filter, items, query, sort]);

  const active = [...items].sort((a, b) => b.lastOpenedAt - a.lastOpenedAt)[0] ?? null;

  return (
    <section className="page stack library-page" aria-labelledby="library-title">
      <header className="library-page-head">
        <div>
          <p className="library-eyebrow">NGHE · HIỂU · TIẾN BỘ</p>
          <h1 id="library-title">Mình học tiếp nhé.</h1>
          <p>Một chút tập trung mỗi ngày sẽ tạo nên khác biệt.</p>
        </div>
        <button className="button primary library-create-button" type="button" onClick={onCreate}>
          <span className="library-plus" aria-hidden="true">+</span>
          Tạo bài học
        </button>
      </header>

      {active ? (
        <section className="library-feature card" aria-label="Bài học đang học">
          <div className="library-feature-main">
            <span className="badge purple">ĐANG HỌC</span>
            <h2>{active.title}</h2>
            <p className="library-japanese" lang="ja">{active.japanese || "日本語のリスニング"}</p>
            <p>{active.level} · {active.durationLabel} · {active.chunkCount} đoạn · Tiếng Nhật → Tiếng Việt</p>
            <div className="library-feature-actions">
              <button className="button primary" type="button" onClick={() => onOpen(active)}>
                {active.status === "draft" ? "Chuẩn bị bài học" : active.progress > 0 ? "Tiếp tục học" : "Bắt đầu luyện nghe"}
              </button>
              <span className="muted small">Đoạn {String(active.currentChunk).padStart(2, "0")} / {active.chunkCount}</span>
            </div>
          </div>
          <aside className="library-feature-aside">
            <div className="library-progress-heading">
              <span>Tiến độ học</span>
              <strong>{active.progress}%</strong>
            </div>
            <div className="library-progress" role="progressbar" aria-valuenow={active.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Tiến độ bài học">
              <span style={{ width: active.progress + "%" }} />
            </div>
            <span className="muted small">{Math.round((active.chunkCount * active.progress) / 100)} / {active.chunkCount} đoạn đã hoàn thành</span>
            <span className="badge green">{active.status === "draft" ? "Đang chờ media" : "Học liệu sẵn sàng"}</span>
          </aside>
        </section>
      ) : null}

      <div className="library-stat-grid" aria-label="Tổng quan học tập">
        <div className="library-stat card">
          <span>Bài học</span>
          <strong>{String(items.length).padStart(2, "0")}</strong>
          <small>Trong thư viện</small>
        </div>
        <div className="library-stat card">
          <span>Đoạn đã luyện</span>
          <strong>{sampleMode ? "00" : "—"}</strong>
          <small>Nghe chép, điền từ, dịch</small>
        </div>
        <div className="library-stat card">
          <span>Lượt tự làm</span>
          <strong>{sampleMode ? "00" : "—"}</strong>
          <small>Không tính lượt xem đáp án</small>
        </div>
        <div className="library-stat card">
          <span>Cần ôn</span>
          <strong>{sampleMode ? "02" : "—"}</strong>
          <small>Đoạn bạn đã đánh dấu</small>
        </div>
      </div>

      <section className="library-list" aria-labelledby="lesson-list-title">
        <div className="library-section-head">
          <div>
            <h2 id="lesson-list-title">Bài học của bạn <span>· {items.length}</span></h2>
            <p className="muted small">Chọn một bài để tiếp tục luyện nghe.</p>
          </div>
          <div className="library-filters">
            <label className="library-search">
              <span className="sr-only">Tìm bài học</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm bài học…" />
            </label>
            <label>
              <span className="sr-only">Lọc theo loại bài</span>
              <select className="select library-select" value={filter} onChange={(event) => setFilter(event.target.value as "all" | "audio" | "video")}>
                <option value="all">Đang học</option>
                <option value="audio">Audio</option>
                <option value="video">Video</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Sắp xếp bài học</span>
              <select className="select library-select" value={sort} onChange={(event) => setSort(event.target.value as "recent" | "name")}>
                <option value="recent">Gần đây</option>
                <option value="name">Tên A–Z</option>
              </select>
            </label>
          </div>
        </div>

        {filtered.length ? (
          <div className="library-grid">
            {filtered.map((item) => (
              <article className="library-project card" key={item.id}>
                <div className="library-project-top">
                  <span className="badge">{item.level} · {item.type === "video" ? "Video" : "Audio"}</span>
                  {item.isSample ? <span className="library-sample-tag">Bài mẫu</span> : null}
                </div>
                <div>
                  <button className="library-project-title" type="button" onClick={() => onOpen(item)}>{item.title}</button>
                  <p className="library-japanese" lang="ja">{item.japanese}</p>
                  <div className="library-project-meta">
                    <span>{item.durationLabel} · {item.chunkCount} đoạn</span>
                    <span>{Math.round((item.chunkCount * item.progress) / 100)}/{item.chunkCount} đã học</span>
                  </div>
                  <div className="library-progress compact" role="progressbar" aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100} aria-label={"Tiến độ " + item.title}>
                    <span style={{ width: item.progress + "%" }} />
                  </div>
                </div>
                <div className="library-project-foot">
                  <span className={"badge " + (item.status === "ready" ? "green" : "amber")}>
                    {item.status === "ready" ? "Sẵn sàng" : item.status === "draft" ? "Cần hoàn tất" : item.status}
                  </span>
                  <div className="library-card-actions">
                    <button className="button small" type="button" onClick={() => onOpen(item)}>{item.status === "draft" ? "Tiếp tục import" : "Học tiếp"}</button>
                    {!item.isSample ? <button className="button danger small" type="button" onClick={() => onRemove(item)} aria-label={"Xóa " + item.title}>Xóa</button> : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <section className="card library-empty">
            <h3>Chưa tìm thấy bài phù hợp.</h3>
            <p>Thử tìm bằng tên khác hoặc điều chỉnh bộ lọc.</p>
            <button className="button" type="button" onClick={() => { setQuery(""); setFilter("all"); }}>Xóa bộ lọc</button>
          </section>
        )}
      </section>

      {statusNote ? <p className="library-status-note" role="status">{statusNote}</p> : null}
    </section>
  );
}
