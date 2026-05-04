import { mkdir, rm } from "node:fs/promises";
import { build } from "esbuild";
import { globSync } from "node:fs";
import { spawn } from "node:child_process";

const outdir = ".tmp/tests";
await rm(outdir, { force: true, recursive: true });
await mkdir(outdir, { recursive: true });

const entryPoints = globSync("tests/**/*.test.ts");
await build({
  entryPoints,
  outdir,
  bundle: true,
  format: "esm",
  platform: "node",
  target: "node22",
  external: ["jsdom"],
  sourcemap: false
});

const builtTests = globSync(`${outdir.replace(/\\/g, "/")}/*.js`);
const child = spawn(process.execPath, ["--test", ...builtTests], { stdio: "inherit", shell: false });
child.on("exit", (code) => {
  process.exit(code ?? 1);
});
