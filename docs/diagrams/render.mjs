// Render a local HTML/SVG file to a high-resolution PNG with headless Edge (DevTools protocol).
//   node docs/diagrams/render.mjs <input.html|svg> <output.png> [cssWidth=1600] [scale=2]
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [input, output, width = "1600", scale = "2"] = process.argv.slice(2);
const BROWSER = process.env.BROWSER_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9334 + Math.floor(Math.random() * 500);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(BROWSER, ["--headless=new", `--remote-debugging-port=${PORT}`, "--hide-scrollbars",
  `--user-data-dir=${join(tmpdir(), "gs-render-" + PORT)}`, "about:blank"], { stdio: "ignore" });
let ws, seq = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });

try {
  let target;
  for (let i = 0; i < 40 && !target; i++) {
    await sleep(250);
    try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === "page"); } catch {}
  }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d.result); pending.delete(d.id); } };
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: Number(width), height: 800, deviceScaleFactor: Number(scale), mobile: false });
  await send("Page.navigate", { url: pathToFileURL(resolve(input)).href });
  await sleep(2500);                                   // fonts + CDN scripts
  const { result } = await send("Runtime.evaluate", {
    // height of the real content (not the 800px window), so short pages have no empty space
    expression: `JSON.stringify({w: document.documentElement.scrollWidth,
      h: Math.ceil(Math.max(...[...document.body.children].map(el =>
           el.getBoundingClientRect().bottom + parseFloat(getComputedStyle(el).marginBottom || 0))))})`,
    returnByValue: true });
  const { w, h } = JSON.parse(result.value);
  const { data } = await send("Page.captureScreenshot", {
    format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: h, scale: 1 } });
  writeFileSync(output, Buffer.from(data, "base64"));
  console.log(`saved ${output} (${w}x${h} css px @${scale}x)`);
} finally {
  ws?.close();
  proc.kill();
}
