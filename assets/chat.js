/* Chat widget for the portfolio. Two transports:
   - proxy (recommended): a Cloudflare Worker (worker/) holds the AI key, so the key is never on this site;
   - direct: the key comes from a GitHub Actions secret at build time (camouflaged, NOT secret: anyone can read it in DevTools).
   It only appears when the site was built with window.HA_CHAT. */
(function () {
  var cfg = window.HA_CHAT;
  if (!cfg || !(cfg.endpoint || (cfg.mode === 'direct' && cfg.k))) return;
  var d = document, KEY = 'ha_chat_v1', MAX_KEEP = 12;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var site = (cfg.site || location.origin).replace(/\/$/, '');
  var rootPath = (function () { var s = d.querySelector('script[src*="assets/chat.js"]'); return s ? s.getAttribute('src').replace('assets/chat.js', '') : ''; })();

  var GREETING = 'Hi! I can answer questions about Hammad\'s Odoo projects, skills, experience and availability, or the apps he has published. What would you like to know?';
  var CHIPS = ['What Odoo projects has Hammad delivered?', 'Which Odoo versions does he work with?', 'Does he have manufacturing experience?', 'How can I hire him?'];
  var history = [];
  try { history = JSON.parse(sessionStorage.getItem(KEY) || '[]').filter(function (m) { return m && typeof m.content === 'string' && (m.role === 'user' || m.role === 'assistant'); }); } catch (e) {}
  var busy = false;

  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };
  var safeUrl = function (u) {
    u = u.trim();
    if (u.indexOf(site) === 0 || u.indexOf('https://neuralbytea.github.io/') === 0 || u.indexOf('https://apps.odoo.com/') === 0 || /^\/(?!\/)/.test(u)) return u;
    return null;
  };
  var inline = function (t) {
    t = esc(t);
    t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (m, label, url) {
      var u = safeUrl(url.replace(/&amp;/g, '&'));
      return u ? '<a href="' + esc(u) + '"' + (u.indexOf(site) === 0 || u.charAt(0) === '/' ? '' : ' target="_blank" rel="noopener"') + '>' + label + '</a>' : label;
    });
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return t;
  };
  // Small, safe markdown subset: paragraphs, bullet/numbered lists, tables, bold, allowed links.
  var render = function (src) {
    var lines = String(src).replace(/\r/g, '').split('\n'), out = '', list = null, tbl = [];
    var closeList = function () { if (list) { out += '</' + list + '>'; list = null; } };
    var flushTbl = function () {
      if (!tbl.length) return;
      var rows = tbl.filter(function (r) { return !/^\s*\|?[\s:|-]+\|?\s*$/.test(r); }).map(function (r) { return r.replace(/^\s*\||\|\s*$/g, '').split('|').map(function (c) { return c.trim(); }); });
      var head = rows.shift() || [];
      var skip = head.map(function (h) { return /^(link|page|url|store)/i.test(h); });
      // a table is too wide for a chat bubble: show every row as a small card (title, details, link)
      out += '<div class="hac-cards">' + rows.map(function (r) {
        var link = null;
        r.forEach(function (c) { var m = c.match(/\[[^\]]+\]\(([^)\s]+)\)/); if (m && !link && safeUrl(m[1])) link = safeUrl(m[1]); });
        var plain = function (c) { return c.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/\*\*/g, ''); };
        var title = plain(r[0] || ''), meta = r.slice(1).filter(function (c, i) { return !skip[i + 1] && c && plain(c) !== title; }).map(plain);
        var body = '<b>' + esc(title) + '</b>' + (meta.length ? '<span>' + meta.map(esc).join(' · ') + '</span>' : '');
        return link ? '<a class="hac-card" href="' + esc(link) + '"' + (link.indexOf(site) === 0 || link.charAt(0) === '/' ? '' : ' target="_blank" rel="noopener"') + '>' + body + '<i>View →</i></a>' : '<div class="hac-card">' + body + '</div>';
      }).join('') + '</div>';
      tbl = [];
    };
    lines.forEach(function (ln) {
      if (/^\s*\|/.test(ln)) { closeList(); tbl.push(ln); return; }
      flushTbl();
      var b = ln.match(/^\s*[-*•]\s+(.*)/), n = ln.match(/^\s*\d+[.)]\s+(.*)/);
      if (b || n) { var tag = b ? 'ul' : 'ol'; if (list !== tag) { closeList(); out += '<' + tag + '>'; list = tag; } out += '<li>' + inline((b || n)[1]) + '</li>'; return; }
      closeList();
      if (ln.trim()) out += '<p>' + inline(ln) + '</p>';
    });
    flushTbl(); closeList();
    return out;
  };

  // ---- DOM
  var root = d.createElement('div'); root.className = 'hac';
  root.innerHTML =
    '<button class="hac-fab" type="button" aria-label="Open chat assistant" aria-expanded="false"><svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true"><path fill="currentColor" d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/></svg><span>Ask AI</span></button>' +
    '<section class="hac-panel" role="dialog" aria-label="Portfolio assistant" hidden>' +
    '<header><img src="' + esc(rootPath) + 'assets/images/mark-512.png" alt="" width="34" height="34"><div><b>Hammad\'s Assistant</b><small>Ask about projects, skills or hiring</small></div>' +
    '<button type="button" class="hac-new" title="Start a new chat" aria-label="Start a new chat">↺</button><button type="button" class="hac-x" aria-label="Close chat">×</button></header>' +
    '<div class="hac-log" role="log" aria-live="polite"></div>' +
    '<div class="hac-chips"></div>' +
    '<form class="hac-form"><textarea rows="1" maxlength="500" placeholder="Type your question…" aria-label="Your question"></textarea><button type="submit" aria-label="Send"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M3 20.5v-6l9-2.5-9-2.5v-6L22 12z"/></svg></button></form>' +
    '<p class="hac-note">AI answers can be wrong: check the project pages or the CV. Please do not share passwords or private data.</p></section>';
  d.body.appendChild(root);
  var $ = function (s) { return root.querySelector(s); };
  var fab = $('.hac-fab'), panel = $('.hac-panel'), log = $('.hac-log'), chips = $('.hac-chips'), form = $('.hac-form'), ta = form.querySelector('textarea');

  var save = function () { try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-MAX_KEEP))); } catch (e) {} };
  var scroll = function () { log.scrollTop = log.scrollHeight; };
  var bubble = function (role, html) { var el = d.createElement('div'); el.className = 'hac-m hac-' + role; el.innerHTML = html; log.appendChild(el); scroll(); return el; };
  var drawAll = function () {
    log.innerHTML = '';
    bubble('bot', render(GREETING));
    history.forEach(function (m) { bubble(m.role === 'user' ? 'me' : 'bot', m.role === 'user' ? '<p>' + esc(m.content) + '</p>' : render(m.content)); });
    chips.hidden = history.length > 0;
  };
  chips.innerHTML = CHIPS.map(function (c) { return '<button type="button">' + esc(c) + '</button>'; }).join('');

  var open = function (on) {
    panel.hidden = !on; fab.setAttribute('aria-expanded', on ? 'true' : 'false'); root.classList.toggle('open', on);
    if (on) { drawAll(); setTimeout(function () { ta.focus(); }, reduce ? 0 : 150); } else fab.focus();
  };
  fab.addEventListener('click', function () { open(panel.hidden); });
  $('.hac-x').addEventListener('click', function () { open(false); });
  d.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) open(false); });
  $('.hac-new').addEventListener('click', function () { history = []; save(); drawAll(); });
  chips.addEventListener('click', function (e) { if (e.target.tagName === 'BUTTON') send(e.target.textContent); });

  var fail = function (html) { bubble('bot hac-err', html); };
  // Two transports with the same result shape {status, j:{reply, retry_after}}:
  //  - proxy: our Cloudflare Worker holds the key (recommended)
  //  - direct: GitHub-Pages-only; the key was injected at build time from a CI secret (camouflaged, not secret)
  var brain = null, lastCall = 0, lastQuestion = '';
  var groqKey = function () { try { return atob(cfg.k.join('')).split('').reverse().join(''); } catch (e) { return ''; } };
  var loadBrain = function () {
    // never cache a failed import: a transient failure must not break the chat until the page is reloaded
    brain = brain || import('./chat/prompt.js').catch(function (err) { brain = null; err.nbWhy = 'script'; throw err; });
    return brain;
  };
  // Every outcome has the same shape {status, j:{reply, retry_after}} or {why, detail} for failures that never got an HTTP answer.
  var fetchFail = function (err) { return { why: err && err.name === 'AbortError' ? 'timeout' : (err && err.nbWhy) || 'network', detail: String(err && (err.name + ': ' + err.message) || err) }; };
  var ask = function (msgs, signal) {
    if (!cfg.endpoint) {
      var wait = 3000 - (Date.now() - lastCall);
      if (wait > 0) return Promise.resolve({ status: 429, j: { retry_after: Math.ceil(wait / 1000) }, soft: true });
      lastCall = Date.now();
      return loadBrain().then(function (m) {
        var clean = msgs.map(function (x) { return { role: x.role, content: String(x.content).slice(0, 600) }; });
        return fetch('https://api.groq.com/openai/v1/chat/completions', { method: 'POST', signal: signal,
          headers: { authorization: 'Bearer ' + groqKey(), 'content-type': 'application/json' }, body: JSON.stringify(m.groqBody(clean, cfg.model)) })
          .then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (j) {
              var text = j && j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
              var api = j && j.error && (j.error.message || j.error.code) || '';
              return { status: r.status === 200 && !text ? 502 : r.status, detail: 'HTTP ' + r.status + (api ? ' ' + String(api).slice(0, 120) : ''),
                j: { reply: text ? String(text).replace(/gsk_[A-Za-z0-9]+/g, '[removed]').trim().slice(0, 2500) : '', retry_after: Math.min(60, Math.ceil(parseFloat(r.headers.get('retry-after')) || 20)) } };
            });
          });
      }).catch(fetchFail);
    }
    return fetch(cfg.endpoint, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ messages: msgs }), signal: signal })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, j: j, detail: 'HTTP ' + r.status }; }); })
      .catch(fetchFail);
  };
  var contactLink = '<a href="' + esc(rootPath) + 'contact.html">contact form</a>';
  // Turn a failed outcome into a clear message for the visitor (plus a technical line for support)
  var explain = function (x) {
    var m, det = x.detail ? '<small class="hac-det">Details: ' + esc(x.detail) + '</small>' : '';
    if (x.why === 'timeout') m = 'The assistant took too long to answer.';
    else if (x.why === 'script') m = 'A chat file could not be loaded. Please refresh the page (Ctrl+Shift+R) and try again.';
    else if (x.why === 'network') m = 'Your browser could not connect to the AI service (api.groq.com). This is usually a network, VPN, firewall or ad-blocker setting.';
    else if (x.status === 401 || x.status === 403) m = 'The assistant\'s access key was rejected, so it cannot answer right now.';
    else if (x.status === 404 || x.status === 400) m = 'The assistant is misconfigured at the moment.';
    else if (x.status >= 500) m = 'The AI service is having a temporary problem.';
    else m = 'Sorry, the assistant is not available right now.';
    try { console.error('[Portfolio chat]', x.why || x.status, x.detail || ''); } catch (e) {}
    return '<p>' + m + '</p>' + det + '<p><button type="button" class="hac-retry">Try again</button> or use the ' + contactLink + '.</p>';
  };
  var send = function (text) {
    text = String(text || '').trim().slice(0, 500);
    if (!text || busy) return;
    busy = true; form.classList.add('busy'); chips.hidden = true; lastQuestion = text;
    history.push({ role: 'user', content: text }); save();
    bubble('me', '<p>' + esc(text) + '</p>');
    var typing = bubble('bot hac-typing', '<span></span><span></span><span></span>');
    var ctl = new AbortController(), to = setTimeout(function () { ctl.abort(); }, 40000);
    ask(history.slice(-5), ctl.signal)
      .then(function (x) {
        typing.remove();
        if (x.status === 200 && x.j && x.j.reply) { history.push({ role: 'assistant', content: x.j.reply }); save(); bubble('bot', render(x.j.reply)); return; }
        history.pop(); save();
        if (x.status === 429) fail(x.soft ? '<p>One moment, please send your next question in a couple of seconds.</p>' : '<p>I am getting a lot of questions right now. Please try again in about ' + (x.j.retry_after || 30) + ' seconds, or use the ' + contactLink + '.</p><p><button type="button" class="hac-retry">Try again</button></p>');
        else fail(explain(x));
      })
      .catch(function (err) { typing.remove(); history.pop(); save(); fail(explain(fetchFail(err))); })
      .then(function () { clearTimeout(to); busy = false; form.classList.remove('busy'); ta.focus(); });
  };
  log.addEventListener('click', function (e) {
    if (e.target.classList && e.target.classList.contains('hac-retry') && lastQuestion && !busy) { var el = e.target.closest('.hac-m'); if (el) el.remove(); send(lastQuestion); }
  });
  // Public hooks so any button on the page can open the chat (optionally with a question)
  window.HAChat = { open: function (q) { if (panel.hidden) open(true); hideTeaser(true); if (q) setTimeout(function () { send(q); }, 350); } };
  d.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-hac-open],[data-hac-ask]');
    if (!el) return;
    e.preventDefault(); d.body.classList.remove('menu-open');
    window.HAChat.open(el.getAttribute('data-hac-ask') || '');
  });
  // Greeting pop-up next to the bubble (once per tab session, dismissible)
  var teaser = d.createElement('div'); teaser.className = 'hac-teaser'; teaser.hidden = true;
  teaser.innerHTML = '<button type="button" class="hac-tx" aria-label="Dismiss">×</button><p><b>Hi! 👋</b> Ask me about Hammad\'s Odoo projects, skills or availability.</p>';
  root.insertBefore(teaser, fab);
  function hideTeaser(remember) { teaser.hidden = true; if (remember) try { sessionStorage.setItem('ha_chat_teaser', '1'); } catch (e) {} }
  teaser.querySelector('.hac-tx').addEventListener('click', function (e) { e.stopPropagation(); hideTeaser(true); });
  teaser.querySelector('p').addEventListener('click', function () { window.HAChat.open(''); });
  var seen = false; try { seen = sessionStorage.getItem('ha_chat_teaser') === '1'; } catch (e) {}
  if (!seen && !history.length) {
    var shown = false;
    var showTeaser = function () { if (shown) return; shown = true; window.removeEventListener('scroll', onScroll); if (panel.hidden) teaser.hidden = false; };
    var onScroll = function () { if (window.scrollY > (d.body.scrollHeight - window.innerHeight) * 0.5) showTeaser(); };
    setTimeout(showTeaser, 20000);
    window.addEventListener('scroll', onScroll, { passive: true });
  }
  fab.addEventListener('click', function () { hideTeaser(true); });
  form.addEventListener('submit', function (e) { e.preventDefault(); var t = ta.value; ta.value = ''; ta.style.height = ''; send(t); });
  ta.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  ta.addEventListener('input', function () { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 110) + 'px'; });
})();
