# Scraper Refactor Design

## Architecture & Data Flow
Instead of crawling board directories and relying on fragile Greenhouse DOM selectors (`#content`), the Sourcing Engine will now be intent-driven.
1. Use `duckduckgo-search` to query exact intent (e.g., "Software Engineer Intern Vancouver site:boards.greenhouse.io").
2. Retrieve direct URLs.
3. Fetch the HTML of the direct URLs and use `BeautifulSoup` to extract the raw text from `<body>`, stripping `<script>` and `<style>`.

## Data Structures
- `IntentScraper(BaseScraper)`: Takes an intent query instead of a generic company URL.
- Continues to output a list of `Job` models.

## Integration
This drops the heavy Playwright dependency for simple fetching, making the pipeline faster and less susceptible to timeouts. We will remove `GreenhouseScraper`.
