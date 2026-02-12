import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = (env.VITE_BASE_PATH || "/").trim();
  const normalizedBase = basePath.endsWith("/") ? basePath : `${basePath}/`;

  return {
    base: normalizedBase,
    plugins: [react()],
    test: {
      environment: "jsdom",
      globals: true
    }
  };
});
