"use client";

import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { api } from "./lib/api";

type Stats = { document_count: number; entity_count: number; relationship_count: number; project_count: number; factor_count: number; factor_distribution: Record<string, number>; risk_distribution?: Record<string, number> };
const fallback: Stats = { document_count: 0, entity_count: 0, relationship_count: 0, project_count: 0, factor_count: 0, factor_distribution: {} };

const riskColors: Record<string, string> = { "重大风险": "#b52d47", "较大风险": "#a95515", "一般风险": "#255eae", "低风险": "#087e77" };
const factorColors: Record<string, string> = { "人员因素": "#ab3067", "物理因素": "#b85c17", "环境因素": "#128071", "管理因素": "#657d25" };
const counts = new Intl.NumberFormat("zh-CN");
const percents = new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 1 });

type MetricKind = "entity" | "relation" | "document" | "project";

function MetricIcon({ kind }: { kind: MetricKind }) {
  const glyphs = {
    entity: <><path d="M32 25 21 41h22L32 25Z" /><circle cx="32" cy="23" r="3.5" /><circle cx="20" cy="42" r="3.5" /><circle cx="44" cy="42" r="3.5" /></>,
    relation: <><path d="m29 35 6-6m0-4 3-3a5.7 5.7 0 0 1 8 8l-5 5a5.7 5.7 0 0 1-7.2.7M29 39l-3 3a5.7 5.7 0 0 1-8-8l5-5a5.7 5.7 0 0 1 7.2-.7" /></>,
    document: <><path d="M25 20h12l5 5v19H22V20h3Zm12 0v6h5M27 32h10m-10 6h10" /></>,
    project: <><path d="M20 44h24M23 44V26h11v18m0-12h7v12M27 31h3m-3 5h3m7 1h2" /></>,
  };
  return <span className={`metric-emblem metric-emblem-${kind}`} aria-hidden="true">
    <svg viewBox="0 0 64 64" fill="none">
      <circle className="metric-ring-base" cx="32" cy="32" r="27" />
      <circle className="metric-ring-inner" cx="32" cy="32" r="21" />
      <g className="metric-sweep">
        <path d="M32 5a27 27 0 0 1 27 27M32 59A27 27 0 0 1 5 32" />
        <circle cx="59" cy="32" r="2.4" />
      </g>
      <g className="metric-glyph">{glyphs[kind]}</g>
    </svg>
  </span>;
}

function Distribution({ title, values, risk = false, loading }: { title: string; values: Record<string, number>; risk?: boolean; loading: boolean }) {
  const chart = useRef<HTMLElement>(null);
  const [mode, setMode] = useState<"count" | "share">("count");
  const [progress, setProgress] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const palette = risk ? riskColors : factorColors;
  const items = Object.entries(values).filter(([, value]) => Number.isFinite(value) && value >= 0);
  const hasData = items.length > 0;
  const ordered = [...items].sort(([a], [b]) => {
    const order = Object.keys(palette);
    const index = (name: string) => order.includes(name) ? order.indexOf(name) : order.length;
    return index(a) - index(b);
  });
  const total = items.reduce((sum, [, count]) => sum + count, 0);
  const max = Math.max(1, ...items.map(([, count]) => count));
  const selection = items.find(([name]) => name === selected);

  useEffect(() => {
    if (!hasData) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduced.matches) { setProgress(1); return; }
    let frame = 0;
    let observer: IntersectionObserver | undefined;
    function play() {
      const start = performance.now();
      function step(now: number) {
        const t = reduced.matches ? 1 : Math.min(1, (now - start) / 850);
        setProgress(1 - (1 - t) ** 3);
        if (t < 1) frame = requestAnimationFrame(step);
      }
      frame = requestAnimationFrame(step);
    }
    if (chart.current && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) { observer?.disconnect(); play(); }
      }, { threshold: 0.2 });
      observer.observe(chart.current);
    } else play();
    return () => { observer?.disconnect(); cancelAnimationFrame(frame); };
  }, [hasData]);

  return <article className="panel dashboard-chart" ref={chart} aria-label={title}>
    <header className="dashboard-chart-head">
      <div><h2>{title}</h2><p>{loading ? "正在读取知识库" : hasData ? `统计合计 ${counts.format(total)} 条` : "暂无统计数据"}</p></div>
      <div className="dashboard-mode" role="group" aria-label={`${title}显示方式`}>
        <button type="button" disabled={!hasData} aria-pressed={mode === "count"} onClick={() => setMode("count")}>数量</button>
        <button type="button" disabled={!hasData} aria-pressed={mode === "share"} onClick={() => setMode("share")}>占比</button>
      </div>
    </header>
    {hasData && <>
      <div className={`bars${progress === 1 ? " bars-ready" : ""}`}>
        {ordered.map(([name, count]) => {
          const share = total ? count / total : 0;
          const bar = mode === "count" ? count / max : share;
          const style = { "--bar-color": palette[name] || "#61728a", "--bar-width": `${bar * progress * 100}%` } as CSSProperties;
          return <button type="button" className="bar-row" key={name} style={style}
            aria-pressed={selected === name} aria-label={`${name}，${counts.format(count)} 条，占比 ${percents.format(share)}`}
            onClick={() => setSelected(selected === name ? null : name)}>
            <span className="dashboard-bar-name"><i />{name}</span>
            <span className="dashboard-bar-track" aria-hidden="true"><i /></span>
            <b aria-hidden="true">{mode === "count" ? counts.format(Math.round(count * progress)) : percents.format(share * progress)}</b>
          </button>;
        })}
      </div>
      {selection && <footer className="dashboard-chart-note" aria-live="polite">
        <strong>{selection[0]}</strong><span>{counts.format(selection[1])} 条 · 占 {percents.format(total ? selection[1] / total : 0)}</span>
      </footer>}
    </>}
  </article>;
}

export default function Home() {
  const [stats, setStats] = useState(fallback);
  const [online, setOnline] = useState<boolean | null>(null);
  const [iconsVisible, setIconsVisible] = useState(false);
  const metrics = useRef<HTMLDivElement>(null);
  useEffect(() => { api<Stats>("/home/stats").then(value => { setStats(value); setOnline(true); }).catch(() => setOnline(false)); }, []);
  useEffect(() => {
    if (!metrics.current || typeof IntersectionObserver === "undefined") { setIconsVisible(true); return; }
    const observer = new IntersectionObserver(entries => {
      setIconsVisible(entries.some(entry => entry.isIntersecting));
    }, { threshold: .25 });
    observer.observe(metrics.current);
    return () => observer.disconnect();
  }, []);
  const cards = [
    ["知识实体", stats.entity_count, "NEO4J NODES", "entity"],
    ["图谱关系", stats.relationship_count, "GRAPH EDGES", "relation"],
    ["安全文献", stats.document_count, "DOCUMENTS", "document"],
    ["工程项目", stats.project_count, "PROJECT TYPES", "project"],
  ] as const;
  return <section>
    <div className="hero">
      <img src="/safeon-hero.png" alt="数字化施工现场安全管理" />
      <div className="hero-overlay" />
      <div className="hero-copy">
        <div className="hero-wordmark">
          <span className="hero-logo"><img src="/safeon-brand-reference.png" alt="SafeON" width="237" height="124" /></span>
          <div className="hero-brand-text">
            <h1>施工安全知识智能研判平台</h1>
          </div>
        </div>
        <p className="hero-brand-english" lang="en">Safety Intelligence Always <strong>ON</strong></p>
        <ul className="hero-advantages">
          <li><strong>核心功能</strong><span>知识提取、风险研判</span></li>
          <li><strong>多模态适配</strong><span>支持文本与图像</span></li>
          <li><strong>双端支持</strong><span>适配电脑与手机</span></li>
        </ul>
        <div className="hero-actions"><a className="primary-button compact" href="/settings">配置 API Key</a></div>
      </div>
      <div className="hero-badge"><span className={online ? "live-dot" : "status-dot offline"} />{online === null ? "正在读取图谱" : online ? "知识图谱实时连接" : "图谱暂不可用"}</div>
    </div>
    <div className={`metric-grid home-metrics${iconsVisible ? " icons-visible" : ""}`} ref={metrics}>
      {cards.map(([label, value, cap, kind]) => <div className="metric-card" key={kind}>
        <MetricIcon kind={kind} />
        <div className="metric-card-copy"><small>{cap}</small><strong>{online ? counts.format(value) : "—"}</strong><p>{label}</p></div>
      </div>)}
    </div>
    <div className="dashboard-grid">
      <Distribution title="危险因素结构" values={stats.factor_distribution} loading={online === null} />
      <Distribution title="知识库风险等级" values={stats.risk_distribution || {}} loading={online === null} risk />
    </div>
    <nav className="workflow-entries icons-visible" aria-label="核心功能">
      <a className="workflow-entry entry-extraction" href="/extraction">
        <MetricIcon kind="document" /><div><span>KNOWLEDGE EXTRACTION</span><h2>知识提取</h2></div>
      </a>
      <a className="workflow-entry entry-reasoning" href="/reasoning">
        <MetricIcon kind="relation" /><div><span>RISK REASONING</span><h2>风险研判</h2></div>
      </a>
    </nav>
  </section>;
}
