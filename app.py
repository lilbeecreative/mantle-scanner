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
    .stApp { background-color: #0f1117; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    hr { border-color: #e2e8f0 !important; margin: 0.75rem 0; }

    [data-testid="stTextInput"] input {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #e2e8f0 !important;
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
        color: #e2e8f0 !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        height: 34px !important;
    }
    [data-testid="stSelectbox"] > div > div {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #e2e8f0 !important;
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
        border: 1px solid #2d3348 !important;
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
    .tab-batch     [data-testid="baseButton-primary"] { background: #0891b2 !important; }
    .tab-auction   [data-testid="baseButton-primary"] { background: #b45309 !important; }
    .tab-settings  [data-testid="baseButton-primary"] { background: #475569 !important; }

    /* Start scanning button - green with glow */
    div[data-testid="stButton"]:has(> button[kind="primary"]) button[kind="primary"] {
        transition: box-shadow 0.2s ease;
    }
    /* Expander dark mode - high contrast */
    [data-testid="stExpander"] {
        background: #1e2130 !important;
        border: 1px solid #3d4663 !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary {
        background: #2d3348 !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
    }
    [data-testid="stExpander"] summary span p {
        color: #e2e8f0 !important;
        font-size: 12px !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: #3d4663 !important;
    }
    [data-testid="stExpander"] summary svg {
        fill: #94a3b8 !important;
    }
    [data-testid="stExpander"] > div > div {
        background: #1e2130 !important;
        padding: 8px 4px !important;
    }
    /* Force black text inside all input fields (white bg) */
    [data-testid="stTextInput"] input {
        background: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    [data-testid="stSelectbox"] > div > div {
        background: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    [data-testid="stSelectbox"] option {
        background: #ffffff !important;
        color: #0f172a !important;
    }
    [data-testid="stNumberInput"] input {
        background: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    [data-testid="stTextArea"] textarea {
        background: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    [data-baseweb="select"] div {
        background: #ffffff !important;
        color: #0f172a !important;
    }
    [data-baseweb="popover"] li {
        color: #0f172a !important;
        background: #ffffff !important;
    }
    [data-testid="stWidgetLabel"] p {
        color: #94a3b8 !important;
        font-size: 11px !important;
    }
    /* Tile grid quantity buttons */
    [data-testid="stButton"] button[kind="secondary"]:has(> div > p:only-child) {
        font-size: 16px !important;
        font-weight: 900 !important;
        padding: 4px !important;
    }

    .field-label {
        color: #64748b;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 3px;
        font-weight: 600;
    }
    .batch-card {
        background: #1e2130;
        border: 1px solid #2d3348;
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
        background: #1e2130;
        border: 1px solid #2d3348;
        border-radius: 14px;
        padding: 1.5rem 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    /* ---- MOBILE RESPONSIVE ---- */
    @media (max-width: 768px) {
        .page-content { padding: 0.5rem 0.6rem !important; }

        /* Toolbar wraps on mobile */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 4px !important;
        }

        /* Buttons full width on mobile */
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] {
            font-size: 0.72rem !important;
            padding: 0.25rem 0.4rem !important;
            min-height: 36px !important;
        }

        /* Compact inputs on mobile */
        [data-testid="stTextInput"] input {
            font-size: 0.9rem !important;
            height: 40px !important;
        }

        /* Item cards full width */
        .item-card { padding: 0.5rem !important; }

        /* Stat tiles smaller on mobile */
        [data-testid="stMetric"] { padding: 0.5rem !important; }

        /* Hide sidebar */
        [data-testid="stSidebar"] { display: none !important; }

        /* Camera input full width */
        [data-testid="stCameraInput"] video,
        [data-testid="stCameraInput"] canvas {
            width: 100% !important;
            max-height: 60vh !important;
        }

        /* Columns stack on mobile */
        [data-testid="stHorizontalBlock"] > div {
            min-width: 100px !important;
        }

        /* Images in cards */
        img { max-height: 120px !important; }

        /* Reduce font sizes */
        .section-label { font-size: 0.58rem !important; }
        .field-label   { font-size: 0.6rem !important; }
    }

    @media (max-width: 480px) {
        /* Extra small phones */
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] {
            font-size: 0.65rem !important;
        }
        .page-content { padding: 0.4rem !important; }
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

def photo_url(photo_id: str, thumb: bool = False) -> str:
    if not photo_id or str(photo_id) in ("0", "", "nan"):
        return ""
    if thumb:
        # Direct URL — preserves EXIF orientation
        return f"{SUPABASE_URL}/storage/v1/object/public/part-photos/{photo_id}"
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
    schedule_time = (datetime.now(timezone.utc) + timedelta(days=19)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

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
    <SellerProfiles>
      <SellerShippingProfile>
        <ShippingProfileID>215936699022</ShippingProfileID>
      </SellerShippingProfile>
      <SellerReturnProfile>
        <ReturnProfileID>139181210022</ReturnProfileID>
      </SellerReturnProfile>
      <SellerPaymentProfile>
        <PaymentProfileID>258479922022</PaymentProfileID>
      </SellerPaymentProfile>
    </SellerProfiles>
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
        print(f"eBay response status: {resp.status_code}")
        print(f"eBay FULL response: {resp.text}")

        root = ET.fromstring(resp.text)
        ns   = {"e": "urn:ebay:apis:eBLBaseComponents"}

        ack = root.findtext("e:Ack", namespaces=ns) or ""

        # Always try to get ItemID first — present on success AND warning
        item_id = root.findtext("e:ItemID", namespaces=ns) or ""

        if item_id:
            # Got an item ID — listing was created (warnings are non-fatal)
            return {"success": True, "item_id": item_id}
        elif ack == "Failure":
            errors = root.findall(".//e:Error", ns)
            fatal  = [e for e in errors if e.findtext("e:SeverityCode", namespaces=ns) == "Error"]
            msgs      = [e.findtext("e:ShortMessage", namespaces=ns) or "" for e in fatal] or                         [e.findtext("e:ShortMessage", namespaces=ns) or "" for e in errors]
            long_msgs = [e.findtext("e:LongMessage", namespaces=ns) or "" for e in fatal] or                         [e.findtext("e:LongMessage", namespaces=ns) or "" for e in errors]
            full_error = " | ".join(filter(None, msgs))
            full_long  = " | ".join(filter(None, long_msgs))
            return {"success": False, "error": f"{full_error} — {full_long}" if full_long else full_error or resp.text[:300]}
        else:
            return {"success": False, "error": f"Ack={ack}, no ItemID returned. Response: {resp.text[:500]}"}

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

EBAY_DESCRIPTION_CSV = """Shipped primarily with UPS and sometimes USPS. If you have special packing or shipping needs, please send a message.

This item is sold in "as-is" condition. The seller assumes no liability for the use, operation, or installation of this product. Due to the technical nature of this equipment, the buyer is responsible for having the item professionally inspected and installed by a certified technician prior to use."""

@st.cache_data(ttl=0, show_spinner=False)
def build_ebay_csv(df: pd.DataFrame) -> bytes:
    output = io.StringIO()
    output.write('#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,\n')
    output.write('#INFO Action and Category ID are required fields.,,,,,,,,,,\n')
    output.write('#INFO After you\'ve successfully uploaded your draft complete your drafts here: https://www.ebay.com/sh/lst/drafts,,,,,,,,,,\n')
    output.write('#INFO,,,,,,,,,,\n')
    output.write('Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8),Custom label (SKU),Category ID,Title,UPC,Price,Quantity,Item photo URL,Condition ID,Description,Format\n')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    for _, row in df.iterrows():
        item_id        = str(row.get("id", ""))
        category_id    = str(row.get("ebay_category_id", "")).replace(".0", "")
        title          = str(row.get("title", ""))[:80]
        price          = f"{float(row.get('price', 0)):.2f}"
        quantity       = str(int(row.get("quantity", 1)))
        condition      = str(row.get("condition", "used") or "used").strip().lower()
        # eBay condition IDs: 1000=New, 2000=Refurbished, 3000=Used
        if condition in ("new", "brand new"):
            ebay_condition = "1000"
        elif condition in ("refurbished", "seller refurbished", "manufacturer refurbished"):
            ebay_condition = "2000"
        else:
            ebay_condition = "3000"

        # Fetch ALL photos for this listing group
        main_photo = str(row.get("photo_id", ""))
        pic_urls = []
        try:
            gp = supabase.table("group_photos").select("group_id").eq("photo_id", main_photo).execute()
            if gp.data and gp.data[0].get("group_id"):
                group_id = gp.data[0]["group_id"]
                all_photos = supabase.table("group_photos").select("photo_id").eq("group_id", group_id).execute()
                pic_urls = [photo_url(p["photo_id"]) for p in (all_photos.data or []) if p.get("photo_id")]
        except Exception as csv_err:
            import traceback; traceback.print_exc()
        if not pic_urls and main_photo:
            pic_urls = [photo_url(main_photo)]

        # eBay accepts up to 12 photos, pipe-separated in the URL column
        pic_url_str = "|".join(pic_urls[:12])
        if len(pic_urls) > 1: print(f"CSV: {len(pic_urls)} photos for {main_photo}")

        writer.writerow([
            "Draft",
            "",                    # Custom SKU — always blank
            category_id,
            title,
            "",                    # UPC
            price,
            quantity,
            pic_url_str,           # All photos pipe-separated
            ebay_condition,
            EBAY_DESCRIPTION_CSV,  # Standard description on every listing
            "FixedPrice",          # Format
        ])
    return output.getvalue().encode("utf-8")

# ------------------------------------------------------------------ #
#  DATA FETCH
# ------------------------------------------------------------------ #

@st.cache_data(ttl=300)
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
<div style='background:#1e2130; border-bottom:1px solid #2d3348; padding:0 1.5rem;
display:flex; align-items:center; justify-content:space-between; height:50px;
box-shadow: 0 1px 4px rgba(0,0,0,0.06);'>
    <div style='color:#e2e8f0; font-size:1rem; font-weight:700; letter-spacing:-0.02em;
    display:flex; align-items:center; gap:8px;'>
        <div style='width:8px; height:8px; background:#2563eb; border-radius:50%;'></div>
        Lister AI
    </div>
    <div style='color:#64748b; font-size:0.68rem; letter-spacing:0.08em; font-weight:500;'>EMPLOYEE DASHBOARD</div>
</div>
""", unsafe_allow_html=True)

# Color-coded nav toolbar — separated from page content
st.markdown("<div style='background:#161925; border-bottom:1px solid #2d3348; padding:4px 8px;'>", unsafe_allow_html=True)
t1, t3, t7 = st.columns([2, 1.5, 1.5])
with t1:
    st.markdown("<div class='tab-dashboard'>", unsafe_allow_html=True)
    if st.button("📊  Batch Dashboard", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "dashboard" else "secondary"):
        st.session_state.active_tab = "dashboard"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t3:
    st.markdown("<div class='tab-batch'>", unsafe_allow_html=True)
    if st.button("📁  Batch Upload", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "batch" else "secondary"):
        st.session_state.active_tab = "batch"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with t7:
    with st.popover("⬇️ Spreadsheet", use_container_width=True):
        if not df_top.empty:
            csv_df = df_top.copy()
            if "created_at" in csv_df.columns:
                csv_df["created_at"] = csv_df["created_at"].astype(str)
            st.download_button(
                label="📄  Raw Data Spreadsheet",
                data=csv_df.to_csv(index=False).encode("utf-8"),
                file_name="listerai_inventory.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                label="🛒  eBay Upload Sheet",
                data=build_ebay_csv(df_top),
                file_name=f"listerai_ebay_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.markdown("<div style='color:#9ca3af; font-size:0.82rem;'>No items yet.</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ================================================================== #
#  TAB: BATCH UPLOAD
# ================================================================== #

if st.session_state.active_tab == "batch":

    from PIL import Image, ExifTags
    import io as _io

    def fix_rot_b(img_bytes):
        try:
            from PIL import ImageOps
            img = Image.open(_io.BytesIO(img_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        except Exception as _re:
            print(f"⚠️  Rotation fix failed: {_re}")
            return img_bytes

    def file_upload_photo(f_bytes, group_id, idx):
        fixed = fix_rot_b(f_bytes)
        dt = datetime.now()
        fn = f"{dt.strftime('%d%m%y')}_{dt.strftime('%H%M%S')}_{idx}.jpg"
        supabase.storage.from_("part-photos").upload(path=fn, file=fixed, file_options={"content-type":"image/jpeg","upsert":"true"})
        supabase.table("group_photos").insert({"group_id":group_id,"photo_id":fn}).execute()

    def create_file_group():
        result = supabase.table("listing_groups").insert({
            "session_id": st.session_state.file_batch_id,
            "status": "waiting", "quantity": 1,
            "condition": st.session_state.file_condition
        }).execute()
        return result.data[0]["id"]

    for k,v in [("file_batch_id",None),("file_condition","used"),("file_items",[]),("file_group_id",None),("file_qty",1)]:
        if k not in st.session_state: st.session_state[k] = v

    # ── NO ACTIVE BATCH — just condition + start ──────────────────
    if st.session_state.file_batch_id is None:
        st.markdown("""
        <div style='text-align:center; padding:1.5rem 0 1rem;'>
            <div style='font-size:2.5rem; margin-bottom:0.4rem;'>📸</div>
            <div style='color:#e2e8f0; font-size:1.1rem; font-weight:700;'>Batch Upload</div>
            <div style='color:#64748b; font-size:0.82rem; margin-top:0.3rem;'>
                Tap <b>Take Photo</b> or select from library. Repeat for each item.
            </div>
        </div>""", unsafe_allow_html=True)

        # Condition — prominent toggle
        st.markdown("<div class='field-label' style='text-align:center; margin-bottom:6px;'>All items in this batch are:</div>", unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            if st.button(
                "✓  Used" if st.session_state.file_condition=="used" else "Used",
                use_container_width=True, key="file_cond_used",
                type="primary" if st.session_state.file_condition=="used" else "secondary"
            ):
                st.session_state.file_condition = "used"; st.rerun()
        with cb:
            if st.button(
                "✓  New" if st.session_state.file_condition=="new" else "New",
                use_container_width=True, key="file_cond_new",
                type="primary" if st.session_state.file_condition=="new" else "secondary"
            ):
                st.session_state.file_condition = "new"; st.rerun()

        st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

        # Big start button
        st.markdown("""
        <style>
        .start-scan-btn button {
            background: #16a34a !important;
            border-color: #15803d !important;
            box-shadow: 0 4px 18px rgba(22,163,74,0.45) !important;
            font-size: 17px !important;
            font-weight: 700 !important;
            height: 58px !important;
            letter-spacing: -0.2px !important;
        }
        .start-scan-btn button:hover {
            background: #15803d !important;
            box-shadow: 0 6px 24px rgba(22,163,74,0.55) !important;
        }
        </style>
        <div class="start-scan-btn">
        """, unsafe_allow_html=True)
        if st.button("🚀  Start Scanning", use_container_width=True, type="primary", key="start_file_batch"):
            st.session_state.file_batch_id = str(uuid.uuid4())
            st.session_state.file_items    = []
            st.session_state.file_qty      = 1
            # Auto-create first item group immediately
            st.session_state.file_group_id = create_file_group()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── ACTIVE BATCH ──────────────────────────────────────────────
    else:
        total_f   = len(st.session_state.file_items)
        cond_clr  = "#22c55e" if st.session_state.file_condition=="new" else "#0891b2"

        # Mini status bar
        col_status, col_end = st.columns([4, 1])
        with col_status:
            st.markdown(f"""
            <div style='background:#1e2130; border:1px solid #2d3348; border-left:4px solid {cond_clr};
            border-radius:8px; padding:0.5rem 0.85rem; margin-bottom:0.6rem;'>
                <span style='color:#e2e8f0; font-size:0.85rem; font-weight:600;'>
                    {st.session_state.file_condition.title()} Batch
                </span>
                <span style='color:#64748b; font-size:0.75rem; margin-left:8px;'>
                    {total_f} item{"s" if total_f != 1 else ""} scanned
                </span>
            </div>""", unsafe_allow_html=True)
        with col_end:
            if st.button("🏁 End", use_container_width=True, type="secondary", key="file_end_batch"):
                st.session_state.file_batch_id = None
                st.session_state.file_items    = []
                st.session_state.file_group_id = None
                st.cache_data.clear(); st.rerun()

        # Previous items (collapsed, just count)
        if st.session_state.file_items:
            with st.expander(f"✅  {total_f} item{'s' if total_f != 1 else ''} sent to scanner", expanded=False):
                for i, item in enumerate(reversed(st.session_state.file_items)):
                    st.markdown(
                        f"<div style='color:#64748b; font-size:0.78rem; padding:2px 0;'>"
                        f"Item {total_f-i} · {item.get('photo_count',0)} photos · Qty {item.get('qty',1)}</div>",
                        unsafe_allow_html=True)

        # ── CURRENT ITEM ─────────────────────────────────────────
        if st.session_state.file_group_id:
            item_num = total_f + 1
            st.markdown(f"""
            <div style='background:#0d1b38; border:1.5px solid #0891b2; border-radius:10px;
            padding:0.6rem 0.9rem; margin-bottom:0.5rem; display:flex; justify-content:space-between; align-items:center;'>
                <span style='color:#e2e8f0; font-size:0.9rem; font-weight:700;'>Item {item_num}</span>
                <span style='color:#0891b2; font-size:0.75rem; font-weight:500;'>Take or upload photos below</span>
            </div>""", unsafe_allow_html=True)

            # File uploader — this is the MAIN action, always visible
            st.markdown("<div style='color:#64748b;font-size:0.72rem;margin-bottom:4px;'>📐 Tip: shoot in landscape (horizontal) for best results</div>", unsafe_allow_html=True)
            cam_col, up_col = st.columns([1,1])
            with cam_col:
                camera_photo = st.camera_input("📷 Take photo", key=f"cam_{st.session_state.file_group_id}", label_visibility="collapsed")
            with up_col:
                st.markdown("<div style='font-size:0.75rem;color:#64748b;margin-bottom:4px;'>Or upload from gallery</div>", unsafe_allow_html=True)

            uploaded_files = st.file_uploader(
                "Tap to take photo or select from library",
                type=["jpg","jpeg","png","heic"],
                accept_multiple_files=True,
                key=f"fup_{st.session_state.file_group_id}",
                label_visibility="collapsed"
            )
            if camera_photo and camera_photo not in (uploaded_files or []):
                uploaded_files = list(uploaded_files or []) + [camera_photo]
            if uploaded_files and len(uploaded_files) > 10:
                st.warning("Max 10 photos — using first 10.")
                uploaded_files = uploaded_files[:10]

            # Thumbnails
            if uploaded_files:
                st.markdown(
                    f"<div style='color:#0891b2; font-size:0.75rem; font-weight:600; margin:4px 0;'>"
                    f"📷 {len(uploaded_files)} photo(s) ready</div>",
                    unsafe_allow_html=True)
                thumb_cols = st.columns(min(len(uploaded_files), 5))
                for col, f in zip(thumb_cols, uploaded_files):
                    with col: st.image(f, use_container_width=True)

            # Quantity — compact stepper
            st.markdown("<div class='field-label' style='margin-top:0.6rem;'>How many of this item?</div>", unsafe_allow_html=True)
            q1, q2, q3 = st.columns([1, 2, 1])
            with q1:
                if st.button("−", key="fq_minus", use_container_width=True):
                    if st.session_state.file_qty > 1: st.session_state.file_qty -= 1; st.rerun()
            with q2:
                st.markdown(
                    f"<div style='text-align:center; font-size:1.5rem; font-weight:700; color:#e2e8f0; padding-top:2px;'>"
                    f"{st.session_state.file_qty}</div>", unsafe_allow_html=True)
            with q3:
                if st.button("+", key="fq_plus", use_container_width=True):
                    st.session_state.file_qty += 1; st.rerun()

            st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

            # Done button — full width, prominent
            done_dis = not uploaded_files
            btn_label = f"✓  Done — Next Item →" if not done_dis else "📷  Select photos above first"
            if st.button(btn_label, use_container_width=True, type="primary",
                         disabled=done_dis, key="file_done_btn"):
                with st.spinner(f"Uploading {len(uploaded_files)} photo(s)..."):
                    group_id = st.session_state.file_group_id
                    upped = 0
                    for i, f in enumerate(uploaded_files[:10]):
                        try:
                            file_upload_photo(f.read(), group_id, i)
                            upped += 1
                        except Exception as e:
                            st.error(f"Photo {i+1} failed: {e}")
                    supabase.table("listing_groups").update({
                        "condition": st.session_state.file_condition,
                        "quantity":  st.session_state.file_qty,
                        "status":    "pending"
                    }).eq("id", group_id).execute()
                    st.session_state.file_items.append({
                        "group_id": group_id, "condition": st.session_state.file_condition,
                        "qty": st.session_state.file_qty, "status": "pending", "photo_count": upped
                    })
                    # Auto-create next item group immediately
                    st.session_state.file_group_id = create_file_group()
                    st.session_state.file_qty = 1
                    st.cache_data.clear(); st.rerun()

            # Cancel this item
            if st.button("✗  Cancel this item", use_container_width=True,
                         type="secondary", key="file_cancel_item"):
                try: supabase.table("listing_groups").delete().eq("id", st.session_state.file_group_id).execute()
                except: pass
                st.session_state.file_group_id = None
                st.session_state.file_qty = 1; st.rerun()

elif st.session_state.active_tab == "dashboard":

    # One-time JS to color all +/- buttons on this tab
    st.markdown("""
    <style>
    button[data-testid="baseButton-secondary"] p { font-weight: 900 !important; }
    </style>
    <script>
    setTimeout(function() {
        document.querySelectorAll('[data-testid="stButton"] button').forEach(function(btn) {
            var txt = btn.innerText.trim();
            if (txt === '−') btn.style.color = '#dc2626';
            if (txt === '+') btn.style.color = '#16a34a';
        });
    }, 400);
    </script>
    """, unsafe_allow_html=True)

    df = fetch_listings()

    if df.empty:
        st.markdown("""
        <div style="text-align:center; padding:3rem 0; color:#64748b;">
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
                <div style='background:#1e2130; border:1px solid #2d3348; border-top:3px solid {color};
                border-radius:10px; padding:0.85rem 1.1rem; margin-bottom:0.75rem;'>
                    <div style='color:#e2e8f0; font-size:1.8rem; font-weight:700; letter-spacing:-0.03em; line-height:1;'>{val}</div>
                    <div style='color:#64748b; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:5px;'>{label}</div>
                    {sub_html}
                </div>""", unsafe_allow_html=True)

        # Clear batch button - prominent placement
        cl1, cl2 = st.columns([3, 1])
        with cl2:
            if st.button("🗑️  Clear Batch", use_container_width=True, type="secondary",
                         key="clear_batch_top"):
                st.session_state.confirm_clear = True
                st.rerun()

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
            submit_clicked = st.button(submit_label, use_container_width=True, type="primary",
                         key="ebay_submit_btn", disabled=sel_count == 0)

        if submit_clicked and sel_count > 0:
            selected_ids = [k for k, v in st.session_state.ebay_selected.items() if v]
            selected_df  = df[df["id"].astype(str).isin(selected_ids)]
            st.info(f"Submitting {len(selected_df)} listings to eBay — do not close this page...")
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
            st.session_state.ebay_selected = {}
            st.cache_data.clear()
            success_count = sum(1 for r in results if r["success"])
            if success_count > 0:
                st.success(f"✅ {success_count} listings submitted to eBay as scheduled drafts. Check Seller Hub under Scheduled Listings.")
            # Store results in session state so they persist across reruns
            st.session_state.ebay_last_results = results
            for r in results:
                if r["success"]:
                    st.success(f"✅ {r['title']} → eBay Item #{r['item_id']}")
                else:
                    st.error(f"❌ {r['title']}: {r['error']}")

        # Show persistent results from last submission
        if st.session_state.get("ebay_last_results") and not submit_clicked:
            st.markdown("<div class='section-label'>Last eBay Submission Results</div>", unsafe_allow_html=True)
            for r in st.session_state.ebay_last_results:
                if r["success"]:
                    st.success(f"✅ {r['title']} → eBay Item #{r['item_id']}")
                else:
                    st.error(f"❌ {r['title']}: {r['error']}")
            if st.button("Clear Results", key="clear_ebay_results"):
                st.session_state.ebay_last_results = []
                st.rerun()

        st.divider()
        st.markdown("<div class='section-label'>Items</div>", unsafe_allow_html=True)

        if "quantities" not in st.session_state:
            st.session_state.quantities = {}

        # Build tile data
        tiles_data = []
        for _, item in df.iterrows():
            item_id    = str(item.get("id", ""))
            pid        = str(item.get("photo_id", ""))
            title      = str(item.get("title", "Unknown"))
            price      = float(item.get("price", 0.0))
            price_note = str(item.get("price_note", "")).strip().lower()
            condition  = str(item.get("condition", "used")).strip().lower()
            category   = str(item.get("ebay_category", ""))
            cat_id     = str(item.get("ebay_category_id", "")).strip().replace(".0", "")
            price_used = float(item.get("price_used", 0.0) or 0.0)
            price_new  = float(item.get("price_new",  0.0) or 0.0)
            url        = photo_url(pid)
            ebay_item_id = str(item.get("ebay_item_id","") or "")
            ebay_status  = str(item.get("ebay_status","") or "")
            if item_id and item_id not in st.session_state.quantities:
                st.session_state.quantities[item_id] = int(item.get("quantity", 1))
            current_qty = st.session_state.quantities.get(item_id, 1)
            tiles_data.append({
                "id": item_id, "pid": pid, "title": title, "price": price,
                "price_note": price_note, "condition": condition, "category": category,
                "cat_id": cat_id, "price_used": price_used, "price_new": price_new,
                "url": url, "ebay_item_id": ebay_item_id, "ebay_status": ebay_status,
                "qty": current_qty, "item": item,
            })

        # Render tile grid — 2 cols mobile, 3 cols desktop
        # Detect mobile via screen width injected into session state
        if "screen_cols" not in st.session_state:
            st.session_state.screen_cols = 3
        st.markdown("""
        <script>
        (function() {
            var cols = window.innerWidth < 768 ? 2 : 3;
            var existing = window.sessionStorage.getItem('tile_cols');
            if (existing != cols) {
                window.sessionStorage.setItem('tile_cols', cols);
            }
        })();
        </script>
        """, unsafe_allow_html=True)

        import streamlit.components.v1 as components
        screen_w = st.session_state.get("screen_cols", 3)

        # Use CSS grid via HTML — most reliable responsive approach
        # Build all tiles as pure HTML in a responsive CSS grid
        tile_htmls = []
        for t in tiles_data:
            item_id   = t["id"]
            is_sel    = st.session_state.ebay_selected.get(item_id, False)
            cond_col  = "#16a34a" if t["condition"] == "new" else "#3b82f6"
            cond_lbl  = "NEW" if t["condition"] == "new" else "USED"
            border    = "#2563eb" if is_sel else "#2d3348"
            ref_parts = []
            if t["price_used"] > 0: ref_parts.append(f"U:${t['price_used']:.0f}")
            if t["price_new"]  > 0: ref_parts.append(f"N:${t['price_new']:.0f}")
            ref_str = "  ".join(ref_parts)

            status_badge = ""
            if t["ebay_status"] == "draft" and t["ebay_item_id"]:
                status_badge = f"<a href='https://www.ebay.com/itm/{t['ebay_item_id']}' target='_blank' style='background:rgba(37,99,235,0.8);color:#fff;border-radius:5px;font-size:9px;font-weight:700;padding:2px 6px;text-decoration:none;'>eBay</a>"
            elif t["price_note"] in ("new","used"):
                status_badge = f"<span style='background:rgba(245,158,11,0.8);color:#fff;border-radius:5px;font-size:9px;font-weight:700;padding:2px 6px;'>⚠</span>"

            thumb_src = photo_url(t['pid'], thumb=True) if t['pid'] else ""
            photo_html = f"<img src='{thumb_src}' style='position:absolute;inset:0;width:100%;height:100%;object-fit:cover;image-orientation:from-image;' loading='lazy'/>" if thumb_src else "<div style='position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:2.5rem;color:#3d4663;'>📷</div>"

            tile_htmls.append(f"""
            <div style='background:#1a1f2e;border:1.5px solid {border};border-radius:14px;
            overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.35);
            {"border-left:3px solid #2563eb;" if t["ebay_status"]=="draft" else ""}'>
              <div style='position:relative;width:100%;padding-top:100%;background:#161925;overflow:hidden;'>
                {photo_html}
                <div style='position:absolute;top:7px;left:7px;right:7px;display:flex;justify-content:space-between;align-items:flex-start;'>
                  <div style='background:rgba(0,0,0,0.65);border-radius:5px;padding:2px 7px;'>
                    <span style='color:{cond_col};font-size:9px;font-weight:700;'>{cond_lbl}</span>
                  </div>
                  <div>{status_badge}</div>
                </div>
                <div style='position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,0.85));padding:28px 10px 8px;'>
                  <div style='color:#fff;font-size:22px;font-weight:900;letter-spacing:-0.5px;line-height:1;'>${t['price']:.2f}</div>
                  {"<div style='color:#cbd5e1;font-size:10px;font-weight:600;margin-top:2px;'>" + ref_str + "</div>" if ref_str else ""}
                </div>
              </div>
              <div style='padding:10px 11px 8px;'>
                <a href='https://www.google.com/search?q={t["title"].replace(" ","+")}' target='_blank' style='font-size:13px;font-weight:700;color:#f8fafc;line-height:1.4;min-height:38px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-decoration:none;' title='Search Google'>{t["title"]} 🔍</a>
                <div style='font-size:10px;color:#475569;margin-top:3px;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis;'>{t['category']}</div>
              </div>
            </div>""")

        # Render grid via HTML — CSS handles 2 vs 3 cols automatically
        grid_html = f"""
        <style>
        .tile-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 12px;
        }}
        @media (max-width: 768px) {{
            .tile-grid {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
        }}
        </style>
        <div class="tile-grid">{''.join(tile_htmls)}</div>
        """
        st.markdown(grid_html, unsafe_allow_html=True)

        # Controls rendered below - one per item using columns
        # Use a hidden index to match tile order
        ctrl_rows = [tiles_data[i:i+3] for i in range(0, len(tiles_data), 3)]
        for row in ctrl_rows:
            cols = st.columns(3)
            for col_idx, t in enumerate(row):
                with cols[col_idx]:
                    item_id   = t["id"]
                    is_sel    = st.session_state.ebay_selected.get(item_id, False)
                    cond_col  = "#16a34a" if t["condition"] == "new" else "#2563eb"
                    cond_lbl  = "NEW" if t["condition"] == "new" else "USED"
                    border    = "1.5px solid #2563eb" if is_sel else ("1.5px solid #2563eb" if t["ebay_status"] == "draft" else "0.5px solid #e2e8f0")
                    border_l  = "3px solid #2563eb" if t["ebay_status"] == "draft" else ""
                    ref_parts = []
                    if t["price_used"] > 0: ref_parts.append(f"U:${t['price_used']:.0f}")
                    if t["price_new"]  > 0: ref_parts.append(f"N:${t['price_new']:.0f}")
                    ref_str = "  ".join(ref_parts)

                    status_badge = ""
                    if t["ebay_status"] == "draft" and t["ebay_item_id"]:
                        status_badge = f"<a href='https://www.ebay.com/itm/{t['ebay_item_id']}' target='_blank' style='background:#0d1b38;color:#2563eb;border:0.5px solid #bfdbfe;border-radius:10px;font-size:9px;font-weight:700;padding:2px 7px;text-decoration:none;'>eBay Draft</a>"
                    elif t["price_note"] in ("new","used"):
                        status_badge = f"<span style='background:#2a1f00;color:#d97706;border-radius:10px;font-size:9px;font-weight:700;padding:2px 7px;'>⚠ fallback</span>"

                    # Card wrapper
                    st.markdown(f"""
                    <div style='background:#1e2130; border:{border}; border-radius:12px; overflow:hidden; margin-bottom:2px;
                    {"border-left:" + border_l + ";" if border_l else ""}'>
                      <div style='position:relative; height:130px; background:#161925; overflow:hidden; cursor:pointer;'>
                        {"<img src='" + photo_url(t['pid'], thumb=True) + "' style='width:100%;height:100%;object-fit:cover;image-orientation:from-image;display:block;'/>" if t['pid'] else "" if t['url'] else "<div style='width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2rem;color:#cbd5e1;'>📷</div>"}
                        <div style='position:absolute;top:6px;right:6px;'>{status_badge}</div>
                      </div>
                      <div style='padding:8px 10px 4px;'>
                        <a href='https://www.google.com/search?q={t["title"].replace(" ","+")}' target='_blank' style='font-size:12px;font-weight:600;color:#e2e8f0;line-height:1.3;min-height:32px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-decoration:none;' title='Search Google'>{t['title']} 🔍</a>
                        <div style='font-size:10px;color:#64748b;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{t['category']}</div>
                        <div style='display:flex;align-items:baseline;justify-content:space-between;margin-top:6px;'>
                          <div style='font-size:18px;font-weight:800;color:#e2e8f0;letter-spacing:-0.3px;'>${t['price']:.2f}</div>
                          <div style='font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;background:{"#f0fdf4" if t["condition"]=="new" else "#eff6ff"};color:{cond_col};'>{cond_lbl}</div>
                        </div>
                        {"<div style='font-size:10px;color:#64748b;margin-top:2px;'>" + ref_str + "</div>" if ref_str else ""}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Checkbox for eBay selection
                    checked = st.checkbox("Select for eBay", value=is_sel,
                                          key=f"chk_{item_id}", label_visibility="collapsed")
                    if checked != is_sel:
                        st.session_state.ebay_selected[item_id] = checked
                        st.rerun()  # no cache clear needed

                    # Quantity stepper with red/green symbols
                    q1, q2, q3 = st.columns([1, 1, 1])
                    with q1:
                        if st.button("−", key=f"minus_{item_id}", use_container_width=True,
                                     help="Decrease quantity"):
                            new_qty = max(0, t["qty"] - 1)
                            st.session_state.quantities[item_id] = new_qty
                            update_field(item_id, "quantity", new_qty)
                            st.rerun()
                    with q2:
                        st.markdown(
                            f"<div style='text-align:center;font-size:14px;font-weight:700;color:#e2e8f0;padding-top:6px;'>{t['qty']}</div>",
                            unsafe_allow_html=True)
                    with q3:
                        if st.button("+", key=f"plus_{item_id}", use_container_width=True,
                                     help="Increase quantity"):
                            new_qty = t["qty"] + 1
                            st.session_state.quantities[item_id] = new_qty
                            update_field(item_id, "quantity", new_qty)
                            st.rerun()



                    # Re-scan button
                    if st.button("🔄 Re-scan", key=f"rescan_{item_id}",
                                 use_container_width=True, type="secondary",
                                 help="Re-submit this item to the scanner"):
                        try:
                            # Reset the listing group to pending so scanner picks it up
                            grp = supabase.table("group_photos")                                .select("group_id")                                .eq("photo_id", t["pid"])                                .limit(1).execute()
                            if grp.data:
                                gid = grp.data[0]["group_id"]
                                supabase.table("listing_groups")                                    .update({"status": "pending"})                                    .eq("id", gid).execute()
                                supabase.table("listings")                                    .update({"status": "pending", "title": "Scanning..."})                                    .eq("id", item_id).execute()
                                st.cache_data.clear()
                                st.success(f"Resubmitted — scanner will process shortly")
                                st.rerun()
                            else:
                                st.warning("Could not find original photos for this item")
                        except Exception as e:
                            st.error(f"Re-scan failed: {e}")

                    # Expandable detail
                    with st.expander("✏️  Edit details", expanded=False):
                        new_title = st.text_input("Title", value=t["title"],
                            key=f"title_{item_id}", label_visibility="visible")
                        if new_title.strip() and new_title.strip() != t["title"]:
                            update_field(item_id, "title", new_title.strip()[:80])
                            st.cache_data.clear()

                        pc1, pc2 = st.columns(2)
                        with pc1:
                            price_key = f"price_{item_id}_{round(t['price'],2)}"
                            price_input = st.text_input("Price", value=f"{t['price']:.2f}",
                                key=price_key)
                            try:
                                new_price = round(float(price_input.replace("$","").strip()), 2)
                                if new_price != round(t["price"], 2):
                                    update_field(item_id, "price", new_price)
                                    update_field(item_id, "price_note", "")
                                    st.cache_data.clear()
                            except ValueError:
                                pass
                        with pc2:
                            new_cond = st.selectbox("Condition", ["used","new"],
                                index=1 if t["condition"]=="new" else 0,
                                key=f"cond_{item_id}")
                            if new_cond != t["condition"]:
                                price_updated = switch_condition(item_id, new_cond, t["price_used"], t["price_new"])
                                if not price_updated:
                                    st.toast("Condition updated — update price manually", icon="⚠️")
                                st.cache_data.clear()
                                st.rerun()

                        matched_label = find_best_label(t["category"], t["cat_id"])
                        options = ["— search or select —"] + CATEGORY_LABELS
                        current_index = options.index(matched_label) if matched_label in options else 0
                        selected_label = st.selectbox("eBay Category", options=options,
                            index=current_index, key=f"cat_{item_id}")
                        if selected_label != "— search or select —" and selected_label != matched_label:
                            supabase.table("listings").update({
                                "ebay_category":    LABEL_TO_NAME[selected_label],
                                "ebay_category_id": LABEL_TO_ID[selected_label],
                            }).eq("id", item_id).execute()
                            st.cache_data.clear()
                            st.rerun()

        st.divider()

        # Issues        st.divider()

        # Issues
        st.markdown("<div class='section-label'>Issues</div>", unsafe_allow_html=True)
        issues_df = fetch_issues()

        if issues_df.empty:
            st.markdown("<p style='color:#64748b; font-size:0.8rem;'>No issues submitted yet.</p>", unsafe_allow_html=True)
        else:
            for _, issue in issues_df.iterrows():
                issue_id  = str(issue.get("id", ""))
                desc      = str(issue.get("description", ""))
                submitted = issue.get("submitted_at", "")
                if hasattr(submitted, "strftime"):
                    submitted = submitted.strftime("%b %d %I:%M %p")
                st.markdown(f"""
                <div style='background:#161925; border:1px solid #2d3348; border-radius:8px;
                padding:0.6rem 0.9rem; margin-bottom:0.4rem;'>
                    <div style='color:#64748b; font-size:0.65rem; margin-bottom:3px;'>{submitted}</div>
                    <div style='color:#e2e8f0; font-size:0.82rem;'>{desc}</div>
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
    if "auction_enrich_running" not in st.session_state:
        st.session_state.auction_enrich_running = False
    if "auction_enrich_stop" not in st.session_state:
        st.session_state.auction_enrich_stop = False

    # ---- Load sessions from DB ----------------------------------- #
    @st.cache_data(ttl=60)
    def fetch_auction_sessions():
        try:
            r = supabase.table("auction_sessions").select("*").order("created_at", desc=True).execute()
            data = r.data or []
            # Active sessions first, archived at bottom
            active   = [s for s in data if s.get("status","active") != "archived"]
            archived = [s for s in data if s.get("status","active") == "archived"]
            return active + archived
        except Exception:
            return []

    @st.cache_data(ttl=60)
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
        <div style='color:#e2e8f0; font-size:1.1rem; font-weight:700; margin-bottom:2px;'>🔨 Auction Scanner</div>
        <div style='color:#64748b; font-size:0.8rem;'>Paste any auction URL — scrapes listings and looks up market values automatically. Scans are saved and can be revisited anytime.</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Saved sessions list + new scan controls ---------------- #
    if sessions:
        sess_col, new_col = st.columns([4, 1])
        with sess_col:
            session_labels = {
                s["session_id"]: (
                    f"📦 [Archived] {s.get('label','Scan')}  ·  {s.get('item_count',0)} items  ·  {s['created_at'][:10]}"
                    if s.get("status") == "archived"
                    else f"{s.get('label','Scan')}  ·  {s.get('item_count',0)} items  ·  {s['created_at'][:10]}"
                )
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
            st.session_state.auction_enrich_stop = False
            ids = st.session_state.get("auction_enrich_ids", [i["id"] for i in items if i.get("value_status") == "pending"])
            total_e = len(ids)
            if total_e > 0:
                import threading
                st.session_state.auction_enrich_running = True
                st.info(f"🔍 Researching {total_e} items in the background. Use Stop button to pause.", icon="⏳")

                def run_enrich(item_ids, stop_flag):
                    try:
                        from auction_scraper import enrich_values
                        for i, item_id in enumerate(item_ids):
                            if stop_flag["stop"]:
                                print("Enrichment stopped by user")
                                break
                            from auction_scraper import enrich_values as ev
                            ev([item_id])
                    except Exception as e:
                        print(f"Enrich error: {e}")
                    finally:
                        stop_flag["running"] = False

                stop_flag = {"stop": False, "running": True}
                st.session_state._enrich_stop_flag = stop_flag
                t = threading.Thread(target=run_enrich, args=(ids, stop_flag), daemon=True)
                t.start()

        # Session action bar
        source_url = session_info.get("source_url","") if session_info else ""
        last_ref   = session_info.get("last_refreshed","")[:10] if session_info else ""
        total_items   = len(items)
        valued_items  = sum(1 for i in items if i.get("value_status") == "done")
        favorited_cnt = sum(1 for i in items if i.get("favorited"))

        st.markdown(f"""
        <div style='background:#1e2130; border:1px solid #2d3348; border-radius:10px;
        padding:0.65rem 1rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='color:#e2e8f0; font-size:0.82rem; font-weight:600; margin-bottom:2px;'>{source_url[:60]}</div>
                <div style='color:#64748b; font-size:0.7rem;'>
                    {total_items} listings · {valued_items} valued · {favorited_cnt} favorited · last refreshed {last_ref}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons
        pending = [i for i in items if i.get("value_status") == "pending"]
        is_running = getattr(st.session_state, "_enrich_stop_flag", {}).get("running", False)

        ac1, ac2, ac3, ac4 = st.columns([2, 1.5, 1.5, 1])
        with ac1:
            if st.button("🔄  Refresh Scan", use_container_width=True, type="primary", key="auction_refresh"):
                with st.spinner("Re-scraping..."):
                    try:
                        from auction_scraper import scrape_and_store
                        supabase.table("auction_items").delete().eq("session_id", session_id).execute()
                        new_ids = scrape_and_store(source_url, session_id, [1])
                        supabase.table("auction_sessions").update({
                            "item_count": len(new_ids),
                            "last_refreshed": datetime.now().isoformat(),
                        }).eq("session_id", session_id).execute()
                        st.session_state.auction_auto_enrich = True
                        st.session_state.auction_enrich_ids  = new_ids
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Refresh failed: {e}")

        with ac2:
            if is_running:
                # Running — show Stop button
                if st.button("⏹  Stop Research", use_container_width=True, type="secondary", key="auction_stop"):
                    flag = getattr(st.session_state, "_enrich_stop_flag", {})
                    flag["stop"] = True
                    st.session_state.auction_enrich_running = False
                    st.info("Research stopped. Use Resume to continue.")
                    st.rerun()
            elif pending:
                # Stopped/paused — show Resume button
                if st.button(f"▶  Resume ({len(pending)})", use_container_width=True,
                              type="secondary", key="auction_resume"):
                    st.session_state.auction_auto_enrich = True
                    st.session_state.auction_enrich_ids  = [i["id"] for i in pending]
                    st.rerun()

        with ac3:
            # Archive session (keeps data, stops enrichment, marks archived)
            if st.button("📦  Archive", use_container_width=True, type="secondary", key="auction_archive"):
                try:
                    # Stop enrichment thread if running
                    flag = getattr(st.session_state, "_enrich_stop_flag", {})
                    if flag:
                        flag["stop"] = True
                    st.session_state.auction_enrich_running = False
                    st.session_state.auction_auto_enrich    = False
                    supabase.table("auction_sessions").update(
                        {"status": "archived"}
                    ).eq("session_id", session_id).execute()
                    st.session_state.auction_active_session = None
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Archive failed: {e}")

        with ac4:
            # Permanent delete
            if st.button("🗑️", use_container_width=True, type="secondary", key="auction_delete",
                         help="Permanently delete this scan"):
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
                    <div style='background:#1e2130; border:1px solid #2d3348; border-top:3px solid {color};
                    border-radius:10px; padding:0.65rem 1rem; margin-bottom:0.75rem;'>
                        <div style='color:#e2e8f0; font-size:1.5rem; font-weight:700; line-height:1;'>{val}</div>
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

            st.markdown(f"<p style='color:#64748b; font-size:0.75rem; margin-bottom:0.5rem;'>Showing {len(filtered)} of {total_items} listings</p>",
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
                    f"<div style='background:#1e2130; border:1px solid {border_color}; "
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
                        st.markdown("<div style='background:#161925; border:1px solid #2d3348; border-radius:8px; height:80px; display:flex; align-items:center; justify-content:center; color:#64748b; font-size:1.2rem;'>🔨</div>", unsafe_allow_html=True)

                with info_col:
                    ai_badge = ""
                    if is_gemini and val_status == "done":
                        conf_color = {"high":"#16a34a","medium":"#d97706","low":"#dc2626"}.get(ai_conf,"#64748b")
                        ai_badge = f"<span style=\'background:#0d2818; color:{conf_color}; border:1px solid #bbf7d0; border-radius:4px; font-size:0.6rem; font-weight:600; padding:1px 6px; margin-left:6px;\'>🤖 AI Vision</span>"

                    st.markdown(f"<div style=\'color:#e2e8f0; font-size:0.85rem; font-weight:600; margin-bottom:4px; line-height:1.3;\'>{title[:120]}{ai_badge}</div>", unsafe_allow_html=True)

                    if ai_desc and ai_desc.lower()[:30] != title.lower()[:30]:
                        st.markdown(f"<div style=\'color:#64748b; font-size:0.76rem; margin-bottom:5px; background:#161925; border-left:3px solid #cbd5e1; padding:4px 8px; border-radius:0 6px 6px 0;\'>📝 {ai_desc}</div>", unsafe_allow_html=True)

                    price_str = f"${cur_price:.2f}" if cur_price > 0 else "No bids"
                    time_str  = f"⏱ {time_left}" if time_left else ""

                    if val_status == "done" and val_used_hi > 0:
                        src_icon = "🤖" if is_gemini else "📦"
                        val_html = f"""
                        <div style='display:flex; gap:16px; align-items:flex-end; flex-wrap:wrap; margin-top:6px;'>
                            <div>
                                <div style='color:#64748b; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:2px;'>Current Bid</div>
                                <div style='color:#e2e8f0; font-size:1.6rem; font-weight:800; letter-spacing:-0.03em; line-height:1;'>{price_str}</div>
                                {f"<div style='color:#64748b; font-size:0.7rem; margin-top:2px;'>{time_str}</div>" if time_str else ""}
                            </div>
                            <div style='width:1px; background:#e2e8f0; align-self:stretch; margin:0 4px;'></div>
                            <div>
                                <div style='color:#64748b; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:2px;'>{src_icon} Est. Value (Used)</div>
                                <div style='color:{margin_color}; font-size:1.6rem; font-weight:800; letter-spacing:-0.03em; line-height:1;'>${val_used_low:.0f}–${val_used_hi:.0f}</div>
                                <div style='color:#64748b; font-size:0.7rem; margin-top:2px;'>New: ${val_new_low:.0f}–${val_new_hi:.0f}</div>
                            </div>
                            {f"<div style='background:{margin_color}18; border:1px solid {margin_color}44; border-radius:8px; padding:6px 12px; align-self:center;'><div style='color:{margin_color}; font-size:0.8rem; font-weight:700;'>{margin_label}</div></div>" if margin_label else ""}
                        </div>"""
                    elif val_status == "pending":
                        val_html = f"""
                        <div style='display:flex; gap:16px; align-items:flex-end; flex-wrap:wrap; margin-top:6px;'>
                            <div>
                                <div style='color:#64748b; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:2px;'>Current Bid</div>
                                <div style='color:#e2e8f0; font-size:1.6rem; font-weight:800; letter-spacing:-0.03em; line-height:1;'>{price_str}</div>
                                {f"<div style='color:#64748b; font-size:0.7rem; margin-top:2px;'>{time_str}</div>" if time_str else ""}
                            </div>
                            <div style='width:1px; background:#e2e8f0; align-self:stretch; margin:0 4px;'></div>
                            <div>
                                <div style='color:#64748b; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:2px;'>Est. Value</div>
                                <div style='color:#64748b; font-size:1rem; font-weight:600;'>⏳ Researching...</div>
                            </div>
                        </div>"""
                    else:
                        val_html = f"""
                        <div style='margin-top:6px;'>
                            <div style='color:#64748b; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:2px;'>Current Bid</div>
                            <div style='color:#e2e8f0; font-size:1.6rem; font-weight:800; letter-spacing:-0.03em; line-height:1;'>{price_str}</div>
                            {f"<div style='color:#64748b; font-size:0.7rem; margin-top:2px;'>{time_str}</div>" if time_str else ""}
                            <div style='color:#64748b; font-size:0.75rem; margin-top:6px;'>Value unavailable</div>
                        </div>"""

                    st.markdown(val_html, unsafe_allow_html=True)

                with action_col:
                    fav_label = "❤️" if favorited else "🤍"
                    if st.button(fav_label, key=f"fav_{item_id}", use_container_width=True):
                        try:
                            supabase.table("auction_items").update({"favorited": not favorited}).eq("id", item_id).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                    if listing_url:
                        st.markdown(
                            f"<a href='{listing_url}' target='_blank' style='display:block; text-align:center; "
                            f"background:#0d1b38; border:1px solid #93c5fd; border-radius:6px; padding:5px 8px; "
                            f"color:#1d4ed8; font-size:0.7rem; font-weight:600; text-decoration:none; margin-top:4px;'>View ↗</a>",
                            unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

    if not sessions and st.session_state.auction_active_session is None:
        st.markdown("""
        <div style='text-align:center; padding:3rem 0; color:#64748b;'>
            <div style='font-size:3rem; margin-bottom:0.75rem;'>🔨</div>
            <div style='color:#64748b; font-size:1rem; font-weight:500; margin-bottom:0.4rem;'>No auction scanned yet</div>
            <div style='font-size:0.82rem;'>Paste an auction URL above and click Scan.<br>Works with BidSpotter, Purple Wave, IronPlanet, GovPlanet, and more.</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='page-content'>", unsafe_allow_html=True)

# ================================================================== #
#  TAB: SETTINGS
# ================================================================== #

if st.session_state.active_tab == "settings":

    st.markdown("""
    <div style='margin-bottom:1rem;'>
        <div style='color:#e2e8f0; font-size:1.1rem; font-weight:700; margin-bottom:2px;'>⚙️ Settings</div>
        <div style='color:#64748b; font-size:0.8rem;'>Configure API keys and credentials. Changes are saved to Supabase and take effect immediately.</div>
    </div>
    """, unsafe_allow_html=True)

    # Load existing settings from Supabase
    @st.cache_data(ttl=60)
    def load_settings():
        try:
            r = supabase.table("app_settings").select("*").execute()
            return {row["key"]: row["value"] for row in (r.data or [])}
        except Exception:
            return {}

    def save_setting(key: str, value: str):
        try:
            supabase.table("app_settings").upsert({"key": key, "value": value}).execute()
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"Failed to save: {e}")
            return False

    settings = load_settings()

    # ---- Gemini API -------------------------------------------- #
    st.markdown("""
    <div style='background:#1e2130; border:1px solid #2d3348; border-left:4px solid #2563eb;
    border-radius:10px; padding:1rem 1.25rem; margin-bottom:1rem;'>
        <div style='color:#e2e8f0; font-size:0.9rem; font-weight:600; margin-bottom:4px;'>🤖 Google Gemini API</div>
        <div style='color:#64748b; font-size:0.75rem;'>Used for AI scanning, image analysis, and auction value research.</div>
    </div>
    """, unsafe_allow_html=True)

    current_gemini = settings.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    masked_gemini  = f"{current_gemini[:8]}...{current_gemini[-4:]}" if len(current_gemini) > 12 else ("Set" if current_gemini else "Not set")

    st.markdown(f"<div class='field-label'>Current Key</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#64748b; font-size:0.8rem; margin-bottom:8px; font-family:monospace;'>{masked_gemini}</div>", unsafe_allow_html=True)

    g1, g2 = st.columns([4, 1])
    with g1:
        new_gemini = st.text_input("Gemini API Key", placeholder="AIza...", type="password",
                                    label_visibility="collapsed", key="settings_gemini_key")
    with g2:
        if st.button("Save", key="save_gemini", use_container_width=True, type="primary"):
            if new_gemini.strip():
                if save_setting("GEMINI_API_KEY", new_gemini.strip()):
                    st.success("✅ Gemini key saved")
            else:
                st.warning("Enter a key first")

    st.markdown("<div style='color:#64748b; font-size:0.72rem; margin-bottom:1.5rem;'>Get your key at console.cloud.google.com → APIs & Services → Credentials</div>", unsafe_allow_html=True)

    # ---- eBay API ---------------------------------------------- #
    st.markdown("""
    <div style='background:#1e2130; border:1px solid #2d3348; border-left:4px solid #ea580c;
    border-radius:10px; padding:1rem 1.25rem; margin-bottom:1rem;'>
        <div style='color:#e2e8f0; font-size:0.9rem; font-weight:600; margin-bottom:4px;'>🏷️ eBay API Credentials</div>
        <div style='color:#64748b; font-size:0.75rem;'>Used for direct listing submission. Find these at developer.ebay.com → Application Keys → Production.</div>
    </div>
    """, unsafe_allow_html=True)

    ebay_fields = [
        ("EBAY_APP_ID",     "App ID (Client ID)",    "sebastia-Listinga-PRD-..."),
        ("EBAY_DEV_ID",     "Dev ID",                "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"),
        ("EBAY_CERT_ID",    "Cert ID (Client Secret)","PRD-xxxxxxxxxxxxxxxx-xxxx-xxxx-xxxx-xxxx"),
        ("EBAY_USER_TOKEN", "User Token",             "v^1.1#i^1..."),
    ]

    for key, label, placeholder in ebay_fields:
        current_val = settings.get(key, os.getenv(key, ""))
        masked = f"{current_val[:6]}...{current_val[-4:]}" if len(current_val) > 10 else ("Set" if current_val else "Not set")
        st.markdown(f"<div class='field-label'>{label} <span style='color:#64748b;'>({masked})</span></div>", unsafe_allow_html=True)
        ef1, ef2 = st.columns([4, 1])
        with ef1:
            new_val = st.text_input(label, placeholder=placeholder, type="password",
                                     label_visibility="collapsed", key=f"settings_{key}")
        with ef2:
            if st.button("Save", key=f"save_{key}", use_container_width=True, type="primary"):
                if new_val.strip():
                    if save_setting(key, new_val.strip()):
                        st.success(f"✅ {label} saved")
                else:
                    st.warning("Enter a value first")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # ---- Supabase info (read only) ----------------------------- #
    st.markdown("""
    <div style='background:#161925; border:1px solid #2d3348; border-radius:10px; padding:1rem 1.25rem; margin-top:1rem;'>
        <div style='color:#e2e8f0; font-size:0.9rem; font-weight:600; margin-bottom:8px;'>🗄️ Supabase</div>
        <div style='color:#64748b; font-size:0.75rem; margin-bottom:4px;'>Project ID: fmrecxmhvodmkuimvjhi</div>
        <div style='color:#64748b; font-size:0.75rem; margin-bottom:4px;'>URL: https://fmrecxmhvodmkuimvjhi.supabase.co</div>
        <div style='color:#64748b; font-size:0.72rem;'>Supabase credentials are managed via Railway environment variables.</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown("</div>", unsafe_allow_html=True)
