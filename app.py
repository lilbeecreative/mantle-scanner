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
#  EBAY CATEGORIES — (name, category_id)
# ------------------------------------------------------------------ #

EBAY_CATEGORIES = [
    # Industrial & Commercial
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
    # Automotive
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
    # Tools
    ("Home & Garden > Tools & Workshop Equipment > Power Tools", "631"),
    ("Home & Garden > Tools & Workshop Equipment > Hand Tools", "632"),
    ("Home & Garden > Tools & Workshop Equipment > Welding & Soldering", "26231"),
    ("Home & Garden > Tools & Workshop Equipment > Air Tools & Air Compressors", "25999"),
    ("Home & Garden > Tools & Workshop Equipment > Measuring & Layout Tools", "42281"),
    # Electronics
    ("Consumer Electronics > Computers & Tablets", "58058"),
    ("Consumer Electronics > TV, Video & Home Audio", "32852"),
    ("Consumer Electronics > Cell Phones & Accessories", "15032"),
    # General
    ("Collectibles > Tools, Hardware & Locks", "4706"),
    ("Home & Garden > Kitchen & Dining", "20625"),
    ("Sporting Goods > Outdoor Sports", "888"),
    ("Toys & Hobbies > Electronic, Battery & Wind-Up", "19068"),
    ("Clothing, Shoes & Accessories > Men > Clothing", "1059"),
    ("Clothing, Shoes & Accessories > Women > Clothing", "15724"),
]

# Build lookup dicts
CATEGORY_LABELS = [f"{name}  [{cat_id}]" for name, cat_id in EBAY_CATEGORIES]
LABEL_TO_ID     = {f"{name}  [{cat_id}]": cat_id for name, cat_id in EBAY_CATEGORIES}
LABEL_TO_NAME   = {f"{name}  [{cat_id}]": name   for name, cat_id in EBAY_CATEGORIES}
ID_TO_LABEL     = {cat_id: f"{name}  [{cat_id}]" for name, cat_id in EBAY_CATEGORIES}

def find_label_for_item(category: str, cat_id: str) -> str | None:
    """Find the matching label from existing category name or ID."""
    if cat_id and cat_id in ID_TO_LABEL:
        return ID_TO_LABEL[cat_id]
    for label in CATEGORY_LABELS:
        if category.lower() in label.lower():
            return label
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
    .stApp { background-color: #0a0a0c; }
    .block-container { padding: 0 !important; max-width: 100% !important; }

    [data-testid="metric-container"] {
        background: #141418;
        border: 1px solid #1e1e28;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
    }
    [data-testid="metric-container"] label {
        color: #4a4a5a !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        font-weight: 500;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.9rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    hr { border-color: #1e1e28 !important; margin: 1.5rem 0; }

    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {
        border-color: #2196F3 !important;
    }
    [data-testid="stSelectbox"] > div > div {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-size: 0.85rem !important;
    }
    [data-testid="baseButton-secondary"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    [data-testid="baseButton-primary"] {
        background: #2196F3 !important;
        border: none !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        border-radius: 12px !important;
    }
    [data-testid="stAlert"] {
        background: #1e1218 !important;
        border: 1px solid #3e1e28 !important;
        border-radius: 10px !important;
        color: #ffaaaa !important;
    }
    [data-testid="baseButton-download"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #6b8fb5 !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploader"] {
        background: #141418 !important;
        border: 1.5px dashed #2196F3 !important;
        border-radius: 12px !important;
    }
    .field-label {
        color: #4a4a5a;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 3px;
        font-weight: 500;
    }
    .batch-card {
        background: #141418;
        border: 1.5px solid #1e1e28;
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
    }
    .batch-card.active { border-color: #2196F3; }
    .batch-card.processing { border-color: #f59e0b; }
    .batch-card.done { border-color: #22c55e; }
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 500;
    }
    .pill-active { background: #0a1e3a; color: #2196F3; }
    .pill-processing { background: #1e1608; color: #f59e0b; }
    .pill-done { background: #0a1e10; color: #22c55e; }
    .pill-waiting { background: #1a1a22; color: #6b6b7b; }
    .section-label {
        color: #4a4a5a;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 500;
        margin-bottom: 1rem;
    }
    .page-content { padding: 2rem 2.5rem; max-width: 1400px; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase       = get_supabase()
SUPABASE_URL   = os.getenv("SUPABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
NOTIFY_EMAIL   = "sebastian@lilbeecreative.com"

ARCHIVE_FILE    = "mantle_archive.csv"
ARCHIVE_HEADERS = [
    "batch_cleared_at", "id", "photo_id", "title", "ebay_category",
    "ebay_category_id", "weight_oz", "weight_lb", "price_low", "price_high",
    "price", "price_note", "price_used", "price_new", "condition",
    "quantity", "status", "created_at"
]

# ------------------------------------------------------------------ #
#  NAV BAR
# ------------------------------------------------------------------ #

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"

st.markdown(f"""
<div style='background:#0f0f13; border-bottom:1px solid #1e1e28; padding:0 2rem;
display:flex; align-items:center; justify-content:space-between; height:56px;'>
    <div style='color:#ffffff; font-size:1.1rem; font-weight:700; letter-spacing:-0.02em;
    display:flex; align-items:center; gap:8px;'>
        <div style='width:8px; height:8px; background:#2196F3; border-radius:50%;'></div>
        Lister AI
    </div>
    <div style='color:#4a4a5a; font-size:0.75rem;'>Current batch</div>
</div>
""", unsafe_allow_html=True)

ncol1, ncol2, ncol3 = st.columns([1, 1, 1])
with ncol1:
    if st.button("📊  Dashboard", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "dashboard" else "secondary"):
        st.session_state.active_tab = "dashboard"
        st.rerun()
with ncol2:
    if st.button("📷  Batch Upload", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "batch" else "secondary"):
        st.session_state.active_tab = "batch"
        st.rerun()
with ncol3:
    if st.button("↺  Refresh", use_container_width=True, type="secondary"):
        st.cache_data.clear()
        st.rerun()

st.markdown("<div class='page-content'>", unsafe_allow_html=True)

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
                "html":    f"<h2>New Issue</h2><p>{description}</p><p style='color:#999;font-size:12px;'>{submitted_at}</p>",
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

@st.cache_data(ttl=300)
def image_exists(url: str) -> bool:
    if not url:
        return False
    try:
        r = requests.head(url, timeout=8)
        return r.status_code in (200, 301, 302)
    except Exception:
        return True

def update_field(item_id: str, field: str, value):
    try:
        supabase.table("listings").update({field: value}).eq("id", item_id).execute()
    except Exception as e:
        st.error(f"Failed to update {field}: {e}")

def switch_condition(item_id: str, new_cond: str, price_used: float, price_new: float):
    if new_cond == "used":
        active = price_used if price_used > 0 else price_new
        note   = "new" if price_used == 0 and price_new > 0 else ""
    else:
        active = price_new if price_new > 0 else price_used
        note   = "used" if price_new == 0 and price_used > 0 else ""
    supabase.table("listings").update({
        "condition": new_cond, "price": active, "price_note": note,
    }).eq("id", item_id).execute()

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
        category_id    = str(row.get("ebay_category_id", ""))
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

# ================================================================== #
#  TAB: BATCH UPLOAD
# ================================================================== #

if st.session_state.active_tab == "batch":

    st.markdown("<div class='section-label'>Batch Upload — upload photos per product</div>", unsafe_allow_html=True)

    if "upload_session_id" not in st.session_state:
        st.session_state.upload_session_id = str(uuid.uuid4())
    if "batch_items" not in st.session_state:
        st.session_state.batch_items = []
    if "current_group_id" not in st.session_state:
        st.session_state.current_group_id = None

    total_items   = len(st.session_state.batch_items)
    done_items    = sum(1 for i in st.session_state.batch_items if i["status"] == "done")
    pending_items = sum(1 for i in st.session_state.batch_items if i["status"] == "pending")

    s1, s2, s3 = st.columns(3)
    s1.metric("Items This Session", total_items)
    s2.metric("Sent to Scanner",    pending_items + done_items)
    s3.metric("Processed",          done_items)

    st.divider()

    if st.session_state.current_group_id is None:
        st.markdown("""
        <div style='text-align:center; padding:3rem 0;'>
            <div style='font-size:2rem; margin-bottom:1rem;'>📦</div>
            <div style='color:#aaaacc; font-size:1rem; font-weight:500;'>Ready to scan</div>
            <div style='color:#4a4a5a; font-size:0.85rem; margin-top:0.5rem;'>Tap New Item to start uploading photos for a product</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        current_item_index = len(st.session_state.batch_items) + 1
        st.markdown(f"""
        <div class='batch-card active'>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                <div style='color:#ffffff; font-size:0.95rem; font-weight:500;'>Item {current_item_index}</div>
                <span class='status-pill pill-active'>In progress</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='field-label'>Upload photos (up to 10)</div>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload photos",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.current_group_id}",
            label_visibility="collapsed"
        )

        if uploaded_files and len(uploaded_files) > 10:
            st.warning("Maximum 10 photos per item. Only the first 10 will be used.")
            uploaded_files = uploaded_files[:10]

        if uploaded_files:
            st.markdown(
                f"<div style='color:#2196F3; font-size:0.8rem; margin-bottom:8px;'>"
                f"{len(uploaded_files)} photo(s) selected</div>",
                unsafe_allow_html=True
            )
            thumb_cols = st.columns(min(len(uploaded_files), 10))
            for col, f in zip(thumb_cols, uploaded_files):
                with col:
                    st.image(f, use_container_width=True)

        cond_col, qty_col = st.columns(2)
        with cond_col:
            st.markdown("<div class='field-label'>Condition</div>", unsafe_allow_html=True)
            item_condition = st.selectbox(
                "Condition", ["used", "new"],
                key=f"item_cond_{st.session_state.current_group_id}",
                label_visibility="collapsed"
            )
        with qty_col:
            st.markdown("<div class='field-label'>Quantity</div>", unsafe_allow_html=True)
            item_qty = st.number_input(
                "Quantity", min_value=1, value=1, step=1,
                key=f"item_qty_{st.session_state.current_group_id}",
                label_visibility="collapsed"
            )

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col2:
            if st.button("Done — next item →", use_container_width=True, type="primary",
                         disabled=not uploaded_files):
                with st.spinner("Uploading photos..."):
                    group_id    = st.session_state.current_group_id
                    photo_count = 0
                    for i, f in enumerate(uploaded_files[:10]):
                        try:
                            dt        = datetime.now()
                            date_code = dt.strftime("%d%m%y")
                            time_code = dt.strftime("%H%M%S")
                            ext       = os.path.splitext(f.name)[1].lower()
                            if ext not in (".jpg", ".jpeg", ".png", ".heic"):
                                ext = ".jpg"
                            filename = f"{date_code}_{time_code}_{i}{ext}"
                            file_bytes = f.read()
                            supabase.storage.from_("part-photos").upload(
                                path=filename,
                                file=file_bytes,
                                file_options={"content-type": f.type or "image/jpeg", "upsert": "true"}
                            )
                            supabase.table("group_photos").insert({
                                "group_id": group_id,
                                "photo_id": filename,
                            }).execute()
                            photo_count += 1
                        except Exception as e:
                            st.error(f"Upload failed for {f.name}: {e}")

                    supabase.table("listing_groups").update({
                        "condition": item_condition,
                        "quantity":  item_qty,
                        "status":    "pending",
                    }).eq("id", group_id).execute()

                    st.session_state.batch_items.append({
                        "group_id":    group_id,
                        "condition":   item_condition,
                        "qty":         item_qty,
                        "status":      "pending",
                        "photo_count": photo_count,
                    })
                    st.session_state.current_group_id = None
                    st.cache_data.clear()
                    st.rerun()

        with btn_col1:
            if not uploaded_files:
                st.markdown(
                    "<div style='color:#4a4a5a; font-size:0.8rem; padding-top:8px;'>"
                    "Upload at least one photo to continue</div>",
                    unsafe_allow_html=True
                )

    st.markdown("<div style='margin-top:1rem;'>", unsafe_allow_html=True)
    if st.button("📦  New Item", use_container_width=True, type="secondary",
                 disabled=st.session_state.current_group_id is not None):
        try:
            result = supabase.table("listing_groups").insert({
                "session_id": st.session_state.upload_session_id,
                "status":     "waiting",
                "quantity":   1,
                "condition":  "used",
            }).execute()
            st.session_state.current_group_id = result.data[0]["id"]
            st.rerun()
        except Exception as e:
            st.error(f"Failed to create item: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.batch_items:
        st.divider()
        st.markdown("<div class='section-label'>Items submitted this session</div>", unsafe_allow_html=True)
        for i, item in enumerate(reversed(st.session_state.batch_items)):
            status      = item.get("status", "pending")
            photo_count = item.get("photo_count", 0)
            condition   = item.get("condition", "used")
            qty         = item.get("qty", 1)
            pill_class  = {"pending": "pill-processing", "done": "pill-done"}.get(status, "pill-waiting")
            pill_label  = {"pending": "Processing...", "done": "Listed"}.get(status, status.title())
            card_class  = {"pending": "processing", "done": "done"}.get(status, "")
            st.markdown(f"""
            <div class='batch-card {card_class}'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <div>
                        <span style='color:#ffffff; font-size:0.9rem; font-weight:500;'>
                            Item {len(st.session_state.batch_items) - i}
                        </span>
                        <span style='color:#4a4a5a; font-size:0.75rem; margin-left:10px;'>
                            {photo_count} photo(s) &nbsp;·&nbsp; {condition.title()} &nbsp;·&nbsp; Qty: {qty}
                        </span>
                    </div>
                    <span class='status-pill {pill_class}'>{pill_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    if st.session_state.batch_items and st.session_state.current_group_id is None:
        st.divider()
        if st.button("🔄  Start New Session", use_container_width=True, type="secondary"):
            st.session_state.upload_session_id = str(uuid.uuid4())
            st.session_state.batch_items       = []
            st.session_state.current_group_id  = None
            st.rerun()

# ================================================================== #
#  TAB: DASHBOARD
# ================================================================== #

elif st.session_state.active_tab == "dashboard":

    df = fetch_listings()

    if df.empty:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 0; color:#4a4a5a;">
            <div style="font-size:2.5rem; margin-bottom:1rem;">📭</div>
            <div style="font-size:1.1rem; font-weight:500; color:#aaaacc;">No items in current batch</div>
            <div style="font-size:0.85rem; margin-top:0.5rem;">Use Batch Upload to scan products</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        total_items = len(df)
        total_value = df["price"].sum() if "price" in df.columns else 0

        m1, m2 = st.columns(2)
        m1.metric("Items in Batch", total_items)
        m2.metric("Batch Value",    f"${total_value:,.2f}")

        st.divider()
        st.markdown("<div class='section-label'>Items</div>", unsafe_allow_html=True)

        if "quantities" not in st.session_state:
            st.session_state.quantities = {}

        for _, item in df.iterrows():
            item_id    = str(item.get("id", ""))
            pid        = str(item.get("photo_id", ""))
            title      = str(item.get("title", "Unknown"))
            price      = float(item.get("price", 0.0))
            price_note = str(item.get("price_note", "")).strip().lower()
            condition  = str(item.get("condition", "used")).strip().lower()
            category   = str(item.get("ebay_category", ""))
            cat_id     = str(item.get("ebay_category_id", "")).strip().replace(".0", "")
            weight_oz  = float(item.get("weight_oz", 0.0) or 0.0)
            price_used = float(item.get("price_used", 0.0) or 0.0)
            price_new  = float(item.get("price_new",  0.0) or 0.0)
            url        = photo_url(pid)

            if item_id and item_id not in st.session_state.quantities:
                st.session_state.quantities[item_id] = int(item.get("quantity", 0))

            current_qty = st.session_state.quantities.get(item_id, 0)
            flag_color  = "#f59e0b33" if price_note in ("new", "used") else "#1e1e28"

            st.markdown(
                f"<div style='background:#141418; border:1.5px solid {flag_color}; "
                f"border-radius:14px; padding:1rem; margin-bottom:0.75rem;'>",
                unsafe_allow_html=True
            )

            img_col, fields_col = st.columns([1, 3])

            with img_col:
                if url and image_exists(url):
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        st.markdown(
                            "<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:8px; "
                            "height:140px; display:flex; align-items:center; justify-content:center; "
                            "color:#4a4a5a; font-size:1.5rem;'>📷</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.markdown(
                        "<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:8px; "
                        "height:140px; display:flex; align-items:center; justify-content:center; "
                        "color:#4a4a5a; font-size:1.5rem;'>📷</div>",
                        unsafe_allow_html=True
                    )
                sku_display = pid.rsplit(".", 1)[0] if pid else "—"
                st.markdown(
                    f"<div style='color:#4a4a5a; font-size:0.65rem; text-align:center; margin-top:4px;'>"
                    f"{sku_display}</div>",
                    unsafe_allow_html=True
                )

            with fields_col:
                # Title
                new_title = st.text_input(
                    "Title", value=title, key=f"title_{item_id}",
                    label_visibility="collapsed", placeholder="Title"
                )
                if new_title.strip() and new_title.strip() != title:
                    update_field(item_id, "title", new_title.strip()[:80])
                    st.cache_data.clear()

                pc1, pc2, pc3 = st.columns([2, 2, 2])

                with pc1:
                    st.markdown("<div class='field-label'>List Price</div>", unsafe_allow_html=True)
                    new_price = st.number_input(
                        "Price", value=price, step=0.01, format="%.2f",
                        key=f"price_{item_id}", label_visibility="collapsed"
                    )
                    if round(new_price, 2) != round(price, 2):
                        update_field(item_id, "price", round(new_price, 2))
                        update_field(item_id, "price_note", "")
                        st.cache_data.clear()

                    p_used_str = f"${price_used:.2f}" if price_used > 0 else "—"
                    p_new_str  = f"${price_new:.2f}"  if price_new  > 0 else "—"
                    st.markdown(
                        f"<div style='color:#4a4a5a; font-size:0.65rem; margin-top:2px;'>"
                        f"Used: {p_used_str} &nbsp;·&nbsp; New: {p_new_str}</div>",
                        unsafe_allow_html=True
                    )
                    if price_note in ("new", "used"):
                        st.markdown(
                            f"<div style='color:#f59e0b; font-size:0.65rem;'>"
                            f"⚠ no {price_note} listings — using fallback</div>",
                            unsafe_allow_html=True
                        )

                with pc2:
                    st.markdown("<div class='field-label'>Condition</div>", unsafe_allow_html=True)
                    new_cond = st.selectbox(
                        "Condition", ["used", "new"],
                        index=1 if condition == "new" else 0,
                        key=f"cond_{item_id}", label_visibility="collapsed"
                    )
                    if new_cond != condition:
                        switch_condition(item_id, new_cond, price_used, price_new)
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
                            f"<div style='text-align:center; font-size:1rem; font-weight:600; "
                            f"color:#ffffff; padding-top:6px;'>{current_qty}</div>",
                            unsafe_allow_html=True
                        )
                    with q3:
                        if st.button("+", key=f"plus_{item_id}", use_container_width=True):
                            new_qty = current_qty + 1
                            st.session_state.quantities[item_id] = new_qty
                            update_field(item_id, "quantity", new_qty)
                            st.cache_data.clear()
                            st.rerun()

                # Category search | Cat ID (text) | Weight
                cc1, cc2, cc3 = st.columns([3, 1, 1])

                with cc1:
                    st.markdown("<div class='field-label'>eBay Category</div>", unsafe_allow_html=True)
                    # Find current match in category list
                    current_label = find_label_for_item(category, cat_id)
                    options       = ["— type to search —"] + CATEGORY_LABELS
                    current_index = options.index(current_label) if current_label in options else 0

                    selected_label = st.selectbox(
                        "eBay Category",
                        options=options,
                        index=current_index,
                        key=f"cat_{item_id}",
                        label_visibility="collapsed"
                    )
                    if selected_label != "— type to search —" and selected_label != current_label:
                        new_cat_name = LABEL_TO_NAME.get(selected_label, "")
                        new_cat_id   = LABEL_TO_ID.get(selected_label, cat_id)
                        update_field(item_id, "ebay_category",    new_cat_name)
                        update_field(item_id, "ebay_category_id", new_cat_id)
                        st.cache_data.clear()
                        st.rerun()

                with cc2:
                    st.markdown("<div class='field-label'>Cat. ID</div>", unsafe_allow_html=True)
                    new_cat_id_text = st.text_input(
                        "Cat ID", value=cat_id,
                        key=f"catid_{item_id}", label_visibility="collapsed"
                    )
                    if new_cat_id_text.strip() != cat_id and new_cat_id_text.strip():
                        update_field(item_id, "ebay_category_id", new_cat_id_text.strip())
                        st.cache_data.clear()

                with cc3:
                    st.markdown("<div class='field-label'>Weight (oz)</div>", unsafe_allow_html=True)
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

        # ---- ACTIONS ----------------------------------------- #

        col_export, col_ebay, col_clear = st.columns([2, 2, 1])

        with col_export:
            csv_df = df.copy()
            if "created_at" in csv_df.columns:
                csv_df["created_at"] = csv_df["created_at"].astype(str)
            st.download_button(
                label="⬇️  Export raw CSV",
                data=csv_df.to_csv(index=False).encode("utf-8"),
                file_name="listerai_inventory.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_ebay:
            st.download_button(
                label="🛒  Export eBay draft CSV",
                data=build_ebay_csv(df),
                file_name=f"listerai_ebay_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_clear:
            if "confirm_clear" not in st.session_state:
                st.session_state.confirm_clear = False

            if not st.session_state.confirm_clear:
                if st.button("🗑️  Clear Batch", use_container_width=True, type="secondary"):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning(f"Archive all **{total_items}** items?")
                y, n = st.columns(2)
                with y:
                    if st.button("✅  Confirm", use_container_width=True, type="primary"):
                        try:
                            append_to_archive(df)
                            all_ids = df["id"].dropna().astype(str).tolist()
                            if all_ids:
                                supabase.table("listings").update(
                                    {"status": "archived"}
                                ).in_("id", all_ids).execute()
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

        # ---- ISSUES ------------------------------------------ #

        st.markdown("<div class='section-label'>Submitted Issues</div>", unsafe_allow_html=True)
        issues_df = fetch_issues()

        if issues_df.empty:
            st.markdown(
                "<p style='color:#4a4a5a; font-size:0.85rem;'>No issues submitted yet.</p>",
                unsafe_allow_html=True
            )
        else:
            for _, issue in issues_df.iterrows():
                issue_id  = str(issue.get("id", ""))
                desc      = str(issue.get("description", ""))
                submitted = issue.get("submitted_at", "")
                if hasattr(submitted, "strftime"):
                    submitted = submitted.strftime("%b %d, %Y %I:%M %p")
                st.markdown(f"""
                <div style='background:#141418; border:1px solid #1e1e28; border-radius:10px;
                padding:1rem 1.2rem; margin-bottom:0.75rem;'>
                    <div style='color:#4a4a5a; font-size:0.72rem; margin-bottom:0.4rem;'>{submitted}</div>
                    <div style='color:#ffffff; font-size:0.9rem;'>{desc}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✓ Mark resolved", key=f"resolve_{issue_id}"):
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
                    supabase.table("issues").insert({
                        "description":  issue_text.strip(),
                        "submitted_at": now,
                    }).execute()
                    send_issue_email(issue_text.strip(), now)
                    st.cache_data.clear()
                    st.success("✅ Issue submitted.")
                    st.rerun()
                else:
                    st.warning("Please enter a description.")

st.markdown("</div>", unsafe_allow_html=True)
# force redeploy
