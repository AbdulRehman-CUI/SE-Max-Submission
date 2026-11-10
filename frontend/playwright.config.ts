import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: process.env.SPENDSENSE_BROWSER || undefined,
  },
  webServer: {
    command: "npm run dev -- --strictPort",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
  },
});
