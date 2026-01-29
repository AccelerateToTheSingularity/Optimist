
import unittest
from types import SimpleNamespace
from crosspost_handler import is_already_crossposted

class TestCrosspostHandler(unittest.TestCase):
    def test_is_already_crossposted(self):
        existing_urls = {"https://reddit.com/r/test/comments/existing"}
        history_ids = {"existing_id"}

        # Case 1: Post in existing_urls (permalink)
        sub1 = SimpleNamespace(
            permalink="/r/test/comments/existing",
            url="https://other.url",
            id="new_id"
        )
        self.assertTrue(is_already_crossposted(sub1, existing_urls, history_ids))

        # Case 2: Post in existing_urls (url)
        sub2 = SimpleNamespace(
            permalink="/r/test/comments/new",
            url="https://reddit.com/r/test/comments/existing", # This url is in existing_urls
            id="new_id_2"
        )
        # Note: existing_urls contains "https://reddit.com/r/test/comments/existing"
        self.assertTrue(is_already_crossposted(sub2, existing_urls, history_ids))

        # Case 3: Post in history_ids
        sub3 = SimpleNamespace(
            permalink="/r/test/comments/new_2",
            url="https://new.url",
            id="existing_id"
        )
        self.assertTrue(is_already_crossposted(sub3, existing_urls, history_ids))

        # Case 4: New post
        sub4 = SimpleNamespace(
            permalink="/r/test/comments/fresh",
            url="https://fresh.url",
            id="fresh_id"
        )
        self.assertFalse(is_already_crossposted(sub4, existing_urls, history_ids))

if __name__ == '__main__':
    unittest.main()
