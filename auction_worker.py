"""
Auction Worker Service
Runs as a separate Railway worker — watches Supabase for pending auction items
and enriches them with Gemini value research.
Completely isolated from the dashboard so it never affects dashboard speed.
"""
import os
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
POLL_INTERVAL = 30  # seconds between checks

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_pending_items():
    """Get auction items that need value research."""
    try:
        # Only process items from active sessions
        sessions = supabase.table("auction_sessions")\
            .select("session_id")\
            .eq("status", "active")\
            .execute()
        active_ids = [s["session_id"] for s in (sessions.data or [])]
        if not active_ids:
            return []

        result = supabase.table("auction_items")\
            .select("id, title, image_url, current_price, session_id")\
            .eq("value_status", "pending")\
            .in_("session_id", active_ids)\
            .order("scraped_at")\
            .limit(5)\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"Error fetching pending items: {e}")
        return []

def process_item(item):
    """Enrich a single auction item with value research."""
    item_id = item["id"]
    title   = item.get("title", "")
    try:
        from auction_scraper import enrich_values
        enrich_values([item_id])
        print(f"  ✅ Enriched: {title[:50]}")
    except Exception as e:
        print(f"  ❌ Failed: {title[:40]} — {e}")
        # Mark as done to avoid infinite retry loop
        try:
            supabase.table("auction_items").update({
                "value_status": "done",
                "value_source": "error",
            }).eq("id", item_id).execute()
        except Exception:
            pass

def main():
    print("🔨 Auction Worker started")
    print(f"   Polling every {POLL_INTERVAL}s for pending items...")

    while True:
        try:
            pending = get_pending_items()

            if pending:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(pending)} pending items")
                for item in pending:
                    # Check if session is still active before processing each item
                    try:
                        sess = supabase.table("auction_sessions")\
                            .select("status")\
                            .eq("session_id", item["session_id"])\
                            .single()\
                            .execute()
                        if sess.data and sess.data.get("status") != "active":
                            print(f"  ⏭ Skipping — session archived")
                            continue
                    except Exception:
                        pass
                    process_item(item)
                    time.sleep(2)  # small gap between items
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No pending items", end="\r")

        except Exception as e:
            print(f"Worker loop error: {e}")
            traceback.print_exc()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
