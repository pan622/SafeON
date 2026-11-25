"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Model = { id: string; label: string; description: string; requires_api_key: boolean; available: boolean; api_key_configured: boolean; selected: boolean };
type Settings = { selected_model: string; models: Model[] };

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api<Settings>("/settings").then(setSettings).catch(e => setMessage(e.message));
  useEffect(() => { void load(); }, []);
  async function select(model: string) { setBusy(true); setMessage(""); try { setSettings(await api("/settings/model", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model }) })); setMessage("模型选择已保存。"); } catch(e) { setMessage((e as Error).message); } finally { setBusy(false); } }
  async function save(model: string) { setBusy(true); setMessage(""); try { setSettings(await api("/settings/api-key", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, api_key: keys[model] || "" }) })); setKeys(v => ({ ...v, [model]: "" })); setMessage("API Key 已安全保存。"); } catch(e) { setMessage((e as Error).message); } finally { setBusy(false); } }
  async function test(model: string) { setBusy(true); setMessage("正在测试连接…"); try { const result = await api<{message:string}>("/settings/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, api_key: keys[model] || null }) }); setMessage(result.message); } catch(e) { setMessage((e as Error).message); } finally { setBusy(false); } }
  return <section><div className="page-heading"><div><span className="kicker">SYSTEM CONFIGURATION</span><h1>系统设置</h1><p>选择推理模型并配置调用凭证。API Key 不会返回到浏览器。</p></div></div>
    <div className="settings-list">{settings?.models.map(model => <article className={model.selected ? "model-card selected" : "model-card"} key={model.id}>
      <div className="model-head"><div><span className="model-logo">{model.id.startsWith("qwen") ? "Q" : "D"}</span><div><h2>{model.label}</h2><p>{model.description}</p></div></div><button className={model.selected ? "selected-button" : "outline-button"} disabled={busy} onClick={() => select(model.id)}>{model.selected ? "当前使用" : "选择模型"}</button></div>
      <div className="model-meta"><span className={model.available ? "tag green" : "tag amber"}>{model.available ? "已接入" : "接口预留"}</span><span className={model.api_key_configured ? "tag green" : "tag"}>{model.requires_api_key ? (model.api_key_configured ? "凭证已配置" : "需要 API Key") : "本地模型"}</span></div>
      {model.requires_api_key && <div className="key-row"><input type="password" value={keys[model.id] || ""} onChange={e => setKeys(v => ({...v, [model.id]: e.target.value}))} placeholder={model.api_key_configured ? "已保存；输入新 Key 可覆盖" : "输入 DeepSeek API Key"}/><button className="outline-button" disabled={busy || !(keys[model.id] || model.api_key_configured)} onClick={() => test(model.id)}>测试连接</button><button className="primary-button compact" disabled={busy || !keys[model.id]} onClick={() => save(model.id)}>保存</button></div>}
    </article>)}</div>{message && <div className="toast" role="status">{message}</div>}
    <div className="panel security-note"><span>⌁</span><div><h2>凭证安全</h2><p>API Key 由后端系统凭证服务保存，前端仅能查看“是否已配置”，不能读取明文。</p></div></div>
  </section>;
}
