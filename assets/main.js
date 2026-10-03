document.documentElement.classList.add('js');

// Light only the single .reveal item closest to the viewport centre, page-wide.
// Items inside hidden lists (offsetParent === null) are ignored.
var updateReveal = function () {};

(function () {
  var items = Array.prototype.slice.call(document.querySelectorAll('.reveal > li'));
  var queued = false;

  function update() {
    queued = false;
    var mid = window.innerHeight / 2;
    var best = null, bestD = Infinity;
    items.forEach(function (li) {
      if (li.offsetParent === null) return;
      var b = li.getBoundingClientRect();
      var d = Math.abs((b.top + b.bottom) / 2 - mid);
      if (d < bestD) { bestD = d; best = li; }
    });
    items.forEach(function (li) { li.classList.toggle('is-on', li === best); });
  }

  function queue() {
    if (!queued) { queued = true; requestAnimationFrame(update); }
  }

  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  updateReveal = update;
  update();
})();

(function () {
  var stage = document.querySelector('.stage');
  if (!stage) return;
  var IDS = ['robot', 'drone', 'parking'];
  var tabs = Array.prototype.slice.call(stage.querySelectorAll('.tab'));
  var figs = Array.prototype.slice.call(stage.querySelectorAll('.fig-ex'));
  var sides = Array.prototype.slice.call(stage.querySelectorAll('.side-ex'));
  var traps = Array.prototype.slice.call(document.querySelectorAll('.traps-list'));
  var step = 0;
  var currentEx = null;
  var fadeTimer = 0;

  function byEx(list, id) {
    for (var i = 0; i < list.length; i++) if (list[i].getAttribute('data-ex') === id) return list[i];
    return null;
  }

  // ----- steps -----
  function updateCaps() {
    Array.prototype.forEach.call(stage.querySelectorAll('.caps'), function (group) {
      Array.prototype.forEach.call(group.children, function (c, i) {
        c.setAttribute('aria-hidden', i + 1 === step ? 'false' : 'true');
      });
    });
  }

  // the menu works only at step 0; afterwards the chosen name is a plain label
  function syncTabIndex() {
    tabs.forEach(function (t) {
      t.tabIndex = step === 0 && t.getAttribute('aria-selected') === 'true' ? 0 : -1;
    });
  }

  function setStep(n) {
    if (n === step && stage.getAttribute('data-step') === String(n)) return;
    step = n;
    stage.setAttribute('data-step', String(n));
    updateCaps();
    syncTabIndex();
    // leaving step 0: let go of the menu so Space scrolls again and no ring sits on the label
    if (n !== 0 && tabs.indexOf(document.activeElement) >= 0) document.activeElement.blur();
  }

  // ----- examples -----
  function reducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function showFig(next, prev, instant) {
    clearTimeout(fadeTimer);
    figs.forEach(function (f) { f.classList.remove('is-in', 'is-out'); });
    if (instant || !prev || prev === next || reducedMotion()) {
      figs.forEach(function (f) { f.hidden = f !== next; });
      return;
    }
    figs.forEach(function (f) { f.hidden = f !== next && f !== prev; });
    next.classList.add('is-in');
    next.hidden = false;
    void next.offsetWidth;
    next.classList.remove('is-in');
    prev.classList.add('is-out');
    fadeTimer = setTimeout(function () {
      prev.hidden = true;
      prev.classList.remove('is-out');
    }, 300);
  }

  function setExample(id, instant) {
    if (IDS.indexOf(id) < 0 || id === currentEx) return;
    var prevFig = currentEx ? byEx(figs, currentEx) : null;
    currentEx = id;
    document.body.setAttribute('data-ex', id);
    tabs.forEach(function (t) {
      t.setAttribute('aria-selected', t.getAttribute('data-ex') === id ? 'true' : 'false');
    });
    syncTabIndex();
    sides.forEach(function (s) { s.hidden = s.getAttribute('data-ex') !== id; });
    traps.forEach(function (l) { l.hidden = l.getAttribute('data-ex') !== id; });
    showFig(byEx(figs, id), prevFig, instant);
    updateCaps();
    updateReveal();
  }

  function readHash() {
    var h = (location.hash || '').replace('#', '');
    return IDS.indexOf(h) >= 0 ? h : 'robot';
  }

  function choose(id, focusTab) {
    setExample(id, false);
    try { history.replaceState(null, '', '#' + id); } catch (e) {}
    if (focusTab) { var t = byEx(tabs, id); if (t) t.focus(); }
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      if (step !== 0) return;
      choose(t.getAttribute('data-ex'), false);
    });
    t.addEventListener('keydown', function (e) {
      if (step !== 0) return;
      var i = IDS.indexOf(t.getAttribute('data-ex'));
      var to = -1;
      if (e.key === 'ArrowRight') to = (i + 1) % IDS.length;
      else if (e.key === 'ArrowLeft') to = (i + IDS.length - 1) % IDS.length;
      else if (e.key === 'Home') to = 0;
      else if (e.key === 'End') to = IDS.length - 1;
      if (to < 0) return;
      e.preventDefault();
      choose(IDS[to], true);
    });
  });

  window.addEventListener('hashchange', function () { setExample(readHash(), false); });

  setExample(readHash(), true);
  setStep(0);

  if (!('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) setStep(parseInt(e.target.getAttribute('data-step'), 10));
      });
    },
    { rootMargin: '-50% 0px -50% 0px', threshold: 0 }
  );
  Array.prototype.forEach.call(document.querySelectorAll('.trig'), function (t) {
    io.observe(t);
  });
})();

(function () {
  // Links to #example scroll to the example menu without overwriting the #robot/#drone/#parking hash.
  var target = document.getElementById('example');
  if (!target) return;
  Array.prototype.forEach.call(document.querySelectorAll('a[href="#example"]'), function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      target.scrollIntoView();
      var tab = document.querySelector('[role="tab"][aria-selected="true"]');
      if (tab) tab.focus({ preventScroll: true });
    });
  });
})();
