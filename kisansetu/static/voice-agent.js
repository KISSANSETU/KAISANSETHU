/* GRAM Saathi Voice - hands-free voice agent ("Jarvis" mode).
 *
 * The farmer taps the mic once and then does everything by talking. Saathi
 * listens, works out what they want (server: /api/voice/interpret), and then
 * runs a fixed task recipe that drives the real screens: it opens pages,
 * shines a spotlight on the button it is using, fills in forms, opens the
 * camera, reads results aloud and asks for a spoken "yes" before anything is
 * saved.
 *
 * Design rules
 *  - The AI understands; the recipes act. Steps are fixed code, never invented.
 *  - Recipes reuse app.js's own functions and endpoints, so permissions and
 *    validation are exactly the same as tapping through by hand.
 *  - Anything that saves or changes data needs a confirmation (voice "yes" or a
 *    tap on the big button). Payments are never done by voice.
 *  - yes / no / stop / repeat / photo are recognised in the browser in many
 *    languages, so short replies do not wait for the server.
 *
 * Globals used from app.js: api, me, route, currentPage, currentLang, token,
 * tr, toast, esc, getGPS, openVerifiedCropFlow, renderVerifiedCropStep,
 * goToCropStep, runYoloVerification, publishVerifiedCrop, cropVerify,
 * confirmOfferAcceptance, offerAction, openTransportRequest, saveTransport,
 * openCertificate, setLanguage, logout, LANGS.
 */
(function (w) {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  var VOICE_TAG = {
    en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN', ta: 'ta-IN', te: 'te-IN', bn: 'bn-IN',
    gu: 'gu-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN', or: 'or-IN', as: 'as-IN',
    ur: 'ur-IN', ne: 'ne-NP', sa: 'sa-IN', ks: 'ur-IN', sd: 'sd-IN', kok: 'mr-IN',
    mai: 'hi-IN', doi: 'hi-IN', brx: 'hi-IN', mni: 'bn-IN', sat: 'hi-IN', raj: 'hi-IN'
  };
  // Languages Chrome's built-in recognition handles well. Others use Whisper.
  var BROWSER_STT = { en: 1, hi: 1, mr: 1, ta: 1, te: 1, bn: 1, gu: 1, kn: 1, ml: 1, pa: 1, ur: 1 };

  var PAGE_INFO = {
    dashboard: 'This is your home page with your income and news.',
    crops: 'Here you add crops, see quality certificates and price forecasts.',
    market: 'Here you see offers from buyers and can accept or decline them.',
    preorders: 'Here buyers book your harvest in advance.',
    transport: 'Here you can book a truck or share one with other farmers.',
    paymentsRewards: 'Here you see payments you received and reward points.',
    profile: 'This is your profile with bank and KYC details.',
    feedback: 'Here you can give feedback.',
    grievances: 'Here you can report a problem.',
    linkIndia: 'Here you see markets in other states.',
    chats: 'Here are your messages.',
    discover: 'Here you browse verified harvests and their quality certificates.',
    orders: 'Here are your orders and deliveries.'
  };

  /* ------------------------------------------------------------------ *
   * Quick words - answered without the server
   * ------------------------------------------------------------------ */
  var QUICK = {
    yes: ['yes', 'yeah', 'yep', 'ok', 'okay', 'sure', 'confirm', 'do it', 'correct', 'right',
      'haan', 'han', 'ha', 'haa', 'haanji', 'ji haan', 'theek hai', 'thik hai', 'sahi', 'kar do', 'karo',
      'ho', 'hoy', 'hoi', 'barobar', 'chalel', 'aamaam', 'amam', 'sari', 'seri', 'avunu', 'sare',
      'haudu', 'howdu', 'athe', 'ate', 'shari', 'hya', 'hyan', 'hna', 'hmm haan',
      'हाँ', 'हां', 'हा', 'जी', 'ठीक है', 'सही', 'करो', 'हो', 'होय', 'बरोबर', 'ஆமாம்', 'சரி',
      'అవును', 'సరే', 'ಹೌದು', 'ಸರಿ', 'അതെ', 'ശരി', 'হ্যাঁ', 'ঠিক আছে', 'હા', 'ਹਾਂ', 'ہاں', 'جی'],
    no: ['no', 'nope', 'dont', "don't", 'not now', 'nahi', 'nahin', 'na', 'mat karo', 'rehne do',
      'nako', 'nai', 'illa', 'illai', 'venda', 'vaddu', 'beda', 'venam', 'vendam', 'na na',
      'नहीं', 'नही', 'ना', 'मत', 'नको', 'இல்லை', 'வேண்டாம்', 'వద్దు', 'కాదు', 'ಬೇಡ', 'ಇಲ್ಲ',
      'വേണ്ട', 'ഇല്ല', 'না', 'ના', 'ਨਹੀਂ', 'نہیں'],
    stop: ['stop', 'cancel', 'exit', 'quit', 'bye', 'band karo', 'bas', 'ruko', 'chup', 'thamba',
      'thambaa', 'nirutthu', 'niruthu', 'aapu', 'nillu', 'saak', 'poru',
      'बंद करो', 'बस', 'रुको', 'थांबा', 'बंद', 'நிறுத்து', 'ఆపు', 'ನಿಲ್ಲಿಸು', 'നിർത്തൂ', 'থামো', 'બંધ', 'ਬੰਦ', 'بند'],
    repeat: ['repeat', 'again', 'say again', 'what', 'pardon', 'phir se', 'fir se', 'dobara', 'kya',
      'punha', 'parat', 'marubadiyum', 'malli', 'thirumba',
      'फिर से', 'दोबारा', 'क्या', 'पुन्हा', 'மீண்டும்', 'మళ్ళీ', 'ಮತ್ತೆ', 'വീണ്ടും', 'আবার', 'ફરી', 'ਦੁਬਾਰਾ'],
    photo: ['photo', 'foto', 'click', 'capture', 'snap', 'picture', 'take photo', 'photo lo', 'photo le lo',
      'khicho', 'kheecho', 'kheencho', 'kadha', 'kaadha', 'padam', 'padam edu', 'teeyi', 'tegi',
      'फोटो', 'फ़ोटो', 'खींचो', 'काढा', 'படம்', 'ஃபோட்டோ', 'ఫోటో', 'ಫೋಟೋ', 'ഫോട്ടോ', 'ছবি', 'ફોટો', 'ਫੋਟੋ', 'تصویر'],
    help: ['help', 'what can i say', 'madad', 'madat', 'sahayata', 'udavi', 'sahayam', 'sahaya',
      'मदद', 'मदत', 'உதவி', 'సహాయం', 'ಸಹಾಯ', 'സഹായം', 'সাহায্য', 'મદદ', 'ਮਦਦ', 'مدد']
  };

  function norm(s) {
    return String(s || '').toLowerCase()
      .replace(/[.,!?।॥"'`’“”()\-:;]/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function quick(text) {
    var t = norm(text);
    if (!t) return null;
    var words = t.split(' ');
    for (var key in QUICK) {
      var list = QUICK[key];
      for (var i = 0; i < list.length; i++) {
        var p = list[i].toLowerCase();
        if (t === p) return key;
        // Short utterances that start or end with the word: "haan ji", "okay do it".
        if (words.length <= 3 && (t.indexOf(p + ' ') === 0 || t.slice(-(p.length + 1)) === ' ' + p)) return key;
      }
    }
    return null;
  }

  function firstNumber(text) {
    var m = String(text || '').replace(/,/g, '').match(/\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  /* ------------------------------------------------------------------ *
   * State
   * ------------------------------------------------------------------ */
  var S = {
    active: false,
    mode: 'idle',       // idle | listening | thinking | speaking
    task: null,
    lastSaid: '',
    recog: null,
    recorder: null,
    abortListen: null,
    offers: [],
    greeted: false,
    serverStt: localStorage.getItem('gram_va_stt') === 'server',
    session: 0,
    loops: 0,
    pending: null
  };

  function Cancel(msg) { this.message = msg || 'cancelled'; }
  function Switch(intent) { this.intent = intent; }

  // app.js declares these with let, so they are globals but not window properties.
  function getMe() { try { return me; } catch (e) { return null; } }
  function page() { try { return currentPage; } catch (e) { return ''; } }
  function lang() { return w.currentLang || localStorage.getItem('gram_lang') || 'en'; }
  function tag() { return VOICE_TAG[lang()] || 'en-IN'; }
  function role() { var m = getMe(); return (m && m.role) || 'farmer'; }
  function checkActive() { if (!S.active) throw new Cancel(); }

  /* ------------------------------------------------------------------ *
   * UI
   * ------------------------------------------------------------------ */
  function buildUI() {
    if ($('vaFab')) return;
    var root = document.createElement('div');
    root.id = 'vaRoot';
    root.setAttribute('data-no-i18n', '');
    root.innerHTML =
      '<button id="vaFab" class="va-fab hidden" aria-label="Talk to Saathi">' +
        '<span class="va-fab-icon" aria-hidden="true">🎙️</span><span class="va-fab-label">Talk</span>' +
      '</button>' +
      '<div id="vaNudge" class="va-nudge hidden"><b>🎙️</b><span id="vaNudgeText">Tap and talk. I can do everything for you.</span></div>' +

      '<div id="vaHud" class="va-hud hidden" role="dialog" aria-label="Voice assistant">' +
        '<div class="va-hud-top">' +
          '<div id="vaOrb" class="va-orb"><span></span><span></span><span></span></div>' +
          '<div class="va-captions">' +
            '<div id="vaStatus" class="va-status">Ready</div>' +
            '<div id="vaSaid" class="va-said"></div>' +
            '<div id="vaHeard" class="va-heard"></div>' +
          '</div>' +
          '<button id="vaStop" class="va-stop" aria-label="Stop">✕</button>' +
        '</div>' +
        '<button type="button" id="vaMore" class="va-more" aria-expanded="false">⋯</button>' +
        '<div id="vaChips" class="va-chips"></div>' +
        '<form id="vaTypeForm" class="va-type"><input id="vaType" autocomplete="off" placeholder="Or type here"><button type="submit">➤</button></form>' +
      '</div>' +

      '<div id="vaSpot" class="va-spot hidden" aria-hidden="true">' +
        '<div id="vaHole" class="va-hole"></div>' +
        '<div id="vaBubble" class="va-bubble"><span class="va-arrow">👇</span><span id="vaBubbleText"></span></div>' +
      '</div>' +

      '<div id="vaConfirm" class="va-confirm hidden" role="dialog" aria-modal="true">' +
        '<div class="va-confirm-card">' +
          '<div class="va-confirm-icon">🤔</div>' +
          '<p id="vaConfirmText"></p>' +
          '<div class="va-confirm-btns">' +
            '<button id="vaYes" class="va-yes">✅ <span id="vaYesLabel">Yes</span></button>' +
            '<button id="vaNo" class="va-no">❌ <span id="vaNoLabel">No</span></button>' +
          '</div>' +
          '<small id="vaConfirmHint">Say yes or no</small>' +
        '</div>' +
      '</div>' +

      '<div id="vaCam" class="va-cam hidden" role="dialog" aria-modal="true">' +
        '<video id="vaVideo" playsinline autoplay muted></video>' +
        '<div class="va-cam-hint" id="vaCamHint">Hold the phone over your crop and say "photo"</div>' +
        '<div class="va-cam-btns">' +
          '<button id="vaCamCancel" class="va-cam-cancel">✕</button>' +
          '<button id="vaSnap" class="va-snap" aria-label="Take photo">📸</button>' +
          '<button id="vaCamGallery" class="va-cam-gallery" aria-label="Choose from gallery">🖼️</button>' +
        '</div>' +
        '<input id="vaGallery" type="file" accept="image/*" hidden>' +
      '</div>';
    document.body.appendChild(root);

    $('vaFab').onclick = function () { S.active ? stopAgent(true) : startAgent(); };
    $('vaStop').onclick = function () { stopAgent(true); };
    $('vaNudge').onclick = function () { startAgent(); };
    $('vaMore').onclick = function () {
      var open = $('vaHud').classList.toggle('va-expanded');
      this.setAttribute('aria-expanded', open);
    };
    $('vaTypeForm').onsubmit = function (e) {
      e.preventDefault();
      var v = $('vaType').value.trim();
      if (!v) return;
      $('vaType').value = '';
      deliver(v);
    };
    addEventListener('resize', placeSpot);
    addEventListener('scroll', placeSpot, true);
  }

  /* Route typed or tapped input into the one running conversation. */
  function deliver(text) {
    if (S.abortListen) S.abortListen(text);
    else if (!S.active && !S.starting) startAgent(text);
    else S.pending = text; // picked up by the next listen()
  }

  function setMode(mode, status) {
    S.mode = mode;
    var orb = $('vaOrb'), fab = $('vaFab');
    if (orb) orb.className = 'va-orb va-' + mode;
    if (fab) fab.classList.toggle('va-live', S.active);
    var labels = { idle: 'Ready', listening: 'Listening… speak now', thinking: 'Thinking…', speaking: 'Speaking…' };
    tx(status || labels[mode]).then(function (t) { if ($('vaStatus')) $('vaStatus').textContent = t; });
  }

  function setChips(list) {
    var box = $('vaChips');
    if (!box) return;
    Promise.all(list.map(tx)).then(function (labels) {
      box.innerHTML = labels.map(function (l, i) {
        return '<button type="button" data-say="' + esc(list[i]) + '">' + esc(l) + '</button>';
      }).join('');
      box.onclick = function (e) {
        var b = e.target.closest('button[data-say]');
        if (!b) return;
        var say = b.getAttribute('data-say');
        deliver(say);
      };
    });
  }

  function defaultChips() {
    if (role() === 'farmer') return ['Sell my crop', 'Show buyer offers', "Today's onion price", 'Book a truck', 'My certificates', 'Teach me'];
    if (role() === 'buyer') return ['Discover harvests', 'My orders', "Today's tomato price", 'Teach me'];
    return ['Open dashboard', 'Read this page', 'Help'];
  }

  /* ------------------------------------------------------------------ *
   * Translation + speech out
   * ------------------------------------------------------------------ */
  function tx(s) {
    s = String(s || '');
    if (lang() === 'en' || !w.I18N || !s) return Promise.resolve(s);
    return w.I18N.ensure([s]).then(function () { return w.I18N.t(s); }, function () { return s; });
  }

  function pickVoice() {
    if (!w.speechSynthesis) return null;
    var all = speechSynthesis.getVoices(), want = tag(), base = want.split('-')[0];
    return all.filter(function (v) { return v.lang === want; })[0] ||
      all.filter(function (v) { return v.lang.replace('_', '-').indexOf(base) === 0; })[0] || null;
  }

  function chunks(text) {
    var parts = String(text).match(/[^.!?।]+[.!?।]*/g) || [text];
    var out = [], cur = '';
    parts.forEach(function (p) {
      if ((cur + p).length > 180 && cur) { out.push(cur); cur = p; } else cur += p;
    });
    if (cur.trim()) out.push(cur);
    return out;
  }

  /* Speak and show a caption. opts.raw = already in the user's language. */
  function say(text, opts) {
    opts = opts || {};
    return (opts.raw ? Promise.resolve(text) : tx(text)).then(function (t) {
      checkActive();
      t = String(t || '').replace(/[*#`|_>]+/g, ' ').trim();
      S.lastSaid = t;
      if ($('vaSaid')) $('vaSaid').textContent = t;
      if ($('vaHeard') && !opts.keepHeard) $('vaHeard').textContent = '';
      if (!w.speechSynthesis || !t) return sleep(Math.min(4000, 400 + t.length * 45));
      setMode('speaking');
      try { speechSynthesis.cancel(); } catch (e) {}
      var voice = pickVoice();
      return chunks(t).reduce(function (p, part) {
        return p.then(function () {
          checkActive();
          return new Promise(function (resolve) {
            var u = new SpeechSynthesisUtterance(part);
            if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = tag();
            u.rate = 0.95;
            var done = false, finish = function () { if (!done) { done = true; resolve(); } };
            u.onend = finish; u.onerror = finish;
            // Some phones never fire onend; do not hang the conversation.
            setTimeout(finish, 2500 + part.length * 90);
            speechSynthesis.speak(u);
          });
        });
      }, Promise.resolve()).then(function () { checkActive(); setMode('idle'); });
    });
  }

  /* ------------------------------------------------------------------ *
   * Speech in: browser recognition, or record + Whisper on the server
   * ------------------------------------------------------------------ */
  function useServerStt() {
    return S.serverStt || !BROWSER_STT[lang()] || !(w.SpeechRecognition || w.webkitSpeechRecognition);
  }

  function listen(opts) {
    opts = opts || {};
    checkActive();
    // Text that arrived while Saathi was busy (chip, typing), then scripted
    // replies (SaathiVoice.script) for demos and automated tests.
    if (S.pending || (S.script && S.script.length)) {
      var scripted = S.pending || S.script.shift();
      S.pending = null;
      setMode('listening');
      return sleep(500).then(function () {
        checkActive();
        setMode('idle');
        if (scripted && $('vaHeard')) $('vaHeard').textContent = '🗣️ "' + scripted + '"';
        return scripted;
      });
    }
    setMode('listening');
    var p = new Promise(function (resolve) {
      var settled = false;
      var finish = function (text) {
        if (settled) return;
        settled = true;
        S.abortListen = null;
        stopRecognition();
        resolve(text == null ? null : String(text).trim() || null);
      };
      // A chip, typed text or a tap elsewhere can answer instead of the voice.
      S.abortListen = finish;
      if (useServerStt()) recordAndTranscribe(finish, opts);
      else browserRecognize(finish, opts);
    });
    return p.then(function (text) {
      checkActive();
      setMode('idle');
      if (text && $('vaHeard')) {
        tx('You said').then(function (l) { $('vaHeard').textContent = '🗣️ ' + l + ': "' + text + '"'; });
      }
      return text;
    });
  }

  function browserRecognize(finish, opts) {
    var SR = w.SpeechRecognition || w.webkitSpeechRecognition;
    var r = new SR();
    S.recog = r;
    r.lang = tag();
    r.interimResults = true;
    r.continuous = false;
    var finalText = '';
    r.onresult = function (e) {
      var interim = '';
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      if ($('vaHeard')) $('vaHeard').textContent = '🗣️ ' + (finalText + interim);
    };
    r.onerror = function (e) {
      if (e.error === 'network' || e.error === 'language-not-supported' || e.error === 'service-not-allowed') {
        // Browser service unusable here: switch to Whisper for the rest of the session.
        S.serverStt = true;
        S.recog = null;
        recordAndTranscribe(finish, opts);
        return;
      }
      if (e.error === 'not-allowed') {
        micBlocked();
      }
      finish(null);
    };
    r.onend = function () { if (S.recog === r) finish(finalText); };
    try { r.start(); } catch (e) { finish(null); }
    setTimeout(function () { if (S.recog === r) { try { r.stop(); } catch (e) {} } }, opts.maxMs || 12000);
  }

  function recordAndTranscribe(finish, opts) {
    if (!navigator.mediaDevices || !w.MediaRecorder) { finish(null); return; }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var rec, chunksArr = [], ctx, analyser, data, heard = false, lastLoud = Date.now(), started = Date.now();
      try { rec = new MediaRecorder(stream); } catch (e) { stream.getTracks().forEach(function (t) { t.stop(); }); finish(null); return; }
      S.recorder = { rec: rec, stream: stream };
      rec.ondataavailable = function (e) { if (e.data && e.data.size) chunksArr.push(e.data); };
      rec.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        if (ctx) { try { ctx.close(); } catch (e) {} }
        if (!heard || !chunksArr.length) { finish(null); return; }
        setMode('thinking', 'Understanding…');
        var fd = new FormData();
        var type = rec.mimeType || 'audio/webm';
        fd.append('audio', new Blob(chunksArr, { type: type }), 'speech.' + (type.indexOf('mp4') >= 0 ? 'mp4' : type.indexOf('ogg') >= 0 ? 'ogg' : 'webm'));
        fd.append('lang', lang());
        api('/api/voice/transcribe', { method: 'POST', body: fd })
          .then(function (d) { finish(d.text); }, function () { finish(null); });
      };
      // Simple voice-activity detection: stop 1.3 s after the person stops talking.
      try {
        ctx = new (w.AudioContext || w.webkitAudioContext)();
        analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        ctx.createMediaStreamSource(stream).connect(analyser);
        data = new Uint8Array(analyser.fftSize);
      } catch (e) { analyser = null; }
      rec.start(250);
      (function tick() {
        if (rec.state !== 'recording') return;
        var now = Date.now();
        if (analyser) {
          analyser.getByteTimeDomainData(data);
          var peak = 0;
          for (var i = 0; i < data.length; i++) peak = Math.max(peak, Math.abs(data[i] - 128));
          if (peak > 14) { heard = true; lastLoud = now; }
        } else if (now - started > 1500) heard = true;
        var silentTooLong = heard && now - lastLoud > 1300;
        var nothingSaid = !heard && now - started > (opts.silenceMs || 8000);
        if (silentTooLong || nothingSaid || now - started > (opts.maxMs || 15000)) { rec.stop(); return; }
        requestAnimationFrame(tick);
      })();
    }, function () { micBlocked(); finish(null); });
  }

  function stopRecognition() {
    if (S.recog) { var r = S.recog; S.recog = null; try { r.abort(); } catch (e) {} }
    if (S.recorder) {
      var x = S.recorder; S.recorder = null;
      try { if (x.rec.state === 'recording') x.rec.stop(); } catch (e) {}
      try { x.stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
    }
  }

  function micBlocked() {
    toast(w.I18N ? I18N.t('Microphone is blocked. Allow microphone access for this site and tap the mic again.') :
      'Microphone is blocked. Allow microphone access for this site and tap the mic again.');
  }

  /* ------------------------------------------------------------------ *
   * Spotlight
   * ------------------------------------------------------------------ */
  var spotEl = null;

  /* Visible = has a size and is not in a closed drawer or hidden panel. */
  function visible(el) {
    if (!el || !document.body.contains(el) || el.closest('.hidden')) return false;
    var r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    var aside = el.closest('aside');
    if (aside) {
      var a = aside.getBoundingClientRect();
      if (a.right <= 1 || a.left >= innerWidth - 1) return false; // mobile drawer is closed
    }
    return true;
  }

  function highlight(el, caption) {
    if (typeof el === 'string') el = document.querySelector(el);
    if (!visible(el)) { clearHighlight(); return Promise.resolve(false); }
    var wasHidden = $('vaSpot').classList.contains('hidden');
    spotEl = el;
    // Appear in place instead of sliding over from the previous target.
    $('vaHole').style.transition = wasHidden ? 'none' : '';
    $('vaSpot').classList.remove('hidden');
    try { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) { el.scrollIntoView(); }
    return (caption ? tx(caption) : Promise.resolve('')).then(function (t) {
      $('vaBubbleText').textContent = t;
      $('vaBubble').classList.toggle('hidden', !t);
      placeSpot();
      requestAnimationFrame(function () { $('vaHole').style.transition = ''; });
      setTimeout(placeSpot, 350);
      setTimeout(placeSpot, 800);
      return true;
    });
  }

  function placeSpot() {
    if (!spotEl || $('vaSpot').classList.contains('hidden')) return;
    if (!document.body.contains(spotEl)) { clearHighlight(); return; }
    var r = spotEl.getBoundingClientRect(), pad = 8;
    var hole = $('vaHole');
    hole.style.left = (r.left - pad) + 'px';
    hole.style.top = (r.top - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px';
    hole.style.height = (r.height + pad * 2) + 'px';
    var b = $('vaBubble'), bw = Math.min(320, innerWidth - 24);
    b.style.maxWidth = bw + 'px';
    var below = r.top < innerHeight * 0.45;
    b.classList.toggle('below', below);
    var left = Math.max(12, Math.min(innerWidth - bw - 12, r.left + r.width / 2 - bw / 2));
    b.style.left = left + 'px';
    if (below) { b.style.top = (r.bottom + pad + 14) + 'px'; b.style.bottom = 'auto'; }
    else { b.style.bottom = (innerHeight - r.top + pad + 14) + 'px'; b.style.top = 'auto'; }
  }

  function clearHighlight() {
    spotEl = null;
    if ($('vaSpot')) $('vaSpot').classList.add('hidden');
  }

  function waitFor(fn, ms) {
    var end = Date.now() + (ms || 6000);
    return new Promise(function (resolve) {
      (function poll() {
        var v = null;
        try { v = fn(); } catch (e) {}
        if (v) return resolve(v);
        if (Date.now() > end || !S.active) return resolve(null);
        setTimeout(poll, 120);
      })();
    });
  }

  function setField(id, value) {
    var el = $(id);
    if (!el) return null;
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.classList.add('va-filled');
    setTimeout(function () { el.classList.remove('va-filled'); }, 1600);
    return el;
  }

  function go(pageKey) {
    checkActive();
    if (page() === pageKey && $('content') && $('content').children.length) return Promise.resolve();
    var nav = document.querySelector('[onclick="route(\'' + pageKey + '\')"]');
    return highlight(nav, null).then(function () { return sleep(450); })
      .then(function () { return route(pageKey); })
      .then(function () { clearHighlight(); return sleep(350); });
  }

  /* ------------------------------------------------------------------ *
   * Dialogue primitives
   * ------------------------------------------------------------------ */
  function interpret(text, expect, screen) {
    setMode('thinking');
    return api('/api/voice/interpret', {
      method: 'POST',
      body: JSON.stringify({
        text: text, lang: lang(), page: page() || 'dashboard',
        expect: expect || null, screen: screen || null, session_id: 'voice'
      })
    });
  }

  /* Ask one question and return the answer value. Throws Cancel or Switch. */
  function ask(question, expect, opts) {
    opts = opts || {};
    expect = expect || { type: 'text' };
    var tries = 0;
    function attempt(speakIt) {
      return (speakIt ? say(question) : Promise.resolve())
        .then(function () { return listen(); })
        .then(function (text) {
          if (!text) {
            tries++;
            if (tries >= 3) return say('I will stop here. Tap the mic when you are ready.').then(function () { throw new Cancel(); });
            return say('I did not hear you.').then(function () { return attempt(true); });
          }
          var q = quick(text);
          if (q === 'stop') throw new Cancel();
          if (q === 'repeat') return attempt(true);
          if (expect.type === 'yesno' && (q === 'yes' || q === 'no')) return q === 'yes';
          if (expect.type === 'photo' && q === 'photo') return 'photo';
          if ((expect.type === 'number' || expect.type === 'price') && /^\D{0,12}\d[\d,.]*\D{0,20}$/.test(text) && firstNumber(text) != null) {
            return firstNumber(text);
          }
          return interpret(text, Object.assign({ question: question }, expect)).then(function (r) {
            if (r.kind === 'answer' && r.value !== null && r.value !== undefined && r.value !== '') return r.value;
            if (r.kind === 'command' && r.intent === 'stop') throw new Cancel();
            if (r.kind === 'command' && r.intent === 'repeat') return attempt(true);
            if (r.kind === 'intent' && r.intent === 'stop') throw new Cancel();
            if (r.kind === 'intent' && r.intent && !opts.noSwitch && r.intent !== 'question') throw new Switch(r);
            tries++;
            if (tries >= 3) return say('Sorry, I could not understand. Let us stop here.').then(function () { throw new Cancel(); });
            return say('Sorry, I did not understand.').then(function () { return attempt(true); });
          });
        });
    }
    return attempt(true);
  }

  /* Spoken + on-screen confirmation. Resolves true / false. */
  function confirm(summary) {
    var card = $('vaConfirm');
    return Promise.all([tx(summary), tx('Yes'), tx('No'), tx('Say yes or no')]).then(function (t) {
      $('vaConfirmText').textContent = t[0];
      $('vaYesLabel').textContent = t[1];
      $('vaNoLabel').textContent = t[2];
      $('vaConfirmHint').textContent = t[3];
      card.classList.remove('hidden');
      var decided = false;
      var tapped = new Promise(function (resolve) {
        $('vaYes').onclick = function () { decided = true; resolve(true); };
        $('vaNo').onclick = function () { decided = true; resolve(false); };
      });
      var never = function () { return new Promise(function () {}); };
      var spoken = say(summary + ' Say yes or no.').then(function () {
        return (function loop(n) {
          if (decided) return never();
          return listen().then(function (text) {
            if (decided) return never();
            if (text == null) return n < 2 ? loop(n + 1) : false;
            var q = quick(text);
            if (q === 'yes') return true;
            if (q === 'no' || q === 'stop') return false;
            if (q === 'repeat') return say(summary).then(function () { return loop(n); });
            return interpret(text, { type: 'yesno', question: summary }).then(function (r) {
              if (r.kind === 'answer' && typeof r.value === 'boolean') return r.value;
              if (r.kind === 'command' && r.intent === 'stop') return false;
              return say('Please say yes or no.').then(function () { return loop(n + 1); });
            });
          });
        })(0);
      });
      spoken = spoken.catch(function (e) { if (decided) return never(); throw e; });
      return Promise.race([tapped.then(function (v) { if (S.abortListen) S.abortListen(null); try { speechSynthesis.cancel(); } catch (e) {} return v; }), spoken]);
    }).then(function (v) {
      card.classList.add('hidden');
      return v;
    }, function (e) { card.classList.add('hidden'); throw e; });
  }

  /* ------------------------------------------------------------------ *
   * Camera
   * ------------------------------------------------------------------ */
  function capturePhoto(crop) {
    var cam = $('vaCam'), video = $('vaVideo'), stream = null;
    return tx('Hold the phone over your ' + crop + ' and say "photo", or tap the camera button').then(function (hint) {
      $('vaCamHint').textContent = hint;
      return new Promise(function (resolve, reject) {
        var done = false;
        function close() {
          cam.classList.add('hidden');
          if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
          if (S.abortListen) S.abortListen(null);
        }
        function finish(file) { if (done) return; done = true; close(); resolve(file); }
        function fail(err) { if (done) return; done = true; close(); reject(err); }
        function snap() {
          if (!video.videoWidth) return;
          var c = document.createElement('canvas');
          c.width = video.videoWidth; c.height = video.videoHeight;
          c.getContext('2d').drawImage(video, 0, 0);
          c.toBlob(function (b) {
            finish(new File([b], 'voice_' + Date.now() + '.jpg', { type: 'image/jpeg' }));
          }, 'image/jpeg', 0.9);
        }
        $('vaSnap').onclick = snap;
        $('vaCamCancel').onclick = function () { fail(new Cancel()); };
        $('vaCamGallery').onclick = function () { $('vaGallery').click(); };
        $('vaGallery').onchange = function (e) {
          var f = e.target.files && e.target.files[0];
          e.target.value = '';
          if (f) finish(f);
        };
        cam.classList.remove('hidden');
        var camOk = navigator.mediaDevices && navigator.mediaDevices.getUserMedia
          ? navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
          : Promise.reject(new Error('no camera'));
        camOk.then(function (s) {
          stream = s;
          video.srcObject = s;
        }, function () {
          tx('Camera not available. Tap the picture button to choose a photo.').then(function (t) { $('vaCamHint').textContent = t; });
        });
        // Keep listening for "photo" / "stop" while the camera is open.
        (function loop(misses) {
          if (done || !S.active) return;
          say('Show me your ' + crop + ' and say photo.', { bubble: false })
            .then(function () { return listenLoop(misses); })
            .catch(fail);
        })(0);
        function listenLoop(misses) {
          if (done || !S.active) return;
          return listen({ silenceMs: 10000 }).then(function (text) {
            if (done) return;
            var q = quick(text);
            if (q === 'photo' || q === 'yes') { snap(); return; }
            if (q === 'stop' || q === 'no') { fail(new Cancel()); return; }
            if (!text && misses >= 3) { return say('Tap the camera button when ready.', { bubble: false }).then(function () { return listenLoop(0); }); }
            return listenLoop(text ? misses : misses + 1);
          }, fail);
        }
      });
    });
  }

  function putFileInInput(input, file) {
    try {
      var dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      return true;
    } catch (e) { return false; }
  }

  /* ------------------------------------------------------------------ *
   * Tasks
   * ------------------------------------------------------------------ */
  function qtyWords(qtl) {
    if (qtl < 1) return Math.round(qtl * 100) + ' kg';
    return (Math.round(qtl * 100) / 100) + ' quintal';
  }

  var TASKS = {};

  TASKS.sell_produce = function (it) {
    if (role() !== 'farmer') return say('Only a farmer account can sell produce.');
    var crop = it.crop, qtl = it.quantity_qtl, ver, grade, priceInfo, price;
    return Promise.resolve()
      .then(function () { return crop || ask('Which crop do you want to sell?', { type: 'crop' }).then(function (v) { crop = v; }); })
      .then(function () {
        if (qtl) return;
        return ask('How much ' + crop + ' do you have? Say it in kilo or quintal.', { type: 'quantity' }).then(function (v) {
          qtl = typeof v === 'object' && v ? v.quantity_qtl : (typeof v === 'number' ? v / 100 : null);
          if (!qtl) throw new Cancel();
        });
      })
      .then(function () { return say('Okay, ' + qtyWords(qtl) + ' of ' + crop + '. Let us put it up for sale. I will open the add crop form.'); })
      .then(function () { return go('crops'); })
      .then(function () { return highlight('[onclick*="openVerifiedCropFlow"]', 'Add crop'); })
      .then(function () { return sleep(900); })
      .then(function () {
        clearHighlight();
        openVerifiedCropFlow();
        cropVerify.crop = crop;
        return waitFor(function () { return $('vcrop'); });
      })
      .then(function () {
        setField('vcrop', crop);
        return highlight('[onclick*="captureCropGPS"]', 'Step 1: your farm location');
      })
      .then(function () { return say('Step 1. I need your farm location. If the phone asks, tap Allow.'); })
      .then(function getLocation() {
        return getGPS().then(function (g) {
          cropVerify.g = { lat: g.lat, lon: g.lon, source: 'gps' };
          cropVerify.crop = crop;
          renderVerifiedCropStep();
        }, function () {
          return ask('I could not get your location. Turn on location and allow it for this site. Shall I try again?', { type: 'yesno' }, { noSwitch: true })
            .then(function (yes) { if (!yes) throw new Cancel(); return getLocation(); });
        });
      })
      .then(function () { clearHighlight(); return say('Location saved.'); })
      .then(function () { goToCropStep(2); return waitFor(function () { return $('vphoto'); }); })
      .then(function photoStep() {
        return highlight('#vphoto', 'Step 2: photo of your ' + crop)
          .then(function () { return say('Step 2. Now I need a photo of your ' + crop + '. I am opening the camera.'); })
          .then(function () { clearHighlight(); return capturePhoto(crop); })
          .then(function (file) {
            if (!putFileInInput($('vphoto'), file)) throw new Error('This browser cannot attach the photo automatically.');
            return highlight('[onclick*="runYoloVerification"]', 'Checking quality');
          })
          .then(function () { return say('Got it. Checking the quality now. Please wait.'); })
          .then(function () {
            setMode('thinking', 'Grading your crop…');
            cropVerify.ver = null;
            return runYoloVerification();
          })
          .then(function () {
            clearHighlight();
            if (cropVerify && cropVerify.ver) return;
            return ask('The quality check did not work. Shall we try another photo?', { type: 'yesno' }, { noSwitch: true })
              .then(function (yes) { if (!yes) throw new Cancel(); goToCropStep(2); return waitFor(function () { return $('vphoto'); }).then(photoStep); });
          });
      })
      .then(function () {
        ver = cropVerify.ver;
        grade = ver.grade;
        return Promise.all([
          api('/api/produce/certificate/' + ver.verification_id + '/details').catch(function () { return null; }),
          waitFor(function () { return document.querySelector('.quality-result'); })
        ]);
      })
      .then(function (res) {
        var cert = res[0];
        highlight('.quality-result', 'Grade ' + grade);
        var line = 'Your ' + crop + ' is grade ' + grade + '. The quality certificate is ready';
        if (cert && cert.validity_days) line += ' and stays valid for ' + cert.validity_days + ' days';
        return say(line + '.');
      })
      .then(function () {
        setField('vqty', qtl);
        if ($('vdate') && !$('vdate').value) setField('vdate', new Date().toISOString().slice(0, 10));
        return highlight('#vqty', qtyWords(qtl));
      })
      .then(function () { return api('/api/voice/price?crop=' + encodeURIComponent(crop)).catch(function () { return { found: false }; }); })
      .then(function (p) {
        priceInfo = p;
        if (it.price) { price = it.price; return; }
        var q = p && p.found
          ? 'Today ' + crop + ' sells for about ' + p.average + ' rupees a quintal in ' + p.state + '. The best price is ' + p.best + ' rupees at ' + p.best_market + '. What price per quintal do you want? You can say market price.'
          : 'What price per quintal do you want for your ' + crop + '?';
        return highlight('#vprice', 'Price per quintal')
          .then(function () { return ask(q, { type: 'price' }); })
          .then(function (v) {
            price = (v === 'market' || typeof v !== 'number') ? (priceInfo && priceInfo.found ? priceInfo.suggested : null) : v;
            if (!price) throw new Cancel();
          });
      })
      .then(function () {
        setField('vprice', price);
        return highlight('[onclick*="publishVerifiedCrop"]', 'Publish');
      })
      .then(function () {
        var total = Math.round(price * qtl);
        return confirm(qtyWords(qtl) + ' ' + crop + ', grade ' + grade + ', at ' + price + ' rupees per quintal. That is about ' + total + ' rupees in total. Shall I put this up for buyers?');
      })
      .then(function (yes) {
        if (!yes) { clearHighlight(); return say('Okay, I did not publish it. The form is still open if you want to change something.'); }
        setMode('thinking', 'Publishing…');
        return publishVerifiedCrop().then(function () {
          clearHighlight();
          var published = $('modal').classList.contains('hidden');
          if (!published) return say('Publishing did not work. Please check the form on the screen.');
          return waitFor(function () { return document.querySelector('[onclick*="openCertificate"]'); }, 4000)
            .then(function (certBtn) {
              if (certBtn) highlight(certBtn, 'Your certificate');
              return say('Done! Your ' + crop + ' is now visible to buyers. When a buyer makes an offer, say show offers.');
            })
            .then(function () { return sleep(1200); })
            .then(clearHighlight);
        });
      });
  };

  function pendingOffers() {
    return api('/api/v2/v3/offers').then(function (list) {
      S.offers = (list || []).filter(function (o) {
        return ['ACCEPT', 'DECLINE', 'DECLINED', 'ACCEPTED', 'CANCELLED', 'COMPLETED'].indexOf(String(o.status || '').toUpperCase()) < 0;
      });
      return S.offers;
    });
  }

  function offerLine(o, i) {
    var total = Math.round((o.offer_price || 0) * (o.quantity_qtl || 0));
    return 'Offer ' + (i + 1) + ': ' + (o.buyer_name || 'A buyer') + ' wants ' + qtyWords(o.quantity_qtl || 0) + ' ' + o.crop +
      ' at ' + Math.round(o.offer_price) + ' rupees per quintal, total ' + total + ' rupees.';
  }

  function offerCard(o) {
    var b = document.querySelector('[onclick*="openOfferConfirmation(' + o.id + ')"]');
    return b ? b.closest('.offer-card') || b : null;
  }

  function findOffer(ref) {
    var list = S.offers;
    if (!list.length) return null;
    if (ref == null || ref === '') return list.length === 1 ? list[0] : null;
    var n = typeof ref === 'number' ? ref : parseInt(ref, 10);
    if (!isNaN(n) && list[n - 1]) return list[n - 1];
    var r = String(ref).toLowerCase();
    return list.filter(function (o) {
      return String(o.crop || '').toLowerCase().indexOf(r) >= 0 || String(o.buyer_name || '').toLowerCase().indexOf(r) >= 0 ||
        r.indexOf(String(o.crop || '').toLowerCase()) >= 0;
    })[0] || null;
  }

  TASKS.show_offers = function () {
    if (role() !== 'farmer') return go(role() === 'buyer' ? 'orders' : 'dashboard').then(function () { return say(PAGE_INFO[page()] || ''); });
    return go('market').then(pendingOffers).then(function (offers) {
      if (!offers.length) return say('You have no new buyer offers right now. Say sell my crop to add a crop for buyers.');
      var shown = offers.slice(0, 3);
      return say('You have ' + offers.length + ' new ' + (offers.length === 1 ? 'offer' : 'offers') + '.')
        .then(function () {
          return shown.reduce(function (p, o, i) {
            return p.then(function () { return highlight(offerCard(o), 'Offer ' + (i + 1)); })
              .then(function () { return say(offerLine(o, i)); });
          }, Promise.resolve());
        })
        .then(function () {
          var screen = shown.map(offerLine).join('\n');
          return say(shown.length === 1 ? 'Do you want to accept it, decline it, or wait?' : 'Which offer do you want to accept or decline? For example, say accept offer 1.')
            .then(function () { return listen(); })
            .then(function (text) {
              clearHighlight();
              if (!text) return say('Okay. The offers are on the screen.');
              var q = quick(text);
              if (q === 'stop' || q === 'no') return say('Okay.');
              if (q === 'yes' && shown.length === 1) return TASKS.accept_offer({ offer_ref: 1 });
              return interpret(text, null, screen).then(runIntent);
            });
        });
    });
  };

  function offerDecision(it, action) {
    if (role() !== 'farmer') return say('Only the farmer can answer offers.');
    return go('market').then(function () { return S.offers.length ? S.offers : pendingOffers(); }).then(function () {
      var o = findOffer(it.offer_ref);
      if (!o) {
        if (!S.offers.length) return say('There are no open offers to ' + (action === 'ACCEPT' ? 'accept.' : 'decline.'));
        return ask('Which offer? Say the offer number.', { type: 'choice', options: S.offers.slice(0, 5).map(offerLine) }, { noSwitch: true })
          .then(function (v) { return offerDecision({ offer_ref: v }, action); });
      }
      var idx = S.offers.indexOf(o);
      return highlight(offerCard(o), 'Offer ' + (idx + 1)).then(function () {
        var total = Math.round(o.offer_price * o.quantity_qtl);
        var q = action === 'ACCEPT'
          ? 'Accept ' + (o.buyer_name || 'the buyer') + "'s offer: " + qtyWords(o.quantity_qtl) + ' ' + o.crop + ' at ' + Math.round(o.offer_price) + ' rupees per quintal, total ' + total + ' rupees? The buyer must pay the security token before the order is confirmed.'
          : 'Decline ' + (o.buyer_name || 'the buyer') + "'s offer for " + o.crop + ' at ' + Math.round(o.offer_price) + ' rupees per quintal?';
        return confirm(q);
      }).then(function (yes) {
        clearHighlight();
        if (!yes) return say('Okay, I did not change anything.');
        setMode('thinking');
        var p = action === 'ACCEPT' ? confirmOfferAcceptance(o.id) : offerAction(o.id, 'DECLINE');
        return Promise.resolve(p).then(function () {
          S.offers = S.offers.filter(function (x) { return x.id !== o.id; });
          return say(action === 'ACCEPT'
            ? 'Accepted. I will tell the buyer to pay the token. You can see the order on the screen.'
            : 'Declined. The buyer has been told.');
        });
      });
    });
  }

  TASKS.accept_offer = function (it) { return offerDecision(it, 'ACCEPT'); };
  TASKS.decline_offer = function (it) { return offerDecision(it, 'DECLINE'); };

  TASKS.book_transport = function (it) {
    if (role() !== 'farmer') return say('Transport booking is for farmers. Buyers can use bulk logistics.').then(function () { return go('bulk'); });
    var crop = it.crop, pickup = it.pickup, drop = it.dropoff, km;
    return go('transport')
      .then(function () { return highlight('[onclick*="openTransportRequest"]', 'Request transport'); })
      .then(function () { return say('Let us book a truck.'); })
      .then(function () { clearHighlight(); openTransportRequest(); return waitFor(function () { return $('trCrop'); }); })
      .then(function () { return crop || ask('Which crop will the truck carry?', { type: 'crop' }).then(function (v) { crop = v; }); })
      .then(function () { setField('trCrop', crop); return pickup || highlight('#trPick', 'Pickup place').then(function () { return ask('Where should the truck pick up from? Say your village or farm.', { type: 'text' }); }).then(function (v) { pickup = v; }); })
      .then(function () { setField('trPick', pickup); return drop || highlight('#trDrop', 'Drop place').then(function () { return ask('Where should it go? Say the market name.', { type: 'text' }); }).then(function (v) { drop = v; }); })
      .then(function () { setField('trDrop', drop); return highlight('#trKm', 'Distance').then(function () { return ask('About how many kilometres is that?', { type: 'number' }); }); })
      .then(function (v) {
        km = Math.max(1, Math.round(Number(v) || 0));
        setField('trKm', km);
        setField('trCost', km * 22);
        return highlight('#trCost', 'Estimated cost');
      })
      .then(function () { return confirm('Book a truck for ' + crop + ' from ' + pickup + ' to ' + drop + ', ' + km + ' kilometres, estimated ' + (km * 22) + ' rupees?'); })
      .then(function (yes) {
        clearHighlight();
        if (!yes) return say('Okay, not booked. The form is still open.');
        return Promise.resolve(saveTransport()).then(function () {
          return say($('modal').classList.contains('hidden') ? 'Your transport request is sent. Transporters nearby will respond.' : 'Booking did not go through. Please check the form.');
        });
      });
  };

  TASKS.show_certificates = function () {
    if (role() === 'buyer') {
      return go('discover').then(function () { return waitFor(function () { return document.querySelector('.cert-strip'); }, 2500); })
        .then(function (strip) {
          if (!strip) return say('Each harvest card shows its quality certificate when it has one. None of the listings here have one yet. You can find more under Connect Buyers.');
          return highlight(strip, 'Quality certificate').then(function () { return say('This strip shows the grade, the date the photo was scanned, and until when the certificate is valid. Tap View to see the photo.'); });
        });
    }
    return go('crops').then(function () { return waitFor(function () { return document.querySelector('[onclick*="openCertificate"]'); }, 2500); })
      .then(function (btn) {
        if (!btn) return say('You have no quality certificates yet. Say sell my crop and I will help you make one.');
        var m = btn.getAttribute('onclick').match(/openCertificate\('([^']+)'\)/);
        return highlight(btn, 'Certificate').then(function () {
          return m ? api(m[1].replace(/\/?$/, '') + '/details').catch(function () { return null; }) : null;
        }).then(function (c) {
          clearHighlight();
          if (m) openCertificate(m[1]);
          if (!c) return say('Here is your latest certificate.');
          var status = c.status === 'EXPIRED' ? 'It has expired. Take a new photo to get a fresh grade.'
            : c.status === 'EXPIRING' ? 'It expires soon.' : 'It is valid for ' + c.days_left + ' more days.';
          return waitFor(function () { return document.querySelector('.cert-view'); }, 3000).then(function () {
            highlight('.cert-status', null);
            return say('Your latest certificate: ' + c.crop + ', grade ' + c.grade + '. ' + status);
          }).then(function () { return sleep(800); }).then(clearHighlight);
        });
      });
  };

  TASKS.navigate = function (it) {
    if (!it.page) return say('Which page do you want to open?');
    return go(it.page).then(function () {
      var nav = document.querySelector('[onclick="route(\'' + it.page + '\')"]');
      return highlight(nav, null).then(function () {
        return say(PAGE_INFO[it.page] || ('Opened ' + (w.tr ? tr(it.page) : it.page) + '.'));
      }).then(clearHighlight);
    });
  };

  TASKS.read_page = function () {
    var content = $('content');
    var parts = [];
    var title = $('pageTitle') ? $('pageTitle').textContent : '';
    if (title) parts.push(title);
    if (content) {
      content.querySelectorAll('h1,h2,h3,.stat-card,.hero-reco,.offer-main,.listing-body h3,.cert-strip-text,p').forEach(function (el) {
        if (parts.join(' ').length > 700) return;
        if (el.closest('button,.hidden')) return;
        var t = el.innerText.replace(/\s+/g, ' ').trim();
        if (t && parts.indexOf(t) < 0) parts.push(t);
      });
    }
    return say(parts.join('. ').slice(0, 900), { raw: true });
  };

  TASKS.question = function (it) {
    return say(it.answer || 'Sorry, I do not have an answer for that.', { raw: !!it.answer });
  };
  TASKS.check_price = function (it) {
    return TASKS.question(it).then(function () {
      if (role() !== 'farmer' || !it.crop) return;
      return say('Do you want to sell your ' + it.crop + ' now?').then(function () { return listen(); }).then(function (text) {
        if (quick(text) === 'yes') return TASKS.sell_produce({ crop: it.crop });
        if (text && quick(text) !== 'no' && quick(text) !== 'stop') return interpret(text).then(runIntent);
      });
    });
  };

  TASKS.change_language = function (it) {
    var code = it.language;
    if (!code || !w.LANGS || !LANGS[code]) return say('Which language? Say for example Hindi, Marathi or Tamil.');
    setLanguage(code);
    return sleep(600).then(function () { return say('Okay. I will talk in this language now.'); });
  };

  TASKS.help = function () {
    setChips(defaultChips());
    var farmer = 'You can say: I have 30 kilo tomatoes. Show buyer offers. Accept offer 1. What is the onion price today. Book a truck. Show my certificates. Open payments. Read this page. Or say teach me, and I will show you how the app works.';
    var buyer = 'You can say: Show harvests. Open my orders. What is the tomato price today. Show certificates. Read this page. Or say teach me.';
    return say(role() === 'farmer' ? farmer : role() === 'buyer' ? buyer : 'You can say the name of a page to open it, or ask read this page.');
  };

  TASKS.logout = function () {
    return confirm('Do you want to log out?').then(function (yes) {
      if (!yes) return say('Okay.');
      return say('Goodbye.').then(function () { stopAgent(false); logout(); });
    });
  };

  TASKS.stop = function () { throw new Cancel(); };

  /* ---------- tutorials ("teach me") ---------- */
  var TOURS = {
    farmer_app: [
      { page: 'dashboard', sel: '[onclick="route(\'dashboard\')"]', text: 'This is your home page. It shows your income and important news.' },
      { sel: '[onclick="route(\'crops\')"]', text: 'Crops is where you add a crop to sell and see its quality certificate.' },
      { sel: '[onclick="route(\'market\')"]', text: 'Market and Offers shows what buyers offer you. You can accept or decline.' },
      { sel: '[onclick="route(\'transport\')"]', text: 'Transport is where you book a truck.' },
      { sel: '[onclick="route(\'paymentsRewards\')"]', text: 'Payments shows the money you received.' },
      { sel: '#vaFab', text: 'And whenever you need me, tap this green mic and just talk. I can do all of this for you.' }
    ],
    farmer_sell: [
      { page: 'crops', sel: '[onclick*="openVerifiedCropFlow"]', text: 'To sell, tap Add Crop. Or just tell me, for example: I have 30 kilo tomatoes.' },
      { sel: '[onclick*="openVerifiedCropFlow"]', text: 'First the app saves your farm location. Then you take a photo of the crop.' },
      { sel: '[onclick*="openVerifiedCropFlow"]', text: 'KisanSetu checks the photo and gives a grade: A, B or C, with a quality certificate.' },
      { sel: '[onclick*="openCertificate"]', text: 'Your certificates appear here. Buyers see the photo, the grade and until when it is valid.' },
      { sel: '#vaFab', text: 'Then you choose a price and publish. I can do all these steps with you by voice.' }
    ],
    farmer_offers: [
      { page: 'market', sel: '.offer-card', text: 'Each card is an offer from a buyer: the crop, how much, and the price.' },
      { sel: '[onclick*="openOfferConfirmation"]', text: 'Accept agrees to the offer. The buyer then pays a security token.' },
      { sel: '[onclick*="\'DECLINE\'"]', text: 'Decline says no to this offer.' },
      { sel: '[onclick*="openNegotiationChat"]', text: 'Negotiate lets you ask for a better price in chat.' },
      { sel: '#vaFab', text: 'You can also say: show offers, or accept offer 1.' }
    ],
    farmer_transport: [
      { page: 'transport', sel: '[onclick*="openTransportRequest"]', text: 'Tap here to request a truck. You say where to pick up and where to drop.' },
      { sel: '#vaFab', text: 'Or just say: book a truck, and I will fill it in with you.' }
    ],
    buyer_app: [
      { page: 'discover', sel: '[onclick="route(\'discover\')"]', text: 'Discover shows verified harvests you can buy.' },
      { sel: '.cert-strip', text: 'This strip is the quality certificate: grade, scan date and validity. Tap View to see the crop photo.' },
      { sel: '[onclick="route(\'orders\')"]', text: 'My Orders shows what you bought and its delivery.' },
      { sel: '#vaFab', text: 'Tap the mic any time and tell me what you need.' }
    ]
  };

  TASKS.tour = function (it) {
    var topic = String(it.topic || 'app').toLowerCase();
    var key = role() + '_' + (/sell|crop|list/.test(topic) ? 'sell' : /offer|buyer/.test(topic) ? 'offers' : /transport|truck/.test(topic) ? 'transport' : /cert/.test(topic) ? 'sell' : 'app');
    var steps = TOURS[key] || TOURS[role() + '_app'] || TOURS.farmer_app;
    return say('Let me show you. Say stop at any time.').then(function () {
      return steps.reduce(function (p, step) {
        return p.then(function () {
          checkActive();
          return (step.page ? go(step.page) : Promise.resolve())
            .then(function () { return waitFor(function () { return document.querySelector(step.sel); }, 1500); })
            .then(function (el) { return el ? highlight(el, step.text) : Promise.resolve(); })
            .then(function () { return say(step.text); })
            .then(function () { return sleep(500); });
        });
      }, Promise.resolve());
    }).then(function () {
      clearHighlight();
      return say('That is it. What would you like to do now?');
    });
  };

  /* ------------------------------------------------------------------ *
   * Dispatch
   * ------------------------------------------------------------------ */
  function runIntent(r, depth) {
    depth = depth || 0;
    if (!r) return Promise.resolve();
    if (r.kind === 'command' && r.intent === 'stop') throw new Cancel();
    if (r.kind === 'unclear' || (r.kind === 'answer' && !r.intent)) return say('Sorry, I did not understand. Say help to hear what I can do.');
    var task = TASKS[r.intent] || TASKS.question;
    S.task = r.intent;
    return Promise.resolve().then(function () { return task(r); }).catch(function (e) {
      if (e instanceof Switch && depth < 3) return runIntent(e.intent, depth + 1);
      throw e;
    }).then(function () { S.task = null; }, function (e) { S.task = null; throw e; });
  }

  function handleUtterance(text) {
    var q = quick(text);
    if (q === 'stop') return stopAgent(true);
    if (q === 'repeat') return say(S.lastSaid || 'How can I help?', { raw: true });
    if (q === 'help') return TASKS.help();
    return interpret(text).then(runIntent);
  }

  /* The conversation loop: listen -> act -> listen again, until stopped.
     Only one may run. S.loops counts live loops (including the greeting), and
     startAgent() waits for an old loop to finish unwinding before starting a
     new one - otherwise two loops would share, and misroute, the user's replies. */
  function mainLoop(firstText, greet) {
    var sid = ++S.session;
    var misses = 0, pendingText = firstText;
    var alive = function () { return S.active && S.session === sid; };

    function step() {
      if (!alive()) return Promise.resolve();
      var turn = pendingText ? Promise.resolve(pendingText) : listen();
      pendingText = null;
      return turn.then(function (t) {
        if (!alive()) return;
        if (!t) {
          misses++;
          // Hands-free mode stays on until the user taps Stop; just keep listening.
          if (misses === 3) setMode('listening', 'Still listening… tap Stop to end');
          return step();
        }
        misses = 0;
        return Promise.resolve().then(function () { return handleUtterance(t); }).catch(function (e) {
          clearHighlight();
          closeCamera();
          if (!alive()) return;
          if (e instanceof Cancel) return say('Okay, stopped. What else can I do?');
          console.error('[voice]', e);
          return say('Something went wrong: ' + (e && e.message ? e.message : 'please try again') + '.');
        }).then(step);
      });
    }

    S.loops++;
    (greet ? say(greet) : Promise.resolve())
      .then(step)
      .catch(function (e) { if (!(e instanceof Cancel)) console.error('[voice]', e); })
      .then(function () { S.loops--; });
  }

  function closeCamera() {
    var cam = $('vaCam'), v = $('vaVideo');
    if (cam) cam.classList.add('hidden');
    if (v && v.srcObject) { v.srcObject.getTracks().forEach(function (t) { t.stop(); }); v.srcObject = null; }
  }

  function startAgent(firstText) {
    if (S.active || S.starting) return;
    if (!getMe()) return;
    if (!w.isSecureContext) { toast('Voice needs https or localhost.'); return; }
    S.starting = true;
    $('vaNudge').classList.add('hidden');
    $('vaHud').classList.remove('hidden');
    $('vaFab').classList.add('va-live');
    document.body.classList.add('va-on');
    setChips(defaultChips());
    // Unlock speech on iOS/Chrome: first utterance must come from the tap.
    try { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(' ')); } catch (e) {}
    try { if (w.LP && LP.stop) LP.stop(); } catch (e) {}
    var greet = S.greeted
      ? 'Yes, I am listening.'
      : 'Namaste ' + ((getMe() || {}).name || '').split(' ')[0] + '. I am Saathi. Tell me what you want to do. For example: I have 30 kilo tomatoes, or show buyer offers, or teach me.';
    S.greeted = true;
    // A loop from before the last stop may still be finishing a network call.
    // It cancels itself at its next step (S.active was false); wait for that.
    // S.active stays false meanwhile, so the old task fails its next check.
    var waited = 0;
    (function begin() {
      if (!S.starting) return; // stopped while waiting
      if (S.loops > 0 && waited < 60000) { setMode('thinking', 'Starting…'); waited += 150; return setTimeout(begin, 150); }
      S.starting = false;
      S.active = true;
      $('vaFab').classList.add('va-live');
      mainLoop(firstText, firstText ? null : greet);
    })();
  }

  function stopAgent(sayBye) {
    var wasStarting = S.starting;
    S.starting = false;
    if (!S.active && !wasStarting) return;
    S.active = false;
    S.session++;
    S.pending = null;
    if (S.abortListen) S.abortListen(null);
    stopRecognition();
    try { speechSynthesis.cancel(); } catch (e) {}
    clearHighlight();
    closeCamera();
    $('vaConfirm').classList.add('hidden');
    $('vaHud').classList.add('hidden');
    $('vaFab').classList.remove('va-live');
    document.body.classList.remove('va-on');
    setMode('idle');
  }

  /* ------------------------------------------------------------------ *
   * Wiring
   * ------------------------------------------------------------------ */
  /* The Talk button lives in the page header, not floating over content. */
  function placeFab() {
    var fab = $('vaFab'), controls = document.querySelector('.header-controls');
    var header = controls && controls.closest('header'), hud = $('vaHud');
    // The voice panel is a strip inside the header, so it takes its own space
    // instead of floating over page buttons.
    if (header && hud && hud.parentNode !== header) { hud.classList.add('va-hud-docked'); header.appendChild(hud); }
    if (!fab || !controls || fab.parentNode === controls) return;
    fab.classList.add('va-fab-header');
    controls.insertBefore(fab, controls.firstChild);
  }

  function showForUser() {
    var logged = !!(getMe() && $('appShell') && !$('appShell').classList.contains('hidden'));
    $('vaFab').classList.toggle('hidden', !logged);
    if (!logged) { stopAgent(false); $('vaNudge').classList.add('hidden'); return; }
    tx('Talk').then(function (t) { document.querySelector('.va-fab-label').textContent = t; });
    placeFab();
  }

  function wrap(name, after) {
    var orig = w[name];
    if (typeof orig !== 'function') return;
    w[name] = function () {
      var out = orig.apply(this, arguments);
      Promise.resolve(out).then(after, after);
      return out;
    };
  }

  function init() {
    buildUI();
    wrap('boot', showForUser);
    wrap('logout', showForUser);
    wrap('setLanguage', function () { if (getMe()) showForUser(); });
    // If the person navigates by hand, drop a stale spotlight.
    document.addEventListener('click', function (e) {
      if (!S.active && spotEl && !e.target.closest('#vaRoot')) clearHighlight();
    }, true);
    var appShell = $('appShell');
    if (appShell && w.MutationObserver) {
      new MutationObserver(showForUser).observe(appShell, { attributes: true, attributeFilter: ['class'] });
    }
    if (w.speechSynthesis) speechSynthesis.getVoices();
    // A stop can reject promises nobody is waiting on any more; that is expected.
    addEventListener('unhandledrejection', function (e) {
      if (e.reason instanceof Cancel || e.reason instanceof Switch) e.preventDefault();
    });
    showForUser();
  }

  w.SaathiVoice = {
    start: startAgent, stop: stopAgent, handle: deliver,
    quick: quick, state: S,
    script: function (lines) { S.script = (lines || []).slice(); },
    useServerStt: function (on) { S.serverStt = !!on; localStorage.setItem('gram_va_stt', on ? 'server' : 'browser'); }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window);
