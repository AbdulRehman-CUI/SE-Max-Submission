import { readdir, readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import process from "node:process";

const frontendRoot = resolve(import.meta.dirname, "..");
const expectedBase = "https://se-max-submission-backend.vercel.app";

const buildCommand = process.platform === "win32" ? process.env.ComSpec : "npm";
const buildArguments =
  process.platform === "win32"
    ? ["/d", "/s", "/c", "npm run build"]
    : ["run", "build"];
const build = spawn(
  buildCommand,
  buildArguments,
  {
    cwd: frontendRoot,
    env: { ...process.env, VITE_API_URL: expectedBase },
    stdio: "inherit",
  },
);

const exitCode = await new Promise((resolveExit) => {
  build.on("close", resolveExit);
});
if (exitCode !== 0) process.exit(exitCode ?? 1);

const assets = await readdir(resolve(frontendRoot, "dist", "assets"));
const javascript = assets.filter((file) => file.endsWith(".js"));
const contents = await Promise.all(
  javascript.map((file) =>
    readFile(resolve(frontendRoot, "dist", "assets", file), "utf8"),
  ),
);
const bundle = contents.join("\n");

if (!bundle.includes(expectedBase)) {
  throw new Error(`Production bundle does not contain ${expectedBase}`);
}
if (bundle.includes("https://se-max-submission.vercel.app/api/auth/register")) {
  throw new Error("Production bundle contains a frontend-origin registration URL");
}

globalThis.console.log(`Production API URL verified: ${expectedBase}`);
