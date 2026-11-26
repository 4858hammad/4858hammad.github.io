// Portfolio chat proxy (Cloudflare Worker).
// The Groq API key lives ONLY here, as the secret GROQ_API_KEY. The website never sees it.
import { MODEL, groqBody } from "./prompt.js";

const MAX_CHARS = 600;        // per message
const MAX_MESSAGES = 5;       // history kept (about 2 turns): Groq free tier allows only 8000 tokens/min
const MAX_TOTAL = 2400;       // total characters accepted per request
const RATE_PER_MIN = 10;      // per IP, per Worker instance (best effort; add a Cloudflare rate-limit rule for a hard cap)
const hits = new Map();

const json = (obj, status, cors) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...cors } });

function allowedOrigin(origin, env) {
  const list = (env.ALLOWED_ORIGINS || "https://4858hammad.github.io").split(",").map((s) => s.trim()).filter(Boolean);
  if (list.includes(origin)) return origin;
  if (env.ALLOW_LOCALHOST === "1" && /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin || "")) return origin;
  return null;
}

function rateLimited(ip) {
  const now = Date.now();
  const arr = (hits.get(ip) || []).filter((t) => now - t < 60000);
  arr.push(now);
  hits.set(ip, arr);
  if (hits.size > 5000) for (const [k, v] of hits) if (!v.some((t) => now - t < 60000)) hits.delete(k);
  return arr.length > RATE_PER_MIN;
}

async function sha(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
}

export async function handle(request, env, fetchImpl = fetch) {
  const origin = request.headers.get("Origin") || "";
  const ok = allowedOrigin(origin, env);
  const cors = ok ? { "access-control-allow-origin": ok, vary: "Origin", "access-control-allow-methods": "POST, OPTIONS", "access-control-allow-headers": "content-type", "access-control-max-age": "86400" } : { vary: "Origin" };
  if (request.method === "OPTIONS") return new Response(null, { status: ok ? 204 : 403, headers: cors });
  if (!ok) return json({ error: "forbidden" }, 403, cors);
  if (request.method !== "POST") return json({ error: "method not allowed" }, 405, cors);
  if (!env.GROQ_API_KEY) return json({ error: "not configured" }, 503, cors);

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (rateLimited(ip)) return json({ error: "too many requests" }, 429, cors);

  let body;
  try { body = await request.json(); } catch { return json({ error: "bad request" }, 400, cors); }
  const raw = Array.isArray(body && body.messages) ? body.messages.slice(-MAX_MESSAGES) : null;
  if (!raw || !raw.length) return json({ error: "bad request" }, 400, cors);
  const messages = [];
  let total = 0;
  for (const m of raw) {
    if (!m || (m.role !== "user" && m.role !== "assistant") || typeof m.content !== "string") return json({ error: "bad request" }, 400, cors);
    const content = m.content.trim().slice(0, MAX_CHARS);
    total += content.length;
    if (content) messages.push({ role: m.role, content });
  }
  if (!messages.length || messages[messages.length - 1].role !== "user") return json({ error: "bad request" }, 400, cors);
  if (total > MAX_TOTAL) return json({ error: "too long" }, 413, cors);

  // Identical first questions (e.g. the suggestion chips) are answered from the edge cache: free and instant.
  const cacheable = messages.length === 1 && typeof caches !== "undefined";
  const cacheKey = cacheable ? new Request("https://cache.portfolio.invalid/chat/" + (await sha(messages[0].content.toLowerCase().replace(/\s+/g, " ")))) : null;
  if (cacheable) { const hit = await caches.default.match(cacheKey); if (hit) return json({ reply: await hit.text(), cached: true }, 200, cors); }

  let res;
  try {
    res = await fetchImpl("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { authorization: `Bearer ${env.GROQ_API_KEY}`, "content-type": "application/json" },
      body: JSON.stringify(groqBody(messages, env.MODEL || MODEL)),
    });
  } catch { return json({ error: "upstream unavailable" }, 502, cors); }
  if (res.status === 429) return json({ error: "busy", retry_after: Math.min(60, Math.ceil(parseFloat(res.headers.get("retry-after")) || 20)) }, 429, cors);
  if (!res.ok) return json({ error: "upstream error" }, 502, cors);
  const data = await res.json().catch(() => null);
  let reply = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
  if (!reply || typeof reply !== "string") return json({ error: "empty reply" }, 502, cors);
  reply = reply.replace(/gsk_[A-Za-z0-9]+/g, "[removed]").trim().slice(0, 2500);
  if (cacheable) await caches.default.put(cacheKey, new Response(reply, { headers: { "cache-control": "public, max-age=86400" } }));
  return json({ reply }, 200, cors);
}

export default { fetch: (request, env) => handle(request, env) };
