/* Colour-scheme bootstrap — runs inside <head>, before the application paints.
 *
 * The problem it solves: Gradio picks the theme asynchronously from the OS
 * preference, so on a dark machine a stored light choice would flash dark (and
 * the reverse). Reading the stored choice here and applying it to <html> before
 * the first paint removes that flash entirely; main.js keeps it in sync later.
 *
 * Storage key: "ktem-theme" with the values "light" / "dark". When it is absent
 * the OS preference decides.
 *
 * This is the only place where a literal colour is allowed: the inline background
 * has to be written before tokens.css is guaranteed to have been applied, and it
 * mirrors --ui-bg (dark) from that file.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "ktem-theme";
  var DARK_BG = "#0A0F1E"; // tokens.css: --ui-bg (dark)
  var LIGHT_BG = ""; // let the stylesheet own the light background

  function readStored() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return value === "dark" || value === "light" ? value : null;
    } catch (err) {
      return null; // storage disabled (private mode): fall back to the OS
    }
  }

  function systemPrefersDark() {
    try {
      return !!(
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      );
    } catch (err) {
      return false;
    }
  }

  function preferredTheme() {
    return readStored() || (systemPrefersDark() ? "dark" : "light");
  }

  function isDark() {
    return preferredTheme() === "dark";
  }

  function apply(theme) {
    var dark = theme === "dark";
    var root = document.documentElement;

    if (dark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

    try {
      root.style.colorScheme = dark ? "dark" : "light";
    } catch (err) {
      /* old browser: color-scheme is a hint only */
    }

    // what prevents the white flash on a dark page
    root.style.backgroundColor = dark ? DARK_BG : LIGHT_BG;

    // Gradio applies its own `.dark` class to <body> from the OS preference, and
    // its component variables follow that class. Keep it in sync with ours.
    var body = document.body;
    if (body) {
      if (dark) {
        body.classList.add("dark");
      } else {
        body.classList.remove("dark");
      }
    }

    return dark;
  }

  function sync() {
    return apply(preferredTheme());
  }

  function setTheme(theme) {
    var next = theme === "dark" ? "dark" : "light";
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (err) {
      /* not fatal: the choice just will not survive a reload */
    }
    return apply(next);
  }

  window.__KTEM_theme = {
    key: STORAGE_KEY,
    stored: readStored,
    preferred: preferredTheme,
    isDark: isDark,
    apply: apply,
    sync: sync,
    set: setTheme,
  };

  // first paint: <html> exists here, <body> does not yet
  sync();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", sync);
  }

  // Gradio applies its theme once the app config arrives, i.e. later than this
  // script. Re-assert the stored choice a few times so an explicit "light" wins
  // over a dark OS setting.
  [0, 150, 600, 1500].forEach(function (delay) {
    window.setTimeout(sync, delay);
  });

  // With no stored choice, follow the OS live.
  try {
    if (window.matchMedia) {
      var media = window.matchMedia("(prefers-color-scheme: dark)");
      var onSystemChange = function () {
        if (!readStored()) {
          sync();
        }
      };
      if (media.addEventListener) {
        media.addEventListener("change", onSystemChange);
      } else if (media.addListener) {
        media.addListener(onSystemChange);
      }
    }
  } catch (err) {
    /* no matchMedia: the initial preference is still applied */
  }
})();
