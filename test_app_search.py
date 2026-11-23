import os
import unittest
from unittest.mock import patch

import app


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class WebSearchTests(unittest.TestCase):
    def test_uses_lite_search_when_html_search_has_no_results(self) -> None:
        lite_results = """
        <table>
          <tr><td><a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F">Python Release</a></td></tr>
          <tr><td class="result-snippet">Release date: Oct. 2, 2023.</td></tr>
        </table>
        """
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            with patch("app.requests.get", side_effect=[
                FakeResponse("<html><body>No results</body></html>"),
                FakeResponse(lite_results),
            ]) as get:
                results = app.web_search("Python 3.12 release date", limit=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://www.python.org/")
        self.assertIn("Oct. 2, 2023", results[0]["snippet"])
        self.assertEqual(get.call_count, 2)

    def test_no_search_results_require_review_not_false(self) -> None:
        claim = app.Claim("Python 3.12 was released on 2 October 2023.", 1, "Date")
        with patch("app.web_search", return_value=[]):
            result = app.verify_claim(claim)

        self.assertEqual(result["status"], "Needs review")
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
