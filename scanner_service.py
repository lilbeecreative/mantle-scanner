import os
import re
import time
import json
import io
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from google import genai
from google.genai import types
from PIL import Image
from PIL.ExifTags import TAGS

# ------------------------------------------------------------------ #
#  SETUP
# ------------------------------------------------------------------ #

load_dotenv()
url     = os.getenv("SUPABASE_URL")
key     = os.getenv("SUPABASE_KEY")
api_key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")

if not all([url, key, api_key]):
    print(f"❌ ERROR: Missing credentials.")
    exit()

supabase = create_client(url, key)
client   = genai.Client(api_key=api_key)

# ------------------------------------------------------------------ #
#  SEEN FILES — stored in Supabase, persists across Railway restarts
# ------------------------------------------------------------------ #

def load_seen() -> set:
    try:
        result = supabase.table("seen_files").select("filename").execute()
        return {row["filename"] for row in (result.data or [])}
    except Exception as e:
        print(f"⚠️  Could not load seen_files from Supabase: {e}")
        return set()

def mark_seen(filename: str):
    try:
        supabase.table("seen_files").upsert(
            {"filename": filename},
            on_conflict="filename"
        ).execute()
    except Exception as e:
        print(f"⚠️  Could not mark {filename} as seen: {e}")

# ------------------------------------------------------------------ #
#  MODEL PICKER
# ------------------------------------------------------------------ #

def resolve_model():
    print("🔍 Finding best available model...")
    try:
        all_models = [m.name for m in client.models.list()]
        for pref in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]:
            match = next((m for m in all_models if pref in m), None)
            if match:
                print(f"✅ Using model: {match}")
                return match
        if all_models:
            print(f"✅ Using model: {all_models[0]}")
            return all_models[0]
    except Exception as e:
        print(f"⚠️  Model list failed: {e}")
    return "models/gemini-1.5-flash"

model = resolve_model()

# ------------------------------------------------------------------ #
#  EXIF DATE
# ------------------------------------------------------------------ #

def get_exif_date(raw_bytes: bytes):
    try:
        img  = Image.open(io.BytesIO(raw_bytes))
        exif = img._getexif()
        if exif:
            exif_data = {TAGS.get(tag, tag): val for tag, val in exif.items()}
            for field in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
                raw_date = exif_data.get(field)
                if raw_date:
                    try:
                        dt = datetime.strptime(str(raw_date), "%Y:%m:%d %H:%M:%S")
                        return dt, dt.isoformat()
                    except ValueError:
                        continue
    except Exception:
        pass
    dt = datetime.now()
    return dt, dt.isoformat()

# ------------------------------------------------------------------ #
#  IMAGE HELPERS
# ------------------------------------------------------------------ #

def to_jpeg_bytes(raw_bytes: bytes) -> bytes:
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    img = Image.open(io.BytesIO(raw_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()

def build_new_filename(dt: datetime, original_name: str) -> str:
    date_code = dt.strftime("%d%m%y")
    time_code = datetime.now().strftime("%H%M%S")
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".heic"):
        ext = ".jpg"
    return f"{date_code}_{time_code}{ext}"

def rename_in_supabase(raw_bytes: bytes, old_name: str, new_name: str) -> bool:
    try:
        supabase.storage.from_("part-photos").upload(
            path=new_name,
            file=raw_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        supabase.storage.from_("part-photos").remove([old_name])
        print(f"   🔁 Renamed: {old_name} → {new_name}")
        return True
    except Exception as e:
        print(f"   ⚠️  Rename failed: {e}")
        return False

# ------------------------------------------------------------------ #
#  NUMBER PARSING
# ------------------------------------------------------------------ #

def parse_num(val):
    cleaned = re.sub(r"[^0-9.]", "", str(val))
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return 0.00

def parse_int(val):
    cleaned = re.sub(r"[^0-9]", "", str(val))
    try:
        return int(cleaned)
    except ValueError:
        return 0

# ------------------------------------------------------------------ #
#  GEMINI PROMPT
# ------------------------------------------------------------------ #

def make_prompt(photo_count: int, condition: str = "used") -> str:
    return f"""You are a JSON-only resale pricing expert analyzing {photo_count} photo(s) of the same item.

Step 1 — Identify the item. Read any visible text, brand names, model numbers, or part numbers.

Step 2 — Search eBay SOLD listings and find:
- The price range for USED condition sold listings
- The price range for NEW condition sold listings
- If no used listings exist, set used prices to 0
- If no new listings exist, set new prices to 0

The item was marked as condition: {condition} by the employee scanning it.

Return ONLY a raw JSON object, no markdown, no backticks:

{{
  "title": "eBay listing title under 80 characters, keyword-rich",
  "ebay_category": "full eBay category path",
  "ebay_category_id": "numeric eBay category ID only",
  "weight_oz": "estimated weight in ounces as number only",
  "weight_lb": "estimated weight in pounds as number only",
  "price_used_low": "lowest USED sold price as number only, 0 if none found",
  "price_used_high": "highest USED sold price as number only, 0 if none found",
  "price_used": "suggested listing price for USED condition as number only, 0 if none found",
  "price_new_low": "lowest NEW sold price as number only, 0 if none found",
  "price_new_high": "highest NEW sold price as number only, 0 if none found",
  "price_new": "suggested listing price for NEW condition as number only, 0 if none found"
}}

If you cannot identify the item use "Unknown Item" for title and 0 for all numeric fields.
Always search before answering. Never return placeholder text."""

# ------------------------------------------------------------------ #
#  PROCESS A GROUP
# ------------------------------------------------------------------ #

def process_group(group: dict):
    group_id  = group["id"]
    condition = group.get("condition", "used")
    quantity  = group.get("quantity", 1)

    print(f"\n📦 Processing group {group_id} — condition: {condition}, qty: {quantity}")

    supabase.table("listing_groups").update(
        {"status": "processing"}
    ).eq("id", group_id).execute()

    photos_result = (
        supabase.table("group_photos")
        .select("*")
        .eq("group_id", group_id)
        .order("uploaded_at")
        .execute()
    )

    if not photos_result.data:
        print(f"   ⚠️  No photos found for group {group_id}")
        supabase.table("listing_groups").update({"status": "error"}).eq("id", group_id).execute()
        return

    photo_records = photos_result.data
    print(f"   📸 Found {len(photo_records)} photos")

    image_parts  = []
    primary_name = None
    scanned_at   = datetime.now().isoformat()

    for i, record in enumerate(photo_records):
        old_name = record["photo_id"]
        try:
            raw_bytes = supabase.storage.from_("part-photos").download(old_name)
            if i == 0:
                dt, scanned_at = get_exif_date(raw_bytes)
                new_name = build_new_filename(dt, old_name)
            else:
                dt       = datetime.now()
                new_name = build_new_filename(dt, old_name)

            jpeg_bytes = to_jpeg_bytes(raw_bytes)
            renamed    = rename_in_supabase(jpeg_bytes, old_name, new_name)
            final_name = new_name if renamed else old_name

            supabase.table("group_photos").update(
                {"photo_id": final_name}
            ).eq("id", record["id"]).execute()

            if i == 0:
                primary_name = final_name

            image_parts.append(
                types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
            )

            # Mark both old and new names as seen
            mark_seen(old_name)
            mark_seen(final_name)

            time.sleep(1)

        except Exception as e:
            print(f"   ⚠️  Error processing photo {old_name}: {e}")

    if not image_parts:
        print(f"   ⚠️  No images could be processed")
        supabase.table("listing_groups").update({"status": "error"}).eq("id", group_id).execute()
        return

    prompt = make_prompt(len(image_parts), condition)
    print(f"   🤖 Sending {len(image_parts)} photos to Gemini...")

    try:
        response = client.models.generate_content(
            model=model,
            contents=[*image_parts, prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw).strip()

        data             = json.loads(raw)
        title            = str(data.get("title", "Unknown Item")).strip()[:80]
        ebay_category    = str(data.get("ebay_category", "")).strip()
        ebay_category_id = str(parse_int(data.get("ebay_category_id", 0)))
        weight_oz        = parse_num(data.get("weight_oz", 0))
        weight_lb        = parse_num(data.get("weight_lb", 0))
        price_used_low   = parse_num(data.get("price_used_low", 0))
        price_used_high  = parse_num(data.get("price_used_high", 0))
        price_used       = parse_num(data.get("price_used", 0))
        price_new_low    = parse_num(data.get("price_new_low", 0))
        price_new_high   = parse_num(data.get("price_new_high", 0))
        price_new        = parse_num(data.get("price_new", 0))

        if condition == "used":
            active_price = price_used if price_used > 0 else price_new
            active_low   = price_used_low if price_used_low > 0 else price_new_low
            active_high  = price_used_high if price_used_high > 0 else price_new_high
            price_note   = "new" if price_used == 0 and price_new > 0 else ""
        else:
            active_price = price_new if price_new > 0 else price_used
            active_low   = price_new_low if price_new_low > 0 else price_used_low
            active_high  = price_new_high if price_new_high > 0 else price_used_high
            price_note   = "used" if price_new == 0 and price_used > 0 else ""

    except Exception as e:
        print(f"   ⚠️  Gemini error: {e}")
        title, ebay_category, price_note = "Unknown Item", "", ""
        ebay_category_id = "0"
        weight_oz = weight_lb = 0.00
        price_used = price_used_low = price_used_high = 0.00
        price_new  = price_new_low  = price_new_high  = 0.00
        active_price = active_low = active_high = 0.00

    supabase.table("listings").insert({
        "title":            title,
        "ebay_category":    ebay_category,
        "ebay_category_id": ebay_category_id,
        "weight_oz":        weight_oz,
        "weight_lb":        weight_lb,
        "price_low":        active_low,
        "price_high":       active_high,
        "price":            active_price,
        "price_note":       price_note,
        "price_used":       price_used,
        "price_new":        price_new,
        "photo_id":         primary_name,
        "quantity":         quantity,
        "condition":        condition,
        "status":           "scanned",
        "created_at":       scanned_at,
    }).execute()

    supabase.table("listing_groups").update({"status": "done"}).eq("id", group_id).execute()

    print(f"   ✅ {title}")
    print(f"   SKU      : {primary_name}")
    print(f"   Category : {ebay_category} (ID: {ebay_category_id})")
    print(f"   Used     : ${price_used:.2f} / New: ${price_new:.2f}")
    print(f"   Active   : ${active_price:.2f}{' (' + price_note + ')' if price_note else ''}")
    print(f"   Quantity : {quantity}")

# ------------------------------------------------------------------ #
#  LEGACY SINGLE-PHOTO WATCHER
# ------------------------------------------------------------------ #

def process_legacy_photo(file_info):
    old_name = file_info['name']
    print(f"📸 Legacy scan: {old_name}")

    try:
        raw_bytes      = supabase.storage.from_("part-photos").download(old_name)
        dt, scanned_at = get_exif_date(raw_bytes)
        new_name       = build_new_filename(dt, old_name)
        jpeg_bytes     = to_jpeg_bytes(raw_bytes)
        renamed        = rename_in_supabase(jpeg_bytes, old_name, new_name)
        photo_id       = new_name if renamed else old_name

        # Mark both as seen immediately
        mark_seen(old_name)
        mark_seen(photo_id)

        image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
        prompt     = make_prompt(1, "used")

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

        data             = json.loads(raw)
        title            = str(data.get("title", "Unknown Item")).strip()[:80]
        ebay_category    = str(data.get("ebay_category", "")).strip()
        ebay_category_id = str(parse_int(data.get("ebay_category_id", 0)))
        weight_oz        = parse_num(data.get("weight_oz", 0))
        weight_lb        = parse_num(data.get("weight_lb", 0))
        price_used       = parse_num(data.get("price_used", 0))
        price_used_low   = parse_num(data.get("price_used_low", 0))
        price_used_high  = parse_num(data.get("price_used_high", 0))
        price_new        = parse_num(data.get("price_new", 0))
        price_new_low    = parse_num(data.get("price_new_low", 0))
        price_new_high   = parse_num(data.get("price_new_high", 0))

        active_price = price_used if price_used > 0 else price_new
        active_low   = price_used_low if price_used_low > 0 else price_new_low
        active_high  = price_used_high if price_used_high > 0 else price_new_high
        price_note   = "new" if price_used == 0 and price_new > 0 else ""

        supabase.table("listings").insert({
            "title":            title,
            "ebay_category":    ebay_category,
            "ebay_category_id": ebay_category_id,
            "weight_oz":        weight_oz,
            "weight_lb":        weight_lb,
            "price_low":        active_low,
            "price_high":       active_high,
            "price":            active_price,
            "price_note":       price_note,
            "price_used":       price_used,
            "price_new":        price_new,
            "photo_id":         photo_id,
            "condition":        "used",
            "status":           "scanned",
            "created_at":       scanned_at,
        }).execute()

        print(f"   ✅ {title} — used: ${price_used:.2f} / new: ${price_new:.2f}")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

# ------------------------------------------------------------------ #
#  WATCHER LOOP
# ------------------------------------------------------------------ #

print("🕵️  Lister AI ACTIVE... Watching for groups and photos.")
print("📋 Loading seen files from Supabase...")

seen_files = load_seen()
print(f"📋 {len(seen_files)} files already seen.")

# Seed seen_files with everything currently in storage on first run
if len(seen_files) == 0:
    try:
        existing = {f['name'] for f in supabase.storage.from_("part-photos").list()}
        for fname in existing:
            mark_seen(fname)
        seen_files = existing
        print(f"📋 Seeded {len(seen_files)} existing files — watching for new ones only.")
    except Exception as e:
        print(f"⚠️  Could not seed existing files: {e}")

while True:
    try:
        # 1. Reload seen files from Supabase every loop
        seen_files = load_seen()

        # 2. Check for pending groups
        pending = (
            supabase.table("listing_groups")
            .select("*")
            .eq("status", "pending")
            .execute()
        )
        for group in (pending.data or []):
            process_group(group)

        # 3. Check for legacy single photos
        current = supabase.storage.from_("part-photos").list()
        for f in current:
            if f['name'] not in seen_files:
                # Check if this photo belongs to a group
                group_check = (
                    supabase.table("group_photos")
                    .select("id")
                    .eq("photo_id", f['name'])
                    .execute()
                )
                if not group_check.data:
                    process_legacy_photo(f)
                else:
                    # Part of a group — just mark as seen
                    mark_seen(f['name'])

    except Exception as e:
        print(f"⚠️  Connection hiccup: {e}")

    time.sleep(5)
