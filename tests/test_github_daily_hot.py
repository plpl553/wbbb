import base64
import hashlib
import hmac
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from github_daily_hot import (
    add_feishu_signature,
    build_feishu_card,
    build_search_url,
    compact_text,
    response_is_success,
)


class GitHubDailyHotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc)
        self.repo = {
            "full_name": "example/hot-project",
            "html_url": "https://github.com/example/hot-project",
            "description": "A useful new project",
            "language": "Python",
            "stargazers_count": 1234,
            "forks_count": 56,
        }

    def test_build_search_url_uses_cutoff_and_limit(self):
        url = build_search_url(self.now, days=7, limit=10)
        query = parse_qs(urlparse(url).query)
        self.assertIn("created:>=2026-08-24", query["q"][0])
        self.assertEqual(query["sort"], ["stars"])
        self.assertEqual(query["per_page"], ["10"])

    def test_card_contains_title_repo_and_metrics(self):
        card = build_feishu_card([self.repo], self.now, days=7)
        self.assertEqual(card["msg_type"], "interactive")
        self.assertIn("2026-08-31", card["card"]["header"]["title"]["content"])
        markdown = card["card"]["elements"][0]["content"]
        self.assertIn("github", markdown)
        self.assertIn("example/hot-project", markdown)
        self.assertIn("1,234", markdown)
        self.assertIn("GitHub Search API", card["card"]["elements"][1]["elements"][0]["content"])

    def test_empty_result_has_clear_message(self):
        card = build_feishu_card([], self.now, days=7)
        self.assertIn("没有找到", card["card"]["elements"][0]["content"])

    def test_compact_text_flattens_and_truncates(self):
        self.assertEqual(compact_text("one\n two"), "one two")
        self.assertEqual(compact_text("abcdef", 4), "abc…")

    def test_signature_matches_feishu_algorithm(self):
        payload = {"msg_type": "text"}
        add_feishu_signature(payload, "secret", 1234567890)
        key = b"1234567890\nsecret"
        expected = base64.b64encode(hmac.new(key, digestmod=hashlib.sha256).digest()).decode()
        self.assertEqual(payload["timestamp"], "1234567890")
        self.assertEqual(payload["sign"], expected)

    def test_success_response_variants(self):
        self.assertTrue(response_is_success({"code": 0, "msg": "success"}))
        self.assertTrue(response_is_success({"StatusCode": 0}))
        self.assertFalse(response_is_success({"code": 19024}))


if __name__ == "__main__":
    unittest.main()

