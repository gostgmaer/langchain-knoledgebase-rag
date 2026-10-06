/**
 * Embeddable chat widget (docs/BUGS.md item 37). Self-contained, no dependencies, no build step —
 * a customer drops this on their own site as a plain <script> tag:
 *
 *   <script src="https://<this app>/widget.js" data-agent="wgt_..." data-api="https://<rag api>/api/v1" async></script>
 *
 * Everything it talks to is the RAG API's public, unauthenticated /widget/* endpoints
 * (packages/api/routers/widget.py) — never this admin app itself. The actual security boundary is
 * server-side (the agent's configured allowed origins + rate limiting), not anything in this file;
 * this script has no secret to protect, same trust model as a Stripe/Google Analytics snippet.
 *
 * Rendered inside a Shadow DOM so the host page's CSS can never leak in, and this widget's CSS can
 * never leak out onto the host page.
 */
(function () {
  "use strict";

  var currentScript = document.currentScript;
  if (!currentScript) return;

  var agentId = currentScript.getAttribute("data-agent");
  var apiBase = (currentScript.getAttribute("data-api") || "").replace(/\/+$/, "");
  if (!agentId || !apiBase) {
    console.error("[widget.js] missing data-agent or data-api attribute; the widget will not load.");
    return;
  }

  var VISITOR_KEY = "rag_widget_visitor_" + agentId;
  var CONVERSATION_KEY = "rag_widget_conversation_" + agentId;

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    // Fallback for older browsers: RFC4122-ish v4 from Math.random (fine for a visitor id — this
    // is not a security token, just a continuity key the visitor's own browser hands back to us).
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function getVisitorId() {
    try {
      var existing = window.localStorage.getItem(VISITOR_KEY);
      if (existing) return existing;
      var fresh = uuid();
      window.localStorage.setItem(VISITOR_KEY, fresh);
      return fresh;
    } catch (e) {
      return uuid(); // private browsing / storage blocked: still works, just no continuity
    }
  }

  function getStoredConversationId() {
    try {
      return window.localStorage.getItem(CONVERSATION_KEY);
    } catch (e) {
      return null;
    }
  }

  function storeConversationId(id) {
    try {
      window.localStorage.setItem(CONVERSATION_KEY, id);
    } catch (e) {
      /* ignore */
    }
  }

  var visitorId = getVisitorId();
  var conversationId = getStoredConversationId();

  // ------------------------------------------------------------------ DOM / styles

  var host = document.createElement("div");
  host.setAttribute("data-rag-widget", agentId);
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  var style = document.createElement("style");
  style.textContent = [
    ":host { all: initial; }",
    "* { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }",
    ".bubble { position: fixed; bottom: 20px; right: 20px; width: 56px; height: 56px; border-radius: 50%;",
    "  background: #4f46e5; color: #fff; border: none; cursor: pointer; box-shadow: 0 4px 14px rgba(0,0,0,.2);",
    "  display: flex; align-items: center; justify-content: center; font-size: 26px; z-index: 2147483000; }",
    ".bubble:hover { background: #4338ca; }",
    ".panel { position: fixed; bottom: 88px; right: 20px; width: 340px; max-width: calc(100vw - 32px);",
    "  height: 480px; max-height: calc(100vh - 120px); background: #fff; border-radius: 12px;",
    "  box-shadow: 0 10px 40px rgba(0,0,0,.25); display: none; flex-direction: column; overflow: hidden;",
    "  z-index: 2147483000; }",
    ".panel.open { display: flex; }",
    ".header { background: #4f46e5; color: #fff; padding: 14px 16px; font-weight: 600; font-size: 14px; }",
    ".messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }",
    ".msg { max-width: 85%; padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.4; white-space: pre-wrap; }",
    ".msg.user { align-self: flex-end; background: #4f46e5; color: #fff; }",
    ".msg.bot { align-self: flex-start; background: #f3f4f6; color: #111827; }",
    ".msg.error { align-self: center; background: #fef2f2; color: #b91c1c; font-size: 12px; }",
    ".cites { font-size: 11px; color: #6b7280; margin-top: 4px; }",
    ".composer { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #e5e7eb; }",
    ".composer input { flex: 1; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 10px; font-size: 13px; }",
    ".composer button { background: #4f46e5; color: #fff; border: none; border-radius: 8px; padding: 0 14px;",
    "  font-size: 13px; cursor: pointer; }",
    ".composer button:disabled { opacity: .5; cursor: default; }",
  ].join("\n");
  root.appendChild(style);

  var bubble = document.createElement("button");
  bubble.className = "bubble";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.textContent = "\u{1F4AC}";
  root.appendChild(bubble);

  var panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML =
    '<div class="header">Chat</div>' +
    '<div class="messages"></div>' +
    '<div class="composer">' +
    '<input type="text" placeholder="Type a message…" />' +
    "<button>Send</button>" +
    "</div>";
  root.appendChild(panel);

  var header = panel.querySelector(".header");
  var messages = panel.querySelector(".messages");
  var input = panel.querySelector("input");
  var sendButton = panel.querySelector("button");

  function addMessage(text, cls, citations) {
    var el = document.createElement("div");
    el.className = "msg " + cls;
    el.textContent = text;
    messages.appendChild(el);
    if (citations && citations.length) {
      var cites = document.createElement("div");
      cites.className = "cites";
      cites.textContent =
        "Sources: " +
        citations
          .map(function (c) {
            return c.document_name || c.source_name || "source";
          })
          .join(", ");
      messages.appendChild(cites);
    }
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  var configLoaded = false;
  function ensureConfig() {
    if (configLoaded) return;
    configLoaded = true;
    fetch(apiBase + "/widget/" + encodeURIComponent(agentId) + "/config")
      .then(function (r) {
        if (!r.ok) throw new Error("config " + r.status);
        return r.json();
      })
      .then(function (body) {
        var data = body.data || body;
        header.textContent = data.name || "Chat";
        addMessage(data.greeting || "Hi! How can I help?", "bot");
      })
      .catch(function () {
        header.textContent = "Chat";
        addMessage("This chat is currently unavailable.", "error");
      });
  }

  bubble.addEventListener("click", function () {
    var willOpen = !panel.classList.contains("open");
    panel.classList.toggle("open", willOpen);
    if (willOpen) {
      ensureConfig();
      input.focus();
    }
  });

  var sending = false;
  function send() {
    var text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    sendButton.disabled = true;
    addMessage(text, "user");
    input.value = "";

    fetch(apiBase + "/widget/" + encodeURIComponent(agentId) + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        visitor_id: visitorId,
        conversation_id: conversationId,
      }),
    })
      .then(function (r) {
        if (r.status === 429) throw new Error("Too many messages — please wait a moment.");
        if (r.status === 403) throw new Error("This site is not registered for this chat widget.");
        if (!r.ok) throw new Error("Something went wrong (" + r.status + ").");
        return r.json();
      })
      .then(function (body) {
        var data = body.data || body;
        conversationId = data.conversation_id;
        storeConversationId(conversationId);
        addMessage(data.message, "bot", data.citations);
      })
      .catch(function (err) {
        addMessage(err.message || "Something went wrong.", "error");
      })
      .finally(function () {
        sending = false;
        sendButton.disabled = false;
      });
  }

  sendButton.addEventListener("click", send);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") send();
  });
})();
