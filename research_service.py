import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
SERPAPI_KEY   = "1cd5da20e5f995c7390f7a699d8a00257f502c4c43bd73c8fe92c00bd7e29a4f"
RUN_INTERVAL  = 3600  # seconds between runs (1 hour)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------------ #
#  FETCH ARCHIVED INVENTORY
# ------------------------------------------------------------------ #

def fetch_inventory():
    """Pull all archived and scanned listings to use as research sources."""
    result = (
        supabase.table("listings")
        .select("id, title, price, ebay_category")
        .in_("status", ["scanned", "archived"])
        .execute()
    )
    return result.data or []

# ------------------------------------------------------------------ #
#  SEARCH EBAY VIA SERPAPI
# ------------------------------------------------------------------ #

def search_ebay(query: str, max_price: float) -> list:
    """
    Search eBay for Buy It Now / Best Offer listings at or below max_price.
    Returns list of result dicts.
    """
    try:
        params = {
            "engine":        "ebay",
            "ebay_domain":   "ebay.com",
            "_nkw":          query,
            "LH_BIN":        "1",      # Buy It Now only
            "LH_PrefLoc":    "1",      # US listings
            "_sop":          "15",     # Sort by price + shipping low to high
            "api_key":       SERPAPI_KEY,
        }

        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=15
        )
        data = response.json()

        results = []
        organic = data.get("organic_results", [])

        for item in organic:
            # Price parsing
            price_str = item.get("price", {})
            if isinstance(price_str, dict):
                price_raw = price_str.get("extracted", 0)
            else:
                price_raw = 0

            try:
                price = float(price_raw)
            except (ValueError, TypeError):
                price = 0.0

            # Skip if price is 0 or above our max
            if price <= 0 or price > max_price:
                continue

            # Skip auctions (no Buy It Now)
            listing_type = item.get("type", "").lower()
            if "auction" in listing_type:
                continue

            title   = item.get("title", "")
            link    = item.get("link", "")
            image   = item.get("thumbnail", "")
            condition = item.get("condition", "")

            if not title or not link:
                continue

            results.append({
                "ebay_title":       title,
                "ebay_price":       price,
                "ebay_image_url":   image,
                "ebay_listing_url": link,
                "ebay_condition":   condition,
                "listing_type":     "Buy It Now",
            })

        return results[:10]  # Max 10 results per item

    except Exception as e:
        print(f"   ⚠️  SerpAPI error for '{query}': {e}")
        return []

# ------------------------------------------------------------------ #
#  STORE RESULTS
# ------------------------------------------------------------------ #

def store_results(source_title: str, source_price: float, results: list):
    if not results:
        return

    rows = []
    for r in results:
        rows.append({
            "source_title":     source_title,
            "source_price":     source_price,
            "ebay_title":       r["ebay_title"],
            "ebay_price":       r["ebay_price"],
            "ebay_image_url":   r["ebay_image_url"],
            "ebay_listing_url": r["ebay_listing_url"],
            "ebay_condition":   r["ebay_condition"],
            "listing_type":     r["listing_type"],
            "found_at":         datetime.now().isoformat(),
        })

    try:
        supabase.table("ebay_research").insert(rows).execute()
        print(f"   ✅ Stored {len(rows)} results for '{source_title[:40]}'")
    except Exception as e:
        print(f"   ⚠️  Failed to store results: {e}")

# ------------------------------------------------------------------ #
#  CLEAR OLD RESULTS
# ------------------------------------------------------------------ #

def clear_old_results():
    """Delete all previous research results before each run."""
    try:
        supabase.table("ebay_research").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("🗑️  Cleared old research results")
    except Exception as e:
        print(f"⚠️  Failed to clear old results: {e}")

# ------------------------------------------------------------------ #
#  MAIN LOOP
# ------------------------------------------------------------------ #

print("🔍 eBay Research Service ACTIVE")
print(f"   Runs every {RUN_INTERVAL // 60} minutes")

while True:
    print(f"\n{'='*50}")
    print(f"🕐 Research run starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    inventory = fetch_inventory()
    print(f"📦 Found {len(inventory)} items in inventory to research")

    if inventory:
        clear_old_results()

        for item in inventory:
            title       = item.get("title", "")
            price       = float(item.get("price", 0) or 0)
            category    = item.get("ebay_category", "")

            if not title or price <= 0:
                continue

            # Search with a simplified version of the title (first 6 words)
            short_title = " ".join(title.split()[:6])
            print(f"\n🔎 Searching: {short_title} (max ${price:.2f})")

            results = search_ebay(short_title, price)
            print(f"   Found {len(results)} matching listings")

            store_results(title, price, results)

            # Rate limit — SerpAPI free tier allows ~100/month
            time.sleep(3)

    print(f"\n✅ Research run complete. Next run in {RUN_INTERVAL // 60} minutes.")
    time.sleep(RUN_INTERVAL)
