/* GRAM AI quality certificate view.
 *
 * Replaces app.js's openCertificate(url), which only opened the PDF, with a
 * certificate card for farmers and buyers: produce photo, grade, the date the
 * photo was scanned, and how long the grade stays valid. The PDF is still one
 * tap away. Also provides certStrip() for listing cards and loads protected
 * produce photos (they need the login token, so a plain <img src> cannot work).
 *
 * Uses globals from app.js: api, token, esc, toast, $.
 */
(function (w) {
  'use strict';

  var STATUS = {
    VALID: { icon: '✅', label: 'Valid' },
    EXPIRING: { icon: '⚠️', label: 'Expires soon' },
    EXPIRED: { icon: '❌', label: 'Expired' },
    UNKNOWN: { icon: '❔', label: 'Validity unknown' }
  };

  function parseUtc(s) {
    return s ? new Date(String(s).replace(' ', 'T') + 'Z') : null;
  }

  function dateOnly(s) {
    var d = parseUtc(s);
    return d ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
  }

  function dateTime(s) {
    var d = parseUtc(s);
    return d ? d.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—';
  }

  function daysText(n) {
    return n === 1 ? '1 day' : n + ' days';
  }

  function statusLine(c) {
    if (c.status === 'EXPIRED') return 'Expired on ' + dateOnly(c.valid_until) + '. Ask the farmer to scan the produce again.';
    if (c.status === 'EXPIRING') return c.days_left < 1 ? 'Expires today, ' + dateTime(c.valid_until) + '.' : 'Expires soon: ' + daysText(c.days_left) + ' left.';
    if (c.status === 'VALID') return daysText(c.days_left) + ' left. Valid until ' + dateOnly(c.valid_until) + '.';
    return 'Validity could not be worked out.';
  }

  function vidFromUrl(url) {
    var m = String(url || '').match(/certificate\/(\d+)/);
    return m ? m[1] : null;
  }

  /* Fetch an auth-protected file and return an object URL. */
  function authBlobUrl(url) {
    return fetch(url, { headers: { Authorization: 'Bearer ' + token } })
      .then(function (r) {
        if (!r.ok) throw new Error('unavailable');
        return r.blob();
      })
      .then(function (b) { return URL.createObjectURL(b); });
  }

  /* ---------- compact strip for listing cards ---------- */

  function certStrip(c) {
    if (!c) return '';
    var st = STATUS[c.status] || STATUS.UNKNOWN;
    return '<div class="cert-strip cert-' + c.status + '">' +
      '<span class="cert-strip-icon" aria-hidden="true">📜</span>' +
      '<div class="cert-strip-text">' +
        '<b>' + st.icon + ' ' + st.label + '</b>' +
        '<small>Scanned ' + esc(dateOnly(c.scanned_at)) + ' • Valid till ' + esc(dateOnly(c.valid_until)) + '</small>' +
      '</div>' +
      '<button type="button" class="secondary" onclick="openCertificate(\'' + c.pdf_url + '\')">View</button>' +
    '</div>';
  }

  /* ---------- full certificate card ---------- */

  function openPdf(url) {
    authBlobUrl(url).then(function (u) {
      w.open(u, '_blank');
      setTimeout(function () { URL.revokeObjectURL(u); }, 60000);
    }).catch(function () { toast('Certificate unavailable'); });
  }

  function render(c) {
    var st = STATUS[c.status] || STATUS.UNKNOWN;
    var total = c.validity_days * 86400000;
    var used = total ? Math.min(100, Math.max(0, (Date.now() - parseUtc(c.scanned_at)) / total * 100)) : 100;
    var place = [c.district, c.state].filter(Boolean).join(', ');

    $('modalBody').innerHTML =
      '<div class="cert-view">' +
        '<div class="cert-head">' +
          '<span class="cert-seal" aria-hidden="true">📜</span>' +
          '<div><h2>Quality Certificate</h2><small data-no-i18n>' + esc(c.certificate_number) + '</small></div>' +
          (w.LP ? '<button type="button" class="app-listen cert-listen" onclick="LP.speakEl(document.querySelector(\'.cert-view\'))"><span aria-hidden="true">🔊</span><span class="app-listen-label">Listen</span></button>' : '') +
        '</div>' +

        '<div class="cert-status cert-' + c.status + '">' +
          '<span class="cert-status-icon" aria-hidden="true">' + st.icon + '</span>' +
          '<div><b>' + st.label + '</b><p>' + esc(statusLine(c)) + '</p></div>' +
        '</div>' +

        '<div class="cert-body">' +
          '<figure class="cert-photo">' +
            (c.has_photo
              ? '<img alt="Scanned photo of the ' + esc(c.crop) + '" data-cert-photo="' + c.photo_url + '">'
              : '<div class="cert-photo-missing">📷<span>Photo not available</span></div>') +
            '<figcaption>Photo scanned on ' + esc(dateTime(c.scanned_at)) + '</figcaption>' +
          '</figure>' +

          '<div class="cert-facts">' +
            '<div class="cert-grade"><small>Grade</small><b data-no-i18n>' + esc(c.grade || '—') + '</b><span>' + esc(c.crop) + '</span></div>' +
            fact('📅', 'Scanned on', dateTime(c.scanned_at)) +
            fact('⏳', 'Valid until', dateTime(c.valid_until)) +
            fact('🗓️', 'Validity period', daysText(c.validity_days) + ' for ' + c.crop) +
            fact('🎯', 'AI confidence', Math.round((c.confidence || 0) * 100) + '%') +
            fact('👨‍🌾', 'Farmer', (c.farmer_name || '—') + (place ? ', ' + place : '')) +
          '</div>' +
        '</div>' +

        '<div class="cert-timeline" aria-hidden="true">' +
          '<div class="cert-timeline-bar"><span style="width:' + used.toFixed(1) + '%"></span></div>' +
          '<div class="cert-timeline-labels"><span>' + esc(dateOnly(c.scanned_at)) + '</span><span>' + esc(dateOnly(c.valid_until)) + '</span></div>' +
        '</div>' +

        '<p class="cert-note">A grade is valid for the time this crop normally keeps its quality after the photo is taken. After that the produce must be photographed and graded again.</p>' +

        '<div class="cert-actions">' +
          '<button type="button" class="primary" id="certPdfBtn">📄 Open PDF certificate</button>' +
        '</div>' +
      '</div>';

    $('certPdfBtn').onclick = function () { openPdf(c.pdf_url); };
    $('modal').classList.remove('hidden');
    hydratePhotos($('modalBody'));
  }

  function fact(icon, label, value) {
    return '<div class="cert-fact"><span aria-hidden="true">' + icon + '</span><div><small>' + label + '</small><b>' + esc(value) + '</b></div></div>';
  }

  function openCertificate(url) {
    var vid = vidFromUrl(url);
    if (!vid) { openPdf(url); return; }
    api('/api/produce/certificate/' + vid + '/details')
      .then(render)
      .catch(function () { openPdf(url); }); // older servers: fall back to the PDF
  }

  /* ---------- protected photos ---------- */

  function hydratePhotos(root) {
    (root || document).querySelectorAll('img[data-cert-photo]').forEach(function (img) {
      var url = img.getAttribute('data-cert-photo');
      if (!url || img.__certLoaded) return;
      img.__certLoaded = true;
      authBlobUrl(url).then(function (u) {
        img.onerror = null;
        img.src = u;
        img.style.display = '';
        var ph = img.nextElementSibling;
        if (ph && ph.classList.contains('photo-placeholder')) ph.style.display = 'none';
      }).catch(function () {});
    });
  }

  function watchContent() {
    var content = $('content');
    if (!content || !w.MutationObserver) return;
    new MutationObserver(function () { hydratePhotos(content); })
      .observe(content, { childList: true, subtree: true });
  }

  w.certStrip = certStrip;
  w.openCertificate = openCertificate;
  w.hydrateCertPhotos = hydratePhotos;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchContent);
  else watchContent();
})(window);
