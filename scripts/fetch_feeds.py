#!/usr/bin/env python3
"""Holt RSS-Feeds seriöser Medien, fasst gleiche Geschichten aus mehreren Quellen zusammen
und schreibt die wichtigsten pro Thema nach feed.json. Kommt ohne KI aus."""
import json, re, html, unicodedata, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FEEDS = {
    "Welt & Politik": {
        "Tagesschau": "https://www.tagesschau.de/ausland/index~rss2.xml",
        "Deutsche Welle": "https://rss.dw.com/xml/rss-de-all",
        "Spiegel": "https://www.spiegel.de/ausland/index.rss",
        "Zeit": "https://newsfeed.zeit.de/politik/ausland/index",
        "FAZ": "https://www.faz.net/rss/aktuell/politik/ausland/",
        "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "The Guardian": "https://www.theguardian.com/world/rss",
        "New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "New York Times (USA)": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "New York Times (Politik)": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "NPR": "https://feeds.npr.org/1004/rss.xml",
        "NPR (Politik)": "https://feeds.npr.org/1014/rss.xml",
        "PBS NewsHour": "https://www.pbs.org/newshour/feeds/rss/headlines",
        "Politico": "https://rss.politico.com/politics-news.xml",
        "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
        "France 24": "https://www.france24.com/en/rss",
        "CBC": "https://www.cbc.ca/webfeed/rss/rss-world",
        "The Hindu": "https://www.thehindu.com/news/international/feeder/default.rss",
        "South China Morning Post": "https://www.scmp.com/rss/91/feed",
        "ABC Australia": "https://www.abc.net.au/news/feed/51120/rss.xml",
        "Kyiv Independent": "https://kyivindependent.com/news-archive/rss/",
    },
    "Deutschland": {
        "Tagesschau": "https://www.tagesschau.de/inland/index~rss2.xml",
        "Spiegel": "https://www.spiegel.de/politik/deutschland/index.rss",
        "Zeit": "https://newsfeed.zeit.de/politik/deutschland/index",
        "FAZ": "https://www.faz.net/rss/aktuell/politik/inland/",
        "Süddeutsche": "https://rss.sueddeutsche.de/rss/Politik",
        "ZDF": "https://www.zdf.de/rss/zdf/nachrichten",
        "SWR": "https://www.swr.de/~rss/swraktuell/swraktuell-bw-100.xml",
    },
    "Polen": {
        "Notes from Poland": "https://notesfrompoland.com/feed/",
        "Rzeczpospolita": "https://www.rp.pl/rss_main",
        "Gazeta Wyborcza": "https://rss.gazeta.pl/pub/rss/wiadomosci.xml",
        "Deutsche Welle (Polen)": "https://rss.dw.com/xml/rss-pol-all",
    },
    "Wirtschaft & Börse": {
        "Tagesschau": "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
        "Handelsblatt": "https://www.handelsblatt.com/contentexport/feed/top-themen",
        "Handelsblatt (Finanzen)": "https://www.handelsblatt.com/contentexport/feed/finanzen",
        "FAZ": "https://www.faz.net/rss/aktuell/wirtschaft/",
        "Spiegel": "https://www.spiegel.de/wirtschaft/index.rss",
        "Zeit": "https://newsfeed.zeit.de/wirtschaft/index",
        "BBC": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "The Guardian": "https://www.theguardian.com/uk/business/rss",
        "New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "CNBC": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "Financial Times": "https://www.ft.com/world?format=rss",
    },
    "Sport": {
        "kicker": "https://newsfeed.kicker.de/news/fussball",
        "Sportschau": "https://www.sportschau.de/fussball/index~rss2.xml",
        "Spiegel": "https://www.spiegel.de/sport/fussball/index.rss",
        "Zeit": "https://newsfeed.zeit.de/sport/index",
        "FAZ": "https://www.faz.net/rss/aktuell/sport/fussball/",
        "11 Freunde": "https://11freunde.de/feed",
        "BBC": "https://feeds.bbci.co.uk/sport/football/rss.xml",
        "The Guardian": "https://www.theguardian.com/football/rss",
        "Sportschau (alle Sportarten)": "https://www.sportschau.de/index~rss2.xml",
        "The Guardian (Barcelona)": "https://www.theguardian.com/football/barcelona/rss",
        "Mundo Deportivo (Barça)": "https://www.mundodeportivo.com/rss/futbol/fc-barcelona.xml",
    },
    "Tech & KI": {
        "heise online": "https://www.heise.de/rss/heise-top-atom.xml",
        "Golem": "https://rss.golem.de/rss.php?feed=RSS2.0",
        "t3n": "https://t3n.de/rss.xml",
        "BBC": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Wired": "https://www.wired.com/feed/rss",
    },
}
MAX_PER_FEED, MAX_AGE, MAX_CLUSTERS, MAX_PER_CLUSTER = 10, timedelta(hours=36), 12, 3
NOW = datetime.now(timezone.utc)
FAVORITE = re.compile(r"barcelona|barça|barca\b|bar\u00e7a", re.I)  # Florians Lieblingsverein
STOP = set("""der die das und oder aber ein eine einer eines einem den dem des mit von vom für fuer auf aus bei nach über ueber unter vor zum zur ist sind war wird werden hat haben nicht noch auch nur wie was wer als bis seit gegen ohne mehr neue neuer neues jetzt heute soll will sich sein ihre ihr sie wir ich man doch schon sehr
the a an and or but of in on at to for from with by about after over under into is are was were be been has have had not no new says said will would could more than that this these those its their his her they it as up out amid how why what who what's report reports live update latest""".split())
SYN = {"russland": "russia", "russische": "russia", "russischen": "russia", "russian": "russia", "ukrainische": "ukraine", "ukrainischen": "ukraine", "ukrainian": "ukraine",
       "deutschland": "germany", "german": "germany", "deutsche": "germany", "polen": "poland", "polish": "poland", "polnische": "poland", "china": "china", "chinese": "china", "chinesische": "china",
       "usa": "us", "amerikanische": "us", "american": "us", "frankreich": "france", "french": "france", "israelische": "israel", "israeli": "israel", "iranische": "iran", "iranian": "iran",
       "türkei": "turkey", "turkish": "turkey", "japan": "japan", "japanese": "japan", "indien": "india", "indian": "india", "gazastreifen": "gaza", "zölle": "tariffs", "zoelle": "tariffs", "zoll": "tariffs",
       "waffenruhe": "ceasefire", "waffenstillstand": "ceasefire", "wahl": "election", "wahlen": "election", "präsident": "president", "praesident": "president", "regierung": "government"}


def text(node, *names):
    for n in names:
        for child in node:
            if child.tag.split("}")[-1] == n and (child.text or "").strip():
                return child.text.strip()
    return ""


def clean(s, limit):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:limit]


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


def keys(title):
    t = unicodedata.normalize("NFKC", title).lower()
    words = re.findall(r"[\wäöüß]+", t)
    return {SYN.get(w, w) for w in words if (len(w) > 3 or w in ("us", "uk", "eu", "un", "kI")) and w not in STOP}


def fetch(job):
    topic, source, url = job
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; weltlage-news/1.0; personal RSS reader)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            root = ET.fromstring(r.read())
        items = []
        for e in [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]:
            u, t = link(e), clean(text(e, "title"), 220)
            d = when(text(e, "pubDate", "date", "published", "updated"))
            if not u.startswith("https://") or not t or (d and NOW - d > MAX_AGE):
                continue
            items.append({"title": t, "url": u, "source": source, "date": d.isoformat(timespec="minutes") if d else "",
                          "teaser": clean(text(e, "description", "summary", "content"), 300), "_k": keys(t), "_d": d})
            if len(items) >= MAX_PER_FEED:
                break
        return topic, source, url, items, None
    except Exception as ex:  # Ein kaputter Feed darf die anderen nicht aufhalten.
        return topic, source, url, [], f"{type(ex).__name__}: {ex}"[:160]


def cluster(items):
    groups = []
    for it in items:
        best, score = None, 0
        for g in groups:
            inter = len(it["_k"] & g["k"])
            s = inter / (min(len(it["_k"]), len(g["k"])) or 1)
            if inter >= 2 and s >= .5 and s > score:
                best, score = g, s
        if best:
            best["items"].append(it); best["k"] |= it["_k"]
        else:
            groups.append({"k": set(it["_k"]), "items": [it]})
    out = []
    for g in groups:
        srcs = {i["source"].split(" (")[0] for i in g["items"]}
        newest = max((i["_d"] for i in g["items"] if i["_d"]), default=None)
        age = (NOW - newest).total_seconds() / 3600 if newest else 24
        seen, picked = set(), []
        for i in sorted(g["items"], key=lambda i: (-len(i["teaser"]), i["source"])):
            base = i["source"].split(" (")[0]
            if base in seen:
                continue
            seen.add(base); picked.append({k: v for k, v in i.items() if not k.startswith("_")})
            if len(picked) >= MAX_PER_CLUSTER:
                break
        fav = any(FAVORITE.search(i["title"] + " " + i["teaser"]) for i in g["items"])
        out.append({"sourceCount": len(srcs), "score": round(len(srcs) * 2 - age / 12, 2), **({"favorite": True} if fav else {}), "items": picked})
    out.sort(key=lambda c: -c["score"])
    for c in [c for c in out if c.get("favorite")][:3]:  # Die drei stärksten Barça-Geschichten bleiben immer drin.
        c["score"] += 6
    return sorted(out, key=lambda c: -c["score"])[:MAX_CLUSTERS]


def main():
    jobs = [(t, s, u) for t, feeds in FEEDS.items() for s, u in feeds.items()]
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(fetch, jobs))
    out = {"fetchedAt": NOW.isoformat(timespec="seconds"), "topics": {}, "report": []}
    for topic in FEEDS:
        items, seen = [], set()
        for t, s, u, its, err in results:
            if t != topic:
                continue
            out["report"].append({"topic": t, "source": s, "ok": err is None, "items": len(its), **({"error": err} if err else {})})
            for i in its:
                if i["url"] not in seen:
                    seen.add(i["url"]); items.append(i)
        out["topics"][topic] = cluster(items)
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for r in out["report"]:
        print(r)


if __name__ == "__main__":
    main()
