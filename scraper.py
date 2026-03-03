import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import time

SOURCES = [
    {"url": "https://id.medanaktual.com/category/bpjs-kesehatan/", "category": "BPJS Kesehatan"},
]

FEED_TITLE = "BPJS Kesehatan - MedanAktual RSS Feed"
FEED_DESCRIPTION = "RSS Feed untuk id.medanaktual.com kategori BPJS Kesehatan"
FEED_LINK = "https://id.medanaktual.com/category/bpjs-kesehatan/"
OUTPUT_FILE = "feed.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=True, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        print(f"  [ERROR] Gagal mengambil {url}: {e}")
        return None

def get_domain(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc

def parse_articles(html, source_url, category):
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_urls = set()
    domain = get_domain(source_url)

    links = []
    for tag in ["h1", "h2", "h3", "h4"]:
        for heading in soup.find_all(tag):
            for a in heading.find_all("a", href=True):
                links.append(a)

    for cls in ["post-title", "entry-title", "jeg_post_title", "article-title", "title"]:
        for a in soup.select(f"a.{cls}, .{cls} a"):
            if a not in links:
                links.append(a)

    for article in soup.find_all("article"):
        for a in article.find_all("a", href=True):
            title_text = a.get_text(strip=True)
            if len(title_text) > 20 and a not in links:
                links.append(a)

    for link in links:
        url = link.get("href", "").strip()
        title = link.get_text(strip=True)

        if not url or not title or len(title) < 15:
            continue
        if url in seen_urls:
            continue
        if url.startswith("/"):
            url = f"https://{domain}{url}"
        if domain not in url:
            continue
        skip = ["/category/", "/tag/", "/page/", "/kategori/", "/author/", "#", "javascript:"]
        if any(p in url for p in skip):
            continue
        if url.rstrip("/") == source_url.rstrip("/"):
            continue

        seen_urls.add(url)

        excerpt = ""
        parent = link.parent
        for _ in range(8):
            if parent is None:
                break
            parent = parent.parent
            if parent:
                p_tag = parent.find("p")
                if p_tag and len(p_tag.get_text(strip=True)) > 30:
                    excerpt = p_tag.get_text(strip=True)[:300]
                    break

        image = ""
        img_parent = link.parent
        for _ in range(6):
            if img_parent is None:
                break
            img_parent = img_parent.parent
            if img_parent:
                img = img_parent.find("img")
                if img:
                    src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
                    if src and "jeg-empty" not in src and "data:image" not in src and "placeholder" not in src:
                        if src.startswith("/"):
                            src = f"https://{domain}{src}"
                        image = src
                        break

        articles.append({
            "title": title,
            "url": url,
            "excerpt": excerpt,
            "image": image,
            "category": category,
            "source": domain,
        })

    return articles

def fetch_article_date(url):
    html = fetch_page(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    for meta_prop in ["article:published_time", "og:published_time", "datePublished"]:
        meta = soup.find("meta", {"property": meta_prop}) or soup.find("meta", {"name": meta_prop})
        if meta and meta.get("content"):
            return meta["content"]

    time_tag = soup.find("time", {"datetime": True})
    if time_tag:
        return time_tag["datetime"]

    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            import json
            data = json.loads(script.string)
            if isinstance(data, dict) and "datePublished" in data:
                return data["datePublished"]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "datePublished" in item:
                        return item["datePublished"]
        except Exception:
            pass
    return ""

def format_date_rfc822(date_str):
    if not date_str:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except Exception:
        return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

def generate_rss(articles):
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:media", "http://search.yahoo.com/mrss/")

    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = FEED_TITLE
    ET.SubElement(channel, "description").text = FEED_DESCRIPTION
    ET.SubElement(channel, "link").text = FEED_LINK
    ET.SubElement(channel, "language").text = "id"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    github_user = os.environ.get("GITHUB_REPOSITORY_OWNER", "Kimjo12")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1] if os.environ.get("GITHUB_REPOSITORY") else "BPJS-Kesehatan---MedanAktual-RSS-Feed"
    feed_url = f"https://{github_user}.github.io/{repo_name}/feed.xml"

    atom_link = ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    print(f"\nMengambil tanggal untuk {len(articles)} artikel...")

    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article['title'][:60]}...")
        if i > 0 and i % 5 == 0:
            time.sleep(1)

        pub_date = format_date_rfc822(fetch_article_date(article["url"]))

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article["title"]
        ET.SubElement(item, "link").text = article["url"]
        ET.SubElement(item, "guid").text = article["url"]
        ET.SubElement(item, "pubDate").text = pub_date
        ET.SubElement(item, "category").text = article.get("category", "")

        if article.get("excerpt"):
            ET.SubElement(item, "description").text = article["excerpt"]

        if article.get("image"):
            media = ET.SubElement(item, "{http://search.yahoo.com/mrss/}content")
            media.set("url", article["image"])
            media.set("medium", "image")

    xml_string = ET.tostring(rss, encoding="unicode", xml_declaration=False)
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string

    try:
        dom = minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent="  ", encoding=None)
        pretty_xml = "\n".join(pretty_xml.split("\n")[1:])
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty_xml
    except Exception:
        pass

    return xml_string

def main():
    print("=" * 60)
    print("RSS Feed Generator - BPJS Kesehatan")
    print("=" * 60)

    all_articles = []
    seen_urls = set()

    for source in SOURCES:
        url = source["url"]
        category = source["category"]

        print(f"\nScraping: {url}")
        html = fetch_page(url)
        if not html:
            continue

        articles = parse_articles(html, url, category)
        for article in articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                all_articles.append(article)

        print(f"  Ditemukan: {len(articles)} artikel")

    if not all_articles:
        rss_content = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        rss_content += f"<title>{FEED_TITLE}</title><link>{FEED_LINK}</link>"
        rss_content += f"<description>{FEED_DESCRIPTION}</description></channel></rss>"
    else:
        rss_content = generate_rss(all_articles)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss_content)

    print(f"\n[SUCCESS] Feed disimpan ke {OUTPUT_FILE}")
    print(f"Total artikel: {len(all_articles)}")

if __name__ == "__main__":
    main()
