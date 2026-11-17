// Capture report screenshots of the running app with headless Edge/Chrome over the
// DevTools protocol (no extra npm packages).  Needs backend (8000) + frontend (3000) running.
//   node docs/capture_screenshots.mjs [username] [password] [prefix] [page,page,...]
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [user = "admin", pass = "Admin@123", prefix = "", only = ""] = process.argv.slice(2);
const BROWSER = process.env.BROWSER_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const OUT = new URL("./screenshots/", import.meta.url);
mkdirSync(OUT, { recursive: true });
const PORT = 9333;
const PAGES = [
  ["dashboard", "/dashboard"], ["employees", "/employees"], ["cards", "/cards"], ["gates", "/gates"],
  ["access_logs", "/access-logs"], ["incidents", "/incidents"], ["incident_detail", "/incidents/7"],
  ["observations", "/observations"], ["reports", "/reports"], ["alerts", "/alerts"], ["query_lab", "/query-lab"],
].filter(([n]) => !only || only.split(",").includes(n));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const proc = spawn(BROWSER, [
  "--headless=new", `--remote-debugging-port=${PORT}`, "--window-size=1440,1000", "--hide-scrollbars",
  `--user-data-dir=${join(tmpdir(), "gs-shots")}`, "about:blank",
], { stdio: "ignore" });

let ws, seq = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((res) => {
  const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params }));
});

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
  await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });

  // log in through the real API, then store the session like the login page does
  const login = await (await fetch("http://localhost:8000/api/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: user, password: pass }),
  })).json();
  await send("Page.navigate", { url: "http://localhost:3000/login" });
  await sleep(2500);
  await send("Runtime.evaluate", { expression: `localStorage.setItem("gatesentry_token", ${JSON.stringify(login.access_token)}); localStorage.setItem("gatesentry_user", ${JSON.stringify(JSON.stringify(login.user))});` });

  for (const [name, path] of PAGES) {
    await send("Page.navigate", { url: `http://localhost:3000${path}` });
    await sleep(3500);
    if (name === "query_lab") {   // open one recursive query so the result is visible
      await send("Runtime.evaluate", { expression: `[...document.querySelectorAll("aside button")].find(b => b.textContent.includes("burst chains"))?.click()` });
      await sleep(1500);
    }
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
    writeFileSync(new URL(`${prefix}${name}.png`, OUT), Buffer.from(data, "base64"));
    console.log("saved", `${prefix}${name}.png`);
  }
  // the login page itself
  await send("Runtime.evaluate", { expression: "localStorage.clear()" });
  await send("Page.navigate", { url: "http://localhost:3000/login" });
  await sleep(2500);
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(new URL(`${prefix}login.png`, OUT), Buffer.from(data, "base64"));
  console.log("saved", `${prefix}login.png`);
} finally {
  ws?.close();
  proc.kill();
}
