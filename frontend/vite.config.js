import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const apiProxyTarget = "http://127.0.0.1:8000";
const desktopBuild = process.env.AGENT_PLAYGROUND_DESKTOP_BUILD === "1";

export default defineConfig({
  base: desktopBuild ? "./" : "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  // npm run preview 默认不走 dev proxy，需要同样转发 /api，否则相对路径 /api/export/... 会 404
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
