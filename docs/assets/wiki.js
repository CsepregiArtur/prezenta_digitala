/* ===================================================================
   Attendance Control — wiki language switcher
   English is the default; the choice is remembered in localStorage and
   can be overridden with ?lang=ro / ?lang=en.
   =================================================================== */
(function () {
  'use strict';

  var DEFAULT_LANG = 'en';
  var STORAGE_KEY = 'attendance-wiki-lang';
  var SUPPORTED = ['en', 'ro'];

  var dict = window.WIKI_I18N || {};

  function normalise(value) {
    var lang = String(value || '').slice(0, 2).toLowerCase();
    return SUPPORTED.indexOf(lang) >= 0 ? lang : DEFAULT_LANG;
  }

  function fromQuery() {
    var match = /[?&]lang=([a-zA-Z-]+)/.exec(window.location.search);
    return match ? normalise(match[1]) : null;
  }

  function fromStorage() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;   // private mode / blocked storage
    }
  }

  function remember(lang) {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch (error) { /* ignore */ }
  }

  /* Resolve the starting language: query string wins, then storage, then default. */
  function initialLanguage() {
    return normalise(fromQuery() || fromStorage() || DEFAULT_LANG);
  }

  function translate(lang) {
    var table = dict[lang] || dict[DEFAULT_LANG] || {};

    // Plain text nodes.
    document.querySelectorAll('[data-i18n]').forEach(function (node) {
      var value = table[node.getAttribute('data-i18n')];
      if (typeof value === 'string') node.textContent = value;
    });

    // Nodes that intentionally contain inline markup.
    document.querySelectorAll('[data-i18n-html]').forEach(function (node) {
      var value = table[node.getAttribute('data-i18n-html')];
      if (typeof value === 'string') node.innerHTML = value;
    });

    // Image alt text.
    document.querySelectorAll('[data-i18n-alt]').forEach(function (node) {
      var value = table[node.getAttribute('data-i18n-alt')];
      if (typeof value === 'string') node.setAttribute('alt', value);
    });

    // <title> and <meta name="description">.
    document.querySelectorAll('[data-i18n-meta]').forEach(function (node) {
      var value = table[node.getAttribute('data-i18n-meta')];
      if (typeof value !== 'string') return;
      if (node.tagName === 'TITLE') {
        node.textContent = value;
      } else {
        node.setAttribute('content', value);
      }
    });
  }

  function apply(lang, options) {
    lang = normalise(lang);
    var settings = options || {};

    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('data-lang', lang);

    document.querySelectorAll('.lang-btn').forEach(function (button) {
      var active = button.getAttribute('data-lang') === lang;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    translate(lang);

    if (settings.persist !== false) remember(lang);

    // Reflect the choice in the URL without adding history entries.
    if (window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      url.searchParams.set('lang', lang);
      window.history.replaceState(null, '', url.toString());
    }

    document.dispatchEvent(new CustomEvent('wiki:languagechange', { detail: { lang: lang } }));
  }

  function wire() {
    document.querySelectorAll('.lang-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        apply(button.getAttribute('data-lang'));
      });
    });
  }

  window.wikiSetLanguage = apply;

  function start() {
    wire();
    apply(initialLanguage());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
