import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base "./" so the built page works from the shiori:// scheme (no absolute URLs).
export default defineConfig({ base: "./", plugins: [react()], build: { outDir: "dist", target: "es2022" } });
