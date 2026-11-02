// Screenshots of the dashboard for the docs. Needs Chrome started with --remote-debugging-port=9333 and the dashboard on port 8791.
import { writeFileSync } from "node:fs";
const base = "http://127.0.0.1:8791/", out = process.argv[2] || "docs/img";
const t = await (await fetch(`http://127.0.0.1:9333/json/new?${encodeURIComponent(base + "#/sweep")}`, { method: "PUT" })).json();
const ws = new WebSocket(t.webSocketDebuggerUrl); let id = 0; const wait = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (method, params = {}) => new Promise(r => { const i = ++id; wait.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const sleep = ms => new Promise(r => setTimeout(r, ms));
await send("Runtime.enable"); await send("Page.enable");
await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
await send("Emulation.setDeviceMetricsOverride", { width: 1240, height: 860, deviceScaleFactor: 1, mobile: false });
await sleep(1500);
const shots = [["frontier", "#/frontier", 860], ["compare", "#/compare", 860], ["sweep", "#/sweep", 860], ["by-source", "#/source", 860],
  ["drill-down", "#/radar?cat=Power%20deals", 860], ["status", "#/status", 780]];
for (const [name, hash, h] of shots) {
  await send("Runtime.evaluate", { expression: `location.hash=${JSON.stringify(hash)}` });
  await sleep(name == "status" ? 2800 : 1800);
  await send("Emulation.setDeviceMetricsOverride", { width: 1240, height: h, deviceScaleFactor: 1, mobile: false });
  await sleep(200);
  const shown = (await send("Runtime.evaluate", { expression: `document.querySelector("#main").innerText.slice(0,120)`, returnByValue: true })).result.result.value;
  if (/not answering|could not be drawn/.test(shown)) throw new Error(name + ": " + shown);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${out}/${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log(name);
  if (name == "frontier") {
    const box = (await send("Runtime.evaluate", { expression: `(()=>{const b=document.querySelector("#c-front").getBoundingClientRect();return JSON.stringify({x:b.x,y:b.y+scrollY,width:b.width,height:b.height})})()`, returnByValue: true })).result.result.value;
    const c = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { ...JSON.parse(box), scale: 1.5 } });
    writeFileSync(`${out}/frontier-chart.png`, Buffer.from(c.result.data, "base64"));
  }
}
ws.close(); process.exit(0);
