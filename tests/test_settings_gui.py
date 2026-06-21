"""Tests for the local settings GUI HTTP API."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import settings_gui


class TestSettingsGUI(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_env_path = settings_gui.ENV_PATH
        self._orig_repo = settings_gui.REPO_ROOT
        settings_gui.ENV_PATH = Path(self._tmpdir.name) / ".env"
        settings_gui.REPO_ROOT = Path(self._tmpdir.name)
        settings_gui.save_env_file(
            settings_gui.ENV_PATH,
            {"BOT_MODERATION_RULES_FILE": "data/rules.json"},
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), settings_gui.SettingsHandler)
        settings_gui.SettingsHandler.http_server = self.server
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        settings_gui.ENV_PATH = self._orig_env_path
        settings_gui.REPO_ROOT = self._orig_repo
        self._tmpdir.cleanup()

    def test_get_settings_and_save(self):
        with urlopen(f"{self.base}/api/settings") as resp:
            data = json.loads(resp.read().decode())
        self.assertTrue(data["ok"])
        self.assertIn("BOT_LLM_PROVIDER", data["values"])

        payload = json.dumps({
            "BOT_LLM_PROVIDER": "claude",
            "BOT_SAFE_MODE": "true",
            "ANTHROPIC_API_KEY": "sk-ant-test",
        }).encode()
        req = Request(
            f"{self.base}/api/settings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as resp:
            result = json.loads(resp.read().decode())
        self.assertTrue(result["ok"])

        saved = settings_gui.load_env_file(settings_gui.ENV_PATH)
        self.assertEqual(saved["BOT_LLM_PROVIDER"], "claude")
        self.assertEqual(saved["ANTHROPIC_API_KEY"], "sk-ant-test")

    def test_meta_lists_providers(self):
        with urlopen(f"{self.base}/api/meta") as resp:
            data = json.loads(resp.read().decode())
        self.assertIn("claude", data["providers"])
        self.assertIn("glm", data["providers"])

    def test_rules_load_and_save(self):
        example = Path(self._tmpdir.name) / "data" / "rules.example.json"
        example.parent.mkdir(parents=True)
        example.write_text(
            json.dumps([{
                "name": "spam_detector",
                "description": "Is this spam?",
                "active": True,
                "order": 10,
                "target": "both",
                "actions": ["report"],
                "conditions": {},
            }]),
            encoding="utf-8",
        )
        # Point REPO_ROOT example - copy to repo root data
        settings_gui.REPO_ROOT = Path(self._tmpdir.name)
        (settings_gui.REPO_ROOT / "data").mkdir(exist_ok=True)
        (settings_gui.REPO_ROOT / "data" / "rules.example.json").write_text(
            example.read_text(encoding="utf-8"), encoding="utf-8"
        )

        with urlopen(f"{self.base}/api/rules") as resp:
            data = json.loads(resp.read().decode())
        self.assertTrue(data["ok"])
        self.assertEqual(data["rules"][0]["name"], "spam_detector")

        rules = data["rules"]
        rules[0]["description"] = "Updated question"
        payload = json.dumps({"rules": rules}).encode()
        req = Request(
            f"{self.base}/api/rules",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as resp:
            result = json.loads(resp.read().decode())
        self.assertTrue(result["ok"])

        rules_file = settings_gui.REPO_ROOT / "data" / "rules.json"
        saved = json.loads(rules_file.read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["description"], "Updated question")

    def test_shutdown_endpoint(self):
        req = Request(f"{self.base}/api/shutdown", data=b"", method="POST")
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        self.assertTrue(data["ok"])
        self.server.shutdown()
        self.thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
