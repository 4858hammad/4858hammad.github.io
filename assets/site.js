(function () {
  var d = document, de = d.documentElement;
  de.classList.add('js');
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // mobile menu
  var burger = d.querySelector('.burger');
  if (burger) burger.addEventListener('click', function () { d.body.classList.toggle('menu-open'); });

  // scroll reveal
  var els = [].slice.call(d.querySelectorAll('.reveal'));
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } });
    }, { threshold: 0.08 });
    els.forEach(function (n, i) { n.style.setProperty('--d', (i % 6) * 60 + 'ms'); io.observe(n); });
  } else els.forEach(function (n) { n.classList.add('in'); });

  // carousel: arrows, dots, autoplay (pauses on hover/focus, off with reduced motion)
  [].forEach.call(d.querySelectorAll('[data-carousel]'), function (root) {
    var track = root.querySelector('.car-track'), items = [].slice.call(track.children);
    var dots = root.querySelector('.car-dots'), prev = root.querySelector('.prev'), next = root.querySelector('.next');
    var perView = function () { var w = items[0].getBoundingClientRect().width; return Math.max(1, Math.round(track.clientWidth / (w + 20))); };
    var pages = function () { return Math.max(1, Math.ceil(items.length / perView())); };
    var step = function () { return items[0].getBoundingClientRect().width + 20; };
    var current = function () { return Math.round(track.scrollLeft / (step() * perView())); };
    var go = function (p) { track.scrollTo({ left: Math.max(0, Math.min(p, pages() - 1)) * step() * perView(), behavior: reduce ? 'auto' : 'smooth' }); };
    var drawDots = function () {
      dots.innerHTML = '';
      for (var i = 0; i < pages(); i++) (function (i) {
        var b = d.createElement('button'); b.setAttribute('aria-label', 'Go to slide ' + (i + 1));
        b.addEventListener('click', function () { go(i); }); dots.appendChild(b);
      })(i);
      mark();
    };
    var mark = function () { var c = Math.min(current(), pages() - 1); [].forEach.call(dots.children, function (b, i) { b.classList.toggle('on', i === c); }); };
    prev.addEventListener('click', function () { go(current() - 1); });
    next.addEventListener('click', function () { go(current() + 1 >= pages() ? 0 : current() + 1); });
    track.addEventListener('scroll', function () { window.requestAnimationFrame(mark); }, { passive: true });
    window.addEventListener('resize', drawDots);
    drawDots();
    var timer = null, paused = false;
    var play = function () { if (reduce || timer) return; timer = setInterval(function () { if (!paused) go(current() + 1 >= pages() ? 0 : current() + 1); }, 5000); };
    root.addEventListener('mouseenter', function () { paused = true; });
    root.addEventListener('mouseleave', function () { paused = false; });
    root.addEventListener('focusin', function () { paused = true; });
    root.addEventListener('focusout', function () { paused = false; });
    play();
  });


  // filter chips + search: <div class="fchips" data-for="GRID_ID"> buttons with data-f; cards carry data-tags (space separated)
  [].forEach.call(d.querySelectorAll('.fchips'), function (bar) {
    var grid = d.getElementById(bar.getAttribute('data-for'));
    if (!grid) return;
    var cards = [].slice.call(grid.children), q = d.getElementById(bar.getAttribute('data-search') || ''), none = d.getElementById(grid.id + '-none');
    var count = d.getElementById(grid.id + '-count'), cur = 'all';
    var apply = function () {
      var term = q ? q.value.trim().toLowerCase() : '', n = 0;
      cards.forEach(function (c) {
        var okTag = cur === 'all' || (' ' + (c.getAttribute('data-tags') || '') + ' ').indexOf(' ' + cur + ' ') > -1;
        var okQ = !term || (c.getAttribute('data-q') || '').indexOf(term) > -1;
        var show = okTag && okQ; c.hidden = !show; if (show) n++;
      });
      if (count) count.textContent = n + ' shown';
      if (none) none.hidden = n > 0;
      [].forEach.call(bar.querySelectorAll('button'), function (b) { b.classList.toggle('on', b.getAttribute('data-f') === cur); b.setAttribute('aria-pressed', b.getAttribute('data-f') === cur ? 'true' : 'false'); });
    };
    bar.addEventListener('click', function (e) { var b = e.target.closest('button[data-f]'); if (!b) return; cur = b.getAttribute('data-f'); apply(); });
    if (q) q.addEventListener('input', apply);
    var want = (new URLSearchParams(location.search).get('line') || location.hash.replace('#', '')).toLowerCase();
    if (want && bar.querySelector('button[data-f="' + want + '"]')) cur = want;
    apply();
  });

  // contact form: prefill subject, send via fetch (Formspree)
  var f = d.querySelector('form.form');
  if (f) {
    var P2 = new URLSearchParams(location.search);
    if (P2.get('subject')) d.getElementById('subject').value = P2.get('subject').slice(0, 120);
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var st = d.getElementById('status'), b = f.querySelector('button'); b.disabled = true; st.textContent = 'Sending…'; st.className = 'status';
      fetch(f.action, { method: 'POST', body: new FormData(f), headers: { Accept: 'application/json' } })
        .then(function (r) { if (!r.ok) throw 0; f.reset(); st.textContent = 'Thanks, I will reply by email soon.'; st.className = 'status ok'; })
        .catch(function () { st.textContent = 'Could not send. Please email me directly.'; st.className = 'status err'; })
        .then(function () { b.disabled = false; });
    });
  }
})();

// tech route: stagger cards, then fill rings and count numbers up when scrolled into view
(function () {
  var s = document.getElementById('tech-route'); if (!s) return;
  var cards = [].slice.call(s.querySelectorAll('.tr-card,.tr-ai'));
  cards.forEach(function (c, i) { c.style.setProperty('--i', i % 5); });
  var nums = [].slice.call(s.querySelectorAll('[data-count]'));
  function setAll() { nums.forEach(function (n) { n.textContent = n.getAttribute('data-count'); }); }
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!('IntersectionObserver' in window) || reduce) { setAll(); s.classList.add('is-in'); return; }
  s.classList.add('js');
  function run() {
    s.classList.add('is-in');
    var t0 = null, dur = 1500;
    function tick(t) { if (!t0) t0 = t; var k = Math.min(1, (t - t0) / dur), ease = 1 - Math.pow(1 - k, 3);
      nums.forEach(function (n) { n.textContent = Math.round(ease * +n.getAttribute('data-count')); });
      if (k < 1) requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  }
  var io = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { run(); io.disconnect(); } }, { threshold: 0.2 });
  io.observe(s);
})();

// career roadmap: grow the line upward and reveal steps from the bottom
(function () {
  var j = document.getElementById('journey'); if (!j) return;
  var steps = [].slice.call(j.querySelectorAll('.jr-step')).reverse();
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!('IntersectionObserver' in window) || reduce) { j.classList.add('is-in'); return; }
  j.classList.add('js');
  var io = new IntersectionObserver(function (en) { en.forEach(function (x) { if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } }); }, { threshold: 0.25 });
  steps.forEach(function (s) { io.observe(s); });
  var io2 = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { j.classList.add('is-in'); io2.disconnect(); } }, { threshold: 0.15 });
  io2.observe(j);
})();

// projects showcase: tabs, autoplay with progress bar, pause on hover/focus, arrow-key support
(function () {
  [].forEach.call(document.querySelectorAll('[data-showcase]'), function (root) {
    var tabs = [].slice.call(root.querySelectorAll('.sc-tab')), panels = [].slice.call(root.querySelectorAll('.sc-panel'));
    if (!tabs.length) return;
    var cur = 0, timer = null, MS = 6500;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    root.style.setProperty('--sc-ms', MS + 'ms');
    function show(i, focus) {
      cur = (i + tabs.length) % tabs.length;
      tabs.forEach(function (t, k) { var on = k === cur; t.classList.toggle('on', on); t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1; });
      panels.forEach(function (p, k) { var on = k === cur; p.classList.toggle('on', on); p.hidden = !on; });
      root.classList.remove('playing'); void root.offsetWidth; if (timer !== false && !reduce) root.classList.add('playing');
      if (focus) tabs[cur].focus();
      if (tabs[cur].scrollIntoView && window.innerWidth <= 980) tabs[cur].scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
    }
    function start() { if (reduce) return; stop(); timer = setTimeout(function () { show(cur + 1); start(); }, MS); root.classList.remove('paused'); }
    function stop() { if (timer) clearTimeout(timer); timer = null; }
    tabs.forEach(function (t, k) {
      t.addEventListener('click', function () { show(k); start(); });
      t.addEventListener('keydown', function (ev) {
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowRight') { ev.preventDefault(); show(cur + 1, true); start(); }
        if (ev.key === 'ArrowUp' || ev.key === 'ArrowLeft') { ev.preventDefault(); show(cur - 1, true); start(); }
      });
    });
    root.addEventListener('mouseenter', function () { stop(); root.classList.add('paused'); });
    root.addEventListener('mouseleave', function () { root.classList.remove('paused'); show(cur); start(); });
    root.addEventListener('focusin', function () { stop(); root.classList.add('paused'); });
    var vis = new IntersectionObserver(function (en) { if (en[0].isIntersecting) { show(cur); start(); } else { stop(); } }, { threshold: 0.3 });
    vis.observe(root);
  });
})();
