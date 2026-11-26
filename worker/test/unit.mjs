import assert from "node:assert/strict";
import { handle } from "../src/index.js";

const ORIGIN = "https://4858hammad.github.io";
const env = { GROQ_API_KEY: "test-key" };
const req = (body, { origin = ORIGIN, method = "POST", ip = "1.1.1.1" } = {}) =>
  new Request("https://w.test/", { method, headers: { Origin: origin, "CF-Connecting-IP": ip, "content-type": "application/json" }, body: method === "POST" ? JSON.stringify(body) : undefined });
const groq = (text, status = 200) => async () => new Response(JSON.stringify({ choices: [{ message: { content: text } }] }), { status, headers: { "content-type": "application/json" } });
const msg = (c) => ({ messages: [{ role: "user", content: c }] });
let n = 0; const ip = () => `10.0.0.${++n}`;
const t = async (name, fn) => { await fn(); console.log("ok -", name); };

await t("rejects unknown origin", async () => { assert.equal((await handle(req(msg("hi"), { origin: "https://evil.example" }), env, groq("x"))).status, 403); });
await t("OPTIONS preflight for allowed origin", async () => { assert.equal((await handle(req(null, { method: "OPTIONS" }), env)).status, 204); });
await t("503 without key", async () => { assert.equal((await handle(req(msg("hi"), { ip: ip() }), {}, groq("x"))).status, 503); });
await t("bad body", async () => { assert.equal((await handle(req({ messages: [] }, { ip: ip() }), env, groq("x"))).status, 400); });
await t("last message must be user", async () => { assert.equal((await handle(req({ messages: [{ role: "assistant", content: "x" }] }, { ip: ip() }), env, groq("x"))).status, 400); });
await t("returns reply", async () => { const r = await handle(req(msg("What do you build?"), { ip: ip() }), env, groq("Odoo modules.")); assert.equal(r.status, 200); assert.equal((await r.json()).reply, "Odoo modules."); });
await t("redacts key-like strings", async () => { const r = await handle(req(msg("leak"), { ip: ip() }), env, groq("here gsk_abcDEF123 ok")); assert.ok(!(await r.json()).reply.includes("gsk_")); });
await t("upstream 429 -> busy", async () => { const r = await handle(req(msg("busy"), { ip: ip() }), env, groq("", 429)); assert.equal(r.status, 429); });
await t("rate limit per IP", async () => { let last; const who = ip(); for (let i = 0; i < 12; i++) last = await handle(req(msg("q" + i), { ip: who }), env, groq("ok")); assert.equal(last.status, 429); });
await t("key never in response", async () => { const r = await handle(req(msg("hello"), { ip: ip() }), env, groq("fine")); assert.ok(!(await r.text()).includes("test-key")); });
