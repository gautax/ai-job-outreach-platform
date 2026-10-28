import re
from urllib.parse import urljoin, urlparse

from fastapi import FastAPI, HTTPException
from scrapling.fetchers import Fetcher


app = FastAPI(
    title="Job Outreach Scraper",
    version="0.7.0",
)

COUNTRY_SOURCES = {
    "Austria": (
        "https://www.eu-startups.com/"
        "category/austria-startups/"
    ),
    "Poland": (
        "https://www.eu-startups.com/"
        "category/poland-startups/"
    ),
    "Bulgaria": (
        "https://www.eu-startups.com/"
        "category/bulgaria/"
    ),
}

FUNDING_ACTION_PATTERN = re.compile(
    r"\b("
    r"raise|raises|raised|raising|"
    r"secure|secures|secured|"
    r"close|closes|closed|"
    r"bag|bags|bagged|"
    r"land|lands|landed|"
    r"funding|investment|"
    r"pre[- ]seed|seed round|"
    r"series [a-z]"
    r")\b",
    re.IGNORECASE,
)

MONEY_PATTERN = re.compile(
    r"(?:€|£|\$)\s?\d[\d.,]*"
    r"(?:\s?(?:k|m|bn|million|billion))?"
    r"|"
    r"(?:EUR|USD|GBP)\s?\d[\d.,]*"
    r"(?:\s?(?:k|m|bn|million|billion))?",
    re.IGNORECASE,
)

EXCLUDED_PATTERN = re.compile(
    r"weekly funding round[- ]?up"
    r"|funding rounds we tracked"
    r"|majority stake"
    r"|acquisition"
    r"|acquires?"
    r"|startups to watch",
    re.IGNORECASE,
)

ALLOWED_ARTICLE_HOSTS = {
    "eu-startups.com",
    "www.eu-startups.com",
}

SOCIAL_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "youtube.com",
    "www.youtube.com",
    "tiktok.com",
    "www.tiktok.com",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").split())


def validate_article_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail="Only HTTP or HTTPS URLs are allowed.",
        )

    if parsed.hostname not in ALLOWED_ARTICLE_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Only EU-Startups article URLs are allowed.",
        )


def get_first_value(page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        value = page.css(selector).get()

        if value:
            return clean_text(value)

    return ""


def get_article_paragraphs(page):
    selectors = (
        ".td-post-content p",
        ".entry-content p",
        "article p",
    )

    for selector in selectors:
        nodes = page.css(selector)

        paragraphs = []

        for node in nodes:
            text = clean_text(node.get_all_text())

            if len(text) < 40:
                continue

            if text not in paragraphs:
                paragraphs.append(text)

        if len(paragraphs) >= 2:
            return paragraphs

    return []


def get_article_links(page, article_url: str):
    selectors = (
        ".td-post-content a",
        ".entry-content a",
        "article a",
    )

    external_links = []
    social_links = []
    seen_links = set()

    for selector in selectors:
        nodes = page.css(selector)

        if not nodes:
            continue

        for node in nodes:
            href = clean_text(
                node.attrib.get("href", "")
            )

            if not href:
                continue

            absolute_url = urljoin(article_url, href)
            parsed = urlparse(absolute_url)

            if parsed.scheme not in {"http", "https"}:
                continue

            if absolute_url in seen_links:
                continue

            seen_links.add(absolute_url)

            hostname = parsed.hostname or ""

            if hostname in ALLOWED_ARTICLE_HOSTS:
                continue

            if hostname in SOCIAL_HOSTS:
                social_links.append(absolute_url)
            else:
                external_links.append(absolute_url)

        if external_links or social_links:
            break

    return {
        "external_links": external_links[:20],
        "social_links": social_links[:10],
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "job-outreach-scraper",
        "version": "0.7.0",
    }


@app.get("/discover-test")
def discover_test(country: str = "Austria", pages: int = 3):
    requested_country = country.strip().title()

    if requested_country == "All":
        countries = list(COUNTRY_SOURCES.keys())
    elif requested_country in COUNTRY_SOURCES:
        countries = [requested_country]
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported country. "
                "Use Austria, Poland, Bulgaria, or All."
            ),
        )

    # Keep discovery bounded for the MVP.
    pages = max(1, min(pages, 5))

    all_articles = []
    seen_urls = set()

    country_results = []
    errors = []

    total_heading_links = 0
    successful_pages = 0

    for country_name in countries:
        source_url = COUNTRY_SOURCES[country_name]

        country_articles_before = len(all_articles)
        country_heading_links = 0
        pages_scanned = 0

        for page_number in range(1, pages + 1):

            if page_number == 1:
                page_url = source_url
            else:
                page_url = urljoin(
                    source_url,
                    f"page/{page_number}/",
                )

            try:
                page = Fetcher.get(
                    page_url,
                    impersonate="chrome",
                    stealthy_headers=True,
                    timeout=30,
                    retries=2,
                )
            except Exception as exc:
                errors.append(
                    {
                        "country": country_name,
                        "page": page_number,
                        "url": page_url,
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }
                )
                continue

            successful_pages += 1
            pages_scanned += 1

            heading_links = page.css(
                ".td_block_big_grid_flex_2 h2 a, "
                ".td_block_big_grid_flex_2 h3 a, "
                ".tdb-category-loop-posts h2 a, "
                ".tdb-category-loop-posts h3 a"
            )

            country_heading_links += len(
                heading_links
            )
            total_heading_links += len(
                heading_links
            )

            for link in heading_links:
                title = clean_text(
                    link.get_all_text()
                )

                href = clean_text(
                    link.attrib.get("href", "")
                )

                if not title or not href:
                    continue

                article_url = urljoin(
                    page_url,
                    href,
                )

                parsed_url = urlparse(
                    article_url
                )

                if (
                    parsed_url.hostname
                    not in ALLOWED_ARTICLE_HOSTS
                ):
                    continue

                if parsed_url.path.startswith(
                    (
                        "/category/",
                        "/author/",
                        "/tag/",
                        "/page/",
                    )
                ):
                    continue

                # Deduplicate across pages AND countries.
                if article_url in seen_urls:
                    continue

                if EXCLUDED_PATTERN.search(title):
                    continue

                if not FUNDING_ACTION_PATTERN.search(
                    title
                ):
                    continue

                if not MONEY_PATTERN.search(title):
                    continue

                seen_urls.add(article_url)

                all_articles.append(
                    {
                        "title": title,
                        "article_url": article_url,
                        "country": country_name,
                        "source": "EU-Startups",
                        "status": "NEW",
                        "discovery_page": page_number,
                    }
                )

        country_results.append(
            {
                "country": country_name,
                "source_url": source_url,
                "pages_scanned": pages_scanned,
                "heading_links_found":
                    country_heading_links,
                "articles_found":
                    (
                        len(all_articles)
                        - country_articles_before
                    ),
            }
        )

    if successful_pages == 0:
        raise HTTPException(
            status_code=502,
            detail={
                "message":
                    "No discovery pages could be fetched.",
                "errors": errors,
            },
        )

    return {
        "status":
            "ok" if not errors else "partial",
        "country": requested_country,
        "countries_scanned": countries,
        "pages_requested": pages,
        "pages_scanned": successful_pages,
        "heading_links_found":
            total_heading_links,
        "articles_found":
            len(all_articles),
        "country_results":
            country_results,
        "errors": errors,
        "articles": all_articles,
    }


@app.get("/article-details")
def article_details(url: str):
    validate_article_url(url)

    try:
        page = Fetcher.get(
            url,
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
            retries=2,
        )

        title = get_first_value(
            page,
            (
                "h1::text",
                'meta[property="og:title"]::attr(content)',
                "title::text",
            ),
        )

        published_at = get_first_value(
            page,
            (
                'meta[property="article:published_time"]'
                "::attr(content)",
                "time::attr(datetime)",
            ),
        )

        paragraphs = get_article_paragraphs(page)
        full_text = "\n\n".join(paragraphs)

        maximum_length = 7000
        article_text = full_text[:maximum_length]

        links = get_article_links(page, url)

        return {
            "status": "ok",
            "article_url": url,
            "title": title,
            "published_at": published_at,
            "article_text": article_text,
            "word_count": len(full_text.split()),
            "text_truncated": len(full_text) > maximum_length,
            "external_links": links["external_links"],
            "social_links": links["social_links"],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
