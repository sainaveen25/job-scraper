import { cp, mkdir } from "node:fs/promises";
import { build } from "esbuild";

const root = new URL("..", import.meta.url);
const dist = new URL("dist/", root);

await mkdir(dist, { recursive: true });
await Promise.all([
  cp(new URL("manifest.json", root), new URL("manifest.json", dist)),
  cp(new URL("sidepanel/index.html", root), new URL("sidepanel/index.html", dist), { recursive: true }),
  cp(new URL("sidepanel/styles.css", root), new URL("sidepanel/styles.css", dist), { recursive: true }),
  cp(new URL("assets", root), new URL("assets", dist), { recursive: true })
]);

await build({
  entryPoints: {
    "background/service_worker": "background/service_worker.ts",
    "content/content_script": "content/content_script.ts",
    "sidepanel/panel": "sidepanel/panel.tsx"
  },
  outdir: "dist",
  bundle: true,
  format: "esm",
  target: "chrome114",
  sourcemap: false,
  minify: true,
  treeShaking: true,
  legalComments: "none"
});
