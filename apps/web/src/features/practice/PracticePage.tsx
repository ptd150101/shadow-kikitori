import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useAudio } from "../../components/AudioProvider";
import RubyText from "../../components/RubyText";
import type { Attempt, Exercise, ExerciseAnswer } from "../../types/api";

export default function PracticePage({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const [mode, setMode] = useState<"full" | "cloze">("full");
  const [randomize, setRandomize] = useState(false);
  const [blankCount, setBlankCount] = useState(1);
  const [message, setMessage] = useState<string | null>(null);
  const exercises = useQuery({ queryKey: ["exercises", projectId, mode], queryFn: () => api.listExercises(projectId, mode) });
  const generate = useMutation({ mutationFn: () => api.generateExercises(projectId, { mode, settings: { blank_count: blankCount, randomize, seed: Date.now() } }), onSuccess: () => { void client.invalidateQueries({ queryKey: ["exercises", projectId, mode] }); setMessage("Đã tạo session mới."); }, onError: (error) => setMessage(error instanceof ApiError ? error.message : "Không thể tạo bài luyện.") });
  return <section className="stack">
    <div className="card card-pad stack"><div className="row between wrap"><div><h2>Practice mode</h2><p className="muted small">Đáp án được giữ ở server và chỉ trả sau khi bạn bấm kiểm tra/xem đáp án.</p></div><div className="tabs"><button className={mode === "full" ? "active" : ""} onClick={() => setMode("full")}>Điền cả câu</button><button className={mode === "cloze" ? "active" : ""} onClick={() => setMode("cloze")}>Điền chỗ trống</button></div></div><div className="row wrap"><label className="row muted small"><input type="checkbox" checked={randomize} onChange={(event) => setRandomize(event.target.checked)} /> Thứ tự ngẫu nhiên</label>{mode === "cloze" ? <label className="row muted small">Số blank<select className="select" value={blankCount} onChange={(event) => setBlankCount(Number(event.target.value))}>{[1, 2, 3].map((count) => <option value={count} key={count}>{count}</option>)}</select></label> : null}</div><button className="button primary" onClick={() => generate.mutate()} disabled={generate.isPending}>{generate.isPending ? "Đang tạo…" : `Tạo ${mode === "full" ? "full transcript" : "cloze"}`}</button>{message ? <div className="notice">{message}</div> : null}</div>
    {exercises.isLoading ? <div className="card empty">Đang tải bài luyện…</div> : null}
    {exercises.data?.map((exercise, index) => <ExerciseCard key={exercise.id} exercise={exercise} index={index} />)}
    {exercises.data?.length === 0 ? <div className="card empty">Chưa có bài. Hãy tạo session sau khi transcript đã sẵn sàng.</div> : null}
  </section>;
}

function ExerciseCard({ exercise, index }: { exercise: Exercise; index: number }) {
  const audio = useAudio();
  const draftKey = `jlpt-studio:draft:${exercise.id}`;
  const blankCount = exercise.blank_spec.blank_count ?? exercise.blank_spec.blank_token_indexes?.length ?? 1;
  const [answer, setAnswer] = useState(() => { try { return JSON.parse(localStorage.getItem(draftKey) ?? "{}").answer ?? ""; } catch { return ""; } });
  const [blanks, setBlanks] = useState<string[]>(() => { try { const saved = JSON.parse(localStorage.getItem(draftKey) ?? "{}").blanks; return Array.isArray(saved) ? saved : Array(blankCount).fill(""); } catch { return Array(blankCount).fill(""); } });
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [revealed, setRevealed] = useState<ExerciseAnswer | null>(null);
  const [manualIndexes, setManualIndexes] = useState<number[]>(exercise.blank_spec.blank_token_indexes ?? []);
  const [difficult, setDifficult] = useState(exercise.is_difficult);
  const [error, setError] = useState<string | null>(null);
  const submit = async (reveal = false) => {
    setError(null);
    try { const result = await api.submitAttempt(exercise.id, { answer_text: answer, blank_answers: exercise.mode === "cloze" ? blanks : undefined, revealed_answer: reveal }); setAttempt(result); if (result.answer) setRevealed({ exercise_id: exercise.id, chunk_id: exercise.chunk_id, mode: exercise.mode, reference_text: result.answer.reference_text, furigana: result.answer.furigana, translation_vi: result.answer.translation_vi, blank_spec: {}, cloze_expected: result.answer.cloze_expected, reference_confirmed: result.answer.reference_confirmed }); } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể chấm bài."); }
  };
  async function fetchAnswer() { try { setRevealed(await api.getExerciseAnswer(exercise.id)); } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể lấy đáp án."); } }
  const chunk = exercise.chunk;
  useEffect(() => { localStorage.setItem(draftKey, JSON.stringify({ answer, blanks })); }, [answer, blanks, draftKey]);
  const submitOnShortcut = (event: React.KeyboardEvent) => { if (!event.nativeEvent.isComposing && (event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); void submit(); } };
  return <article className="card card-pad practice-card stack"><div className="row between"><div><span className="badge">#{index + 1} · {exercise.mode === "full" ? "Điền cả câu" : `${blankCount} chỗ trống`}</span><h3>Nghe và nhập câu tiếng Nhật</h3></div><button className="button small" onClick={() => chunk && void audio.playRange(chunk.start_ms, chunk.end_ms, true)} disabled={!chunk}>Loop audio</button></div><p className="muted small">Transcript, furigana và bản dịch sẽ hiện sau khi kiểm tra hoặc bấm “Xem đáp án”. Ctrl/⌘+Enter để chấm nhanh sau khi IME đã commit.</p>{exercise.mode === "cloze" ? <div className="cloze-inputs">{Array.from({ length: blankCount }, (_, item) => <input className="input" key={item} value={blanks[item] ?? ""} onChange={(event) => setBlanks((current) => current.map((value, indexValue) => indexValue === item ? event.target.value : value))} onKeyDown={submitOnShortcut} placeholder={`Đáp án ${item + 1}`} />)}</div> : <textarea className="textarea" value={answer} onChange={(event) => setAnswer(event.target.value)} onKeyDown={submitOnShortcut} placeholder="Nhập toàn bộ transcript tiếng Nhật…" /> }<div className="row wrap"><button className="button primary" onClick={() => void submit()} disabled={Boolean(attempt?.revealed_answer)}>Kiểm tra</button><button className="button" onClick={() => void fetchAnswer()}>Xem đáp án</button><button className="button ghost" onClick={() => void submit(true)}>Hiện và ghi nhận</button><button className={`button ${difficult ? "primary" : ""}`} onClick={() => { const next = !difficult; void api.updateExercise(exercise.id, { is_difficult: next }).then(() => setDifficult(next)); }}>{difficult ? "Bỏ đánh dấu khó" : "Đánh dấu khó"}</button></div>{error ? <div className="notice error">{error}</div> : null}{attempt ? <Result attempt={attempt} answer={revealed} /> : null}{revealed && exercise.mode === "cloze" ? <ManualBlankEditor answer={revealed} indexes={manualIndexes} onChange={setManualIndexes} onSave={(next) => { void api.updateExercise(exercise.id, { blank_spec: { blank_token_indexes: next } }); }} /> : null}{revealed && !attempt ? <Answer answer={revealed} /> : null}</article>;
}

function Result({ attempt, answer }: { attempt: Attempt; answer: ExerciseAnswer | null }) { return <div className="answer-card"><div className="row between"><strong>Điểm forgiving</strong><span className="score">{attempt.score == null ? "—" : `${attempt.score.toFixed(1)}%`}</span></div><p className="muted small">Strict: {attempt.strict_score == null ? "—" : `${attempt.strict_score.toFixed(1)}%`} · {attempt.revealed_answer ? "đã xem đáp án" : "chưa xem đáp án"}</p><Diff diff={attempt.diff} />{answer ? <Answer answer={answer} /> : null}</div>; }
function Diff({ diff }: { diff: Attempt["diff"] }) { return <div className="diff">{diff.map((item, index) => <span key={index} className={`diff-${item.kind}`}>{item.text ?? item.actual ?? item.expected ?? ""}</span>)}</div>; }
function Answer({ answer }: { answer: ExerciseAnswer }) { const indexes = answer.blank_spec.blank_token_indexes ?? []; const tokenAnswers = indexes.map((index) => answer.blank_spec.tokens?.[index]?.surface).filter(Boolean) as string[]; const expected = answer.cloze_expected?.length ? answer.cloze_expected : tokenAnswers; return <div className="answer-card"><div className="row between"><strong>Đáp án</strong><span className={`badge ${answer.reference_confirmed ? "ready" : "stale"}`}>{answer.reference_confirmed ? "User confirmed" : "AI unverified"}</span></div><RubyText tokens={answer.furigana} fallback={answer.reference_text} /><p className="translation">{answer.translation_vi || "Chưa có bản dịch"}</p>{answer.mode === "cloze" && expected.length ? <p className="muted small">Từ điền: {expected.join(" · ")}</p> : null}</div>; }
function ManualBlankEditor({ answer, indexes, onChange, onSave }: { answer: ExerciseAnswer; indexes: number[]; onChange: (indexes: number[]) => void; onSave: (indexes: number[]) => void }) { const tokens = answer.blank_spec.tokens ?? answer.furigana ?? []; if (!tokens.length) return null; return <div className="manual-blank"><div className="row between"><strong>Chọn blank thủ công</strong><button className="button small" onClick={() => onSave(indexes)}>Lưu blank</button></div><div className="token-picker">{tokens.map((token, index) => <button type="button" className={`token-chip ${indexes.includes(index) ? "selected" : ""}`} key={`${token.surface}-${index}`} onClick={() => onChange(indexes.includes(index) ? indexes.filter((item) => item !== index) : [...indexes, index].sort((left, right) => left - right))}>{token.surface}</button>)}</div></div>; }
