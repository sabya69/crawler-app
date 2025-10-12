import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["webcrawler_db"]
collection = db["crawl_results"]

# Global states
visited_urls = set()
broken_links = []  # stores tuples like (parent_url, broken_url)
markup_issues = []

# Normalize URLs to avoid duplicate visits
def normalize_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip('/')

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

def check_link_status(url):
    try:
        res = requests.head(url, allow_redirects=True, timeout=5)
        return res.status_code, res.status_code < 400
    except requests.RequestException:
        return 0, False

def crawl(url, depth, level=0):
    url = normalize_url(url)

    if depth == 0 or url in visited_urls:
        return

    try:
        response = requests.get(url, timeout=5)
        visited_urls.add(url)

        indent = "│   " * level + "├── "
        print(f"{indent}{url}")

        soup = BeautifulSoup(response.text, "html.parser")

        # ✅ Check markup issues
        markup_issues.extend(check_markup_issues(soup, url))

        # ▶ CSS files
        for link_tag in soup.find_all("link", rel="stylesheet"):
            css_href = link_tag.get("href")
            if css_href:
                css_url = normalize_url(urljoin(url, css_href))
                if is_valid_url(css_url):
                    code, is_ok = check_link_status(css_url)
                    if not is_ok:
                        broken_links.append((url, css_url))
                    print(f"{'│   ' * (level + 1)}├── [CSS] {css_url}")

        # ▶ JS files
        for script_tag in soup.find_all("script", src=True):
            js_url = normalize_url(urljoin(url, script_tag['src']))
            if is_valid_url(js_url):
                code, is_ok = check_link_status(js_url)
                if not is_ok:
                    broken_links.append((url, js_url))
                print(f"{'│   ' * (level + 1)}├── [JS] {js_url}")

        # ▶ Images
        for img_tag in soup.find_all("img", src=True):
            img_url = normalize_url(urljoin(url, img_tag['src']))
            if is_valid_url(img_url):
                code, is_ok = check_link_status(img_url)
                if not is_ok:
                    broken_links.append((url, img_url))
                print(f"{'│   ' * (level + 1)}├── [IMG] {img_url}")

        # ▶ Hyperlinks
        for a_tag in soup.find_all("a", href=True):
            href = a_tag['href']
            link_url = normalize_url(urljoin(url, href))
            if is_valid_url(link_url):
                code, is_ok = check_link_status(link_url)
                if not is_ok:
                    broken_links.append((url, link_url))
                if link_url not in visited_urls:
                    crawl(link_url, depth - 1, level + 1)

    except requests.RequestException:
        pass  # Silently skip errors without printing anything

def check_markup_issues(soup, url):
    issues = []

    # 🔤 Missing lang attribute on <html>
    if soup.html:
        if not soup.html.get("lang"):
            issues.append(f"[MISSING LANG] <html> tag missing 'lang' attribute on {url}")
    else:
        issues.append(f"[NO HTML TAG] <html> tag not found on {url}")

    # 🖼 Missing alt attributes on images
    for img in soup.find_all("img"):
        if not img.get("alt"):
            issues.append(f"[MISSING ALT] Image with no alt on {url}")

    # 🧙 Deprecated tags
    for tag in ["center", "font", "marquee"]:
        if soup.find_all(tag):
            issues.append(f"[DEPRECATED TAG] <{tag}> used on {url}")

    # 🕳 Empty tags
    for tag in soup.find_all():
        if tag.name not in ["br", "hr", "input", "img"] and not tag.text.strip() and not tag.attrs:
            issues.append(f"[EMPTY TAG] <{tag.name}> on {url}")

    # 🆔 Duplicate IDs
    seen_ids = set()
    for tag in soup.find_all(attrs={"id": True}):
        id_val = tag['id']
        if id_val in seen_ids:
            issues.append(f"[DUPLICATE ID] #{id_val} appears more than once on {url}")
        else:
            seen_ids.add(id_val)

    return issues

def reset_state():
    global visited_urls, broken_links, markup_issues
    visited_urls = set()
    broken_links = []
    markup_issues = []

def get_crawl_report():
    return {
        "visited_urls": visited_urls,
        "broken_links": broken_links,
        "markup_issues": markup_issues
    }


# ▶ Terminal test run
if __name__ == "__main__":
    start_url = "https://sabya69.github.io/Study-Class/"
    max_depth = 2

    print("🌐 Website Crawl Tree (CSS + JS + IMG):")
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
