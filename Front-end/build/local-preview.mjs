// Local Node preview for the FastAPI-backed application.
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";

// Vite probes Windows mapped drives through a shell. This checkout uses a
// local drive, so the sandbox can use Vite's normal no-mapping fallback.
if (process.platform === "win32") {
  const exec = cp.exec;
  cp.exec = function (command, ...args) {
    if (command === "net use") {
      queueMicrotask(() => args.at(-1)?.(null, "", ""));
      return;
    }
    return exec.call(this, command, ...args);
  };
  syncBuiltinESMExports();
}

const { default: vinext } = await import("vinext");
const { createBuilder, createServer } = await import("vite");
const config = {
  configFile: false,
  plugins: [vinext()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
};
if (process.argv.includes("--build")) {
  const builder = await createBuilder({ ...config, build: { outDir: "dist-local" } });
  await builder.buildApp();
} else {
  const server = await createServer(config);
  await server.listen();
  server.printUrls();
}
