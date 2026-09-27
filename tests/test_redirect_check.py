import unittest

from main import resolve_redirect_url


class RedirectCheckTests(unittest.TestCase):
    def test_returns_same_url_for_non_redirect(self):
        self.assertEqual(
            resolve_redirect_url("https://example.com/file.pdf", ask_user=False),
            "https://example.com/file.pdf",
        )

    def test_returns_target_url_for_redirect(self):
        self.assertEqual(
            resolve_redirect_url(
                "https://example.com/start",
                location="https://example.com/final.pdf",
                ask_user=False,
            ),
            "https://example.com/final.pdf",
        )


if __name__ == "__main__":
    unittest.main()
