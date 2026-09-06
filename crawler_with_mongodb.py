import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pymongo import MongoClient

# Ensure UTF-8 output encoding for Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ------------------ MongoDB Setup ------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["webcrawler_db"]
collection = db["crawl_results"]

# ------------------ Global Data Stores ------------------
visited_urls = set()
broken_links = []          # Stores (parent_url, broken_url)
markup_issues = []         # Stores string issues

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ------------------ Utility Functions ------------------

def normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

def check_link_status(url, session=None):
    if session is None:
        session = requests.Session()
    try:
        res = session.head(url, allow_redirects=True, timeout=5, headers=DEFAULT_HEADERS)
        if res.status_code in (405, 403, 400):
            res = session.get(url, allow_redirects=True, timeout=5, headers=DEFAULT_HEADERS, stream=True)
        return res.status_code < 400
    except requests.RequestException:
        return False

def check_markup_issues(soup, url):
    issues = []

    # Missing alt attributes on images
    for img in soup.find_all("img"):
        if not img.get("alt"):
            issues.append(f"[MISSING ALT] Image with no alt on {url}")

    # Deprecated tags
    for tag in ["center", "font", "marquee"]:
        if soup.find_all(tag):
            issues.append(f"[DEPRECATED TAG] <{tag}> used on {url}")

    # Empty tags (except self-closing)
    for tag in soup.find_all():
        if tag.name not in ["br", "hr", "input", "img"] and not tag.text.strip() and not tag.attrs:
            issues.append(f"[EMPTY TAG] <{tag.name}> on {url}")

    # Duplicate IDs
    seen_ids = set()
    for tag in soup.find_all(attrs={"id": True}):
        id_val = tag['id']
        if id_val in seen_ids:
            issues.append(f"[DUPLICATE ID] #{id_val} appears more than once on {url}")
        else:
            seen_ids.add(id_val)

    return issues

# ------------------ Main Crawler Function ------------------

def crawl(url, depth, level=0, session=None):
    if session is None:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)

    url = normalize_url(url)

    if depth == 0 or url in visited_urls:
        return

    try:
        response = session.get(url, timeout=7, headers=DEFAULT_HEADERS)
        visited_urls.add(url)

        indent = "│   " * level + "├── "
        print(f"{indent}{url}")

        soup = BeautifulSoup(response.text, "html.parser")

        # Check markup issues
        markup_issues.extend(check_markup_issues(soup, url))

        # CSS files
        for link_tag in soup.find_all("link", rel="stylesheet"):
            css_href = link_tag.get("href")
            if css_href:
                css_url = normalize_url(urljoin(url, css_href))
                if is_valid_url(css_url):
                    status = "[CSS]"
                    if not check_link_status(css_url, session):
                        broken_links.append((url, css_url))
                        status = "[BROKEN CSS]"
                    print(f"{'│   ' * (level + 1)}├── {status} {css_url}")

        # JS files
        for script_tag in soup.find_all("script", src=True):
            js_url = normalize_url(urljoin(url, script_tag['src']))
            if is_valid_url(js_url):
                status = "[JS]"
                if not check_link_status(js_url, session):
                    broken_links.append((url, js_url))
                    status = "[BROKEN JS]"
                print(f"{'│   ' * (level + 1)}├── {status} {js_url}")

        # Images
        for img_tag in soup.find_all("img", src=True):
            img_url = normalize_url(urljoin(url, img_tag['src']))
            if is_valid_url(img_url):
                status = "[IMG]"
                if not check_link_status(img_url, session):
                    broken_links.append((url, img_url))
                    status = "[BROKEN IMG]"
                print(f"{'│   ' * (level + 1)}├── {status} {img_url}")

        # Hyperlinks
        for a_tag in soup.find_all("a", href=True):
            href = a_tag['href']
            link_url = normalize_url(urljoin(url, href))
            if is_valid_url(link_url):
                if not check_link_status(link_url, session):
                    broken_links.append((url, link_url))
                    print(f"{'│   ' * (level + 1)}├── [BROKEN LINK] {link_url}")
                crawl(link_url, depth - 1, level + 1, session)

    except requests.RequestException as e:
        error_indent = "│   " * level + "├── "
        print(f"{error_indent}[ERROR] Failed to crawl {url}: {e}")

# ------------------ Report & Save ------------------

def get_crawl_report():
    report = {
        "visited_urls": list(visited_urls),
        "broken_links": broken_links,
        "markup_issues": markup_issues
    }

    try:
        result = collection.insert_one(report)
        print(f"\n✅ Crawl report saved to MongoDB with _id: {result.inserted_id}")
    except Exception as e:
        print(f"\n❌ Error saving to MongoDB: {e}")

    return report

def reset_state():
    global visited_urls, broken_links, markup_issues
    visited_urls = set()
    broken_links = []
    markup_issues = []

# ------------------ Entry Point ------------------

if __name__ == "__main__":
    start_url = "https://sabya69.github.io/Study-Class/"
    max_depth = 2

    print("🌐 Website Crawl Tree (CSS + JS + IMG + Broken Links):")
    crawl(start_url, max_depth)

    print("\n❌ Broken Links Found:")
    for parent, bl in broken_links:
        print(f" - {bl} (found on: {parent})")

    print("\n⚠ Markup Issues Found:")
    for issue in markup_issues:
        print(f" - {issue}")

    print("\n📊 Crawl Summary:")
    print(f" - Pages Visited: {len(visited_urls)}")
    print(f" - Broken Links: {len(broken_links)}")
    print(f" - Markup Issues: {len(markup_issues)}")

    # Save report to MongoDB
    get_crawl_report()
