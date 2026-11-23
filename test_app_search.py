import os
import threading
import unittest
from unittest.mock import patch

import app


class FakeResponse:
    def __init__(self, text: str = "", json_data=None) -> None:
        self.text = text
        self.json_data = json_data

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.json_data


class FakePageResponse(FakeResponse):
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}
    encoding = "utf-8"
    is_redirect = False
    is_permanent_redirect = False

    def iter_content(self, chunk_size: int):
        yield self.text.encode()

    def close(self) -> None:
        return None


class FakeProgress:
    def progress(self, *_args, **_kwargs) -> None:
        return None

    def empty(self) -> None:
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

    def test_uses_wikipedia_search_when_duckduckgo_has_no_results(self) -> None:
        wikipedia_results = {
            "query": {
                "search": [
                    {
                        "title": "Eiffel Tower replicas and derivatives",
                        "snippet": "A list of replicas.",
                    },
                    {
                        "title": "Eiffel Tower",
                        "snippet": "The tower is 330 metres tall.",
                    },
                ]
            }
        }
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            with patch("app.requests.get", side_effect=[
                FakeResponse("<html><body>No results</body></html>"),
                FakeResponse("<html><body>No results</body></html>"),
                FakeResponse(json_data=wikipedia_results),
            ]) as get:
                results = app.web_search(
                    "Since 2022, the Eiffel Tower has been 330 metres tall.",
                    limit=3,
                )

        self.assertEqual(results[0]["title"], "Eiffel Tower")
        self.assertEqual(results[0]["url"], "https://en.wikipedia.org/wiki/Eiffel_Tower")
        self.assertEqual(results[0]["snippet"], "The tower is 330 metres tall.")
        self.assertEqual(get.call_args_list[2].kwargs["params"]["srsearch"], "Eiffel Tower")
        self.assertEqual(get.call_args_list[2].kwargs["params"]["srlimit"], 10)

    def test_measurement_with_year_is_not_classified_as_date_only(self) -> None:
        claims = app.extract_claims([
            "Since 2022, the Eiffel Tower has been 330 metres tall, including its new antenna."
        ])

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].kind, "Statistic")

    def test_source_page_table_rows_can_verify_a_supply_limit(self) -> None:
        claim = app.Claim(
            "The Bitcoin protocol has a maximum supply limit of 21 million bitcoins.",
            1,
            "Statistic",
        )
        hit = {
            "title": "Bitcoin",
            "url": "https://en.wikipedia.org/wiki/Bitcoin",
            "snippet": "",
        }
        with patch("app.web_search", return_value=[hit]), patch(
            "app.fetch_source_text", return_value="Supply limit — ₿21,000,000"
        ):
            result = app.verify_claim(claim, limit=1)

        self.assertEqual(result["status"], "Verified")
        self.assertIn("21,000,000", result["sources"][0]["evidence"][0])

    def test_unrelated_bitcoin_transaction_amount_does_not_conflict_with_supply_limit(self) -> None:
        claim = app.Claim(
            "The Bitcoin protocol has a maximum supply limit of 21 million bitcoins.",
            1,
            "Statistic",
        )
        hit = {
            "title": "Bitcoin",
            "url": "https://en.wikipedia.org/wiki/Bitcoin",
            "snippet": "",
        }
        page_text = (
            "Supply limit — ₿21,000,000\n"
            + "The Bitcoin protocol was designed to handle transactions securely.\n" * 5
            + "During its 30 months of existence, Silk Road exclusively accepted "
            "bitcoins as payment, transacting ₿9.9"
        )
        with patch("app.web_search", return_value=[hit]), patch(
            "app.fetch_source_text", return_value=page_text
        ):
            result = app.verify_claim(claim, limit=1)

        self.assertEqual(result["status"], "Verified")
        self.assertIn("21,000,000", result["sources"][0]["evidence"][0])

    def test_replica_tower_height_does_not_count_as_eiffel_tower_conflict(self) -> None:
        claim = app.Claim(
            "Since 2022, the Eiffel Tower has been 330 metres tall, including its new antenna.",
            1,
            "Statistic",
        )
        hit = {
            "title": "Eiffel Tower replicas and derivatives",
            "url": "https://en.wikipedia.org/wiki/Eiffel_Tower_replicas_and_derivatives",
            "snippet": "",
        }
        with patch("app.web_search", return_value=[hit]), patch(
            "app.fetch_source_text",
            return_value="New Brighton Tower — United Kingdom — 173 m (568 ft)",
        ):
            result = app.verify_claim(claim, limit=1)

        self.assertEqual(result["status"], "Needs review")

    def test_fetch_source_text_keeps_table_labels_with_values(self) -> None:
        response = FakePageResponse(
            "<html><main><table>"
            "<tr><th>Circulating supply</th><td>20,057,778</td></tr>"
            "<tr><th>Supply limit</th><td>₿21,000,000</td></tr>"
            "</table></main></html>"
        )
        with patch("app.socket.getaddrinfo", return_value=[
            (None, None, None, None, ("8.8.8.8", 443))
        ]), patch("app.requests.get", return_value=response):
            text = app.fetch_source_text("https://example.com/bitcoin")

        self.assertIn("Supply limit — ₿21,000,000", text)
        segments = app.split_evidence(text)
        self.assertIn("Circulating supply — 20,057,778", segments)
        self.assertIn("Supply limit — ₿21,000,000", segments)

    def test_fetch_source_text_joins_inline_markup_within_sentences(self) -> None:
        response = FakePageResponse(
            "<html><main><p>The tower is <a>330 metres</a> tall.</p></main></html>"
        )
        with patch("app.socket.getaddrinfo", return_value=[
            (None, None, None, None, ("8.8.8.8", 443))
        ]), patch("app.requests.get", return_value=response):
            text = app.fetch_source_text("https://example.com/eiffel-tower")

        self.assertIn("The tower is 330 metres tall.", text)

    def test_no_search_results_require_review_not_false(self) -> None:
        claim = app.Claim("Python 3.12 was released on 2 October 2023.", 1, "Date")
        with patch("app.web_search", return_value=[]):
            result = app.verify_claim(claim)

        self.assertEqual(result["status"], "Needs review")
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["sources"], [])

    def test_verify_claim_uses_one_full_depth_query_when_it_finds_enough_sources(self) -> None:
        claim = app.Claim(
            "The Bitcoin protocol has a maximum supply limit of 21 million bitcoins.",
            1,
            "Statistic",
        )
        hits = [
            {"title": f"Source {index}", "url": f"https://source{index}.example", "snippet": ""}
            for index in range(6)
        ]

        def search(_query, limit):
            return hits[:limit]

        with patch("app.web_search", side_effect=search) as web_search, patch(
            "app.fetch_source_text", return_value=""
        ):
            app.verify_claim(claim, limit=6)

        self.assertEqual(web_search.call_count, 1)
        self.assertEqual(web_search.call_args.args[1], 6)

    def test_run_all_checks_claims_concurrently_and_preserves_input_order(self) -> None:
        claims = [
            app.Claim("First claim has 12 units.", 1, "Statistic"),
            app.Claim("Second claim has 34 units.", 2, "Statistic"),
        ]
        barrier = threading.Barrier(2)

        def verify(claim, _limit):
            barrier.wait(timeout=1)
            return {"claim": claim.text}

        with patch("app.verify_claim", side_effect=verify), patch(
            "app.st.progress", return_value=FakeProgress()
        ):
            results = app.run_all(claims, limit=3)

        self.assertEqual([result["claim"] for result in results], [claim.text for claim in claims])


if __name__ == "__main__":
    unittest.main()
