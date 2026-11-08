import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Calorific",
        short_name: "Calorific",
        start_url: "/",
        display: "standalone",
        background_color: "#f6f7f4",
        theme_color: "#15803d",
        icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
    }),
  ],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
