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
EBAY_APP_ID  = os.getenv("EBAY_APP_ID", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

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
#  PRICE EXTRACTION FROM TEXT
# ------------------------------------------------------------------ #

def extract_prices_from_text(text: str) -> list[float]:
    """Pull all dollar amounts from a block of text."""
    matches = re.findall(r'\$\s*([\d,]+(?:\.\d{1,2})?)', text)
    prices = []
    for m in matches:
        try:
            v = float(m.replace(",", ""))
            if 0.5 < v < 100000:
                prices.append(v)
        except Exception:
            continue
    return prices

def prices_to_range(prices: list[float], condition: str = "used") -> dict:
    """Convert a list of prices into low/high range for used and new."""
    if not prices:
        return {}
    prices_sorted = sorted(prices)
    # Remove outliers (top and bottom 10% if enough data)
    if len(prices_sorted) >= 5:
        cut = max(1, len(prices_sorted) // 10)
        prices_sorted = prices_sorted[cut:-cut]
    low  = round(min(prices_sorted), 2)
    high = round(max(prices_sorted), 2)
    mid  = round(sum(prices_sorted) / len(prices_sorted), 2)
    if condition == "used":
        return {
            "value_used_low":  low,
            "value_used_high": high,
            "value_new_low":   round(high * 1.15, 2),
            "value_new_high":  round(high * 1.5,  2),
        }
    else:
        return {
            "value_used_low":  round(low * 0.6, 2),
            "value_used_high": round(high * 0.75, 2),
            "value_new_low":   low,
            "value_new_high":  high,
        }

# ------------------------------------------------------------------ #
#  STEP 1: GEMINI GOOGLE SEARCH (natural language response)
# ------------------------------------------------------------------ #

def gemini_web_search(query: str) -> str:
    """
    Call Gemini with Google Search grounding.
    Returns the full natural language response text including prices found.
    """
    if not GEMINI_KEY:
        return ""
    try:
        from google.genai import types
        client, model = get_gemini()

        prompt = (
            f"Search the internet and find the current market value of: {query}\n\n"
            f"Search eBay sold listings, eBay active listings, Amazon, Google Shopping, "
            f"industrial supply sites, machinery dealers, and any other relevant marketplace. "
            f"Report all prices you find with their source. Be specific about used vs new pricing."
        )

        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        return response.text or ""
    except Exception as e:
        print(f"Gemini search error: {e}")
        return ""

# ------------------------------------------------------------------ #
#  STEP 2: GEMINI EXTRACT STRUCTURED DATA FROM SEARCH RESULTS
# ------------------------------------------------------------------ #

def gemini_extract_values(title: str, search_text: str, current_price: float) -> dict:
    """
    Given raw search result text, use Gemini to extract structured value estimates.
    This second call does NOT use search — it just reads and parses.
    """
    if not GEMINI_KEY or not search_text:
        return {}
    try:
        from google.genai import types
        client, model = get_gemini()

        prompt = f"""Based on this market research data, extract pricing for: "{title}"
Current auction bid: ${current_price:.2f}

Research data:
{search_text[:3000]}

Return ONLY a raw JSON object, no markdown, no backticks, no extra text:
{{
  "value_used_low": number,
  "value_used_high": number,
  "value_new_low": number,
  "value_new_high": number,
  "notes": "brief note on sources used"
}}

Rules:
- All values must be plain numbers (no $ signs, no commas)
- Use 0 if you cannot determine a value
- Base used pricing on sold/used listings found
- Base new pricing on new retail prices found
- If only one price point found, set low = high * 0.7"""

        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(max_output_tokens=500)
        )

        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw).strip()
        # Sometimes Gemini wraps in extra text — find the JSON block
        json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group()
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
            "notes":           str(data.get("notes", "")),
        }
    except Exception as e:
        print(f"Gemini extract error: {e}")
        return {}

# ------------------------------------------------------------------ #
#  MAIN VALUE RESEARCH (clear titles)
# ------------------------------------------------------------------ #

def research_value_gemini(title: str, current_price: float) -> dict:
    """
    Two-step approach:
    1. Gemini + Google Search → gets natural language with real prices from across the web
    2. Gemini extraction → parses that text into structured low/high values
    Falls back to regex price extraction if step 2 fails.
    """
    print(f"  Searching web for: {title[:60]}")

    # Step 1: Web search
    search_text = gemini_web_search(title)
    if not search_text:
        return {"value_status": "unavailable", "value_source": "gemini_search"}

    print(f"  Got {len(search_text)} chars of search results")

    # Step 2: Extract structured values
    values = gemini_extract_values(title, search_text, current_price)

    if values and (values.get("value_used_high", 0) > 0 or values.get("value_new_high", 0) > 0):
        return {
            **values,
            "ai_description": values.get("notes", ""),
            "value_status":   "done",
            "value_source":   "gemini_search",
        }

    # Fallback: regex extract prices from search text
    print(f"  Falling back to regex price extraction")
    prices = extract_prices_from_text(search_text)
    if prices:
        range_vals = prices_to_range(prices, "used")
        return {
            **range_vals,
            "ai_description": f"Prices found via web search: {', '.join(f'${p:.0f}' for p in sorted(prices)[:5])}",
            "value_status":   "done",
            "value_source":   "gemini_search",
        }

    return {"value_status": "unavailable", "value_source": "gemini_search"}

# ------------------------------------------------------------------ #
#  GEMINI VISION (mixed lots / poor titles)
# ------------------------------------------------------------------ #

def analyze_image_gemini(image_url: str, title: str, current_price: float) -> dict:
    """
    For vague/mixed lot titles: analyze the image with Gemini Vision,
    identify all items, then search the web for their values.
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

        # Step 1: Vision — identify what's in the image
        vision_prompt = f"""Look carefully at this auction lot image. The listing title is: "{title}"

List EVERY item you can see. Be specific — include brands, models, quantities, and condition if visible.
Then search the internet to find the resale value of these items.

Report:
1. What specific items you see
2. Prices found on eBay, Amazon, Google Shopping, and any other marketplace for each item
3. Your total estimated value for the lot

Include all dollar amounts you find."""

        image_part = types.Part.from_bytes(data=img_bytes, mime_type=content_type)
        response = client.models.generate_content(
            model=model,
            contents=[image_part, vision_prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        vision_text = response.text or ""
        print(f"  Vision response: {len(vision_text)} chars")

        # Step 2: Extract structured values from vision text
        values = gemini_extract_values(title, vision_text, current_price)

        # Also try regex fallback
        if not values or values.get("value_used_high", 0) == 0:
            prices = extract_prices_from_text(vision_text)
            if prices:
                values = prices_to_range(prices, "used")

        # Extract item description from vision text (first 2 sentences)
        sentences = [s.strip() for s in vision_text.split('.') if len(s.strip()) > 20]
        description = '. '.join(sentences[:2])[:400] if sentences else ""

        return {
            "ai_description":  description,
            "ai_confidence":   "high" if values.get("value_used_high", 0) > 0 else "low",
            "value_used_low":  values.get("value_used_low", 0),
            "value_used_high": values.get("value_used_high", 0),
            "value_new_low":   values.get("value_new_low", 0),
            "value_new_high":  values.get("value_new_high", 0),
            "value_status":    "done" if values.get("value_used_high", 0) > 0 else "unavailable",
            "value_source":    "gemini_vision",
        }

    except Exception as e:
        print(f"Gemini vision error: {e}")
        # Fall back to text search
        return research_value_gemini(title, current_price)

# ------------------------------------------------------------------ #
#  eBay Finding API (Production only)
# ------------------------------------------------------------------ #

def lookup_ebay_api(title: str) -> dict | None:
    if not EBAY_APP_ID or "SBX" in EBAY_APP_ID:
        return None
    try:
        short_title = " ".join(title.split()[:6])
        resp = requests.get(
            "https://svcs.ebay.com/services/search/FindingService/v1",
            params={
                "OPERATION-NAME":          "findCompletedItems",
                "SERVICE-VERSION":         "1.0.0",
                "SECURITY-APPNAME":        EBAY_APP_ID,
                "RESPONSE-DATA-FORMAT":    "JSON",
                "keywords":                short_title,
                "sortOrder":               "EndTimeSoonest",
                "paginationInput.entriesPerPage": "10",
                "itemFilter(0).name":      "SoldItemsOnly",
                "itemFilter(0).value":     "true",
            },
            timeout=10
        )
        data = resp.json()
        items = (data.get("findCompletedItemsResponse",[{}])[0]
                     .get("searchResult",[{}])[0]
                     .get("item",[]))
        prices = []
        for item in items:
            try:
                price = float(item["sellingStatus"][0]["currentPrice"][0]["__value__"])
                prices.append(price)
            except Exception:
                continue
        if prices:
            range_vals = prices_to_range(prices, "used")
            return {**range_vals, "value_status": "done", "value_source": "ebay_api"}
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
#  SCRAPING
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
        for el in data.get("itemListElement",[]):
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
#  STORE
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
#  ENRICH VALUES
# ------------------------------------------------------------------ #

def enrich_values(item_ids: list[str], progress_callback=None):
    """
    Route each item to best research method:
    - Poor/vague title + image → Gemini Vision (sees what's in the photo, searches web)
    - Clear title → eBay API (if production key) then Gemini web search
    - Gemini web search searches ALL of: eBay, Amazon, Google Shopping,
      industrial suppliers, machinery dealers, and any other marketplace
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
            print(f"[{idx+1}/{total}] Gemini Vision (lot): {title[:50]}")
            values = analyze_image_gemini(image_url, title, current_price)
        else:
            # Try eBay API first (fast, accurate for common items)
            ebay_result = lookup_ebay_api(title)
            if ebay_result and ebay_result.get("value_used_high", 0) > 0:
                print(f"[{idx+1}/{total}] eBay API: {title[:50]}")
                values = ebay_result
            else:
                # Full web search via Gemini — searches ENTIRE internet
                print(f"[{idx+1}/{total}] Gemini web search: {title[:50]}")
                values = research_value_gemini(title, current_price)
                # Last resort: vision if image available
                if values.get("value_status") == "unavailable" and image_url:
                    print(f"  → Falling back to Gemini Vision")
                    values = analyze_image_gemini(image_url, title, current_price)

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
        time.sleep(1)
