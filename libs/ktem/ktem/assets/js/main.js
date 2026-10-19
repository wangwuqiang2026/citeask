/* Browser side of the UI.
 *
 * Gradio renders the page; this script performs the small structural fixes the
 * server-side layout cannot express (moving a few controls into their panels),
 * publishes the helpers the server-side `js=` callbacks call, and keeps the theme
 * toggle, the icon-button labels and the table tooltips current.
 *
 * IMPORTANT — this file must stay a *single function expression*: Gradio evaluates
 * `js=` as `let result = await (${js})(...args)`, so any top-level statement
 * (a `var`, a second function declaration, a comment *before* `function` is fine
 * but code is not) turns the whole bundle into a syntax error, and every handler
 * in it silently stops working. Everything therefore lives inside run().
 *
 * Everything here is defensive: the DOM is Gradio's, so every element may be
 * absent (component hidden, different page, re-render in progress). A missing
 * element must never take the whole script — and with it the other handlers —
 * down, hence the null checks and the try/catch around the bootstrap.
 */
function run() {
  /* Labels of the icon-only buttons. The text is a lookup key for the UI catalog
   * (window.__KTEM_t, published in <head>); with no catalog entry the English
   * literal is used. The two panel toggles are labelled from their current state
   * instead (see decorateIconButtons). */
  var ICON_BUTTON_LABELS = {
    "toggle-dark-button": "Toggle theme",
    "new-conv-button": "New chat",
    "rename-conv-button": "Rename conversation",
    "delete-conv-button": "Delete conversation",
  };

  var THEME_STORAGE_KEY = "ktem-theme";
  var DEFAULT_CONV_COLUMN_MIN_WIDTH = "min(300px, 100%)";
  /* Mirrors pages/chat/__init__.py: the information panel starts expanded. */
  var infoPanelExpanded = true;

  function t(text) {
    try {
      if (typeof window.__KTEM_t === "function") {
        return window.__KTEM_t(text);
      }
    } catch (err) {
      /* identity fallback below */
    }
    return text;
  }

  function themeApi() {
    return window.__KTEM_theme || null;
  }

  /* ------------------------------------------------------------------------ */
  /* theme                                                                    */
  /* ------------------------------------------------------------------------ */

  function isDarkTheme() {
    var api = themeApi();
    if (api) {
      try {
        return !!api.isDark();
      } catch (err) {
        /* fall through to the DOM */
      }
    }
    return document.documentElement.classList.contains("dark");
  }

  /* Keep <html>, <body> and the toggle's aria state on the same theme. */
  function syncThemeUi() {
    var dark = isDarkTheme();

    if (document.documentElement.classList.contains("dark") !== dark) {
      if (dark) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    }
    if (document.body) {
      if (document.body.classList.contains("dark") !== dark) {
        if (dark) {
          document.body.classList.add("dark");
        } else {
          document.body.classList.remove("dark");
        }
      }
    }

    var button = document.getElementById("toggle-dark-button");
    if (button) {
      button.setAttribute("aria-pressed", dark ? "true" : "false");
      button.title = t("Toggle theme");
    }

    return dark;
  }

  /* Switch light/dark, persist the choice and refresh the control. Called by the
   * header button (see main.py) and exposed for keyboard/automation use. */
  function toggleTheme() {
    try {
      var api = themeApi();
      var next = isDarkTheme() ? "light" : "dark";

      if (api && typeof api.set === "function") {
        api.set(next);
      } else {
        var dark = next === "dark";
        document.documentElement.classList.toggle("dark", dark);
        if (document.body) {
          document.body.classList.toggle("dark", dark);
        }
        try {
          window.localStorage.setItem(THEME_STORAGE_KEY, next);
        } catch (err) {
          /* storage disabled: the theme still switches for this page */
        }
      }

      syncThemeUi();
      return next;
    } catch (err) {
      console.warn("ktem: could not switch the colour scheme", err);
      return null;
    }
  }

  /* ------------------------------------------------------------------------ */
  /* icon buttons                                                             */
  /* ------------------------------------------------------------------------ */

  function applyIconLabel(button, text) {
    if (!button) {
      return;
    }
    var label = t(text);
    if (button.getAttribute("aria-label") !== label) {
      button.setAttribute("aria-label", label);
    }
    if (button.title !== label) {
      button.title = label;
    }
  }

  function decorateIconButtons() {
    var dark = isDarkTheme();

    Object.keys(ICON_BUTTON_LABELS).forEach(function (id) {
      var button = document.getElementById(id);
      if (!button) {
        return;
      }
      applyIconLabel(button, ICON_BUTTON_LABELS[id]);
      if (id === "toggle-dark-button") {
        button.setAttribute("aria-pressed", dark ? "true" : "false");
      }
    });

    // the sidebar toggle names the action it performs, not the panel it controls
    var convColumn = document.getElementById("conv-settings-panel");
    var chatExpandButton = document.getElementById("chat-expand-button");
    if (chatExpandButton) {
      var collapsed = convColumn
        ? convColumn.classList.contains("is-collapsed")
        : false;
      applyIconLabel(
        chatExpandButton,
        collapsed ? "Expand sidebar" : "Collapse sidebar"
      );
      chatExpandButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }

    var infoExpandButton = document.getElementById("info-expand-button");
    if (infoExpandButton) {
      applyIconLabel(
        infoExpandButton,
        infoPanelExpanded
          ? "Collapse information panel"
          : "Expand information panel"
      );
      infoExpandButton.setAttribute(
        "aria-expanded",
        infoPanelExpanded ? "true" : "false"
      );
    }
  }

  /* The buttons are re-rendered with their containers, so the labels have to be
   * re-applied after Gradio touches the DOM. Mutations are coalesced into one
   * animation frame. */
  function observeIconButtons() {
    decorateIconButtons();

    var root = document.body || document.documentElement;
    if (!root || typeof MutationObserver === "undefined") {
      return;
    }

    var scheduled = false;
    var observer = new MutationObserver(function () {
      if (scheduled) {
        return;
      }
      scheduled = true;
      var runAgain = function () {
        scheduled = false;
        decorateIconButtons();
      };
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(runAgain);
      } else {
        window.setTimeout(runAgain, 16);
      }
    });

    observer.observe(root, { childList: true, subtree: true });
  }

  /* ------------------------------------------------------------------------ */
  /* DOM helpers                                                              */
  /* ------------------------------------------------------------------------ */

  function moveNode(node, parent, before) {
    if (!node || !parent) {
      return false;
    }
    try {
      if (before && before.parentNode === parent) {
        parent.insertBefore(node, before);
      } else {
        parent.appendChild(node);
      }
      return true;
    } catch (err) {
      console.warn("ktem: could not move", node, err);
      return false;
    }
  }

  /* ------------------------------------------------------------------------ */
  /* shell                                                                    */
  /* ------------------------------------------------------------------------ */

  function decorateShell() {
    var appTabs = document.getElementById("app-tabs");
    var chatTab = document.getElementById("chat-tab");
    var tabsRoot = appTabs || (chatTab ? chatTab.parentNode : null);

    if (tabsRoot) {
      var nav = tabsRoot.querySelector(".tab-nav");
      if (nav) {
        nav.classList.add("header-bar");
      }
      tabsRoot.style.padding = "0";
      tabsRoot.style.margin = "0";
      if (tabsRoot.parentNode) {
        tabsRoot.parentNode.style.gap = "0";
        if (tabsRoot.parentNode.parentNode) {
          tabsRoot.parentNode.parentNode.style.padding = "0";
        }
      }
    }

    // add favicon (the launch call also serves one; this keeps deep links in sync)
    try {
      var favicon = document.createElement("link");
      favicon.rel = "icon";
      favicon.type = "image/svg+xml";
      favicon.href = "/favicon.ico";
      document.head.appendChild(favicon);
    } catch (err) {
      console.warn("ktem: could not add the favicon", err);
    }
  }

  /* ------------------------------------------------------------------------ */
  /* conversation panel + chat settings                                       */
  /* ------------------------------------------------------------------------ */

  function setupConversationControls() {
    var convColumn = document.getElementById("conv-settings-panel");
    var chatColumn = document.getElementById("main-chat-bot");
    var chatExpandButton = document.getElementById("chat-expand-button");

    if (convColumn) {
      convColumn.style.minWidth = DEFAULT_CONV_COLUMN_MIN_WIDTH;
    }

    // wide sidebar <-> collapsed sidebar; the CSS class owns the visual state so
    // the layout stays valid whichever media query is active
    globalThis.toggleChatColumn = function () {
      try {
        if (!convColumn) {
          return;
        }
        var collapsed = convColumn.classList.toggle("is-collapsed");
        convColumn.style.flexGrow = collapsed ? "0" : "1";
        convColumn.style.minWidth = collapsed
          ? "0px"
          : DEFAULT_CONV_COLUMN_MIN_WIDTH;
        if (chatExpandButton) {
          chatExpandButton.setAttribute(
            "aria-expanded",
            collapsed ? "false" : "true"
          );
        }
      } catch (err) {
        console.warn("ktem: could not toggle the sidebar", err);
      }
    };

    if (chatColumn && chatExpandButton) {
      chatColumn.insertBefore(chatExpandButton, chatColumn.firstChild);
    }

    // move the information-panel toggle into the accordion header
    var infoExpandButton = document.getElementById("info-expand-button");
    var infoPanel = document.getElementById("info-expand");
    if (infoExpandButton && infoPanel) {
      var infoAnchor =
        infoPanel.childNodes.length > 2 ? infoPanel.childNodes[2] : null;
      moveNode(infoExpandButton, infoPanel, infoAnchor);
    }
    if (infoExpandButton) {
      // Gradio's own handler resizes the panel; this only tracks the state the
      // label and aria-expanded describe.
      infoExpandButton.addEventListener("click", function () {
        infoPanelExpanded = !infoPanelExpanded;
        decorateIconButtons();
      });
    }

    // move the settings close button into its tab bar
    var settingsNav = document.querySelector("#settings-tab .tab-nav");
    var saveButton = document.getElementById("save-setting-btn");
    if (settingsNav && saveButton) {
      settingsNav.appendChild(saveButton);
    }

    // conversation dropdown placeholder
    var convInput = document.querySelector("#conversation-dropdown input");
    if (convInput) {
      convInput.placeholder = t("Browse conversation");
    }

    // move the mindmap checkbox and the citation dropdown into the chat settings
    var mindmapCheckbox = document.getElementById("use-mindmap-checkbox");
    var citationDropdown = document.getElementById("citation-dropdown");
    var chatSettingsPanel = document.getElementById("chat-settings-expand");
    if (chatSettingsPanel) {
      var settingsAnchor =
        chatSettingsPanel.childNodes.length > 2
          ? chatSettingsPanel.childNodes[2]
          : null;
      if (mindmapCheckbox) {
        moveNode(mindmapCheckbox, chatSettingsPanel, settingsAnchor);
      }
      if (citationDropdown) {
        moveNode(
          citationDropdown,
          chatSettingsPanel,
          mindmapCheckbox && mindmapCheckbox.parentNode === chatSettingsPanel
            ? mindmapCheckbox
            : settingsAnchor
        );
      }
    }

    // move the "share this conversation" checkbox into the feedback accordion
    var reportDiv = document.querySelector(
      "#report-accordion > div:nth-child(3) > div:nth-child(1)"
    );
    var shareCheckbox = document.getElementById("is-public-checkbox");
    if (reportDiv && shareCheckbox) {
      moveNode(shareCheckbox, reportDiv, reportDiv.querySelector("button"));
    }

    // create the slider switch around the "suggest chat" checkbox
    var suggestChatCheckbox = document.getElementById("suggest-chat-checkbox");
    if (suggestChatCheckbox) {
      var label = suggestChatCheckbox.getElementsByTagName("label")[0];
      var checkboxSpan = suggestChatCheckbox.getElementsByTagName("span")[0];
      if (label && checkboxSpan) {
        label.classList.add("switch");
        suggestChatCheckbox.appendChild(checkboxSpan);
        label.appendChild(document.createElement("div"));
      }
    }
  }

  /* ------------------------------------------------------------------------ */
  /* globals used by the server-side callbacks                                */
  /* ------------------------------------------------------------------------ */

  function installHelpers() {
    globalThis.toggleTheme = toggleTheme;

    globalThis.clpseFn = function (id) {
      try {
        var obj = document.getElementById("clpse-btn-" + id);
        if (!obj) {
          return;
        }
        obj.classList.toggle("clpse-active");
        var content = obj.nextElementSibling;
        if (!content) {
          return;
        }
        if (content.style.display === "none") {
          content.style.display = "block";
        } else {
          content.style.display = "none";
        }
      } catch (err) {
        console.warn("ktem: could not toggle the section", err);
      }
    };

    // store info in local storage
    globalThis.setStorage = function (key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (err) {
        console.warn("ktem: could not persist", key, err);
      }
    };

    globalThis.getStorage = function (key, value) {
      try {
        var item = window.localStorage.getItem(key);
        return item ? item : value;
      } catch (err) {
        return value;
      }
    };

    globalThis.removeFromStorage = function (key) {
      try {
        window.localStorage.removeItem(key);
      } catch (err) {
        console.warn("ktem: could not clear", key, err);
      }
    };

    // Function to scroll to given citation with ID
    // Sleep function using Promise and setTimeout
    function sleep(ms) {
      return new Promise(function (resolve) {
        window.setTimeout(resolve, ms);
      });
    }

    globalThis.scrollToCitation = async function (event) {
      try {
        event.preventDefault(); // Prevent the default link behavior
        var citationId = event.target.getAttribute("id");

        await sleep(100);

        var modal = document.getElementById("pdf-modal");
        var citation = document.querySelector('mark[id="' + citationId + '"]');
        if (!citation) {
          return;
        }

        if (modal && modal.style.display === "block") {
          // trigger on click event of PDF Preview link
          var detailElem = citation;
          // traverse up the DOM tree to find the parent element with tag detail
          while (
            detailElem &&
            detailElem.tagName &&
            detailElem.tagName.toLowerCase() !== "details"
          ) {
            detailElem = detailElem.parentElement;
          }
          if (detailElem) {
            var pdfLink = detailElem.getElementsByClassName("pdf-link").item(0);
            if (pdfLink) {
              pdfLink.click();
            }
          }
        } else {
          citation.scrollIntoView({ behavior: "smooth" });
        }
      } catch (err) {
        console.warn("ktem: could not scroll to the citation", err);
      }
    };

    globalThis.fullTextSearch = function () {
      // Assign text selection event to last bot message
      var botMessages = document.querySelectorAll(
        "div#main-chat-bot div.message-row.bot-row"
      );
      var lastBotMessage = botMessages[botMessages.length - 1];
      if (!lastBotMessage) {
        return;
      }

      // check if the last bot message has class "text_selection"
      if (lastBotMessage.classList.contains("text_selection")) {
        return;
      }

      // Full-text search runs in the browser, using a CDN build of MiniSearch.
      if (typeof MiniSearch === "undefined") {
        console.warn("ktem: full-text search is unavailable (MiniSearch missing)");
        return;
      }

      // assign new class to last message
      lastBotMessage.classList.add("text_selection");

      // Get sentences from evidence div. The nesting below is produced by
      // utils/render.py and must not change (see MODIFICATIONS notes).
      var evidences = document.querySelectorAll(
        "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
      );
      console.log("Indexing evidences", evidences);

      var segmenterEn = new Intl.Segmenter("en", { granularity: "sentence" });
      // Split sentences and save to all_segments list
      var allSegments = [];
      for (var i = 0; i < evidences.length; i += 1) {
        var evidence = evidences[i];
        // check if <details> tag is open
        if (!evidence.parentElement.open) {
          continue;
        }
        var markmapDiv = evidence.querySelector("div.markmap");
        if (markmapDiv) {
          continue;
        }

        var evidenceContent = evidence.textContent.replace(/[\r\n]+/g, " ");
        var sentenceIt = segmenterEn
          .segment(evidenceContent)
          [Symbol.iterator]();
        var sentence = sentenceIt.next();
        while (!sentence.done) {
          var segment = sentence.value.segment.trim();
          if (segment) {
            allSegments.push({
              id: allSegments.length,
              text: segment,
            });
          }
          sentence = sentenceIt.next();
        }
      }

      var miniSearch = new MiniSearch({
        fields: ["text"], // fields to index for full-text search
        storeFields: ["text"],
      });

      // Index all documents
      miniSearch.addAll(allSegments);

      lastBotMessage.addEventListener("mouseup", function () {
        try {
          var selection = window.getSelection().toString();
          var results = miniSearch.search(selection);

          if (results.length === 0) {
            return;
          }
          var matchedText = results[0].text;
          console.log("query\n", selection, "\nmatched text\n", matchedText);

          var evidenceNodes = document.querySelectorAll(
            "#html-info-panel > div:last-child > div > details.evidence div.evidence-content"
          );
          // check if modal is open
          var modal = document.getElementById("pdf-modal");

          // convert all <mark> in evidences to normal text
          evidenceNodes.forEach(function (node) {
            node.querySelectorAll("mark").forEach(function (mark) {
              mark.outerHTML = mark.innerText;
            });
          });

          // highlight matched_text in evidences
          for (var j = 0; j < evidenceNodes.length; j += 1) {
            var content = evidenceNodes[j].textContent.replace(/[\r\n]+/g, " ");
            if (!content.includes(matchedText)) {
              continue;
            }
            // select all p and li elements
            var paragraphs = evidenceNodes[j].querySelectorAll("p, li");
            for (var k = 0; k < paragraphs.length; k += 1) {
              var paragraph = paragraphs[k];
              var paragraphContent = paragraph.textContent.replace(
                /[\r\n]+/g,
                " "
              );
              if (!paragraphContent.includes(matchedText)) {
                continue;
              }
              paragraph.innerHTML = paragraphContent.replace(
                matchedText,
                "<mark>" + matchedText + "</mark>"
              );
              console.log("highlighted", matchedText, "in", paragraph);
              if (modal && modal.style.display === "block") {
                // trigger on click event of PDF Preview link
                var detailElem = paragraph;
                while (
                  detailElem &&
                  detailElem.tagName &&
                  detailElem.tagName.toLowerCase() !== "details"
                ) {
                  detailElem = detailElem.parentElement;
                }
                if (detailElem) {
                  var pdfLink = detailElem
                    .getElementsByClassName("pdf-link")
                    .item(0);
                  if (pdfLink) {
                    pdfLink.click();
                  }
                }
              } else {
                paragraph.scrollIntoView({
                  behavior: "smooth",
                  block: "center",
                });
              }
              break;
            }
          }
        } catch (err) {
          console.warn("ktem: full-text search failed", err);
        }
      });
    };

    globalThis.spawnDocument = function (content, options) {
      var opt = {
        window: "",
        closeChild: true,
        childId: "_blank",
      };
      Object.assign(opt, options);
      // minimal error checking
      if (
        content &&
        typeof content.toString === "function" &&
        content.toString().length
      ) {
        var child = window.open("", opt.childId, opt.window);
        if (!child) {
          return undefined;
        }
        child.document.write(content.toString());
        if (opt.closeChild) {
          child.document.close();
        }
        return child;
      }
      return undefined;
    };

    globalThis.fillChatInput = function (event) {
      try {
        var chatInput = document.querySelector("#chat-input textarea");
        if (!chatInput) {
          return;
        }
        // fill the chat input with the clicked div text
        chatInput.value = t("Explain") + " " + event.target.textContent;
        chatInput.dispatchEvent(new Event("input", { bubbles: true }));
        chatInput.focus();
      } catch (err) {
        console.warn("ktem: could not fill the chat input", err);
      }
    };
  }

  /* ------------------------------------------------------------------------ */
  /* file table tooltips                                                      */
  /* ------------------------------------------------------------------------ */

  /* A table cell that is wider than its column shows an ellipsis; put the full
   * text in a native tooltip so the user can read it on hover. Gradio re-renders
   * the table on every update, so the decoration is re-applied by a
   * MutationObserver. */
  function decorateClampedCells(root) {
    root.querySelectorAll("td").forEach(function (cell) {
      var text = (cell.textContent || "").trim();
      if (!text || text === "-") {
        return;
      }
      if (cell.scrollWidth > cell.clientWidth + 1) {
        cell.title = text;
      } else if (cell.title) {
        cell.removeAttribute("title");
      }
    });
  }

  function observeFileTable() {
    var fileList = document.getElementById("file_list_view");
    if (!fileList) {
      return false;
    }
    decorateClampedCells(fileList);
    if (typeof MutationObserver !== "undefined") {
      new MutationObserver(function () {
        decorateClampedCells(fileList);
      }).observe(fileList, { childList: true, subtree: true });
    }
    return true;
  }

  /* ------------------------------------------------------------------------ */
  /* entry point                                                              */
  /* ------------------------------------------------------------------------ */

  function bootstrapUi() {
    decorateShell();
    setupConversationControls();
    installHelpers();
    observeIconButtons();
    observeFileTable();
  }

  try {
    // Theme first: it decides the background of everything that follows and must
    // match what theme_init.js already applied in <head>.
    syncThemeUi();
    observeIconButtons();

    // The tab bar is rendered by Gradio; wait for it instead of failing on a page
    // that is still being built.
    var attempts = 40;
    var tick = function () {
      try {
        if (
          document.getElementById("app-tabs") ||
          document.getElementById("chat-tab")
        ) {
          bootstrapUi();
          return;
        }
      } catch (err) {
        console.warn("ktem: could not inspect the shell", err);
      }
      attempts -= 1;
      if (attempts <= 0) {
        // last try: still run the parts that do not need the shell
        try {
          installHelpers();
          observeIconButtons();
        } catch (err) {
          console.warn("ktem: UI bootstrap stopped early", err);
        }
        return;
      }
      window.setTimeout(tick, 100);
    };
    tick();
  } catch (err) {
    console.warn("ktem: UI bootstrap stopped early", err);
  }
}
