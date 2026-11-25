"use client";

import { useState } from "react";
import type { CSSProperties } from "react";

const levels = ["重大风险", "较大风险", "一般风险", "低风险", "未知"];
const colors = ["#b52d47", "#a95515", "#255eae", "#087e77", "#61728a"];
const stagger = (index: number) => ({ "--result-delay": `${Math.min(index, 7) * 60}ms` }) as CSSProperties;
type Row = Record<string, string>;
type Hazard = {
  evidence_id: string; cause_name: string; cause_level: string;
  project_names?: string[]; reasoning?: string;
  evidence?: { document_name: string; page: string }[];
  rectification?: { corrective_actions?: string[] };
};
type Report = {
  projects?: { project_name: string; hazards: Hazard[] }[];
  summary?: { project_count: number; hazard_count: number; highest_risk_level: string };
  warnings?: string[];
};

function rank(level: string) {
  const index = levels.indexOf(level);
  return index < 0 ? levels.length - 1 : index;
}

function Level({ value }: { value: string }) {
  const index = rank(value);
  return <span className="risk-label" style={{ color: colors[index], borderColor: colors[index] }}>{levels[index]}</span>;
}

function RiskChart({ values, selected, select }: {
  values: string[]; selected: string; select: (level: string) => void;
}) {
  return <div className="risk-chart" aria-label="风险等级分布">
    {levels.map((name, index) => {
      const count = values.filter(value => rank(value) === index).length;
      if (index === 4 && count === 0) return null;
      return <button type="button" key={name} className="risk-chart-cell result-reveal" style={stagger(index)} aria-pressed={selected === name}
        onClick={() => select(selected === name ? "" : name)}>
        <span><i style={{ background: colors[index] }} />{name}</span><strong>{count}</strong>
        <span className="risk-track"><i style={{ width: `${count / Math.max(1, values.length) * 100}%`, background: colors[index] }} /></span>
      </button>;
    })}
  </div>;
}

function Metrics({ entries }: { entries: [string, string | number][] }) {
  return <dl className="showcase-metrics">{entries.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>;
}

type GraphEntry = { row: Row; index: number };
const factorKinds = [
  { label: "人员因素", color: "#ab3067", values: ["人员因素", "人", "人员"] },
  { label: "物理因素", color: "#b85c17", values: ["物理因素", "物理", "物"] },
  { label: "环境因素", color: "#128071", values: ["环境因素", "环境"] },
  { label: "管理因素", color: "#657d25", values: ["管理因素", "管理"] },
  { label: "其他 / 未分类", color: "#65758d", values: [] },
];
const factorKind = (value?: string) => factorKinds.find(kind => kind.values.includes(value?.trim() || "")) || factorKinds[4];

function RiskGraph({ entries, selected, select }: {
  entries: GraphEntry[]; selected?: GraphEntry; select: (index: number | null) => void;
}) {
  const arranged = [...entries].sort((a, b) =>
    (a.row.Project_Name || "").localeCompare(b.row.Project_Name || "", "zh-CN") ||
    rank(a.row.Cause_Level) - rank(b.row.Cause_Level) || a.index - b.index);
  const height = Math.max(238, arranged.length * 58 + 48);
  const riskY = (i: number) => height / 2 + (i - (arranged.length - 1) / 2) * 58;
  function shared(field: "Document_Name" | "Project_Name") {
    const grouped = new Map<string, number[]>();
    arranged.forEach(({ row }, i) => {
      const name = row[field]?.trim();
      if (name) grouped.set(name, [...(grouped.get(name) || []), i]);
    });
    const groups = [...grouped].map(([name, indices]) => ({
      name, count: indices.length, y: indices.reduce((sum, i) => sum + riskY(i), 0) / indices.length,
    })).sort((a, b) => a.y - b.y);
    groups.forEach((node, i) => {
      const floor = i ? groups[i - 1].y + 55 : 43;
      node.y = Math.max(floor, Math.min(node.y, height - 43 - (groups.length - i - 1) * 55));
    });
    return new Map(groups.map(node => [node.name, node]));
  }
  const docs = shared("Document_Name");
  const projects = shared("Project_Name");
  const short = (value: string, limit: number) => {
    const chars = Array.from(value);
    return chars.length > limit ? chars.slice(0, limit - 1).join("") + "…" : value;
  };
  const row = selected?.row;
  const edge = (x1: number, y1: number, x2: number, y2: number, kind: string, focus: boolean) => {
    const path = `M ${x1} ${y1} C ${x1 + (x2 - x1) * .48} ${y1}, ${x2 - (x2 - x1) * .48} ${y2}, ${x2} ${y2}`;
    return <>
      <path className={`graph-link ${kind}${focus ? " is-focus" : ""}`} d={path} />
      {focus && <path className="graph-link-flow" d={path} aria-hidden="true" />}
    </>;
  };
  return <section className="relation-card result-reveal" style={stagger(2)} aria-label="抽取关系图谱">
    <header><div><h3>文献关系总览</h3><p>点击危险因素，高亮它的来源与所属项目。</p></div>
      <button type="button" className="graph-reset" onClick={() => select(null)} disabled={!selected}>取消高亮</button></header>
    <div className="graph-layout">
    <div className="graph-scroll" tabIndex={0} role="region" aria-label="可滚动的文献关系图">
      <div className="graph-canvas">
        <div className="graph-lanes">
          <span><i /> 来源文献 <b>{docs.size}</b></span>
          <span><i /> 危险因素 <b>{entries.length}</b></span>
          <span><i /> 工程项目 <b>{projects.size}</b></span>
        </div>
        <svg viewBox={`0 0 920 ${height}`} aria-label="文献、风险与项目的关联节点">
          {arranged.map(({ row: record, index }, i) => {
            const source = docs.get(record.Document_Name?.trim());
            const project = projects.get(record.Project_Name?.trim());
            const focus = index === selected?.index;
            return <g key={index}>
              {source && edge(172, source.y, 330, riskY(i), "source-link", focus)}
              {project && edge(592, riskY(i), 748, project.y, "project-link", focus)}
            </g>;
          })}
          {[...docs.values(), ...projects.values()].map((node, i) => {
            const source = i < docs.size;
            const x = source ? 172 : 748;
            const focus = node.name === (source ? row?.Document_Name : row?.Project_Name)?.trim();
            return <g key={`${source}-${node.name}`} className={`graph-entity ${source ? "source-node" : "project-node"}${focus ? " is-focus" : ""}`}>
              <title>{`${node.name}（${node.count} 条）`}</title>
              <circle className="graph-halo" cx={x} cy={node.y} r="23" />
              <circle cx={x} cy={node.y} r="17" />
              <text className="graph-count" x={x} y={node.y + 5}>{node.count}</text>
              <text className="graph-entity-name" x={x + (source ? -27 : 27)} y={node.y + 5} textAnchor={source ? "end" : "start"}>{short(node.name, 9)}</text>
            </g>;
          })}
          {arranged.map(({ row: record, index }, i) => {
            const y = riskY(i);
            const focus = index === selected?.index;
            const kind = factorKind(record.Cause_Type);
            return <g key={index} className={`graph-risk${focus ? " is-focus" : ""}`} role="button" tabIndex={0}
              aria-pressed={focus} aria-label={`${record.Cause_Name}，${kind.label}，${levels[rank(record.Cause_Level)]}`}
              onClick={() => select(focus ? null : index)}
              onKeyDown={event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(focus ? null : index); } }}>
              <title>{record.Cause_Name}</title>
              <rect x="330" y={y - 21} width="262" height="42" rx="13" />
              <circle cx="352" cy={y} r="9" fill={kind.color} />
              <text x="370" y={y + 5}>{short(record.Cause_Name || "未命名危险因素", 14)}</text>
            </g>;
          })}
        </svg>
      </div>
    </div>
    <aside className="graph-legend" aria-label="图谱颜色图例">
      <h4>图谱图例</h4>
      <p>实体类别</p>
      <ul><li><i style={{ background: "#2866ba" }} />来源文献</li><li><i style={{ background: "#7950b5" }} />工程项目</li></ul>
      <p>危险因素类别</p>
      <ul>{factorKinds.map(kind => <li key={kind.label}><i style={{ background: kind.color }} />{kind.label}</li>)}</ul>
    </aside>
    </div>
    {row && <dl className="graph-meta">
      <div><dt>危险因素</dt><dd>{row.Cause_Name}</dd><dd><Level value={row.Cause_Level} /></dd></div>
      <div><dt>来源文献</dt><dd>{row.Document_Name || "未记录"}</dd><dd>{row.Page || "页码未记录"}</dd></div>
      <div><dt>工程项目</dt><dd>{row.Project_Name || "未分类"}</dd><dd>{row.Cause_Type || "类型未记录"}</dd></div>
    </dl>}
  </section>;
}

export function ExtractionShowcase({ result }: { result: Record<string, unknown> }) {
  const rows = (result.preview || []) as Row[];
  const [level, setLevel] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const shown = rows.map((row, index) => ({ row, index })).filter(({ row }) => !level || levels[rank(row.Cause_Level)] === level);
  const selected = shown.find(item => item.index === open);
  return <section className="showcase" aria-label="知识提取结果">
    <header className="showcase-head"><h2>知识提取结果</h2>
      <Metrics entries={[["抽取记录", Number(result.row_count ?? 0)], ["最高风险", String(result.highest_risk_level || "未知")]]} />
    </header>
    <div className="showcase-body">
      <div className="showcase-subhead"><h3>预览风险分布</h3><span>本次展示 {rows.length} 条</span></div>
      <RiskChart values={rows.map(row => row.Cause_Level)} selected={level} select={setLevel} />
      {shown.length > 0 && <RiskGraph entries={shown} selected={selected} select={setOpen} />}
      <div className="showcase-subhead"><h3>风险清单</h3>{level && <button className="outline-button" onClick={() => setLevel("")}>清除筛选</button>}</div>
      <div className="extracted-cards">{shown.map(({ row, index }, order) => <button type="button" key={index}
        className="extracted-card result-reveal" style={stagger(order)} aria-pressed={index === selected?.index} onClick={() => setOpen(index)}>
        <Level value={row.Cause_Level} /><strong>{row.Cause_Name}</strong><small>{[row.Project_Name, row.Page].filter(Boolean).join(" · ")}</small>
      </button>)}</div>
      {!shown.length && <p className="showcase-empty">当前范围没有抽取记录。</p>}
      {rows.length > 0 && <details className="showcase-details"><summary>查看结构化明细</summary><div className="table-scroll"><table>
        <thead><tr>{["危险因素", "等级", "类型", "项目", "文献", "页码"].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{shown.map(({ row, index }) => <tr key={index}>{[row.Cause_Name, row.Cause_Level, row.Cause_Type, row.Project_Name, row.Document_Name, row.Page].map((value, i) => <td key={i}>{value || "—"}</td>)}</tr>)}</tbody>
      </table></div></details>}
    </div>
  </section>;
}

export function ReasoningShowcase({ result, imageUrl }: { result: Record<string, unknown>; imageUrl?: string }) {
  const report = result as Report;
  const [level, setLevel] = useState("");
  const [showImage, setShowImage] = useState(false);
  const entries = new Map<string, Hazard>();
  for (const project of report.projects || []) for (const hazard of project.hazards || []) {
    const key = hazard.evidence_id || hazard.cause_name;
    const previous = entries.get(key);
    entries.set(key, { ...hazard, project_names: [...new Set([...(previous?.project_names || []), ...(hazard.project_names || []), project.project_name])] });
  }
  const hazards = [...entries.values()].sort((a, b) => rank(a.cause_level) - rank(b.cause_level));
  const shown = hazards.filter(hazard => !level || levels[rank(hazard.cause_level)] === level);
  return <section className="showcase report-showcase" aria-label="整改报告">
    <header className="showcase-head"><h2>风险研判与整改报告</h2>
      <Metrics entries={[["最高风险", report.summary?.highest_risk_level || "未知"], ["工程项目", report.summary?.project_count ?? 0], ["危险因素", hazards.length]]} />
    </header>
    <div className="showcase-body">
      {Boolean(report.warnings?.length) && <details className="report-warning"><summary>处理提示（{report.warnings?.length}）</summary><ul>{report.warnings?.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>}
      <RiskChart values={hazards.map(hazard => hazard.cause_level)} selected={level} select={setLevel} />
      {imageUrl && <div className="report-photo"><button type="button" className="outline-button" onClick={() => setShowImage(!showImage)}>{showImage ? "收起现场图片" : "查看现场图片"}</button>
        {showImage && <a href={imageUrl} target="_blank" rel="noreferrer" aria-label="在新标签页查看原图"><img src={imageUrl} alt="上传的现场资料" /></a>}</div>}
      <div className="showcase-subhead"><h3>整改清单</h3>{level && <button className="outline-button" onClick={() => setLevel("")}>清除筛选</button>}</div>
      {shown.map((hazard, index) => <details className="showcase-details report-card result-reveal" style={stagger(index)} key={hazard.evidence_id || hazard.cause_name}>
        <summary><Level value={hazard.cause_level} /><strong>{hazard.cause_name}</strong><span className="report-projects">{hazard.project_names?.join(" · ")}</span></summary>
        <div className="report-columns"><div><h4>研判依据</h4>{hazard.reasoning && <p>{hazard.reasoning}</p>}
          {hazard.evidence?.length ? <ul className="source-list">{hazard.evidence.map((source, i) => <li key={i}><strong>{source.document_name}</strong><span>{source.page || "页码未记录"}</span></li>)}</ul> : <p>暂无可展示的文献依据。</p>}
        </div><div><h4>整改措施</h4>{hazard.rectification?.corrective_actions?.length
          ? <ol className="action-list">{hazard.rectification.corrective_actions.map((action, i) => <li key={i}>{action}</li>)}</ol>
          : <p>暂无整改措施。</p>}</div></div>
      </details>)}
      {!shown.length && <p className="showcase-empty">当前范围没有危险因素。</p>}
    </div>
  </section>;
}
