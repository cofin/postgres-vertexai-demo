import { defineConfig } from "vite";
import litestar from "litestar-vite-plugin";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: Number(process.env.VITE_PORT || "5173"),
    cors: true,
    hmr: {
      host: "localhost",
    },
  },
  plugins: [
    litestar({
      input: ["resources/main.js"],
    }),
  ],
  build: {
    rollupOptions: {
      onwarn(warning, warn) {
        if (warning.code === "EVAL" && warning.id?.includes("htmx")) {
          return;
        }
        warn(warning);
      },
    },
  },
  resolve: {
    alias: {
      "@": "/resources",
    },
  },
});
