import os
import re
import time
import json
import base64
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY   = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")

# eBay Production API — swap in when production key is ready
EBAY_APP_ID  = os.getenv("EBAY_APP_ID", "")  # set in Railway env vars

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ------------------------------------------------------------------ #
#  GEMINI CLIENT
# ------------------------------------------------------------------ #

_gemini_client = None
_gemini_model  = None

def get_gemini():
    global _gemini_client, _gemini_model
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_KEY)
        try:
            models = [m.name for m in _gemini_client.models.list()]
            _gemini_model = next(
                (m for m in models if "gemini-1.5-pro" in m),
                next((m for m in models if "gemini-1.5" in m), "models/gemini-1.5-flash")
            )
        except Exception:
            _gemini_model = "models/gemini-1.5-flash"
    return _gemini_client, _gemini_model

# ------------------------------------------------------------------ #
#  POOR TITLE DETECTION
# ------------------------------------------------------------------ #

VAGUE_WORDS = {
    "lot","lots","misc","miscellaneous","assorted","various","shelf","shelves",
    "box","boxes","pallet","pallets","contents","items","stuff","goods",
    "mixed","unsorted","unknown","untested","as-is","as is","liquidation",
    "estate","bulk","group","collection","tray","bin","drawer","cabinet",
    "rack","floor","warehouse","surplus","row","skid","flat","crate",
}

def is_poor_title(title: str) -> bool:
    if not title or title.strip().lower() in ("unknown",""):
        return True
    words = title.lower().split()
    if len(words) <= 4:
        return True
    return any(w in VAGUE_WORDS for w in words)

# ------------------------------------------------------------------ #
#  GEMINI: INTERNET-WIDE VALUE RESEARCH
# ------------------------------------------------------------------ #

def research_value_gemini(title: str, current_price: float) -> dict:
    """
    Use Gemini + Google Search to research item value across the entire internet.
    Searches eBay sold/active, Amazon, Google Shopping, local listings, and more.
    """
    if not GEMINI_KEY:
        return {"value_status": "unavailable", "value_source": "gemini_search"}

    try:
        from google.genai import types
        client, model = get_gemini()

        prompt = f"""You are a resale pricing expert. Research the current market value of this item.

Item: "{title}"
Current auction bid: ${current_price:.2f}

Search the internet thoroughly — check:
1. eBay SOLD listings (most important)
2. eBay active listings  
3. Amazon pricing
4. Google Shopping
5. Any other marketplace listings you find

Return ONLY a raw JSON object with no markdown or backticks:
{{
  "value_used_low": lowest realistic resale price for used condition as number,
  "value_used_high": highest realistic resale price for used condition as number,
  "value_new_low": lowest price for new condition as number,
  "value_new_high": highest price for new condition as number,
  "sources_checked": ["eBay sold", "Amazon", etc],
  "notes": "brief note on pricing basis or market conditions"
}}

Use 0 for any value you cannot determine. Numbers only, no $ signs."""

        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)

        def safe(v):
            try:
                return round(float(str(v).replace("$","").replace(",","")), 2)
            except Exception:
                return 0.0

        return {
            "value_used_low":  safe(data.get("value_used_low", 0)),
            "value_used_high": safe(data.get("value_used_high", 0)),
            "value_new_low":   safe(data.get("value_new_low", 0)),
            "value_new_high":  safe(data.get("value_new_high", 0)),
            "value_status":    "done",
            "value_source":    "gemini_search",
            "ai_description":  data.get("notes", ""),
        }

    except Exception as e:
        print(f"Gemini search error: {e}")
        return {"value_status": "unavailable", "value_source": "gemini_search"}


def analyze_image_gemini(image_url: str, title: str, current_price: float) -> dict:
    """
    For poor/mixed lot titles: analyze the image with Gemini Vision.
    Identifies items, generates a description, and researches value.
    """
    if not GEMINI_KEY or not image_url:
        return {"value_status": "unavailable", "value_source": "gemini_vision"}

    try:
        img_resp = requests.get(image_url, headers=HEADERS, timeout=15)
        img_resp.raise_for_status()
        img_bytes = img_resp.content
        content_type = img_resp.headers.get("Content-Type","image/jpeg").split(";")[0].strip()
        if content_type not in ("image/jpeg","image/png","image/webp","image/gif"):
            content_type = "image/jpeg"

        from google import genai
        from google.genai import types
        client, model = get_gemini()

        prompt = f"""You are a resale pricing expert analyzing an auction lot image.

Original listing title: "{title}"
Current auction bid: ${current_price:.2f}

Step 1 — Look carefully at the image. Identify EVERY visible item: brands, models, quantities, condition.

Step 2 — Use Google Search to research the resale value of these items on eBay, Amazon, and other marketplaces.

Return ONLY a raw JSON object (no markdown, no backticks):
{{
  "description": "Clear specific description of what is in this lot — 1-2 sentences, mention specific brands/models if visible",
  "items_identified": ["specific item 1 with brand if visible", "item 2", ...],
  "value_used_low": total lot value low end in used condition as number,
  "value_used_high": total lot value high end in used condition as number,
  "value_new_low": total value if items were new as number,
  "value_new_high": total value if items were new high end as number,
  "confidence": "high" or "medium" or "low",
  "notes": "brief note on what drove the valuation"
}}

Be specific. If you see a Milwaukee drill, say Milwaukee drill. Not just "power tool".
All values as numbers only."""

        from google.genai import types
        image_part = types.Part.from_bytes(data=img_bytes, mime_type=content_type)

        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw).strip()
        data = json.loads(raw)

        def safe(v):
            try:
                return round(float(str(v).replace("$","").replace(",","")), 2)
            except Exception:
                return 0.0

        items_list = data.get("items_identified", [])
        items_str  = ", ".join(items_list[:6]) if items_list else ""

        return {
            "ai_description":  str(data.get("description",""))[:500],
            "ai_items":        items_str[:300],
            "ai_confidence":   str(data.get("confidence","low")),
            "value_used_low":  safe(data.get("value_used_low",0)),
            "value_used_high": safe(data.get("value_used_high",0)),
            "value_new_low":   safe(data.get("value_new_low",0)),
            "value_new_high":  safe(data.get("value_new_high",0)),
            "value_status":    "done",
            "value_source":    "gemini_vision",
        }

    except Exception as e:
        print(f"Gemini vision error: {e}")
        # Fall back to text search
        return research_value_gemini(title, current_price)

# ------------------------------------------------------------------ #
#  eBay FINDING API (Production — swap in when PRD key is available)
# ------------------------------------------------------------------ #

def _ebay_search(operation: str, short_title: str, extra_params: dict) -> list[float]:
    """Run one eBay Finding API search and return list of prices."""
    params = {
        "OPERATION-NAME":                operation,
        "SERVICE-VERSION":               "1.0.0",
        "SECURITY-APPNAME":              EBAY_APP_ID,
        "RESPONSE-DATA-FORMAT":          "JSON",
        "keywords":                      short_title,
        "sortOrder":                     "EndTimeSoonest",
        "paginationInput.entriesPerPage": "10",
    }
    params.update(extra_params)
    resp = requests.get(
        "https://svcs.ebay.com/services/search/FindingService/v1",
        params=params, timeout=10
    )
    data = resp.json()
    key  = f"{operation}Response"
    items = (data.get(key, [{}])[0]
                 .get("searchResult", [{}])[0]
                 .get("item", []))
    prices = []
    for item in items:
        try:
            price = float(item["sellingStatus"][0]["currentPrice"][0]["__value__"])
            if price > 0:
                prices.append(price)
        except Exception:
            continue
    return prices

def lookup_ebay_api(title: str) -> dict | None:
    """
    Query the eBay Finding API for BOTH sold/completed AND active listings.
    Combines both datasets to give a realistic value range.
    Returns None if no production key is configured.
    """
    if not EBAY_APP_ID or "SBX" in EBAY_APP_ID:
        return None

    try:
        short_title = " ".join(title.split()[:6])

        # 1. Sold / completed listings (most accurate for value)
        sold_prices = _ebay_search(
            "findCompletedItems", short_title,
            {"itemFilter(0).name": "SoldItemsOnly", "itemFilter(0).value": "true"}
        )

        # 2. Active BIN listings (shows current market ask price)
        active_prices = _ebay_search(
            "findItemsByKeywords", short_title,
            {"itemFilter(0).name": "ListingType", "itemFilter(0).value": "FixedPrice"}
        )

        print(f"  eBay sold prices: {sold_prices}")
        print(f"  eBay active prices: {active_prices}")

        if not sold_prices and not active_prices:
            return None

        all_prices = sold_prices + active_prices

        # Sold prices = realistic value, active prices = asking price
        # Used value based on sold comps, new value based on active listings
        if sold_prices:
            used_low  = round(min(sold_prices), 2)
            used_high = round(max(sold_prices), 2)
        else:
            used_low  = round(min(all_prices) * 0.7, 2)
            used_high = round(max(all_prices) * 0.8, 2)

        if active_prices:
            new_low  = round(min(active_prices), 2)
            new_high = round(max(active_prices), 2)
        else:
            new_low  = round(used_high * 1.2, 2)
            new_high = round(used_high * 1.5, 2)

        return {
            "value_used_low":  used_low,
            "value_used_high": used_high,
            "value_new_low":   new_low,
            "value_new_high":  new_high,
            "value_status":    "done",
            "value_source":    "ebay_api",
            "ai_description":  f"eBay: {len(sold_prices)} sold comps, {len(active_prices)} active listings",
        }
    except Exception as e:
        print(f"eBay API error: {e}")
    return None

# ------------------------------------------------------------------ #
#  PRICE PARSING
# ------------------------------------------------------------------ #

def parse_price(text: str) -> float:
    if not text:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", str(text))
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return 0.0

# ------------------------------------------------------------------ #
#  SCRAPE AUCTION PAGE
# ------------------------------------------------------------------ #

def scrape_auction_page(url: str) -> list[dict]:
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for d in data:
                        items += _parse_jsonld(d)
                elif isinstance(data, dict):
                    items += _parse_jsonld(data)
            except Exception:
                continue

        if items:
            return items

        selectors = [
            "[class*='lot-card']","[class*='item-card']","[class*='auction-item']",
            "[class*='lot-item']","[class*='listing-card']","[class*='product-card']",
            "tr[class*='lot']","tr[class*='item']","article","[class*='result-item']",
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if len(cards) >= 2:
                for card in cards:
                    item = _extract_card_data(card, url)
                    if item.get("title") and item.get("title") != "Unknown":
                        items.append(item)
                if items:
                    break

        if not items:
            items = _generic_extract(soup, url)

    except Exception as e:
        print(f"Scrape error: {e}")

    return items

def _parse_jsonld(data: dict) -> list[dict]:
    items = []
    if data.get("@type") == "ItemList":
        for el in data.get("itemListElement", []):
            item = el.get("item", el)
            items.append({
                "title":         item.get("name","Unknown"),
                "current_price": parse_price(item.get("offers",{}).get("price",0)),
                "time_left":     "",
                "image_url":     item.get("image",""),
                "listing_url":   item.get("url",""),
            })
    elif data.get("@type") in ("Product","Offer"):
        items.append({
            "title":         data.get("name","Unknown"),
            "current_price": parse_price(data.get("offers",{}).get("price",0)),
            "time_left":     "",
            "image_url":     data.get("image",""),
            "listing_url":   data.get("url",""),
        })
    return items

def _extract_card_data(card, base_url: str) -> dict:
    title = ""
    for sel in ["h1","h2","h3","h4","[class*='title']","[class*='name']","a"]:
        el = card.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)[:200]
            break
    price = 0.0
    for sel in ["[class*='price']","[class*='bid']","[class*='amount']","strong","b"]:
        el = card.select_one(sel)
        if el:
            p = parse_price(el.get_text())
            if p > 0:
                price = p
                break
    time_left = ""
    for sel in ["[class*='time']","[class*='countdown']","[class*='ends']","[class*='closes']"]:
        el = card.select_one(sel)
        if el and el.get_text(strip=True):
            time_left = el.get_text(strip=True)[:50]
            break
    image_url = ""
    img = card.find("img")
    if img:
        image_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if image_url and not image_url.startswith("http"):
            from urllib.parse import urljoin
            image_url = urljoin(base_url, image_url)
    listing_url = ""
    a = card.find("a", href=True)
    if a:
        listing_url = a["href"]
        if not listing_url.startswith("http"):
            from urllib.parse import urljoin
            listing_url = urljoin(base_url, listing_url)
    return {
        "title": title or "Unknown",
        "current_price": price,
        "time_left": time_left,
        "image_url": image_url,
        "listing_url": listing_url,
    }

def _generic_extract(soup, base_url: str) -> list[dict]:
    items = []
    price_pattern = re.compile(r'\$[\d,]+(?:\.\d{2})?')
    for el in soup.find_all(text=price_pattern):
        parent = el.parent
        if not parent:
            continue
        container = parent.find_parent(["div","li","tr","article"])
        if not container:
            continue
        price_text = price_pattern.search(str(el))
        price = parse_price(price_text.group()) if price_text else 0.0
        title_el = container.find(["h1","h2","h3","h4","a"])
        title = title_el.get_text(strip=True)[:200] if title_el else "Unknown"
        img = container.find("img")
        image_url = ""
        if img:
            image_url = img.get("src") or img.get("data-src") or ""
            if image_url and not image_url.startswith("http"):
                from urllib.parse import urljoin
                image_url = urljoin(base_url, image_url)
        link = container.find("a", href=True)
        listing_url = ""
        if link:
            listing_url = link["href"]
            if not listing_url.startswith("http"):
                from urllib.parse import urljoin
                listing_url = urljoin(base_url, listing_url)
        if title != "Unknown" and price > 0:
            items.append({
                "title": title, "current_price": price, "time_left": "",
                "image_url": image_url, "listing_url": listing_url,
            })
    return items[:50]

def get_page_count(url: str) -> int:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        nums = []
        for sel in ["[class*='pagination'] a","[class*='pager'] a","nav a"]:
            for a in soup.select(sel):
                t = a.get_text(strip=True)
                if t.isdigit():
                    nums.append(int(t))
        return max(nums) if nums else 1
    except Exception:
        return 1

def get_page_url(base_url: str, page: int) -> str:
    return f"{base_url}?page={page}"

# ------------------------------------------------------------------ #
#  STORE ITEMS
# ------------------------------------------------------------------ #

def scrape_and_store(url: str, session_id: str, pages: list[int]) -> list[str]:
    all_items = []
    for page in pages:
        page_url = url if page == 1 else get_page_url(url, page)
        print(f"Scraping page {page}: {page_url}")
        items = scrape_auction_page(page_url)
        print(f"  Found {len(items)} items")
        all_items.extend(items)
        time.sleep(1)

    inserted_ids = []
    for item in all_items:
        try:
            result = supabase.table("auction_items").insert({
                "session_id":    session_id,
                "source_url":    url,
                "title":         item.get("title","Unknown")[:200],
                "current_price": item.get("current_price",0),
                "time_left":     item.get("time_left","")[:100],
                "image_url":     item.get("image_url","")[:500],
                "listing_url":   item.get("listing_url","")[:500],
                "value_status":  "pending",
                "favorited":     False,
                "scraped_at":    datetime.now().isoformat(),
            }).execute()
            inserted_ids.append(result.data[0]["id"])
        except Exception as e:
            print(f"Insert error: {e}")

    return inserted_ids

# ------------------------------------------------------------------ #
#  ENRICH VALUES — auto-routing, no manual trigger needed
# ------------------------------------------------------------------ #

def enrich_values(item_ids: list[str], progress_callback=None):
    """
    Automatically called after scraping.
    Routes each item to the best analysis method:
      - Poor/mixed lot title + image → Gemini Vision (identifies items + searches web)
      - Clear title → eBay API (if production key set) OR Gemini + Google Search
    """
    total = len(item_ids)
    for idx, item_id in enumerate(item_ids):
        result = supabase.table("auction_items").select(
            "title, image_url, current_price"
        ).eq("id", item_id).execute()

        if not result.data:
            continue

        row           = result.data[0]
        title         = row.get("title","")
        image_url     = row.get("image_url","")
        current_price = float(row.get("current_price",0) or 0)

        if progress_callback:
            progress_callback(idx + 1, total, title)

        poor = is_poor_title(title)

        if poor and image_url:
            # Mixed lot / vague title — use Gemini Vision to see what's actually in it
            print(f"[{idx+1}/{total}] Gemini Vision (lot): {title[:50]}")
            values = analyze_image_gemini(image_url, title, current_price)
        else:
            # Clear title — try eBay API first, fall back to Gemini search
            ebay_result = lookup_ebay_api(title)
            if ebay_result:
                print(f"[{idx+1}/{total}] eBay API: {title[:50]}")
                values = ebay_result
            else:
                print(f"[{idx+1}/{total}] Gemini Search (web): {title[:50]}")
                values = research_value_gemini(title, current_price)
                # If still nothing and there's an image, try vision as last resort
                if values.get("value_status") == "unavailable" and image_url:
                    print(f"  → Falling back to Gemini Vision")
                    values = analyze_image_gemini(image_url, title, current_price)

        # Write results to DB
        update = {
            "value_used_low":  values.get("value_used_low", 0),
            "value_used_high": values.get("value_used_high", 0),
            "value_new_low":   values.get("value_new_low", 0),
            "value_new_high":  values.get("value_new_high", 0),
            "value_status":    values.get("value_status", "unavailable"),
            "value_source":    values.get("value_source", ""),
        }
        if values.get("ai_description"):
            update["ai_description"] = values["ai_description"]
        if values.get("ai_confidence"):
            update["ai_confidence"]  = values["ai_confidence"]

        supabase.table("auction_items").update(update).eq("id", item_id).execute()
        time.sleep(1.5)  # be gentle with APIs
