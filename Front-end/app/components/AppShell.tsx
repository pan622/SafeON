"use client";

import { usePathname } from "next/navigation";

const nav = [
  { href: "/", label: "首页", mark: "⌂" },
  { href: "/extraction", label: "知识抽取", mark: "◫" },
  { href: "/reasoning", label: "知识推理", mark: "◇" },
  { href: "/settings", label: "系统设置", mark: "⚙" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-mark">S</span>
          <span><strong>SafeON</strong><small>智慧安全研判平台</small></span>
        </a>
        <nav className="nav-list" aria-label="主导航">
          {nav.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return <a key={item.href} href={item.href} className={active ? "nav-item active" : "nav-item"}>
              <span className="nav-mark">{item.mark}</span>{item.label}
            </a>;
          })}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />SafeON
          <strong>施工安全知识工作台</strong>
          <small>LLM · FAISS · Neo4j</small>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <span className="eyebrow">SAFETY INTELLIGENCE CONSOLE</span>
          <div className="topbar-right"><span className="live-dot" /> 本地服务</div>
        </header>
        <div className="page-wrap">{children}</div>
      </main>
    </div>
  );
}
