import type { Metadata } from "next";
import "./globals.css";
import "./showcase.css";
import { AppShell } from "./components/AppShell";

export const metadata: Metadata = {
  title: "SafeON · 施工安全知识智能研判平台",
  description: "融合大语言模型、向量检索与知识图谱的施工现场安全风险研判平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
