#!/usr/bin/env python3
"""Holt die RSS-Feeds und schreibt die neuesten Einträge nach feed.json. Kommt ohne KI aus."""
import json, re, html, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FEEDS = {
    "Welt & Politik": {
        "Tagesschau": "https://www.tagesschau.de/ausland/index~rss2.xml",
        "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "The Guardian": "https://www.theguardian.com/world/rss",
        "Deutsche Welle": "https://rss.dw.com/xml/rss-de-all",
    },
    "Deutschland & Polen": {
        "Tagesschau": "https://www.tagesschau.de/inland/index~rss2.xml",
        "SWR": "https://www.swr.de/~rss/swraktuell/swraktuell-bw-100.xml",
        "Notes from Poland": "https://notesfrompoland.com/feed/",
    },
    "Wirtschaft & Börse": {
        "Tagesschau": "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
        "BBC": "https://feeds.bbci.co.uk/news/business/rss.xml",
    },
    "Tech & KI": {
        "heise online": "https://www.heise.de/rss/heise-top-atom.xml",
        "BBC": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "Golem": "https://rss.golem.de/rss.php?feed=RSS2.0",
    },
}
MAX_PER_FEED, MAX_AGE = 8, timedelta(hours=48)
NOW = datetime.now(timezone.utc)


def text(node, *names):
    for n in names:
        for child in node:
            if child.tag.split("}")[-1] == n and (child.text or "").strip():
                return child.text.strip()
    return ""


def clean(s, limit=200):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def when(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def link(node):
    for child in node:
        if child.tag.split("}")[-1] == "link":
            if child.get("href") and child.get("rel", "alternate") == "alternate":
                return child.get("href")
            if (child.text or "").strip():
                return child.text.strip()
    return ""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "weltlage-news/1.0 (personal RSS reader)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def main():
    out = {"fetchedAt": NOW.isoformat(timespec="seconds"), "topics": {}, "report": []}
    for topic, feeds in FEEDS.items():
        seen, items = set(), []
        for source, url in feeds.items():
            try:
                root = fetch(url)
                entries = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
                n = 0
                for e in entries:
                    u, t = link(e), clean(text(e, "title"), 200)
                    d = when(text(e, "pubDate", "date", "published", "updated"))
                    if not u.startswith("https://") or not t or u in seen or (d and NOW - d > MAX_AGE):
                        continue
                    seen.add(u)
                    items.append({"title": t, "url": u, "source": source, "date": d.isoformat(timespec="minutes") if d else ""})
                    n += 1
                    if n >= MAX_PER_FEED:
                        break
                out["report"].append({"url": url, "ok": True, "items": n})
            except Exception as ex:  # Ein kaputter Feed darf die anderen nicht aufhalten.
                out["report"].append({"url": url, "ok": False, "error": f"{type(ex).__name__}: {ex}"[:200]})
        out["topics"][topic] = items
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for r in out["report"]:
        print(r)


if __name__ == "__main__":
    main()
