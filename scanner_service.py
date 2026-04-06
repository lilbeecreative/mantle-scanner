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
#  SETUP & CREDENTIAL CHECK
# ------------------------------------------------------------------ #

load_dotenv()
url     = os.getenv("SUPABASE_URL")
key     = os.getenv("SUPABASE_KEY")
api_key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")

if not all([url, key, api_key]):
    print(f"❌ ERROR: Missing .env credentials. Found: URL({bool(url)}), Key({bool(key)}), Gemini({bool(api_key)})")
    exit()

supabase = create_client(url, key)
client   = genai.Client(api_key=api_key)

SEEN_FILE = "seen_files.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

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
    fallback = "models/gemini-1.5-flash"
    print(f"✅ Using fallback: {fallback}")
    return fallback

model = resolve_model()

# ------------------------------------------------------------------ #
#  EXIF DATE EXTRACTION
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
                        print(f"   📷 EXIF date ({field}): {dt.isoformat()}")
                        return dt, dt.isoformat()
                    except ValueError:
                        continue
    except Exception as e:
        print(f"   ⚠️  EXIF read failed: {e}")

    dt = datetime.now()
    print(f"   ⚠️  No EXIF date — using now: {dt.isoformat()}")
    return dt, dt.isoformat()

# ------------------------------------------------------------------ #
#  FILE RENAMING — DDMMYY_HHMMSS format (always unique)
# ------------------------------------------------------------------ #

def build_new_filename(dt: datetime, original_name: str) -> str:
    """
    Uses date from EXIF + current time for uniqueness.
    Format: DDMMYY_HHMMSS.jpg e.g. 050426_064745.jpg
    """
    date_code  = dt.strftime("%d%m%y")
    time_code  = datetime.now().strftime("%H%M%S")
    ext        = os.path.splitext(original_name)[1].lower()
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
        print(f"   ⚠️  Rename failed ({old_name} → {new_name}): {e}")
        return False

# ------------------------------------------------------------------ #
#  IMAGE CONVERSION
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

# ------------------------------------------------------------------ #
#  GEMINI PROMPT
# ------------------------------------------------------------------ #

PROMPT = """You are a JSON-only industrial parts identifier and resale pricing expert.

Step 1 — Look at this image and identify the item. Read any visible text, part numbers, or brand markings.

Step 2 — Search Google and eBay to find:
- The correct eBay category NAME and its numeric CATEGORY ID
- Realistic resale price range from recent eBay SOLD listings
- Estimated shipping weight

Return ONLY a raw JSON object, no markdown, no backticks, nothing else:

{
  "title": "short descriptive title under 80 characters optimized for eBay search",
  "ebay_category": "full eBay category name path",
  "ebay_category_id": "numeric eBay category ID only, no text",
  "weight_oz": "estimated weight in ounces as a number only",
  "weight_lb": "estimated weight in pounds as a number only",
  "price_low": "lowest recent eBay sold price as a number only, no dollar sign",
  "price_high": "highest recent eBay sold price as a number only, no dollar sign",
  "price": "suggested listing price as a number only, no dollar sign"
}

If you cannot identify the item, use "Unknown Item" for title, "0" for ebay_category_id, and "0" for all numeric fields.
Never return placeholder text. Always search before answering."""


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
#  MAIN PROCESSOR
# ------------------------------------------------------------------ #

def process_new_photo(file_info):
    old_name = file_info['name']
    print(f"📸 New Scan Detected: {old_name}")

    try:
        raw_bytes = supabase.storage.from_("part-photos").download(old_name)

        # Extract EXIF before conversion strips it
        dt, scanned_at = get_exif_date(raw_bytes)

        # Build unique filename
        new_name = build_new_filename(dt, old_name)

        print("🔄 Converting image to JPEG...")
        jpeg_bytes = to_jpeg_bytes(raw_bytes)

        # Rename in Supabase
        renamed  = rename_in_supabase(jpeg_bytes, old_name, new_name)
        photo_id = new_name if renamed else old_name

        # Analyze with Gemini
        image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")

        print("🤖 Analyzing with AI + Google Search...")
        response = client.models.generate_content(
            model=model,
            contents=[image_part, PROMPT],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        raw = response.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw).strip()

        try:
            data             = json.loads(raw)
            title            = str(data.get("title", "Unknown Item")).strip()[:80]
            ebay_category    = str(data.get("ebay_category", "")).strip()
            ebay_category_id = parse_int(data.get("ebay_category_id", 0))
            weight_oz        = parse_num(data.get("weight_oz", 0))
            weight_lb        = parse_num(data.get("weight_lb", 0))
            price_low        = parse_num(data.get("price_low", 0))
            price_high       = parse_num(data.get("price_high", 0))
            price            = parse_num(data.get("price", 0))
        except json.JSONDecodeError:
            print(f"⚠️  JSON parse failed — raw: {raw[:80]}")
            title, ebay_category = "Unknown Item", ""
            ebay_category_id = 0
            weight_oz = weight_lb = price_low = price_high = price = 0.00

        supabase.table("listings").insert({
            "title":            title,
            "ebay_category":    ebay_category,
            "ebay_category_id": ebay_category_id,
            "weight_oz":        weight_oz,
            "weight_lb":        weight_lb,
            "price_low":        price_low,
            "price_high":       price_high,
            "price":            price,
            "photo_id":         photo_id,
            "status":           "scanned",
            "created_at":       scanned_at,
        }).execute()

        print(f"✅ {title}")
        print(f"   SKU      : {photo_id}")
        print(f"   Category : {ebay_category} (ID: {ebay_category_id})")
        print(f"   Weight   : {weight_oz:.1f}oz / {weight_lb:.2f}lb")
        print(f"   Price    : ${price_low:.2f}–${price_high:.2f} → ${price:.2f}")
        print(f"   Scanned  : {scanned_at}")

    except Exception as e:
        print(f"⚠️  Error processing {old_name}: {e}")

# ------------------------------------------------------------------ #
#  WATCHER LOOP
# ------------------------------------------------------------------ #

print("🕵️  Lister AI ACTIVE... Watching Supabase.")
seen_files = load_seen()

existing = {f['name'] for f in supabase.storage.from_("part-photos").list()}
if not seen_files:
    seen_files = existing
    save_seen(seen_files)
    print(f"📋 Found {len(seen_files)} existing files — watching for new ones only.")

while True:
    try:
        current = supabase.storage.from_("part-photos").list()
        for f in current:
            if f['name'] not in seen_files:
                process_new_photo(f)
                seen_files.add(f['name'])
                save_seen(seen_files)
    except Exception as e:
        print(f"⚠️  Connection hiccup: {e}")
    time.sleep(5)
