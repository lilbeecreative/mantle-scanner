import streamlit as st
import pandas as pd
import os
import csv
import io
import uuid
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ------------------------------------------------------------------ #
#  EBAY CATEGORIES
# ------------------------------------------------------------------ #

EBAY_CATEGORIES = [
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > End Mills", "125814"),
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > Drill Bits", "11804"),
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > Taps & Dies", "11803"),
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > Reamers", "11802"),
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > Inserts", "125817"),
    ("Business & Industrial > CNC, Metalworking > Cutting Tools > Tool Holders", "125818"),
    ("Business & Industrial > CNC, Metalworking > Lathes", "12584"),
    ("Business & Industrial > CNC, Metalworking > Milling Machines", "12576"),
    ("Business & Industrial > CNC, Metalworking > Grinding Machines", "12578"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Pumps", "26241"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Cylinders", "26244"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Valves", "26246"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Fittings & Adapters", "26247"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Hoses & Tubing", "26248"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Motors", "26242"),
    ("Business & Industrial > Hydraulics, Pneumatics > Hydraulic Filters", "26249"),
    ("Business & Industrial > Hydraulics, Pneumatics > Pneumatic Cylinders", "26260"),
    ("Business & Industrial > Hydraulics, Pneumatics > Pneumatic Valves", "26261"),
    ("Business & Industrial > Hydraulics, Pneumatics > Air Compressors", "26264"),
    ("Business & Industrial > Electrical Equipment > Electric Motors", "26215"),
    ("Business & Industrial > Electrical Equipment > Generators", "26216"),
    ("Business & Industrial > Electrical Equipment > Transformers", "26220"),
    ("Business & Industrial > Electrical Equipment > Switches & Relays", "26222"),
    ("Business & Industrial > Electrical Equipment > Control Panels", "26219"),
    ("Business & Industrial > Industrial Automation > PLCs & HMIs", "32834"),
    ("Business & Industrial > Industrial Automation > Sensors & Switches", "32835"),
    ("Business & Industrial > Industrial Automation > Servo Drives", "32836"),
    ("Business & Industrial > Industrial Automation > VFDs & Inverters", "32837"),
    ("Business & Industrial > Heavy Equipment Parts > Excavator Parts", "26449"),
    ("Business & Industrial > Heavy Equipment Parts > Bulldozer Parts", "26450"),
    ("Business & Industrial > Heavy Equipment Parts > Forklift Parts", "26451"),
    ("Business & Industrial > Heavy Equipment Parts > Crane Parts", "26452"),
    ("Business & Industrial > Heavy Equipment Parts > Loader Parts", "26453"),
    ("Business & Industrial > MRO & Industrial Supply > Bearings", "26279"),
    ("Business & Industrial > MRO & Industrial Supply > Seals & O-Rings", "26280"),
    ("Business & Industrial > MRO & Industrial Supply > Fasteners & Hardware", "26278"),
    ("Business & Industrial > MRO & Industrial Supply > Gears & Gearboxes", "26281"),
    ("Business & Industrial > MRO & Industrial Supply > Pulleys & Belts", "26282"),
    ("Business & Industrial > MRO & Industrial Supply > Couplings", "26283"),
    ("Business & Industrial > Test Equipment > Pressure Gauges", "4673"),
    ("Business & Industrial > Test Equipment > Flow Meters", "4674"),
    ("Business & Industrial > Test Equipment > Multimeters", "4675"),
    ("Business & Industrial > Pumps > Centrifugal Pumps", "26236"),
    ("Business & Industrial > Pumps > Gear Pumps", "26238"),
    ("Business & Industrial > Pumps > Diaphragm Pumps", "26237"),
    ("Business & Industrial > Pumps > Submersible Pumps", "26239"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Engines & Components", "6030"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Transmission & Drivetrain", "6025"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Brakes & Brake Parts", "33554"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Suspension & Steering", "33558"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Exhaust & Emissions", "6029"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Electrical & Lights", "33596"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > A/C & Heating", "33545"),
    ("eBay Motors > Parts & Accessories > Car & Truck Parts > Fuel System", "6033"),
    ("eBay Motors > Parts & Accessories > Commercial Trucks > Truck Parts", "38634"),
    ("eBay Motors > Parts & Accessories > Commercial Trucks > Semi Truck Parts", "38635"),
    ("Home & Garden > Tools & Workshop Equipment > Power Tools", "631"),
    ("Home & Garden > Tools & Workshop Equipment > Hand Tools", "632"),
    ("Home & Garden > Tools & Workshop Equipment > Welding & Soldering", "26231"),
    ("Home & Garden > Tools & Workshop Equipment > Air Tools & Air Compressors", "25999"),
    ("Home & Garden > Tools & Workshop Equipment > Measuring & Layout Tools", "42281"),
    ("Consumer Electronics > Computers & Tablets", "58058"),
    ("Consumer Electronics > TV, Video & Home Audio", "32852"),
    ("Consumer Electronics > Cell Phones & Accessories", "15032"),
    ("Collectibles > Tools, Hardware & Locks", "4706"),
    ("Home & Garden > Kitchen & Dining", "20625"),
    ("Clothing, Shoes & Accessories > Men > Clothing", "1059"),
    ("Clothing, Shoes & Accessories > Women > Clothing", "15724"),
]

CATEGORY_LABELS = [f"{name}  [{cat_id}]" for name, cat_id in EBAY_CATEGORIES]
LABEL_TO_ID     = {f"{name}  [{cat_id}]": cat_id for name, cat_id in EBAY_CATEGORIES}
LABEL_TO_NAME   = {f"{name}  [{cat_id}]": name   for name, cat_id in EBAY_CATEGORIES}
ID_TO_LABEL     = {cat_id: f"{name}  [{cat_id}]" for name, cat_id in EBAY_CATEGORIES}

def find_best_label(category: str, cat_id: str) -> str | None:
    clean_id = str(cat_id).strip().replace(".0", "") if cat_id else ""
    if clean_id and clean_id in ID_TO_LABEL:
        return ID_TO_LABEL[clean_id]
    if category:
        keywords = [k.strip().lower() for k in category.replace(">", " ").split() if len(k.strip()) > 3]
        best_label, best_score = None, 0
        for label in CATEGORY_LABELS:
            score = sum(1 for kw in keywords if kw in label.lower())
            if score > best_score:
                best_score = score
                best_label = label
        if best_score >= 2:
            return best_label
    return None

# ------------------------------------------------------------------ #
#  SETUP
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Lister AI",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .stApp { background-color: #f1f5f9; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    hr { border-color: #e2e8f0 !important; margin: 0.75rem 0; }

    [data-testid="stTextInput"] input {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #0f172a !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        padding: 4px 8px !important;
        height: 34px !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
        outline: none !important;
    }
    [data-testid="stNumberInput"] input {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #0f172a !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        height: 34px !important;
    }
    [data-testid="stSelectbox"] > div > div {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #0f172a !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        min-height: 34px !important;
    }
    [data-testid="baseButton-secondary"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #374151 !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
    }
    [data-testid="baseButton-secondary"]:hover {
        background: #f8fafc !important;
        border-color: #94a3b8 !important;
    }
    [data-testid="baseButton-primary"] {
        background: #3b82f6 !important;
        border: none !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
    }
    [data-testid="stExpander"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
    }
    [data-testid="stAlert"] {
        background: #fef2f2 !important;
        border: 1px solid #fecaca !important;
        border-radius: 8px !important;
        color: #991b1b !important;
    }
    [data-testid="baseButton-download"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #2563eb !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
    }
    [data-testid="stFileUploader"] {
        background: #ffffff !important;
        border: 2px dashed #93c5fd !important;
        border-radius: 10px !important;
    }
    [data-testid="stCameraInput"] {
        border-radius: 12px !important;
        overflow: hidden;
    }

    /* Tab color coding */
    .tab-dashboard [data-testid="baseButton-primary"] { background: #2563eb !important; }
    .tab-camera    [data-testid="baseButton-primary"] { background: #ea580c !important; }
    .tab-batch     [data-testid="baseButton-primary"] { background: #0891b2 !important; }
    .tab-research  [data-testid="baseButton-primary"] { background: #7c3aed !important; }
    .tab-auction   [data-testid="baseButton-primary"] { background: #b45309 !important; }

    .field-label {
        color: #64748b;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 3px;
        font-weight: 600;
    }
    .batch-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.65rem 0.9rem;
        margin-bottom: 0.4rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .batch-card.active { border-left: 4px solid #ea580c; background: #fff7ed; }
    .batch-card.processing { border-left: 4px solid #d97706; background: #fffbeb; }
    .batch-card.done { border-left: 4px solid #16a34a; background: #f0fdf4; }
    .status-pill {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 20px;
        font-size: 0.62rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .pill-active { background: #fed7aa; color: #9a3412; }
    .pill-processing { background: #fde68a; color: #92400e; }
    .pill-done { background: #bbf7d0; color: #166534; }
    .section-label {
        color: #94a3b8;
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        margin-bottom: 0.6rem;
    }
    .page-content { padding: 0.85rem 1.5rem; max-width: 1400px; margin: 0 auto; }
    .mode-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 1.5rem 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase       = get_supabase()
SUPABASE_URL    = os.getenv("SUPABASE_URL")
RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
NOTIFY_EMAIL    = "sebastian@lilbeecreative.com"
EBAY_APP_ID_ENV = os.getenv("EBAY_APP_ID", "")
EBAY_DEV_ID     = os.getenv("EBAY_DEV_ID", "")
EBAY_CERT_ID    = os.getenv("EBAY_CERT_ID", "")
EBAY_USER_TOKEN = os.getenv("EBAY_USER_TOKEN", "")

ARCHIVE_FILE    = "mantle_archive.csv"
ARCHIVE_HEADERS = [
    "batch_cleared_at", "id", "photo_id", "title", "ebay_category",
    "ebay_category_id", "weight_oz", "weight_lb", "price_low", "price_high",
    "price", "price_note", "price_used", "price_new", "condition",
    "quantity", "status", "created_at"
]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
if "ebay_selected" not in st.session_state:
    st.session_state.ebay_selected = {}
if "ebay_submitting" not in st.session_state:
    st.session_state.ebay_submitting = False

# ------------------------------------------------------------------ #
#  HELPERS
# ------------------------------------------------------------------ #

def send_issue_email(description: str, submitted_at: str):
    if not RESEND_API_KEY:
        return
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from":    "Lister AI <onboarding@resend.dev>",
                "to":      [NOTIFY_EMAIL],
                "subject": "New Issue Submitted — Lister AI",
                "html":    f"<h2>New Issue</h2><p>{description}</p>",
            }
        )
    except Exception:
        pass

def append_to_archive(df: pd.DataFrame):
    file_exists = os.path.exists(ARCHIVE_FILE)
    cleared_at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ARCHIVE_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ARCHIVE_HEADERS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for _, row in df.iterrows():
            record = row.to_dict()
            record["batch_cleared_at"] = cleared_at
            if "created_at" in record and hasattr(record["created_at"], "isoformat"):
                record["created_at"] = record["created_at"].isoformat()
            writer.writerow(record)

def photo_url(photo_id: str) -> str:
    if not photo_id or str(photo_id) in ("0", "", "nan"):
        return ""
    return f"{SUPABASE_URL}/storage/v1/object/public/part-photos/{photo_id}"

# ------------------------------------------------------------------ #
#  eBay TRADING API — SUBMIT LISTING AS DRAFT (SCHEDULED)
# ------------------------------------------------------------------ #

EBAY_DESCRIPTION_TEMPLATE = """Shipped primarily with UPS and sometimes USPS. If you have special packing or shipping needs, please send a message.

This item is sold in "as-is" condition. The seller assumes no liability for the use, operation, or installation of this product. Due to the technical nature of this equipment, the buyer is responsible for having the item professionally inspected and installed by a certified technician prior to use."""

def submit_to_ebay(item: dict) -> dict:
    """
    Submit a listing to eBay as a scheduled draft (29 days out).
    Returns: {"success": True, "item_id": "..."} or {"success": False, "error": "..."}
    """
    import xml.etree.ElementTree as ET
    from datetime import timezone, timedelta

    if not EBAY_USER_TOKEN:
        return {"success": False, "error": "EBAY_USER_TOKEN not configured in Railway Variables"}

    # Build photo URL
    photo_id   = item.get("photo_id", "")
    photo_url  = f"{SUPABASE_URL}/storage/v1/object/public/part-photos/{photo_id}" if photo_id else ""

    # Condition ID
    condition  = item.get("condition", "used").lower()
    cond_id    = "1000" if condition == "new" else "3000"

    # Category
    cat_id     = str(item.get("ebay_category_id", "")).strip().replace(".0","") or "99"

    # Price
    price      = float(item.get("price", 0) or 0)
    if price <= 0:
        return {"success": False, "error": "Price must be greater than 0"}

    # Title — eBay max 80 chars
    title      = str(item.get("title", "")).strip()[:80]
    if not title:
        return {"success": False, "error": "Title is empty"}

    # Quantity
    quantity   = int(item.get("quantity", 1) or 1)

    # Schedule 29 days from now (appears as draft in Seller Hub)
    schedule_time = (datetime.now(timezone.utc) + timedelta(days=29)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Full description
    item_desc  = item.get("description", "") or ""
    full_desc  = (f"{item_desc}\n\n{EBAY_DESCRIPTION_TEMPLATE}".strip()
                   if item_desc else EBAY_DESCRIPTION_TEMPLATE)

    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<AddItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{EBAY_USER_TOKEN}</eBayAuthToken>
  </RequesterCredentials>
  <Item>
    <Title>{title}</Title>
    <Description><![CDATA[{full_desc}]]></Description>
    <PrimaryCategory>
      <CategoryID>{cat_id}</CategoryID>
    </PrimaryCategory>
    <StartPrice>{price:.2f}</StartPrice>
    <ConditionID>{cond_id}</ConditionID>
    <Country>US</Country>
    <Currency>USD</Currency>
    <DispatchTimeMax>3</DispatchTimeMax>
    <ListingDuration>GTC</ListingDuration>
    <ListingType>FixedPriceItem</ListingType>
    <Location>Loveland, CO</Location>
    <PostalCode>80537</PostalCode>
    <Quantity>{quantity}</Quantity>
    <BestOfferDetails>
      <BestOfferEnabled>true</BestOfferEnabled>
    </BestOfferDetails>
    <ReturnPolicy>
      <ReturnsAcceptedOption>ReturnsNotAccepted</ReturnsAcceptedOption>
    </ReturnPolicy>
    {f"<PictureDetails><PictureURL>{photo_url}</PictureURL></PictureDetails>" if photo_url else ""}
    <ScheduleTime>{schedule_time}</ScheduleTime>
    <SKU></SKU>
  </Item>
</AddItemRequest>"""

    headers = {
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-DEV-NAME":   EBAY_DEV_ID,
        "X-EBAY-API-APP-NAME":   EBAY_APP_ID_ENV,
        "X-EBAY-API-CERT-NAME":  EBAY_CERT_ID,
        "X-EBAY-API-CALL-NAME":  "AddItem",
        "X-EBAY-API-SITEID":     "0",
        "Content-Type":          "text/xml",
    }

    try:
        import requests as req
        resp = req.post(
            "https://api.ebay.com/ws/api.dll",
            data=xml_body.encode("utf-8"),
            headers=headers,
            timeout=20
        )
        root = ET.fromstring(resp.text)
        ns   = {"e": "urn:ebay:apis:eBLBaseComponents"}

        ack = root.findtext("e:Ack", namespaces=ns) or ""
        if ack in ("Success", "Warning"):
            item_id = root.findtext("e:ItemID", namespaces=ns) or ""
            return {"success": True, "item_id": item_id}
        else:
            errors = root.findall(".//e:Error", ns)
            msgs   = [e.findtext("e:ShortMessage", namespaces=ns) or "" for e in errors]
            return {"success": False, "error": " | ".join(msgs) or "Unknown eBay error"}

    except Exception as e:
        return {"success": False, "error": str(e)}

def update_field(item_id: str, field: str, value):
    try:
        supabase.table("listings").update({field: value}).eq("id", item_id).execute()
    except Exception as e:
        st.error(f"Failed to update {field}: {e}")

def switch_condition(item_id: str, new_cond: str, price_used: float, price_new: float):
    """Switch condition and update price if we have both stored values."""
    if price_used == 0 and price_new == 0:
        # No dual pricing available (legacy item) — just update condition label
        supabase.table("listings").update({"condition": new_cond}).eq("id", item_id).execute()
        return False  # Signal that price wasn't updated
    if new_cond == "used":
        active = price_used if price_used > 0 else price_new
        note   = "new" if price_used == 0 and price_new > 0 else ""
    else:
        active = price_new if price_new > 0 else price_used
        note   = "used" if price_new == 0 and price_used > 0 else ""
    supabase.table("listings").update({
        "condition": new_cond, "price": active, "price_note": note,
    }).eq("id", item_id).execute()
    return True  # Price was updated

def build_ebay_csv(df: pd.DataFrame) -> bytes:
    output = io.StringIO()
    output.write('#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,\n')
    output.write('#INFO Action and Category ID are required fields.,,,,,,,,,,\n')
    output.write('#INFO After you\'ve successfully uploaded your draft complete your drafts here: https://www.ebay.com/sh/lst/drafts,,,,,,,,,,\n')
    output.write('#INFO,,,,,,,,,,\n')
    output.write('Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8),Custom label (SKU),Category ID,Title,UPC,Price,Quantity,Item photo URL,Condition ID,Description,Format\n')
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    for _, row in df.iterrows():
        sku            = str(row.get("photo_id", "")).rsplit(".", 1)[0]
        category_id    = str(row.get("ebay_category_id", "")).replace(".0", "")
        title          = str(row.get("title", ""))[:80]
        price          = f"{float(row.get('price', 0)):.2f}"
        quantity       = str(int(row.get("quantity", 0)))
        pic_url        = photo_url(str(row.get("photo_id", "")))
        condition      = str(row.get("condition", "used")).strip().lower()
        ebay_condition = "1000" if condition == "new" else "3000"
        writer.writerow(["Draft", sku, category_id, title, "", price, quantity, pic_url, ebay_condition, "", "FixedPrice"])
    return output.getvalue().encode("utf-8")

# ------------------------------------------------------------------ #
#  DATA FETCH
# ------------------------------------------------------------------ #

@st.cache_data(ttl=30)
def fetch_listings():
    result = (
        supabase.table("listings")
        .select("*")
        .eq("status", "scanned")
        .order("created_at", desc=True)
        .execute()
    )
    if not result.data:
        return pd.DataFrame()
    df = pd.DataFrame(result.data)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    for col in ["price", "price_low", "price_high", "weight_oz", "weight_lb", "price_used", "price_new"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    if "quantity" not in df.columns:
        df["quantity"] = 0
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    for col in ["price_note", "condition", "ebay_category", "ebay_category_id"]:
        if col not in df.columns:
            df[col] = ""
    df["price_note"]       = df["price_note"].fillna("")
    df["condition"]        = df["condition"].fillna("used")
    df["ebay_category"]    = df["ebay_category"].fillna("")
    df["ebay_category_id"] = df["ebay_category_id"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    if "price_used" not in df.columns:
        df["price_used"] = 0.0
    if "price_new" not in df.columns:
        df["price_new"] = 0.0
    return df

@st.cache_data(ttl=30)
def fetch_issues():
    result = supabase.table("issues").select("*").order("submitted_at", desc=True).execute()
    if not result.data:
        return pd.DataFrame()
    df = pd.DataFrame(result.data)
    if "submitted_at" in df.columns:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce", utc=True)
    return df

# ------------------------------------------------------------------ #
#  TOOLBAR
# ------------------------------------------------------------------ #

df_top = fetch_listings()

# Logo bar
st.markdown("""
<div style='background:#ffffff; border-bottom:1px solid #e2e8f0; padding:0 1.5rem;
display:flex; align-items:center; justify-content:space-between; height:50px;
box-shadow: 0 1px 4px rgba(0,0,0,0.06);'>
    <div style='color:#0f172a; font-size:1rem; font-weight:700; letter-spacing:-0.02em;
    display:flex; align-items:center; gap:8px;'>
        <div style='width:8px; height:8px; background:#2563eb; border-radius:50%;'></div>
        Lister AI
    </div>
    <div style='color:#94a3b8; font-size:0.68rem; letter-spacing:0.08em; font-weight:500;'>EMPLOYEE DASHBOARD</div>
</div>
""", unsafe_allow_html=True)

# Color-coded nav toolbar — separated from page content
st.markdown("<div style='background:#f8fafc; border-bottom:1px solid #e2e8f0; padding:4px 8px;'>", unsafe_allow_html=True)
t1, t2, t3, t4, t5, t6 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5])
with t1:
    st.markdown("<div class='tab-dashboard'>", unsafe_allow_html=True)
    if st.button("📊  Batch Dashboard", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "dashboard" else "secondary"):
        st.session_state.active_tab = "dashboard"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t2:
    st.markdown("<div class='tab-camera'>", unsafe_allow_html=True)
    if st.button("📸  Scan New Items", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "camera" else "secondary"):
        st.session_state.active_tab = "camera"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t3:
    st.markdown("<div class='tab-batch'>", unsafe_allow_html=True)
    if st.button("📁  Batch Upload", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "batch" else "secondary"):
        st.session_state.active_tab = "batch"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t4:
    st.markdown("<div class='tab-research'>", unsafe_allow_html=True)
    if st.button("🔍  Research", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "research" else "secondary"):
        st.session_state.active_tab = "research"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t5:
    st.markdown("<div class='tab-auction'>", unsafe_allow_html=True)
    if st.button("🔨  Auction Scanner", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "auction" else "secondary"):
        st.session_state.active_tab = "auction"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
# ================================================================== #
#  TAB: CAMERA SCAN
# ================================================================== #

if st.session_state.active_tab == "camera":

    from PIL import Image, ExifTags
    import io as _io

    def fix_rotation(img_bytes):
        try:
            img = Image.open(_io.BytesIO(img_bytes))
            exif = img._getexif()
            if exif:
                ok = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
                if ok and ok in exif:
                    rot = {3:180, 6:270, 8:90}.get(exif[ok])
                    if rot:
                        img = img.rotate(rot, expand=True)
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        except Exception:
            return img_bytes

    def cam_upload(img_bytes, group_id, idx):
        fixed = fix_rotation(img_bytes)
        dt = datetime.now()
        fn = f"{dt.strftime('%d%m%y')}_{dt.strftime('%H%M%S')}_{idx}.jpg"
        supabase.storage.from_("part-photos").upload(path=fn, file=fixed, file_options={"content-type":"image/jpeg","upsert":"true"})
        supabase.table("group_photos").insert({"group_id":group_id,"photo_id":fn}).execute()

    for k,v in [("cam_batch_id",None),("cam_condition","used"),("cam_items",[]),("cam_group_id",None),("cam_photos",[]),("cam_qty",1)]:
        if k not in st.session_state: st.session_state[k] = v

    if st.session_state.cam_batch_id is None:
        st.markdown("""
        <div style='text-align:center; padding:2rem 0 1rem;'>
            <div style='font-size:2.5rem; margin-bottom:0.5rem;'>📸</div>
            <div style='color:#111827; font-size:1.1rem; font-weight:600;'>Camera Scan</div>
            <div style='color:#4a4a5a; font-size:0.82rem; margin-top:0.3rem;'>Take up to 10 photos per item</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div class='field-label' style='text-align:center;'>Condition for this Batch</div>", unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            if st.button("✓  Used" if st.session_state.cam_condition=="used" else "Used", use_container_width=True, key="cam_cond_used", type="primary" if st.session_state.cam_condition=="used" else "secondary"):
                st.session_state.cam_condition = "used"; st.rerun()
        with cb:
            if st.button("✓  New" if st.session_state.cam_condition=="new" else "New", use_container_width=True, key="cam_cond_new", type="primary" if st.session_state.cam_condition=="new" else "secondary"):
                st.session_state.cam_condition = "new"; st.rerun()
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        if st.button("🚀  Start Camera Batch", use_container_width=True, type="primary", key="start_cam_batch"):
            batch_id = str(uuid.uuid4())
            st.session_state.cam_batch_id = batch_id
            st.session_state.cam_items    = []
            st.session_state.cam_photos   = []
            st.session_state.cam_qty      = 1
            # Auto-create first item group so camera opens immediately
            result = supabase.table("listing_groups").insert({
                "session_id": batch_id,
                "status":     "waiting",
                "quantity":   1,
                "condition":  st.session_state.cam_condition,
            }).execute()
            st.session_state.cam_group_id = result.data[0]["id"]
            st.rerun()
    else:
        total_cam = len(st.session_state.cam_items)
        cond_color = "#22c55e" if st.session_state.cam_condition=="new" else "#2196F3"
        st.markdown(f"""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid {cond_color};
        border-radius:10px; padding:0.65rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span style='color:#111827; font-size:0.9rem; font-weight:600;'>Camera Batch</span>
                <span style='color:#4a4a5a; font-size:0.72rem; margin-left:10px;'>
                    {total_cam} items · <span style='color:{cond_color};'>{st.session_state.cam_condition.title()}</span>
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.cam_group_id is None:
            if st.session_state.cam_items:
                st.markdown("<div class='section-label'>Items scanned</div>", unsafe_allow_html=True)
                for i, item in enumerate(reversed(st.session_state.cam_items)):
                    idx = total_cam - i
                    st.markdown(f"""<div class='batch-card processing'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div><span style='color:#0f172a; font-size:0.82rem; font-weight:500;'>Item {idx}</span>
                            <span style='color:#4a4a5a; font-size:0.7rem; margin-left:8px;'>{item.get("photo_count",0)} photos · Qty {item.get("qty",1)}</span></div>
                            <span class='status-pill pill-processing'>Processing...</span>
                        </div></div>""", unsafe_allow_html=True)
                st.divider()
            b1, b2, b3 = st.columns([2,2,1])
            with b1:
                if st.button("📸  Scan Next Item", use_container_width=True, type="primary"):
                    result = supabase.table("listing_groups").insert({"session_id":st.session_state.cam_batch_id,"status":"waiting","quantity":1,"condition":st.session_state.cam_condition}).execute()
                    st.session_state.cam_group_id = result.data[0]["id"]
                    st.session_state.cam_photos = []; st.session_state.cam_qty = 1; st.rerun()
            with b2:
                if st.button("🏁  End Batch", use_container_width=True, type="secondary"):
                    st.session_state.cam_batch_id = None; st.session_state.cam_items = []
                    st.session_state.cam_group_id = None; st.session_state.cam_photos = []
                    st.cache_data.clear(); st.rerun()
            with b3:
                if st.button("✗  Cancel", use_container_width=True, type="secondary"):
                    st.session_state.cam_batch_id = None; st.session_state.cam_items = []
                    st.session_state.cam_group_id = None; st.session_state.cam_photos = []; st.rerun()
        else:
            item_num = total_cam + 1
            photo_count = len(st.session_state.cam_photos)
            remaining = 10 - photo_count
            st.markdown(f"""
            <div style='background:#eff6ff; border:1.5px solid #3b82f6; border-radius:12px;
            padding:0.75rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
                <span style='color:#111827; font-size:0.9rem; font-weight:600;'>Item {item_num}</span>
                <span style='color:#60b4ff; font-size:0.82rem; font-weight:500;'>{photo_count}/10 photos</span>
            </div>""", unsafe_allow_html=True)
            if st.session_state.cam_photos:
                tc = st.columns(min(len(st.session_state.cam_photos),5))
                for col, pb in zip(tc, st.session_state.cam_photos):
                    with col: st.image(pb, use_container_width=True)
            if remaining > 0:
                st.markdown(f"<div style='color:#4a4a5a; font-size:0.72rem; margin-bottom:4px;'>Photo {photo_count+1} of up to 10</div>", unsafe_allow_html=True)
                cam_img = st.camera_input("Take photo", label_visibility="collapsed", key=f"cam_{st.session_state.cam_group_id}_{photo_count}")
                if cam_img:
                    st.session_state.cam_photos.append(cam_img.read()); st.rerun()
            else:
                st.success("Maximum 10 photos — tap Done to process.")
            st.markdown("<div class='field-label' style='margin-top:0.75rem;'>Quantity</div>", unsafe_allow_html=True)
            qq1,qq2,qq3 = st.columns([1,2,1])
            with qq1:
                if st.button("−", key="cam_minus", use_container_width=True):
                    if st.session_state.cam_qty > 1: st.session_state.cam_qty -= 1; st.rerun()
            with qq2:
                st.markdown(f"<div style='text-align:center; font-size:1.3rem; font-weight:700; color:#fff; padding-top:3px;'>{st.session_state.cam_qty}</div>", unsafe_allow_html=True)
            with qq3:
                if st.button("+", key="cam_plus", use_container_width=True):
                    st.session_state.cam_qty += 1; st.rerun()
            da, db = st.columns([3,1])
            with da:
                done_disabled = len(st.session_state.cam_photos) == 0
                if st.button("✓  Done — Send to Scanner" if not done_disabled else "Take at least one photo", use_container_width=True, type="primary", disabled=done_disabled):
                    with st.spinner("Uploading..."):
                        group_id = st.session_state.cam_group_id; uploaded = 0
                        for i, pb in enumerate(st.session_state.cam_photos):
                            try: cam_upload(pb, group_id, i); uploaded += 1
                            except Exception as e: st.error(f"Photo {i+1} failed: {e}")
                        supabase.table("listing_groups").update({"condition":st.session_state.cam_condition,"quantity":st.session_state.cam_qty,"status":"pending"}).eq("id",group_id).execute()
                        st.session_state.cam_items.append({"group_id":group_id,"condition":st.session_state.cam_condition,"qty":st.session_state.cam_qty,"status":"pending","photo_count":uploaded})
                        st.session_state.cam_group_id = None; st.session_state.cam_photos = []; st.session_state.cam_qty = 1
                        st.cache_data.clear(); st.rerun()
            with db:
                if st.button("✗  Cancel Item", use_container_width=True, type="secondary"):
                    try: supabase.table("listing_groups").delete().eq("id",st.session_state.cam_group_id).execute()
                    except: pass
                    st.session_state.cam_group_id = None; st.session_state.cam_photos = []; st.session_state.cam_qty = 1; st.rerun()

# ================================================================== #
#  TAB: FILE UPLOAD
# ================================================================== #

elif st.session_state.active_tab == "batch":

    from PIL import Image, ExifTags
    import io as _io

    def fix_rot_b(img_bytes):
        try:
            img = Image.open(_io.BytesIO(img_bytes))
            exif = img._getexif()
            if exif:
                ok = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
                if ok and ok in exif:
                    rot = {3:180,6:270,8:90}.get(exif[ok])
                    if rot: img = img.rotate(rot, expand=True)
            buf = _io.BytesIO(); img.save(buf, format="JPEG", quality=90); return buf.getvalue()
        except: return img_bytes

    def file_upload_photo(f_bytes, group_id, idx):
        fixed = fix_rot_b(f_bytes)
        dt = datetime.now()
        fn = f"{dt.strftime('%d%m%y')}_{dt.strftime('%H%M%S')}_{idx}.jpg"
        supabase.storage.from_("part-photos").upload(path=fn, file=fixed, file_options={"content-type":"image/jpeg","upsert":"true"})
        supabase.table("group_photos").insert({"group_id":group_id,"photo_id":fn}).execute()

    for k,v in [("file_batch_id",None),("file_condition","used"),("file_items",[]),("file_group_id",None),("file_qty",1)]:
        if k not in st.session_state: st.session_state[k] = v

    if st.session_state.file_batch_id is None:
        st.markdown("""
        <div style='text-align:center; padding:2rem 0 1rem;'>
            <div style='font-size:2.5rem; margin-bottom:0.5rem;'>🗂️</div>
            <div style='color:#111827; font-size:1.1rem; font-weight:600;'>File Upload</div>
            <div style='color:#4a4a5a; font-size:0.82rem; margin-top:0.3rem;'>Upload multiple photos per item from your device</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div class='field-label' style='text-align:center;'>Condition for this Batch</div>", unsafe_allow_html=True)
        fa, fb = st.columns(2)
        with fa:
            if st.button("✓  Used" if st.session_state.file_condition=="used" else "Used", use_container_width=True, key="file_cond_used", type="primary" if st.session_state.file_condition=="used" else "secondary"):
                st.session_state.file_condition = "used"; st.rerun()
        with fb:
            if st.button("✓  New" if st.session_state.file_condition=="new" else "New", use_container_width=True, key="file_cond_new", type="primary" if st.session_state.file_condition=="new" else "secondary"):
                st.session_state.file_condition = "new"; st.rerun()
        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
        if st.button("🚀  Start Upload Batch", use_container_width=True, type="primary", key="start_file_batch"):
            st.session_state.file_batch_id = str(uuid.uuid4())
            st.session_state.file_items = []; st.session_state.file_group_id = None; st.session_state.file_qty = 1; st.rerun()
    else:
        total_f = len(st.session_state.file_items)
        fcond_clr = "#22c55e" if st.session_state.file_condition=="new" else "#7c3aed"
        st.markdown(f"""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid {fcond_clr};
        border-radius:10px; padding:0.65rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span style='color:#111827; font-size:0.9rem; font-weight:600;'>Upload Batch</span>
                <span style='color:#4a4a5a; font-size:0.72rem; margin-left:10px;'>
                    {total_f} items · <span style='color:{fcond_clr};'>{st.session_state.file_condition.title()}</span>
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.file_group_id is None:
            if st.session_state.file_items:
                st.markdown("<div class='section-label'>Items uploaded</div>", unsafe_allow_html=True)
                for i, item in enumerate(reversed(st.session_state.file_items)):
                    idx = total_f - i
                    st.markdown(f"""<div class='batch-card processing'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div><span style='color:#0f172a; font-size:0.82rem; font-weight:500;'>Item {idx}</span>
                            <span style='color:#4a4a5a; font-size:0.7rem; margin-left:8px;'>{item.get("photo_count",0)} photos · Qty {item.get("qty",1)}</span></div>
                            <span class='status-pill pill-processing'>Processing...</span>
                        </div></div>""", unsafe_allow_html=True)
                st.divider()
            fb1, fb2, fb3 = st.columns([2,2,1])
            with fb1:
                if st.button("📁  Add Next Item", use_container_width=True, type="primary"):
                    result = supabase.table("listing_groups").insert({"session_id":st.session_state.file_batch_id,"status":"waiting","quantity":1,"condition":st.session_state.file_condition}).execute()
                    st.session_state.file_group_id = result.data[0]["id"]; st.session_state.file_qty = 1; st.rerun()
            with fb2:
                if st.button("🏁  End Batch", use_container_width=True, type="secondary"):
                    st.session_state.file_batch_id = None; st.session_state.file_items = []
                    st.session_state.file_group_id = None; st.cache_data.clear(); st.rerun()
            with fb3:
                if st.button("✗  Cancel", use_container_width=True, type="secondary"):
                    st.session_state.file_batch_id = None; st.session_state.file_items = []
                    st.session_state.file_group_id = None; st.rerun()
        else:
            item_num = total_f + 1
            st.markdown(f"""
            <div style='background:#faf5ff; border:1.5px solid #7c3aed; border-radius:12px;
            padding:0.75rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
                <span style='color:#111827; font-size:0.9rem; font-weight:600;'>Item {item_num}</span>
                <span class='status-pill pill-active'>Select Photos</span>
            </div>""", unsafe_allow_html=True)
            uploaded_files = st.file_uploader("Select photos (up to 10)", type=["jpg","jpeg","png","heic"], accept_multiple_files=True, key=f"fup_{st.session_state.file_group_id}", label_visibility="collapsed")
            if uploaded_files and len(uploaded_files) > 10:
                st.warning("Maximum 10 photos."); uploaded_files = uploaded_files[:10]
            if uploaded_files:
                st.markdown(f"<div style='color:#7c3aed; font-size:0.75rem; margin-bottom:6px;'>{len(uploaded_files)} photo(s) selected</div>", unsafe_allow_html=True)
                tc = st.columns(min(len(uploaded_files),5))
                for col, f in zip(tc, uploaded_files):
                    with col: st.image(f, use_container_width=True)
            st.markdown("<div class='field-label' style='margin-top:0.75rem;'>Quantity</div>", unsafe_allow_html=True)
            fq1,fq2,fq3 = st.columns([1,2,1])
            with fq1:
                if st.button("−", key="fq_minus", use_container_width=True):
                    if st.session_state.file_qty > 1: st.session_state.file_qty -= 1; st.rerun()
            with fq2:
                st.markdown(f"<div style='text-align:center; font-size:1.3rem; font-weight:700; color:#fff; padding-top:3px;'>{st.session_state.file_qty}</div>", unsafe_allow_html=True)
            with fq3:
                if st.button("+", key="fq_plus", use_container_width=True):
                    st.session_state.file_qty += 1; st.rerun()
            fc1, fc2 = st.columns([3,1])
            with fc1:
                done_dis = not uploaded_files
                if st.button("✓  Done — Send to Scanner" if not done_dis else "Select photos to continue", use_container_width=True, type="primary", disabled=done_dis):
                    with st.spinner("Uploading..."):
                        group_id = st.session_state.file_group_id; upped = 0
                        for i, f in enumerate(uploaded_files[:10]):
                            try: file_upload_photo(f.read(), group_id, i); upped += 1
                            except Exception as e: st.error(f"Photo {i+1} failed: {e}")
                        supabase.table("listing_groups").update({"condition":st.session_state.file_condition,"quantity":st.session_state.file_qty,"status":"pending"}).eq("id",group_id).execute()
                        st.session_state.file_items.append({"group_id":group_id,"condition":st.session_state.file_condition,"qty":st.session_state.file_qty,"status":"pending","photo_count":upped})
                        st.session_state.file_group_id = None; st.session_state.file_qty = 1
                        st.cache_data.clear(); st.rerun()
            with fc2:
                if st.button("✗  Cancel Item", use_container_width=True, type="secondary"):
                    try: supabase.table("listing_groups").delete().eq("id",st.session_state.file_group_id).execute()
                    except: pass
                    st.session_state.file_group_id = None; st.session_state.file_qty = 1; st.rerun()

elif st.session_state.active_tab == "dashboard":

    df = fetch_listings()

    if df.empty:
        st.markdown("""
        <div style="text-align:center; padding:3rem 0; color:#4a4a5a;">
            <div style="font-size:2rem; margin-bottom:0.75rem;">📭</div>
            <div style="font-size:1rem; font-weight:500; color:#aaaacc;">No items in current batch</div>
            <div style="font-size:0.8rem; margin-top:0.4rem;">Use Batch Upload to scan products</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Confirm clear
        if st.session_state.confirm_clear:
            total_items = len(df)
            st.warning(f"Archive all **{total_items}** items and clear this batch?")
            y, n = st.columns(2)
            with y:
                if st.button("✅  Confirm", use_container_width=True, type="primary"):
                    try:
                        append_to_archive(df)
                        all_ids = df["id"].dropna().astype(str).tolist()
                        if all_ids:
                            supabase.table("listings").update({"status": "archived"}).in_("id", all_ids).execute()
                        st.session_state.confirm_clear = False
                        st.session_state.quantities    = {}
                        st.cache_data.clear()
                        st.success(f"✅  {total_items} items archived.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                        st.session_state.confirm_clear = False
            with n:
                if st.button("✗  Cancel", use_container_width=True):
                    st.session_state.confirm_clear = False
                    st.rerun()
            st.divider()

        total_items = len(df)
        total_value = df["price"].sum() if "price" in df.columns else 0
        avg_price   = df["price"].mean() if "price" in df.columns else 0
        total_qty   = int(df["quantity"].sum()) if "quantity" in df.columns else 0

        # Compact stat tiles
        tc1, tc2, tc3 = st.columns(3)
        for col, val, label, sub, color in [
            (tc1, str(total_items),           "Items in Batch",  "",                         "#2196F3"),
            (tc2, f"${total_value:,.2f}",     "Batch Value",     f"avg ${avg_price:.2f}",    "#22c55e"),
            (tc3, str(total_qty),             "Total Units",     "",                         "#f59e0b"),
        ]:
            with col:
                sub_html = f"<div style='color:#6b6b7b; font-size:0.68rem; margin-top:2px;'>{sub}</div>" if sub else ""
                st.markdown(f"""
                <div style='background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid {color};
                border-radius:10px; padding:0.85rem 1.1rem; margin-bottom:0.75rem;'>
                    <div style='color:#0f172a; font-size:1.8rem; font-weight:700; letter-spacing:-0.03em; line-height:1;'>{val}</div>
                    <div style='color:#64748b; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:5px;'>{label}</div>
                    {sub_html}
                </div>""", unsafe_allow_html=True)

        st.divider()

        # eBay submit bar
        sel_count = sum(1 for v in st.session_state.ebay_selected.values() if v)
        eb1, eb2, eb3 = st.columns([2, 2, 2])
        with eb1:
            if st.button("☑  Select All", use_container_width=True, type="secondary", key="ebay_sel_all"):
                for _, row in df.iterrows():
                    st.session_state.ebay_selected[str(row["id"])] = True
                st.rerun()
        with eb2:
            if st.button("☐  Deselect All", use_container_width=True, type="secondary", key="ebay_desel_all"):
                st.session_state.ebay_selected = {}
                st.rerun()
        with eb3:
            submit_label = f"🏷️  Submit {sel_count} to eBay" if sel_count > 0 else "🏷️  Submit to eBay"
            if st.button(submit_label, use_container_width=True, type="primary",
                         key="ebay_submit_btn", disabled=sel_count == 0):
                st.session_state.ebay_submitting = True
                st.rerun()

        if st.session_state.ebay_submitting and sel_count > 0:
            selected_ids = [k for k, v in st.session_state.ebay_selected.items() if v]
            selected_df  = df[df["id"].astype(str).isin(selected_ids)]
            prog = st.progress(0, text=f"Submitting {len(selected_df)} listings to eBay...")
            results = []
            for i, (_, row) in enumerate(selected_df.iterrows()):
                prog.progress((i+1)/len(selected_df), text=f"Submitting: {str(row.get('title',''))[:40]}...")
                result = submit_to_ebay(row.to_dict())
                if result["success"]:
                    supabase.table("listings").update({
                        "ebay_item_id":      result["item_id"],
                        "ebay_status":       "draft",
                        "ebay_submitted_at": datetime.now().isoformat(),
                    }).eq("id", str(row["id"])).execute()
                    results.append({"title": str(row.get("title",""))[:40], "item_id": result["item_id"], "success": True})
                else:
                    results.append({"title": str(row.get("title",""))[:40], "error": result["error"], "success": False})
            prog.empty()
            st.session_state.ebay_submitting = False
            st.session_state.ebay_selected = {}
            st.cache_data.clear()
            success_count = sum(1 for r in results if r["success"])
            fail_count    = len(results) - success_count
            if success_count > 0:
                st.success(f"✅ {success_count} listings submitted to eBay as scheduled drafts. They appear in Seller Hub under Scheduled Listings.")
            for r in results:
                if not r["success"]:
                    st.error(f"❌ {r['title']}: {r['error']}")
            st.rerun()

        st.divider()
        st.markdown("<div class='section-label'>Items</div>", unsafe_allow_html=True)

        if "quantities" not in st.session_state:
            st.session_state.quantities = {}

        for _, item in df.iterrows():
            item_id      = str(item.get("id", ""))
            pid          = str(item.get("photo_id", ""))
            title        = str(item.get("title", "Unknown"))
            price        = float(item.get("price", 0.0))
            price_note   = str(item.get("price_note", "")).strip().lower()
            condition    = str(item.get("condition", "used")).strip().lower()
            category     = str(item.get("ebay_category", ""))
            cat_id       = str(item.get("ebay_category_id", "")).strip().replace(".0", "")
            weight_oz    = float(item.get("weight_oz", 0.0) or 0.0)
            price_used   = float(item.get("price_used", 0.0) or 0.0)
            price_new    = float(item.get("price_new",  0.0) or 0.0)
            url          = photo_url(pid)
            has_dual     = price_used > 0 or price_new > 0
            ebay_item_id = str(item.get("ebay_item_id","") or "")
            ebay_status  = str(item.get("ebay_status","") or "")

            if item_id and item_id not in st.session_state.quantities:
                st.session_state.quantities[item_id] = int(item.get("quantity", 0))

            current_qty = st.session_state.quantities.get(item_id, 0)
            flag_color  = "#f59e0b22" if price_note in ("new", "used") else "#1e1e28"

            is_selected = st.session_state.ebay_selected.get(item_id, False)
            card_border = "#2563eb" if is_selected else flag_color
            ebay_badge = ""
            if ebay_status == "draft" and ebay_item_id:
                ebay_badge = f"<a href='https://www.ebay.com/itm/{ebay_item_id}' target='_blank' style='background:#eff6ff; color:#2563eb; border:1px solid #93c5fd; border-radius:4px; font-size:0.6rem; font-weight:600; padding:2px 7px; text-decoration:none; margin-left:6px;'>🏷️ eBay Draft #{ebay_item_id}</a>"

            st.markdown(
                f"<div style='background:#ffffff; border:1.5px solid {card_border}; "
                f"border-radius:12px; padding:0.75rem; margin-bottom:0.5rem;'>",
                unsafe_allow_html=True
            )

            chk_col, img_col, fields_col = st.columns([0.3, 1, 4])
            with chk_col:
                checked = st.checkbox("", value=is_selected, key=f"chk_{item_id}",
                                       label_visibility="collapsed")
                if checked != is_selected:
                    st.session_state.ebay_selected[item_id] = checked
                    st.rerun()

            with img_col:
                if url:
                    st.markdown(f"<img src='{url}' style='width:100%; border-radius:8px; display:block; max-height:140px; object-fit:cover;' />", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:6px; height:100px; display:flex; align-items:center; justify-content:center; color:#4a4a5a; font-size:1.2rem;'>📷</div>", unsafe_allow_html=True)
                sku_display = pid.rsplit(".", 1)[0] if pid else "—"
                st.markdown(
                    f"<div style='color:#4a4a5a; font-size:0.6rem; text-align:center; margin-top:3px;'>{sku_display}</div>",
                    unsafe_allow_html=True)

            with fields_col:
                # Title — full width
                new_title = st.text_input(
                    "Title", value=title, key=f"title_{item_id}",
                    label_visibility="collapsed", placeholder="Title"
                )
                if new_title.strip() and new_title.strip() != title:
                    update_field(item_id, "title", new_title.strip()[:80])
                    st.cache_data.clear()

                # Row: Price | Condition | Qty
                pc1, pc2, pc3 = st.columns([2, 1, 2])

                with pc1:
                    st.markdown("<div class='field-label'>Price</div>", unsafe_allow_html=True)
                    # Use text_input so there are no +/- spinner buttons
                    # Key includes price so it re-renders when condition changes
                    price_key = f"price_{item_id}_{round(price, 2)}"
                    price_input = st.text_input(
                        "Price", value=f"{price:.2f}",
                        key=price_key, label_visibility="collapsed"
                    )
                    try:
                        new_price = round(float(price_input.replace("$","").strip()), 2)
                        if new_price != round(price, 2):
                            update_field(item_id, "price", new_price)
                            update_field(item_id, "price_note", "")
                            st.cache_data.clear()
                    except ValueError:
                        pass
                    if has_dual:
                        p_used_str = f"${price_used:.2f}" if price_used > 0 else "—"
                        p_new_str  = f"${price_new:.2f}"  if price_new  > 0 else "—"
                        st.markdown(
                            f"<div style='color:#64748b; font-size:0.6rem;'>U:{p_used_str} &nbsp; N:{p_new_str}</div>",
                            unsafe_allow_html=True)
                    if price_note in ("new", "used"):
                        st.markdown(
                            f"<div style='color:#d97706; font-size:0.6rem;'>⚠ fallback to {price_note}</div>",
                            unsafe_allow_html=True)

                with pc2:
                    st.markdown("<div class='field-label'>Cond.</div>", unsafe_allow_html=True)
                    new_cond = st.selectbox(
                        "Condition", ["used", "new"],
                        index=1 if condition == "new" else 0,
                        key=f"cond_{item_id}", label_visibility="collapsed"
                    )
                    if new_cond != condition:
                        price_updated = switch_condition(item_id, new_cond, price_used, price_new)
                        if not price_updated:
                            st.toast("Condition updated — update price manually", icon="⚠️")
                        st.cache_data.clear()
                        st.rerun()

                with pc3:
                    st.markdown("<div class='field-label'>Quantity</div>", unsafe_allow_html=True)
                    q1, q2, q3 = st.columns([1, 1, 1])
                    with q1:
                        if st.button("−", key=f"minus_{item_id}", use_container_width=True):
                            new_qty = max(0, current_qty - 1)
                            st.session_state.quantities[item_id] = new_qty
                            update_field(item_id, "quantity", new_qty)
                            st.cache_data.clear()
                            st.rerun()
                    with q2:
                        st.markdown(
                            f"<div style='text-align:center; font-size:0.9rem; font-weight:600; "
                            f"color:#111827; padding-top:5px;'>{current_qty}</div>", unsafe_allow_html=True)
                    with q3:
                        if st.button("+", key=f"plus_{item_id}", use_container_width=True):
                            new_qty = current_qty + 1
                            st.session_state.quantities[item_id] = new_qty
                            update_field(item_id, "quantity", new_qty)
                            st.cache_data.clear()
                            st.rerun()

                # Row: Category | Cat ID | Weight
                cc1, cc2, cc3 = st.columns([4, 1, 1])

                with cc1:
                    st.markdown("<div class='field-label'>eBay Category</div>", unsafe_allow_html=True)
                    matched_label = find_best_label(category, cat_id)
                    options       = ["— search or select —"] + CATEGORY_LABELS
                    current_index = options.index(matched_label) if matched_label in options else 0
                    selected_label = st.selectbox(
                        "eBay Category", options=options, index=current_index,
                        key=f"cat_{item_id}", label_visibility="collapsed"
                    )
                    if selected_label != "— search or select —" and selected_label != matched_label:
                        supabase.table("listings").update({
                            "ebay_category":    LABEL_TO_NAME[selected_label],
                            "ebay_category_id": LABEL_TO_ID[selected_label],
                        }).eq("id", item_id).execute()
                        st.cache_data.clear()
                        st.rerun()

                with cc2:
                    st.markdown("<div class='field-label'>Cat. ID</div>", unsafe_allow_html=True)
                    display_cat_id  = LABEL_TO_ID.get(matched_label, cat_id) if matched_label else cat_id
                    new_cat_id_text = st.text_input(
                        "Cat ID", value=display_cat_id,
                        key=f"catid_{item_id}", label_visibility="collapsed"
                    )
                    if new_cat_id_text.strip() and new_cat_id_text.strip() != display_cat_id:
                        update_field(item_id, "ebay_category_id", new_cat_id_text.strip())
                        st.cache_data.clear()

                with cc3:
                    st.markdown("<div class='field-label'>oz</div>", unsafe_allow_html=True)
                    new_oz = st.number_input(
                        "oz", value=weight_oz, step=0.1, format="%.1f",
                        key=f"oz_{item_id}", label_visibility="collapsed"
                    )
                    if round(new_oz, 1) != round(weight_oz, 1):
                        update_field(item_id, "weight_oz", round(new_oz, 1))
                        update_field(item_id, "weight_lb", round(new_oz / 16, 2))
                        st.cache_data.clear()

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Issues
        st.markdown("<div class='section-label'>Issues</div>", unsafe_allow_html=True)
        issues_df = fetch_issues()

        if issues_df.empty:
            st.markdown("<p style='color:#4a4a5a; font-size:0.8rem;'>No issues submitted yet.</p>", unsafe_allow_html=True)
        else:
            for _, issue in issues_df.iterrows():
                issue_id  = str(issue.get("id", ""))
                desc      = str(issue.get("description", ""))
                submitted = issue.get("submitted_at", "")
                if hasattr(submitted, "strftime"):
                    submitted = submitted.strftime("%b %d %I:%M %p")
                st.markdown(f"""
                <div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
                padding:0.6rem 0.9rem; margin-bottom:0.4rem;'>
                    <div style='color:#4a4a5a; font-size:0.65rem; margin-bottom:3px;'>{submitted}</div>
                    <div style='color:#111827; font-size:0.82rem;'>{desc}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✓ Resolved", key=f"resolve_{issue_id}"):
                    try:
                        supabase.table("issues").delete().eq("id", issue_id).execute()
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        with st.expander("➕  Submit an issue", expanded=False):
            issue_text = st.text_area("Description", placeholder="Describe the issue...", label_visibility="collapsed")
            if st.button("Submit Issue", type="primary"):
                if issue_text.strip():
                    now = datetime.now().isoformat()
                    supabase.table("issues").insert({"description": issue_text.strip(), "submitted_at": now}).execute()
                    send_issue_email(issue_text.strip(), now)
                    st.cache_data.clear()
                    st.success("✅ Issue submitted.")
                    st.rerun()
                else:
                    st.warning("Please enter a description.")

# ================================================================== #
#  TAB: RESEARCH
# ================================================================== #

elif st.session_state.active_tab == "research":

    @st.cache_data(ttl=60)
    def fetch_research():
        result = (
            supabase.table("ebay_research")
            .select("*")
            .order("found_at", desc=True)
            .execute()
        )
        if not result.data:
            return pd.DataFrame()
        df = pd.DataFrame(result.data)
        if "found_at" in df.columns:
            df["found_at"] = pd.to_datetime(df["found_at"], errors="coerce", utc=True)
        for col in ["ebay_price", "source_price"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df

    st.markdown("<div class='section-label'>eBay Research — Buy It Now listings at or below your cost</div>", unsafe_allow_html=True)

    research_df = fetch_research()

    if research_df.empty:
        st.markdown("""
        <div style="text-align:center; padding:3rem 0; color:#4a4a5a;">
            <div style="font-size:2rem; margin-bottom:0.75rem;">🔍</div>
            <div style="font-size:1rem; font-weight:500; color:#aaaacc;">No research results yet</div>
            <div style="font-size:0.8rem; margin-top:0.4rem;">
                The research service runs every hour and searches eBay for items matching your inventory.<br>
                Make sure research_service.py is running on Railway.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        source_titles = research_df["source_title"].unique()
        total_results = len(research_df)
        total_sources = len(source_titles)
        profitable    = len(research_df[research_df["ebay_price"] < research_df["source_price"]])
        last_run      = research_df["found_at"].max()
        last_run_str  = last_run.strftime("%b %d %I:%M %p") if pd.notna(last_run) else "—"

        rc1, rc2, rc3, rc4 = st.columns(4)
        for col, val, label, color in [
            (rc1, str(total_sources),  "Items Researched", "#2196F3"),
            (rc2, str(total_results),  "Listings Found",   "#a855f7"),
            (rc3, str(profitable),     "Below Your Cost",  "#22c55e"),
            (rc4, last_run_str,        "Last Run",         "#f59e0b"),
        ]:
            with col:
                st.markdown(f"""
                <div style='background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid {color};
                border-radius:10px; padding:0.85rem 1.1rem; margin-bottom:0.75rem;'>
                    <div style='color:#111827; font-size:1.2rem; font-weight:700; line-height:1;'>{val}</div>
                    <div style='color:#4a4a5a; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:5px;'>{label}</div>
                </div>""", unsafe_allow_html=True)

        st.divider()

        fc1, fc2 = st.columns([3, 1])
        with fc1:
            search_filter = st.text_input("Filter", placeholder="Search by title...", label_visibility="collapsed")
        with fc2:
            below_only = st.checkbox("Below cost only", value=False)

        filtered_df = research_df.copy()
        if search_filter:
            filtered_df = filtered_df[
                filtered_df["ebay_title"].str.contains(search_filter, case=False, na=False) |
                filtered_df["source_title"].str.contains(search_filter, case=False, na=False)
            ]
        if below_only:
            filtered_df = filtered_df[filtered_df["ebay_price"] < filtered_df["source_price"]]

        st.markdown(
            f"<p style='color:#4a4a5a; font-size:0.75rem; margin-bottom:1rem;'>Showing {len(filtered_df)} listings</p>",
            unsafe_allow_html=True
        )

        for source_title in source_titles:
            group = filtered_df[filtered_df["source_title"] == source_title]
            if group.empty:
                continue

            source_price = group["source_price"].iloc[0]
            below_count  = len(group[group["ebay_price"] < source_price])

            with st.expander(
                f"📦 {source_title[:55]}  —  your cost: ${source_price:.2f}  ·  {len(group)} listings  ·  {below_count} below cost",
                expanded=True
            ):
                TILES_PER_ROW = 3
                rows = [group.iloc[i:i+TILES_PER_ROW] for i in range(0, len(group), TILES_PER_ROW)]

                for row_df in rows:
                    cols = st.columns(TILES_PER_ROW)
                    for col, (_, listing) in zip(cols, row_df.iterrows()):
                        ebay_price   = float(listing.get("ebay_price", 0))
                        ebay_title   = str(listing.get("ebay_title", ""))
                        ebay_image   = str(listing.get("ebay_image_url", ""))
                        ebay_url     = str(listing.get("ebay_listing_url", ""))
                        ebay_cond    = str(listing.get("ebay_condition", ""))
                        is_below     = ebay_price < source_price
                        price_color  = "#22c55e" if is_below else "#ffffff"
                        border_color = "#22c55e33" if is_below else "#1e1e28"
                        profit       = source_price - ebay_price
                        profit_str   = f"+${profit:.2f} margin" if is_below else f"${abs(profit):.2f} above cost"
                        profit_color = "#22c55e" if is_below else "#4a4a5a"

                        with col:
                            if ebay_image and ebay_image != "nan":
                                try:
                                    st.image(ebay_image, use_container_width=True)
                                except Exception:
                                    st.markdown("<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:8px; height:120px; display:flex; align-items:center; justify-content:center; color:#4a4a5a;'>📷</div>", unsafe_allow_html=True)
                            else:
                                st.markdown("<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:8px; height:120px; display:flex; align-items:center; justify-content:center; color:#4a4a5a;'>📷</div>", unsafe_allow_html=True)

                            st.markdown(f"""
                            <div style='background:#ffffff; border:1px solid {border_color};
                            border-radius:8px; padding:0.6rem 0.75rem; margin-top:6px; margin-bottom:4px;'>
                                <div style='color:#111827; font-size:0.75rem; font-weight:500;
                                overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
                                margin-bottom:6px;' title='{ebay_title}'>{ebay_title[:50]}</div>
                                <div style='color:{price_color}; font-size:1.1rem; font-weight:700;'>${ebay_price:.2f}</div>
                                <div style='color:{profit_color}; font-size:0.65rem; margin-top:2px;'>{profit_str}</div>
                                <div style='color:#4a4a5a; font-size:0.65rem; margin-top:2px;'>{ebay_cond}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            if ebay_url and ebay_url != "nan":
                                st.markdown(
                                    f"<a href='{ebay_url}' target='_blank' style='display:block; text-align:center; "
                                    f"background:#f0f9ff; border:1px solid #93c5fd; border-radius:6px; padding:5px; "
                                    f"color:#2196F3; font-size:0.72rem; text-decoration:none; margin-bottom:12px;'>"
                                    f"View on eBay ↗</a>",
                                    unsafe_allow_html=True
                                )



# ================================================================== #
#  TAB: AUCTION SCANNER
# ================================================================== #

elif st.session_state.active_tab == "auction":

    import sys
    sys.path.insert(0, os.path.dirname(__file__) or ".")

    # ---- State --------------------------------------------------- #
    if "auction_active_session" not in st.session_state:
        st.session_state.auction_active_session = None
    if "auction_auto_enrich" not in st.session_state:
        st.session_state.auction_auto_enrich = False
    if "auction_enrich_ids" not in st.session_state:
        st.session_state.auction_enrich_ids = []

    # ---- Load sessions from DB ----------------------------------- #
    @st.cache_data(ttl=30)
    def fetch_auction_sessions():
        try:
            r = supabase.table("auction_sessions").select("*").order("created_at", desc=True).execute()
            return r.data or []
        except Exception:
            return []

    @st.cache_data(ttl=15)
    def fetch_auction_items(session_id):
        try:
            r = supabase.table("auction_items").select("*").eq("session_id", session_id).order("scraped_at").execute()
            return r.data or []
        except Exception:
            return []

    sessions = fetch_auction_sessions()

    # Auto-load most recent session on first visit
    if st.session_state.auction_active_session is None and sessions:
        st.session_state.auction_active_session = sessions[0]["session_id"]

    # ---- Header -------------------------------------------------- #
    st.markdown("""
    <div style='margin-bottom:0.75rem;'>
        <div style='color:#0f172a; font-size:1.1rem; font-weight:700; margin-bottom:2px;'>🔨 Auction Scanner</div>
        <div style='color:#64748b; font-size:0.8rem;'>Paste any auction URL — scrapes listings and looks up market values automatically. Scans are saved and can be revisited anytime.</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Saved sessions list + new scan controls ---------------- #
    if sessions:
        sess_col, new_col = st.columns([4, 1])
        with sess_col:
            session_labels = {
                s["session_id"]: f"{s.get('label','Scan')}  ·  {s.get('item_count',0)} items  ·  {s['created_at'][:10]}"
                for s in sessions
            }
            selected_label = st.selectbox(
                "Saved scans",
                options=list(session_labels.keys()),
                format_func=lambda x: session_labels[x],
                index=0 if st.session_state.auction_active_session not in session_labels
                      else list(session_labels.keys()).index(st.session_state.auction_active_session),
                label_visibility="collapsed",
                key="auction_session_selector"
            )
            if selected_label != st.session_state.auction_active_session:
                st.session_state.auction_active_session = selected_label
                st.cache_data.clear()
                st.rerun()
        with new_col:
            if st.button("＋ New Scan", use_container_width=True, type="secondary"):
                st.session_state.auction_active_session = None
                st.session_state.auction_auto_enrich = False
                st.rerun()

    # ---- New scan form ------------------------------------------- #
    if st.session_state.auction_active_session is None:
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        col_url, col_scan = st.columns([4, 1])
        with col_url:
            auction_url = st.text_input("URL", placeholder="https://www.bidspotter.com/auctions/...",
                                         label_visibility="collapsed", key="auction_url_new")
        ps1, ps2 = st.columns([1, 2])
        with ps1:
            page_mode = st.selectbox("Pages", ["Single page", "All pages", "Page range"],
                                      label_visibility="collapsed", key="auction_page_mode_new")
        with ps2:
            if page_mode == "Single page":
                page_num = st.number_input("Page", min_value=1, value=1, step=1,
                                            label_visibility="collapsed", key="auction_page_num_new")
                pages_to_scan = [int(page_num)]
            elif page_mode == "All pages":
                st.markdown("<div style='color:#64748b; font-size:0.75rem; padding-top:8px;'>Detects all pages automatically</div>", unsafe_allow_html=True)
                pages_to_scan = None
            else:
                page_range = st.text_input("Range e.g. 1-5", value="1-3",
                                            label_visibility="collapsed", key="auction_page_range_new")
                try:
                    parts = page_range.split("-")
                    pages_to_scan = list(range(int(parts[0]), int(parts[1]) + 1))
                except Exception:
                    pages_to_scan = [1]

        with col_scan:
            scan_clicked = st.button("🔍  Scan", use_container_width=True, type="primary",
                                      key="auction_scan_btn",
                                      disabled=not (auction_url if "auction_url_new" in st.session_state else "").strip())

        if scan_clicked and st.session_state.get("auction_url_new","").strip():
            url = st.session_state.auction_url_new.strip()
            session_id = str(uuid.uuid4())

            with st.spinner("Scraping auction listings..."):
                try:
                    from auction_scraper import scrape_and_store, get_page_count, get_page_url
                    if pages_to_scan is None:
                        total_pages = get_page_count(url)
                        pages_to_scan = list(range(1, total_pages + 1))

                    item_ids = scrape_and_store(url, session_id, pages_to_scan)

                    # Save session to DB
                    label = url.split("/")[2] if "/" in url else url[:40]
                    supabase.table("auction_sessions").insert({
                        "session_id":  session_id,
                        "source_url":  url,
                        "label":       label,
                        "item_count":  len(item_ids),
                        "created_at":  datetime.now().isoformat(),
                        "last_refreshed": datetime.now().isoformat(),
                    }).execute()

                    st.session_state.auction_active_session = session_id
                    st.session_state.auction_auto_enrich    = True
                    st.session_state.auction_enrich_ids     = item_ids
                    st.cache_data.clear()
                    st.rerun()

                except Exception as e:
                    st.error(f"Scan failed: {e}")

    # ---- Active session view ------------------------------------- #
    else:
        session_id = st.session_state.auction_active_session
        session_info = next((s for s in sessions if s["session_id"] == session_id), None)
        items = fetch_auction_items(session_id)

        # Auto-enrich if just scanned
        if st.session_state.get("auction_auto_enrich") and items:
            st.session_state.auction_auto_enrich = False
            ids = st.session_state.get("auction_enrich_ids", [i["id"] for i in items if i.get("value_status") == "pending"])
            total_e = len(ids)
            if total_e > 0:
                prog = st.progress(0, text=f"Researching {total_e} items across the web...")
                def update_prog(done, total, title):
                    prog.progress(done/total, text=f"Researching {done}/{total}: {title[:40]}...")
                try:
                    from auction_scraper import enrich_values
                    enrich_values(ids, progress_callback=update_prog)
                    prog.empty()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    prog.empty()
                    st.error(f"Value lookup failed: {e}")

        # Session action bar
        source_url = session_info.get("source_url","") if session_info else ""
        last_ref   = session_info.get("last_refreshed","")[:10] if session_info else ""
        total_items   = len(items)
        valued_items  = sum(1 for i in items if i.get("value_status") == "done")
        favorited_cnt = sum(1 for i in items if i.get("favorited"))

        st.markdown(f"""
        <div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:10px;
        padding:0.65rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='color:#0f172a; font-size:0.82rem; font-weight:600; margin-bottom:2px;'>{source_url[:60]}</div>
                <div style='color:#94a3b8; font-size:0.7rem;'>
                    {total_items} listings · {valued_items} valued · {favorited_cnt} favorited · last refreshed {last_ref}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons
        ac1, ac2, ac3 = st.columns([2, 2, 1])
        with ac1:
            if st.button("🔄  Refresh Scan", use_container_width=True, type="primary", key="auction_refresh"):
                with st.spinner("Re-scraping and updating values..."):
                    try:
                        from auction_scraper import scrape_and_store, get_page_count, enrich_values
                        # Delete old items for this session
                        supabase.table("auction_items").delete().eq("session_id", session_id).execute()
                        # Re-scrape
                        new_ids = scrape_and_store(source_url, session_id, [1])
                        # Update session
                        supabase.table("auction_sessions").update({
                            "item_count":     len(new_ids),
                            "last_refreshed": datetime.now().isoformat(),
                        }).eq("session_id", session_id).execute()
                        # Re-enrich
                        st.session_state.auction_auto_enrich = True
                        st.session_state.auction_enrich_ids  = new_ids
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Refresh failed: {e}")
        with ac2:
            pending = [i for i in items if i.get("value_status") == "pending"]
            if pending:
                if st.button(f"🔄  Retry Values ({len(pending)} pending)", use_container_width=True,
                              type="secondary", key="auction_retry_values"):
                    st.session_state.auction_auto_enrich = True
                    st.session_state.auction_enrich_ids  = [i["id"] for i in pending]
                    st.rerun()
        with ac3:
            if st.button("🗑️  Delete", use_container_width=True, type="secondary", key="auction_delete"):
                try:
                    supabase.table("auction_items").delete().eq("session_id", session_id).execute()
                    supabase.table("auction_sessions").delete().eq("session_id", session_id).execute()
                    st.session_state.auction_active_session = None
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

        if not items:
            st.info("No items found for this scan.")
        else:
            # Stats
            as1, as2, as3, as4 = st.columns(4)
            for col, val, label, color in [
                (as1, str(total_items),   "Listings",   "#b45309"),
                (as2, str(valued_items),  "Valued",     "#0891b2"),
                (as3, str(total_items - valued_items), "Pending", "#94a3b8"),
                (as4, str(favorited_cnt), "Favorited",  "#dc2626"),
            ]:
                with col:
                    st.markdown(f"""
                    <div style='background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid {color};
                    border-radius:10px; padding:0.65rem 1rem; margin-bottom:0.75rem;'>
                        <div style='color:#0f172a; font-size:1.5rem; font-weight:700; line-height:1;'>{val}</div>
                        <div style='color:#64748b; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:4px;'>{label}</div>
                    </div>""", unsafe_allow_html=True)

            # Filter / sort
            f1, f2, f3 = st.columns([3, 1, 1])
            with f1:
                search_q = st.text_input("Search", placeholder="Filter by title...",
                                          label_visibility="collapsed", key="auction_search")
            with f2:
                show_fav = st.checkbox("Favorites only", key="auction_fav_only")
            with f3:
                sort_by = st.selectbox("Sort", ["Default","Price ↑","Price ↓","Value ↑"],
                                        label_visibility="collapsed", key="auction_sort")

            filtered = items.copy()
            if search_q:
                filtered = [i for i in filtered if search_q.lower() in i.get("title","").lower()]
            if show_fav:
                filtered = [i for i in filtered if i.get("favorited")]
            if sort_by == "Price ↑":
                filtered.sort(key=lambda x: x.get("current_price",0))
            elif sort_by == "Price ↓":
                filtered.sort(key=lambda x: x.get("current_price",0), reverse=True)
            elif sort_by == "Value ↑":
                filtered.sort(key=lambda x: x.get("value_used_high",0))

            st.markdown(f"<p style='color:#94a3b8; font-size:0.75rem; margin-bottom:0.5rem;'>Showing {len(filtered)} of {total_items} listings</p>",
                        unsafe_allow_html=True)

            # Item cards
            for item in filtered:
                item_id       = item.get("id","")
                title         = item.get("title","Unknown")
                cur_price     = float(item.get("current_price",0) or 0)
                time_left     = item.get("time_left","")
                image_url     = item.get("image_url","")
                listing_url   = item.get("listing_url","")
                val_used_low  = float(item.get("value_used_low",0) or 0)
                val_used_hi   = float(item.get("value_used_high",0) or 0)
                val_new_low   = float(item.get("value_new_low",0) or 0)
                val_new_hi    = float(item.get("value_new_high",0) or 0)
                val_status    = item.get("value_status","pending")
                favorited     = item.get("favorited",False)
                ai_desc       = item.get("ai_description","")
                ai_conf       = item.get("ai_confidence","")
                val_source    = item.get("value_source","")
                is_gemini     = val_source == "gemini_vision"

                margin = (val_used_hi - cur_price) if val_used_hi > 0 else 0
                if val_status == "done" and val_used_hi > 0:
                    border_color = "#16a34a" if margin > 0 else "#dc2626"
                    margin_label = f"↑ ${margin:.0f} margin" if margin > 0 else f"↓ ${abs(margin):.0f} above market"
                    margin_color = "#16a34a" if margin > 0 else "#dc2626"
                else:
                    border_color = "#e2e8f0"
                    margin_label = ""
                    margin_color = "#94a3b8"

                st.markdown(
                    f"<div style='background:#ffffff; border:1px solid {border_color}; "
                    f"border-radius:12px; padding:0.75rem; margin-bottom:0.5rem; "
                    f"box-shadow:0 1px 3px rgba(0,0,0,0.05);'>",
                    unsafe_allow_html=True
                )

                img_col, info_col, action_col = st.columns([1, 4, 1])
                with img_col:
                    if image_url:
                        st.markdown(
                            f"<a href='{listing_url}' target='_blank'>"
                            f"<img src='{image_url}' style='width:100%; border-radius:8px; "
                            f"object-fit:cover; max-height:90px; cursor:pointer;'/></a>",
                            unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; height:80px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:1.2rem;'>🔨</div>", unsafe_allow_html=True)

                with info_col:
                    ai_badge = ""
                    if is_gemini and val_status == "done":
                        conf_color = {"high":"#16a34a","medium":"#d97706","low":"#dc2626"}.get(ai_conf,"#64748b")
                        ai_badge = f"<span style=\'background:#f0fdf4; color:{conf_color}; border:1px solid #bbf7d0; border-radius:4px; font-size:0.6rem; font-weight:600; padding:1px 6px; margin-left:6px;\'>🤖 AI Vision</span>"

                    st.markdown(f"<div style=\'color:#0f172a; font-size:0.85rem; font-weight:600; margin-bottom:4px; line-height:1.3;\'>{title[:120]}{ai_badge}</div>", unsafe_allow_html=True)

                    if ai_desc and ai_desc.lower()[:30] != title.lower()[:30]:
                        st.markdown(f"<div style=\'color:#475569; font-size:0.76rem; margin-bottom:5px; background:#f8fafc; border-left:3px solid #cbd5e1; padding:4px 8px; border-radius:0 6px 6px 0;\'>📝 {ai_desc}</div>", unsafe_allow_html=True)

                    price_str = f"${cur_price:.2f}" if cur_price > 0 else "No bids"
                    time_str  = f" · ⏱ {time_left}" if time_left else ""
                    if val_status == "done" and val_used_hi > 0:
                        val_str  = f"Used: ${val_used_low:.0f}–${val_used_hi:.0f} &nbsp;·&nbsp; New: ${val_new_low:.0f}–${val_new_hi:.0f}"
                        src_icon = "🤖" if is_gemini else "📦"
                    elif val_status == "pending":
                        val_str = "⏳ Looking up value..."
                        src_icon = ""
                    else:
                        val_str  = "Value unavailable"
                        src_icon = ""

                    st.markdown(f"""
                    <div style='display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:3px;'>
                        <span style='color:#0f172a; font-size:1rem; font-weight:700;'>{price_str}</span>
                        <span style='color:#64748b; font-size:0.75rem;'>{time_str}</span>
                        {f"<span style='color:{margin_color}; font-size:0.72rem; font-weight:600;'>{margin_label}</span>" if margin_label else ""}
                    </div>
                    <div style='color:#64748b; font-size:0.72rem;'>{src_icon} Est. value: {val_str}</div>
                    """, unsafe_allow_html=True)

                with action_col:
                    fav_label = "❤️" if favorited else "🤍"
                    if st.button(fav_label, key=f"fav_{item_id}", use_container_width=True):
                        try:
                            supabase.table("auction_items").update({"favorited": not favorited}).eq("id", item_id).execute()
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                    if listing_url:
                        st.markdown(
                            f"<a href='{listing_url}' target='_blank' style='display:block; text-align:center; "
                            f"background:#eff6ff; border:1px solid #93c5fd; border-radius:6px; padding:5px 8px; "
                            f"color:#1d4ed8; font-size:0.7rem; font-weight:600; text-decoration:none; margin-top:4px;'>View ↗</a>",
                            unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

    if not sessions and st.session_state.auction_active_session is None:
        st.markdown("""
        <div style='text-align:center; padding:3rem 0; color:#94a3b8;'>
            <div style='font-size:3rem; margin-bottom:0.75rem;'>🔨</div>
            <div style='color:#475569; font-size:1rem; font-weight:500; margin-bottom:0.4rem;'>No auction scanned yet</div>
            <div style='font-size:0.82rem;'>Paste an auction URL above and click Scan.<br>Works with BidSpotter, Purple Wave, IronPlanet, GovPlanet, and more.</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='page-content'>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
