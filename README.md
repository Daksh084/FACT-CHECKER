# FactCheck — Truth Layer

Streamlit PDF fact-checker that extracts statistic, date, financial and technical figure claims, searches the live web, and presents source links with page references. The detailed PDF export includes each verdict, confidence cue, source snippet and link, and reviewer decision.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Set `TAVILY_API_KEY` to use Tavily search. Without it, the app tries DuckDuckGo and then Wikipedia's public search API. Each claim first searches its original wording for up to the selected source depth; number-free and focused entity/metric queries run only when fewer than three results are found. Multiple claims are checked two at a time, and provider/page HTTP requests use explicit timeouts to keep long runs responsive. The checker opens result pages where available, compares figures with relevant text, normalizes common units, checks dates, and weighs independent sources. It automatically assigns **Verified**, **Inaccurate**, or **Needs review** from the evidence; a related source snippet alone is not enough to prove a claim, so weak, ambiguous, or conflicting evidence stays in **Needs review**. Results are still evidence triage: an unsupported claim is not proof of the opposite. Text PDFs are supported; scanned PDF OCR is not included.

## Deploy on Streamlit Community Cloud

The app is configured for Streamlit Community Cloud. From a GitHub repository you own or administer:

1. Push this project to GitHub with `app.py` and `requirements.txt` at the repository root.
2. Sign in at [share.streamlit.io](https://share.streamlit.io/) with GitHub and select **Create app**.
3. Choose the repository and branch, set the app file to `app.py`, and deploy. Streamlit will provide a shareable `*.streamlit.app` URL.
4. Optional: add `TAVILY_API_KEY = "..."` under **App settings → Secrets** for Tavily web search. Without it, the app uses DuckDuckGo and Wikipedia fallbacks.

The `.streamlit/config.toml` sets the dark theme and 20 MB upload limit. Do not commit `.streamlit/secrets.toml` or API keys. Community Cloud deploys from GitHub and requires GitHub access to the repository; code updates pushed to the selected branch trigger redeployment. `Procfile` and `render.yaml` are included for Render hosting as an alternative.
