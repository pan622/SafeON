"use client";

import { DragEvent, useEffect, useRef, useState } from "react";
import { API_BASE, api, Job } from "../lib/api";
import { ExtractionShowcase, ReasoningShowcase } from "./ResultShowcase";

type Props = { mode: "extraction" | "reasoning"; accept: string; title: string; description: string };
type Item = { file: File; job?: Job; error?: string; phase?: string; startedAt?: number };
const done = (job?: Job) => job?.status === "completed" || job?.status === "failed";
const progressDuration = 10_000;
function displayProgress(entry: Item, clock: number) {
  if (entry.job?.status === "completed") return 100;
  if (!entry.startedAt) return 0;
  return Math.floor(99 * Math.max(0, Math.min(1, (clock - entry.startedAt) / progressDuration)));
}

export function UploadWorkspace({ mode, accept, title, description }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState(0);
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [clock, setClock] = useState(0);
  const [imageUrl, setImageUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const runner = useRef<AbortController | null>(null);
  const active = submitting;
  const item = items[selected];
  const file = item?.file;
  const job = item?.job;
  const runningSince = active ? items.find(entry => entry.startedAt && !done(entry.job) && !entry.error)?.startedAt : undefined;
  useEffect(() => {
    if (!runningSince) return;
    const end = runningSince + progressDuration;
    const tick = () => setClock(Math.min(Date.now(), end));
    tick();
    if (Date.now() >= end) return;
    const timer = setInterval(() => {
      tick();
      if (Date.now() >= end) clearInterval(timer);
    }, 100);
    return () => clearInterval(timer);
  }, [runningSince]);
  useEffect(() => () => runner.current?.abort(), []);

  useEffect(() => {
    if (!file || !/\.(?:png|jpe?g)$/i.test(file.name)) { setImageUrl(""); return; }
    const url = URL.createObjectURL(file);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function choose(files: FileList | null) {
    if (runner.current || !files?.length) return;
    const allowed = accept.toLowerCase().split(",").map(value => value.trim());
    const next = Array.from(files).map(file => ({
      file, error: !allowed.some(ext => file.name.toLowerCase().endsWith(ext)) ? "不支持此文件格式"
        : file.size > 30 * 1024 * 1024 ? "文件超过 30 MB" : undefined,
    }));
    setItems(next); setSelected(0); setMessage("");
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); choose(event.dataTransfer.files);
  }

  async function start() {
    if (!items.length || runner.current) return;
    const controller = new AbortController();
    runner.current = controller;
    const signal = controller.signal;
    const update = (index: number, change: Partial<Item>) => {
      if (!signal.aborted) setItems(current => current.map((entry, i) => i === index ? { ...entry, ...change } : entry));
    };
    setSubmitting(true);
    setMessage("");
    try {
      for (const [index, entry] of items.entries()) {
        if (signal.aborted) break;
        if (entry.error || done(entry.job)) continue;
        let current = entry.job;
        try {
          if (!current) {
            const startedAt = Date.now();
            setClock(startedAt);
            update(index, { phase: "正在提交", startedAt });
            const form = new FormData(); form.append("file", entry.file);
            current = await api<Job>(`/${mode}/jobs`, { method: "POST", body: form, signal });
            update(index, { job: current, phase: undefined });
          }
          let failures = 0;
          while (!done(current) && !signal.aborted) {
            await new Promise(resolve => setTimeout(resolve, 1200));
            if (signal.aborted) break;
            try {
              current = await api<Job>(`/jobs/${current.job_id}`, { signal });
              update(index, { job: current, phase: undefined });
              failures = 0;
            } catch (error) {
              if (signal.aborted) break;
              if (++failures === 3) throw error;
              update(index, { phase: "正在重试读取进度" });
            }
          }
        } catch (error) {
          if (signal.aborted) break;
          const typed = error as Error & { code?: string };
          if (["API_KEY_REQUIRED", "MODEL_NOT_IMPLEMENTED"].includes(typed.code || "")) {
            update(index, { phase: undefined, startedAt: undefined });
            setMessage(typed.message);
            break;
          }
          if (current) {
            update(index, { phase: "状态读取中断" });
            setMessage("无法读取任务状态，队列已暂停。点击继续可查询同一任务，无需重复提交。");
            break;
          }
          update(index, { error: typed.message, phase: undefined });
        }
      }
    } finally {
      if (!signal.aborted) { runner.current = null; setSubmitting(false); }
    }
  }

  const ready = job?.status === "completed";
  const progress = item ? displayProgress(item, clock) : 0;
  const isWaiting = !!item?.startedAt && !item.error && !done(job);
  const progressLabel = item?.phase || job?.stage_message || "正在提交";
  const success = items.filter(entry => entry.job?.status === "completed").length;
  const failed = items.filter(entry => entry.error || entry.job?.status === "failed").length;
  return <section>
    <div className="page-heading"><div><span className="kicker">INTELLIGENT WORKFLOW</span><h1>{title}</h1><p>{description}</p></div><span className="model-pill">DeepSeek · 知识引擎</span></div>
    <div className={`workspace-grid workflow-grid workflow-${mode}`}>
      <div className="panel upload-panel">
          <div className="panel-title"><span>01</span><div><h2>上传待处理文件</h2><p>支持多选，逐份处理 · 单文件最大 30 MB</p></div></div>
        <div className={dragging ? "dropzone dragging" : "dropzone"}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}
          onClick={() => { if (!active) inputRef.current?.click(); }} role="button" tabIndex={0}
          aria-disabled={active} onKeyDown={(event) => { if (!active && ["Enter", " "].includes(event.key)) { event.preventDefault(); inputRef.current?.click(); } }}>
          <input ref={inputRef} type="file" accept={accept} multiple onClick={(event) => event.stopPropagation()} onChange={(e) => { choose(e.target.files); e.target.value = ""; }} hidden />
          <span className="upload-symbol">↑</span>
          <strong>{items.length > 1 ? `已选择 ${items.length} 个文件` : file ? file.name : "拖放文件到这里，或点击浏览"}</strong>
          <small>{items.length > 1 ? "点击重新选择整批文件" : file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : accept.replaceAll(",", " · ").toUpperCase()}</small>
        </div>
        <button className="primary-button" disabled={active || !items.some(entry => !entry.error && !done(entry.job))} onClick={start}>
          {active ? "正在处理…" : items.some(entry => entry.job && !done(entry.job)) ? "继续处理" :
            mode === "extraction" ? "开始知识抽取" : "开始风险研判"}
        </button>
        {message && <div className="alert error" role="alert">{message} <a href="/settings">模型设置</a></div>}
      </div>
      <div className="panel result-panel">
        <div className="panel-title"><span>02</span><div><h2>任务进度与结果</h2></div></div>
        {items.length > 0 && <>
          <p className="batch-summary" aria-live="polite">共 {items.length} 份 · 完成 {success} · 失败 {failed} · 未结束 {items.length - success - failed}</p>
          <ul className="batch-list" aria-label="文件队列">{items.map((entry, index) => <li key={index}>
            <button type="button" aria-pressed={selected === index} onClick={() => setSelected(index)}>
              <strong>{entry.file.name}</strong><span>{entry.error || entry.job?.status === "failed" ? "失败" :
                entry.job?.status === "completed" ? "已完成" : entry.phase === "状态读取中断" ? "已暂停" :
                  entry.startedAt ? `${displayProgress(entry, clock)}%` : "排队中"}</span>
            </button>
          </li>)}</ul>
        </>}
        {item?.error && <div className="alert error">{item.error}</div>}
        {!item && <div className="empty-state"><span>◎</span><strong>等待提交任务</strong></div>}
        {(isWaiting || ready) && <>
          <div className="job-status"><div><strong>{progressLabel}</strong>{job && <small>任务编号 {job.job_id}</small>}</div><b>{progress}%</b></div>
          <div className={`progress${isWaiting && active ? " progress-running" : ""}`} role="progressbar"
            aria-label="任务进度" aria-valuenow={progress} aria-valuetext={`${progress}% · ${progressLabel}`}>
            <i style={{ width: `${progress}%` }} />
          </div>
        </>}
        {job?.error && <div className="alert error">{job.error.message}</div>}
        {ready && <div className="success-card"><span>✓</span><div><strong>处理成功</strong><p>{mode === "extraction" ? `已抽取 ${job.result?.hazard_count ?? 0} 个危险因素` : "风险研判报告已生成"}</p></div></div>}
        {ready && job.download_url && <a className="download-button" href={`${API_BASE.replace("/api/v1", "")}${job.download_url}`}>下载{mode === "extraction" ? " CSV" : " TXT"}结果</a>}
      </div>
    </div>
    {ready && job.result && (mode === "extraction" ? <ExtractionShowcase key={job.job_id} result={job.result} /> : <ReasoningShowcase key={job.job_id} result={job.result} imageUrl={imageUrl} />)}
  </section>;
}
