// Marks the table-of-contents link of the section currently being read.
(() => {
  const links = [...document.querySelectorAll('.toc a[href^="#"]')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const byId = new Map(links.map(a => [a.getAttribute('href').slice(1), a]));
  const secs = [...byId.keys()].map(id => document.getElementById(id)).filter(Boolean);
  let current = null;
  const set = id => {
    if (id === current) return;
    current = id;
    links.forEach(a => a.removeAttribute('aria-current'));
    byId.get(id)?.setAttribute('aria-current', 'true');
  };
  const io = new IntersectionObserver(entries => {
    const above = secs.filter(s => s.getBoundingClientRect().top < window.innerHeight * 0.35);
    if (above.length) set(above[above.length - 1].id);
    else if (entries.length) set(secs[0].id);
  }, { rootMargin: '0px 0px -60% 0px', threshold: [0, 1] });
  secs.forEach(s => io.observe(s));
})();

// Copy buttons on dark code blocks.
(() => {
  const live = document.createElement('p');
  live.className = 'sr';
  live.setAttribute('aria-live', 'polite');
  document.body.appendChild(live);
  const copyText = async text => {
    try {
      // 有些情況（頁面沒有焦點）writeText 會一直等不到結果，最多等 1 秒
      await Promise.race([
        navigator.clipboard.writeText(text),
        new Promise((_, no) => setTimeout(() => no(new Error('timeout')), 1000)),
      ]);
      return true;
    } catch {}
    // file:// pages and older browsers: fall back to a hidden textarea
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch {}
    ta.remove();
    return ok;
  };
  document.addEventListener('click', async e => {
    const btn = e.target.closest('.copy');
    if (!btn) return;
    const block = btn.closest('.code');
    // blocks with Windows / macOS / Linux panes copy the pane that is showing
    const os = document.documentElement.dataset.os;
    const pane = os && block.querySelector(`.os-panel[data-os="${os}"]`);
    const ok = await copyText((pane || block).querySelector('code').textContent);
    const name = block.querySelector('.code-name')?.textContent ||
      (btn.getAttribute('aria-label') || '').replace(/^複製 /, '') +
      (pane ? `（${pane.querySelector('.os-name')?.textContent || ''}）` : '');
    btn.textContent = ok ? '已複製' : '複製失敗';
    btn.classList.toggle('done', ok);
    live.textContent = ok ? `已複製 ${name}` : '複製失敗，請手動選取';
    clearTimeout(btn._t);
    btn._t = setTimeout(() => { btn.textContent = '複製'; btn.classList.remove('done'); }, 1800);
  });
})();

// Windows / macOS / Linux switch. The head script picks the first choice; one click changes
// every switch on the page, and the choice is remembered.
(() => {
  const root = document.documentElement;
  const buttons = [...document.querySelectorAll('.os-pick button[data-os]')];
  if (!buttons.length || !root.dataset.os) return;
  const set = os => {
    root.dataset.os = os;
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.os === os)));
  };
  set(root.dataset.os);
  document.addEventListener('click', e => {
    const b = e.target.closest('.os-pick button[data-os]');
    if (!b) return;
    // panes above the button change height; keep the button where it was on screen
    const y = b.getBoundingClientRect().top;
    set(b.dataset.os);
    window.scrollBy({ top: b.getBoundingClientRect().top - y, behavior: 'instant' });
    try { localStorage.setItem('skilllab-os', b.dataset.os); } catch {}
  });
})();

// A link to a closed fold (e.g. alarm-uno.html#setup) opens it.
(() => {
  const open = () => {
    const t = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (t instanceof HTMLDetailsElement) t.open = true;
  };
  window.addEventListener('hashchange', open);
  open();
})();
