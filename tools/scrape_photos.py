import urllib.request
import urllib.parse
import json
import re
import os
import sys

SOURCE_URL = "https://www.kadernictviadam-uh.cz/fotogalerie/"
CDN_BASE   = "https://da3a167c38.clvaw-cdnwnd.com/ae0c45b94cb3f30f2ff9aba64493d889/"
GQL_URL    = "https://kadernictviadam-uh.cz/servers/graphql/"
OUT_DIR    = os.path.join(os.path.dirname(__file__), "..", "photos")
MIN_SIZE   = 5000
SKIP_RE    = re.compile(r"icon|logo|pixel|sprite|thumb|1x1|arrow|btn|banner|spacer", re.I)
IMG_RE     = re.compile(r"https?://[^\s\"'<>]+\.(?:jpe?g|png|webp)(?:\?[^\s\"'<>]*)?", re.I)

headers = {"User-Agent": "Mozilla/5.0"}

def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")

def download(url, path):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        content = r.read()
    if len(content) < MIN_SIZE:
        return False
    with open(path, "wb") as f:
        f.write(content)
    return True

os.makedirs(OUT_DIR, exist_ok=True)

print("Fetching gallery page...")
html = fetch(SOURCE_URL)

# 1. Find all image URLs directly in HTML/JS
candidates = IMG_RE.findall(html)

# 2. Try GraphQL for photo gallery block
print("Trying GraphQL endpoint...")
gql_block_id = "91761750174327294522"
queries = [
    '{"query":"{ photoGallery(id:\\"%s\\") { photos { url } } }"}' % gql_block_id,
    '{"query":"{ block(id:\\"%s\\") { ... on PhotoGalleryBlock { photos { url src } } } }"}' % gql_block_id,
    '{"query":"{ component(id:\\"%s\\") { photos { url } } }"}' % gql_block_id,
]
for q in queries:
    try:
        resp = fetch(GQL_URL, data=q.encode())
        found = IMG_RE.findall(resp)
        if found:
            candidates += found
            print(f"  GraphQL returned {len(found)} image URLs")
            break
    except Exception as e:
        print(f"  GraphQL attempt failed: {e}")

# 3. Also try CDN directory listing patterns seen on Webnode
cdn_patterns = [
    CDN_BASE + "200000084/",  # page ID
]
for cp in cdn_patterns:
    try:
        resp = fetch(cp)
        found = IMG_RE.findall(resp)
        candidates += found
        print(f"  CDN listing returned {len(found)} URLs")
    except:
        pass

# Deduplicate and filter
seen = set()
urls = []
for u in candidates:
    u_clean = u.split("?")[0]
    if u_clean in seen:
        continue
    seen.add(u_clean)
    if SKIP_RE.search(u):
        continue
    urls.append(u)

print(f"Found {len(urls)} candidate images")

# Download
saved = 0
for i, url in enumerate(urls, 1):
    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpeg"
    dest = os.path.join(OUT_DIR, f"foto-{saved+1}.{ext}")
    try:
        ok = download(url, dest)
        if ok:
            saved += 1
            print(f"  [{saved}] {url}")
        else:
            print(f"  SKIP (too small): {url}")
    except Exception as e:
        print(f"  ERR {url}: {e}")

print(f"\nDone. Saved {saved} photos to photos/")
