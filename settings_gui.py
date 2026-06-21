"""
Local settings GUI for Optimist Prime (runs in your browser).

Usage:
    py settings_gui.py
    pyw settings_gui.py          (no console — used by Start Menu shortcut)

Writes to .env and data/rules.json (both gitignored locally).
Closes automatically when you close the browser tab or click Done.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from env_file import load_env_file, save_env_file
from llm_client import PROVIDER_PRESETS
from moderation_rules import RuleLoadError, _validate_rule
from settings_registry import SETTING_FIELDS

REPO_ROOT = Path(__file__).resolve().parent
ENV_PATH = REPO_ROOT / ".env"
DEFAULT_PORT = 8765
RULE_ACTIONS = [
    "report", "remove", "modmail", "ban", "lock", "unlock",
    "spam", "approve", "reply", "set_flair",
]


def _bool_to_env(value: str) -> str:
    return "true" if value.lower() in ("1", "true", "yes", "on") else "false"


def _env_to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _current_values() -> dict[str, str]:
    env = load_env_file(ENV_PATH)
    out: dict[str, str] = {}
    for field in SETTING_FIELDS:
        raw = env.get(field.key, field.default)
        if field.field_type == "bool":
            out[field.key] = "true" if _env_to_bool(raw) else "false"
        else:
            out[field.key] = raw
    return out


def _merge_save_payload(payload: dict[str, str]) -> dict[str, str]:
    existing = load_env_file(ENV_PATH)
    merged: dict[str, str] = {}
    for field in SETTING_FIELDS:
        if field.key not in payload:
            continue
        value = payload[field.key].strip()
        if field.field_type == "password" and not value:
            if field.key in existing:
                merged[field.key] = existing[field.key]
            continue
        if field.field_type == "bool":
            merged[field.key] = _bool_to_env(value)
        else:
            merged[field.key] = value
    return merged


def _rules_path() -> Path:
    rel = load_env_file(ENV_PATH).get("BOT_MODERATION_RULES_FILE", "data/rules.json")
    return REPO_ROOT / rel


def _load_rules_data() -> dict[str, Any]:
    path = _rules_path()
    example = REPO_ROOT / "data" / "rules.example.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            rules = json.load(f)
        source = "file"
    elif example.exists():
        with open(example, encoding="utf-8") as f:
            rules = json.load(f)
        source = "example"
    else:
        rules = []
        source = "empty"
    if not isinstance(rules, list):
        raise RuleLoadError("Rules file must be a JSON array")
    return {"path": str(path), "rules": rules, "source": source}


def _save_rules_data(rules: list[dict]) -> None:
    if not isinstance(rules, list):
        raise RuleLoadError("Rules must be a JSON array")
    for index, rule in enumerate(rules):
        _validate_rule(rule, index)
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
        f.write("\n")


def _provider_info() -> dict[str, dict[str, str]]:
    return {
        name: {
            "base_url": preset.get("base_url", ""),
            "model": preset.get("model", ""),
            "api_key_envs": preset.get("api_key_envs", ""),
        }
        for name, preset in PROVIDER_PRESETS.items()
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Optimist Prime — Settings</title>
  <style>
    :root {
      --bg: #f0f4f8;
      --card: #ffffff;
      --border: #c8d3e0;
      --text: #1c2836;
      --muted: #5a6b7d;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
      --ok: #15803d;
      --err: #b91c1c;
      --shadow: 0 1px 3px rgba(0,0,0,.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    header {
      padding: 1rem 1.5rem;
      border-bottom: 1px solid var(--border);
      background: #fff;
      box-shadow: var(--shadow);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header h1 { margin: 0 0 0.2rem; font-size: 1.3rem; font-weight: 600; }
    header p { margin: 0; color: var(--muted); font-size: 0.88rem; }
    main { max-width: 960px; margin: 0 auto; padding: 1.25rem 1.5rem 3rem; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
      margin-bottom: 1.25rem;
      align-items: center;
    }
    button {
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 0.5rem 1rem;
      font-size: 0.92rem;
      cursor: pointer;
      font-weight: 500;
    }
    button:hover { background: var(--accent-hover); }
    button.secondary { background: #e8eef5; color: var(--text); border: 1px solid var(--border); }
    button.secondary:hover { background: #dce4ee; }
    button.danger { background: #fff; color: var(--err); border: 1px solid #f0c4c4; }
    button.danger:hover { background: #fef2f2; }
    #status { flex: 1; min-width: 180px; font-size: 0.88rem; color: var(--muted); }
    #status.ok { color: var(--ok); }
    #status.err { color: var(--err); }
    section.card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.2rem;
      margin-bottom: 1rem;
      box-shadow: var(--shadow);
    }
    section.card h2 {
      margin: 0 0 0.75rem;
      font-size: 1rem;
      font-weight: 600;
      color: #2d3f54;
    }
    .field { margin-bottom: 0.75rem; }
    .field label { display: block; font-size: 0.86rem; margin-bottom: 0.2rem; font-weight: 500; }
    .field .help { font-size: 0.76rem; color: var(--muted); margin-top: 0.15rem; }
    input[type="text"], input[type="password"], input[type="number"], select, textarea {
      width: 100%;
      padding: 0.45rem 0.6rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: #fff;
      color: var(--text);
      font-size: 0.9rem;
    }
    input:focus, select:focus, textarea:focus {
      outline: 2px solid #93b4f5;
      border-color: var(--accent);
    }
    textarea { min-height: 3.5rem; resize: vertical; font-family: inherit; }
    .bool-row { display: flex; align-items: center; gap: 0.45rem; }
    .bool-row input { width: auto; }
    .bool-row label { margin: 0; font-weight: 500; }
    .provider-hint {
      font-size: 0.8rem;
      color: var(--muted);
      margin-top: 0.5rem;
      padding: 0.45rem 0.6rem;
      background: #f7f9fc;
      border-radius: 6px;
      border: 1px dashed var(--border);
    }
    .rules-toolbar { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; align-items: center; }
    .rules-path { font-size: 0.8rem; color: var(--muted); flex: 1; }
    .rule-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem;
      margin-bottom: 0.65rem;
      background: #fafbfd;
    }
    .rule-card.inactive { opacity: 0.72; }
    .rule-head {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
      flex-wrap: wrap;
    }
    .rule-head .name-input { flex: 1; min-width: 160px; font-weight: 600; }
    .actions-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem 0.75rem;
      margin-top: 0.35rem;
    }
    .actions-grid label { font-size: 0.82rem; font-weight: normal; display: flex; align-items: center; gap: 0.25rem; }
    .conds-row { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.35rem; }
    .conds-row label { font-size: 0.82rem; font-weight: normal; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
    @media (max-width: 640px) { .grid-2 { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Optimist Prime — Settings</h1>
    <p>All changes save locally. Close this tab or click <strong>Done</strong> when finished.</p>
  </header>
  <main>
    <div class="toolbar">
      <button type="button" id="saveBtn">Save all</button>
      <button type="button" class="secondary" id="doneBtn">Done</button>
      <span id="status"></span>
    </div>
    <div id="sections"></div>
    <section class="card" id="rulesSection">
      <h2>AI moderation rules</h2>
      <p style="margin:0 0 0.75rem;font-size:0.88rem;color:var(--muted)">
        Each rule is a yes/no question the AI evaluates on posts and comments.
      </p>
      <div class="rules-toolbar">
        <button type="button" class="secondary" id="addRuleBtn">+ Add rule</button>
        <span class="rules-path" id="rulesPath"></span>
      </div>
      <div id="rulesMetaFields" class="grid-2"></div>
      <div id="rulesList"></div>
    </section>
  </main>
  <script>
    let providers = {};
    let fields = [];
    let rules = [];
    let rulesPath = "";
    let rulesSource = "";
    const RULE_ACTIONS = """ + json.dumps(RULE_ACTIONS) + r""";

    function shutdown() {
      try { navigator.sendBeacon("/api/shutdown"); } catch (e) {}
    }
    window.addEventListener("pagehide", shutdown);
    window.addEventListener("beforeunload", shutdown);

    async function load() {
      const [settingsRes, metaRes, rulesRes] = await Promise.all([
        fetch("/api/settings"),
        fetch("/api/meta"),
        fetch("/api/rules"),
      ]);
      const settings = await settingsRes.json();
      providers = (await metaRes.json()).providers;
      const rulesData = await rulesRes.json();
      fields = settings.fields;
      rules = rulesData.rules || [];
      rulesPath = rulesData.path || "";
      rulesSource = rulesData.source || "";
      render(settings.values);
      renderRules();
      updateProviderHint(settings.values.BOT_LLM_PROVIDER);
      if (rulesSource === "example") {
        setStatus("Showing example rules — click Save all to create your rules file.", null);
      }
    }

    function render(values) {
      const bySection = {};
      for (const f of fields) {
        if (f.section === "Moderation rules") continue;
        (bySection[f.section] ||= []).push(f);
      }
      const root = document.getElementById("sections");
      root.innerHTML = "";
      for (const [section, sectionFields] of Object.entries(bySection)) {
        const card = document.createElement("section");
        card.className = "card";
        card.innerHTML = "<h2>" + section + "</h2>";
        for (const f of sectionFields) {
          card.appendChild(renderField(f, values[f.key] || ""));
        }
        if (section === "LLM") {
          const hint = document.createElement("div");
          hint.className = "provider-hint";
          hint.id = "providerHint";
          card.appendChild(hint);
        }
        root.appendChild(card);
      }
      const rulesMeta = document.getElementById("rulesMetaFields");
      rulesMeta.innerHTML = "";
      for (const f of fields) {
        if (f.section === "Moderation rules") {
          rulesMeta.appendChild(renderField(f, values[f.key] || ""));
        }
      }
      const pathEl = document.getElementById("BOT_MODERATION_RULES_FILE");
      if (pathEl) pathEl.addEventListener("change", () => {
        rulesPath = pathEl.value;
        document.getElementById("rulesPath").textContent = "File: " + rulesPath;
      });
    }

    function renderField(f, value) {
      const wrap = document.createElement("div");
      wrap.className = "field";
      if (f.field_type === "bool") {
        const checked = value === "true";
        wrap.innerHTML = '<div class="bool-row"><input type="checkbox" id="' + f.key + '"' +
          (checked ? " checked" : "") + ' /><label for="' + f.key + '">' + f.label + "</label></div>";
      } else if (f.field_type === "choice") {
        const opts = (f.choices || []).map(c =>
          '<option value="' + c + '"' + (c === value ? " selected" : "") + ">" + (c || "(default)") + "</option>"
        ).join("");
        wrap.innerHTML = '<label for="' + f.key + '">' + f.label + '</label><select id="' + f.key + '">' + opts + "</select>";
      } else if (f.field_type === "text") {
        wrap.innerHTML = '<label for="' + f.key + '">' + f.label + '</label><textarea id="' + f.key + '">' + esc(value) + "</textarea>";
      } else {
        const type = f.field_type === "password" ? "password" : ((f.field_type === "int" || f.field_type === "float") ? "number" : "text");
        const ph = f.field_type === "password" ? "Leave blank to keep existing" : "";
        wrap.innerHTML = '<label for="' + f.key + '">' + f.label + '</label><input type="' + type + '" id="' + f.key +
          '" value="' + escAttr(value) + '" placeholder="' + ph + '" />';
      }
      if (f.help_text) {
        const help = document.createElement("div");
        help.className = "help";
        help.textContent = f.help_text;
        wrap.appendChild(help);
      }
      return wrap;
    }

    function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
    function escAttr(s) { return esc(s).replace(/"/g, "&quot;"); }

    function defaultRule() {
      return {
        name: "new_rule",
        description: "Describe what this rule should detect.",
        active: true,
        order: (rules.length + 1) * 10,
        target: "both",
        actions: ["report"],
        conditions: { stop_on_match: false, skip_mods: true, skip_approved: false },
      };
    }

    function renderRules() {
      document.getElementById("rulesPath").textContent = "File: " + (document.getElementById("BOT_MODERATION_RULES_FILE")?.value || rulesPath);
      const list = document.getElementById("rulesList");
      list.innerHTML = "";
      rules.forEach((rule, idx) => list.appendChild(buildRuleCard(rule, idx)));
    }

    function buildRuleCard(rule, idx) {
      const card = document.createElement("div");
      card.className = "rule-card" + (rule.active ? "" : " inactive");
      const cond = rule.conditions || {};
      const actions = new Set(rule.actions || []);
      const actionBoxes = RULE_ACTIONS.map(a =>
        '<label><input type="checkbox" data-action="' + a + '"' + (actions.has(a) ? " checked" : "") + " /> " + a + "</label>"
      ).join("");
      card.innerHTML =
        '<div class="rule-head">' +
          '<input class="name-input" data-f="name" value="' + escAttr(rule.name || "") + '" />' +
          '<label class="bool-row"><input type="checkbox" data-f="active"' + (rule.active !== false ? " checked" : "") + " /> Active</label>" +
          '<button type="button" class="danger" data-del="' + idx + '">Remove</button>' +
        "</div>" +
        '<div class="field"><label>Question for the AI</label><textarea data-f="description">' + esc(rule.description || "") + "</textarea></div>" +
        '<div class="grid-2">' +
          '<div class="field"><label>Order</label><input type="number" data-f="order" value="' + (rule.order ?? 100) + '" /></div>' +
          '<div class="field"><label>Applies to</label><select data-f="target">' +
            ["posts","comments","both"].map(t => '<option value="' + t + '"' + ((rule.target||"both")===t?" selected":"") + ">" + t + "</option>").join("") +
          "</select></div>" +
        "</div>" +
        '<div class="field"><label>Actions when matched</label><div class="actions-grid" data-actions>' + actionBoxes + "</div></div>" +
        '<div class="conds-row">' +
          '<label><input type="checkbox" data-cond="stop_on_match"' + (cond.stop_on_match ? " checked" : "") + " /> Stop after match</label>" +
          '<label><input type="checkbox" data-cond="skip_mods"' + (cond.skip_mods !== false ? " checked" : "") + " /> Skip moderators</label>" +
          '<label><input type="checkbox" data-cond="skip_approved"' + (cond.skip_approved ? " checked" : "") + " /> Skip approved</label>" +
        "</div>";
      card.querySelector("[data-del]").addEventListener("click", () => { rules.splice(idx, 1); renderRules(); });
      card.querySelectorAll("[data-f]").forEach(el => {
        el.addEventListener("change", () => syncRuleFromCard(card, idx));
        el.addEventListener("input", () => syncRuleFromCard(card, idx));
      });
      card.querySelectorAll("[data-actions] input, [data-cond]").forEach(el => {
        el.addEventListener("change", () => syncRuleFromCard(card, idx));
      });
      return card;
    }

    function syncRuleFromCard(card, idx) {
      const r = rules[idx];
      r.name = card.querySelector('[data-f="name"]').value.trim();
      r.description = card.querySelector('[data-f="description"]').value.trim();
      r.active = card.querySelector('[data-f="active"]').checked;
      r.order = parseInt(card.querySelector('[data-f="order"]').value, 10) || 100;
      r.target = card.querySelector('[data-f="target"]').value;
      r.actions = [...card.querySelectorAll("[data-actions] input:checked")].map(cb => cb.dataset.action);
      if (!r.actions.length) r.actions = ["report"];
      r.conditions = {
        stop_on_match: card.querySelector('[data-cond="stop_on_match"]').checked,
        skip_mods: card.querySelector('[data-cond="skip_mods"]').checked,
        skip_approved: card.querySelector('[data-cond="skip_approved"]').checked,
      };
      card.classList.toggle("inactive", !r.active);
    }

    function collectSettings() {
      const values = {};
      for (const f of fields) {
        const el = document.getElementById(f.key);
        if (!el) continue;
        values[f.key] = f.field_type === "bool" ? (el.checked ? "true" : "false") : el.value;
      }
      return values;
    }

    function collectRules() {
      document.querySelectorAll(".rule-card").forEach((card, idx) => syncRuleFromCard(card, idx));
      return rules;
    }

    function setStatus(msg, ok) {
      const el = document.getElementById("status");
      el.textContent = msg;
      el.className = ok === true ? "ok" : (ok === false ? "err" : "");
    }

    function updateProviderHint(name) {
      const hint = document.getElementById("providerHint");
      if (!hint) return;
      const p = providers[name];
      if (!p) { hint.textContent = ""; return; }
      hint.textContent = "Preset: " + name + " → " + (p.model || "(set LLM_MODEL)") +
        " @ " + (p.base_url || "(set OPENAI_BASE_URL)");
    }

    async function saveAll() {
      setStatus("Saving…");
      const settingsRes = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectSettings()),
      });
      const settingsData = await settingsRes.json();
      if (!settingsData.ok) { setStatus(settingsData.message, false); return false; }

      const rulesRes = await fetch("/api/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: collectRules() }),
      });
      const rulesData = await rulesRes.json();
      if (!rulesData.ok) { setStatus(rulesData.message, false); return false; }

      setStatus("Saved.", true);
      return true;
    }

    document.getElementById("saveBtn").addEventListener("click", () => saveAll());
    document.getElementById("doneBtn").addEventListener("click", async () => {
      await saveAll();
      shutdown();
      setStatus("Closing…", true);
      setTimeout(() => window.close(), 300);
    });
    document.getElementById("addRuleBtn").addEventListener("click", () => {
      rules.push(defaultRule());
      renderRules();
    });
    document.addEventListener("change", (e) => {
      if (e.target && e.target.id === "BOT_LLM_PROVIDER") updateProviderHint(e.target.value);
    });

    load().catch(err => setStatus("Failed to load: " + err, false));
  </script>
</body>
</html>
"""


class SettingsHandler(BaseHTTPRequestHandler):
    http_server: ThreadingHTTPServer | None = None

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _schedule_shutdown(self) -> None:
        server = self.http_server
        if server is None:
            return
        threading.Thread(target=server.shutdown, daemon=True).start()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/settings":
            self._send_json({
                "ok": True,
                "values": _current_values(),
                "fields": [
                    {
                        "key": f.key,
                        "label": f.label,
                        "section": f.section,
                        "field_type": f.field_type,
                        "choices": f.choices,
                        "help_text": f.help_text,
                    }
                    for f in SETTING_FIELDS
                ],
            })
            return
        if path == "/api/meta":
            self._send_json({"ok": True, "providers": _provider_info(), "env_path": str(ENV_PATH)})
            return
        if path == "/api/rules":
            try:
                data = _load_rules_data()
                self._send_json({"ok": True, **data})
            except (RuleLoadError, json.JSONDecodeError, OSError) as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return
        self._send_json({"ok": False, "message": "Not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/settings":
            try:
                payload = self._read_json()
                merged = _merge_save_payload(payload)
                save_env_file(ENV_PATH, merged)
                self._send_json({"ok": True, "message": "Settings saved"})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return
        if path == "/api/rules":
            try:
                payload = self._read_json()
                _save_rules_data(payload.get("rules", []))
                self._send_json({"ok": True, "message": "Rules saved"})
            except (RuleLoadError, json.JSONDecodeError, TypeError) as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return
        if path == "/api/shutdown":
            self._send_json({"ok": True})
            self._schedule_shutdown()
            return
        self._send_json({"ok": False, "message": "Not found"}, status=404)


def run_server(port: int, open_browser: bool) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), SettingsHandler)
    SettingsHandler.http_server = server
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local settings GUI for Optimist Prime")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    args = parser.parse_args()
    run_server(args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
