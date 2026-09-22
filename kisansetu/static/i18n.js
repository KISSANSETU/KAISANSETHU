/* KisanSetu whole-page translation engine.
 *
 * app.js builds its markup with template literals, so almost none of the visible
 * text is reachable through tr() or [data-i18n]. This engine instead walks the
 * rendered DOM after every route change, collects the English it finds, applies
 * anything already known, and asks the server to translate the rest once. Every
 * translation is cached in SQLite server-side and in localStorage client-side,
 * so a language is slow exactly once and instant forever after.
 *
 * Opt out of translation on any element with data-no-i18n.
 */
(function (w) {
  'use strict';

  var RTL = ['ur', 'ks', 'sd'];
  var STORE_PREFIX = 'gram_i18n_';
  var MEM = {};          // lang -> {english: translated}
  var PENDING = {};      // strings queued for the current flush
  var inflight = 0, flushTimer = null, observer = null;
  var currentLang = 'en';

  // Never translate: pure numbers, currency, dates, ids, code-ish tokens.
  var SKIP = /^[\s\d\W_]*$|^[₹$]?\s*[\d,.\-+%/:]+\s*[a-zA-Z%°]{0,6}$/;
  var HAS_WORD = /[A-Za-z]{2}/;
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, CANVAS: 1, SVG: 1, NOSCRIPT: 1 };
  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt', 'data-tooltip'];

  function lsKey(lang) { return STORE_PREFIX + lang; }

  function loadLocal(lang) {
    try {
      var raw = localStorage.getItem(lsKey(lang));
      return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
  }

  function saveLocal(lang) {
    try {
      localStorage.setItem(lsKey(lang), JSON.stringify(MEM[lang] || {}));
    } catch (e) {
      // Quota exceeded: drop the client cache, the server cache still holds it.
      try { localStorage.removeItem(lsKey(lang)); } catch (e2) {}
    }
  }

  function translatable(s) {
    if (!s) return false;
    s = s.trim();
    if (!s || s.length > 900) return false;
    if (SKIP.test(s)) return false;
    return HAS_WORD.test(s);
  }

  function lookup(s) {
    var m = MEM[currentLang];
    if (!m) return null;
    var t = s.trim();
    var hit = m[t];
    if (hit === undefined) return null;
    // Preserve the original leading/trailing whitespace of the node.
    return s.replace(t, hit);
  }

  function queue(s) {
    var t = s.trim();
    if (MEM[currentLang] && MEM[currentLang][t] !== undefined) return;
    PENDING[t] = 1;
    scheduleFlush();
  }

  /* ---------------- DOM walking ---------------- */

  function eachTextNode(root, fn) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode;
        if (!p || SKIP_TAGS[p.nodeName]) return NodeFilter.FILTER_REJECT;
        if (p.closest && p.closest('[data-no-i18n]')) return NodeFilter.FILTER_REJECT;
        if (!translatable(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n, batch = [];
    while ((n = walker.nextNode())) batch.push(n);
    batch.forEach(fn);
  }

  function applyTo(root) {
    if (currentLang === 'en' || !root) return;

    eachTextNode(root, function (node) {
      if (!node.__en) node.__en = node.nodeValue;
      var hit = lookup(node.__en);
      if (hit !== null) { node.nodeValue = hit; } else { queue(node.__en); }
    });

    var els = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.closest('[data-no-i18n]')) continue;
      for (var a = 0; a < ATTRS.length; a++) {
        var name = ATTRS[a], val = el.getAttribute(name);
        if (!translatable(val)) continue;
        var key = '__en_' + name;
        if (!el[key]) el[key] = val;
        var out = lookup(el[key]);
        if (out !== null) { el.setAttribute(name, out); } else { queue(el[key]); }
      }
      // <option> labels live in text nodes the walker already covered, but
      // selects rebuilt by app.js can lose them, so re-apply defensively.
      if (el.tagName === 'OPTION' && translatable(el.textContent)) {
        if (!el.__en) el.__en = el.textContent;
        var o = lookup(el.__en);
        if (o !== null) el.textContent = o;
      }
    }
  }

  /* ---------------- server round trip ---------------- */

  function scheduleFlush() {
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = setTimeout(flush, 180);
  }

  function flush() {
    flushTimer = null;
    var texts = Object.keys(PENDING);
    if (!texts.length || currentLang === 'en') return;
    PENDING = {};
    // Cap a single request; anything left re-queues on the next render pass.
    if (texts.length > 300) texts = texts.slice(0, 300);

    inflight++;
    setBusy(true);
    fetch('/api/i18n/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang: currentLang, texts: texts })
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && d.map) {
          var m = MEM[currentLang] || (MEM[currentLang] = {});
          for (var k in d.map) m[k] = d.map[k];
          saveLocal(currentLang);
          applyTo(document.body);
        }
      })
      .catch(function () { /* stay in English rather than break the page */ })
      .then(function () { inflight--; setBusy(inflight > 0); });
  }

  function setBusy(on) {
    var b = document.getElementById('i18nBusy');
    if (!b) return;
    b.classList.toggle('hidden', !on);
  }

  /* ---------------- observer keeps late renders translated ---------------- */

  function startObserver() {
    if (observer || !w.MutationObserver) return;
    observer = new MutationObserver(function (muts) {
      if (currentLang === 'en') return;
      for (var i = 0; i < muts.length; i++) {
        var added = muts[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var n = added[j];
          if (n.nodeType === 1) applyTo(n);
          else if (n.nodeType === 3 && translatable(n.nodeValue) &&
                   !(n.parentNode && n.parentNode.closest && n.parentNode.closest('[data-no-i18n]'))) {
            if (!n.__en) n.__en = n.nodeValue;
            var hit = lookup(n.__en);
            if (hit !== null) n.nodeValue = hit; else queue(n.__en);
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  /* ---------------- public API ---------------- */

  var I18N = {
    lang: function () { return currentLang; },

    isRTL: function (l) { return RTL.indexOf(l || currentLang) >= 0; },

    /* Translate a single string on demand (for JS-built text such as toasts). */
    t: function (s) {
      if (currentLang === 'en' || !translatable(s)) return s;
      var hit = lookup(s);
      if (hit !== null) return hit;
      queue(s);
      return s;
    },

    /* Called by setLanguage(). Loads the bundle, then repaints the whole page. */
    setLang: function (lang) {
      currentLang = lang || 'en';
      document.documentElement.lang = currentLang;
      document.body.dir = I18N.isRTL(currentLang) ? 'rtl' : 'ltr';
      document.body.classList.toggle('rtl', I18N.isRTL(currentLang));

      if (currentLang === 'en') {
        restoreEnglish(document.body);
        return Promise.resolve();
      }

      if (!MEM[currentLang]) MEM[currentLang] = loadLocal(currentLang);
      startObserver();

      // A bundle fetch warms everything the server already knows in one call.
      setBusy(true);
      return fetch('/api/i18n/bundle?lang=' + encodeURIComponent(currentLang))
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (d && d.map) {
            var m = MEM[currentLang];
            for (var k in d.map) m[k] = d.map[k];
            saveLocal(currentLang);
          }
        })
        .catch(function () {})
        .then(function () {
          setBusy(false);
          applyTo(document.body);
        });
    },

    /* Re-scan a subtree. app.js calls this after each route render. */
    apply: function (root) { applyTo(root || document.body); },

    /* Resolve once the given strings are cached. Needed where the DOM walker
       cannot help - inside data-no-i18n regions such as the chat transcript. */
    ensure: function (texts) {
      if (currentLang === 'en') return Promise.resolve();
      var m = MEM[currentLang] || (MEM[currentLang] = {});
      var miss = texts.filter(function (s) {
        return translatable(s) && m[s.trim()] === undefined;
      });
      if (!miss.length) return Promise.resolve();
      return fetch('/api/i18n/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lang: currentLang, texts: miss })
      }).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (d && d.map) {
            for (var k in d.map) m[k] = d.map[k];
            saveLocal(currentLang);
          }
        }).catch(function () {});
    },

    clearCache: function () {
      for (var k in MEM) { try { localStorage.removeItem(lsKey(k)); } catch (e) {} }
      MEM = {};
    }
  };

  function restoreEnglish(root) {
    eachTextNodeAll(root, function (n) { if (n.__en) n.nodeValue = n.__en; });
    var els = root.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      for (var a = 0; a < ATTRS.length; a++) {
        var key = '__en_' + ATTRS[a];
        if (els[i][key]) els[i].setAttribute(ATTRS[a], els[i][key]);
      }
    }
  }

  function eachTextNodeAll(root, fn) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var n, batch = [];
    while ((n = walker.nextNode())) batch.push(n);
    batch.forEach(fn);
  }

  w.I18N = I18N;
})(window);
