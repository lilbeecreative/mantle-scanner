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
    .stApp { background-color: #0a0a0c; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    hr { border-color: #1e1e28 !important; margin: 1rem 0; }

    /* Compact inputs */
    [data-testid="stTextInput"] input {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
        padding: 4px 8px !important;
        height: 32px !important;
    }
    [data-testid="stTextInput"] input:focus { border-color: #2196F3 !important; }
    [data-testid="stNumberInput"] input {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
        height: 32px !important;
    }
    [data-testid="stSelectbox"] > div > div {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
        min-height: 32px !important;
    }
    [data-testid="baseButton-secondary"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
        padding: 0.2rem 0.5rem !important;
    }
    [data-testid="baseButton-primary"] {
        background: #2196F3 !important;
        border: none !important;
        border-radius: 6px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stExpander"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        border-radius: 10px !important;
    }
    [data-testid="stAlert"] {
        background: #1e1218 !important;
        border: 1px solid #3e1e28 !important;
        border-radius: 8px !important;
        color: #ffaaaa !important;
    }
    [data-testid="baseButton-download"] {
        background: #141418 !important;
        border: 1px solid #1e1e28 !important;
        color: #6b8fb5 !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stFileUploader"] {
        background: #141418 !important;
        border: 1.5px dashed #2196F3 !important;
        border-radius: 10px !important;
    }
    .field-label {
        color: #4a4a5a;
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 2px;
        font-weight: 500;
    }
    .batch-card {
        background: #141418;
        border: 1.5px solid #1e1e28;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .batch-card.active { border-color: #2196F3; }
    .batch-card.processing { border-color: #f59e0b; }
    .batch-card.done { border-color: #22c55e; }
    .status-pill {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 20px;
        font-size: 0.62rem;
        font-weight: 500;
    }
    .pill-active { background: #0a1e3a; color: #2196F3; }
    .pill-processing { background: #1e1608; color: #f59e0b; }
    .pill-done { background: #0a1e10; color: #22c55e; }
    .section-label {
        color: #4a4a5a;
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 500;
        margin-bottom: 0.75rem;
    }
    .page-content { padding: 1rem 1.5rem; max-width: 1400px; margin: 0 auto; }

    /* Item card */
    .item-card {
        background: #141418;
        border-radius: 12px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }
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

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

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
#  NAV BAR
# ------------------------------------------------------------------ #

st.markdown("""
<div style='background:#0f0f13; border-bottom:1px solid #1e1e28; padding:0 1.5rem;
display:flex; align-items:center; justify-content:space-between; height:48px;'>
    <div style='color:#ffffff; font-size:1rem; font-weight:700; letter-spacing:-0.02em;
    display:flex; align-items:center; gap:8px;'>
        <div style='width:7px; height:7px; background:#2196F3; border-radius:50%;'></div>
        Lister AI
    </div>
    <div style='color:#4a4a5a; font-size:0.7rem;'>Current batch</div>
</div>
""", unsafe_allow_html=True)

# Row 1: Nav tabs
n1, n2, n3, n4 = st.columns(4)
with n1:
    if st.button("📊  Dashboard", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "dashboard" else "secondary"):
        st.session_state.active_tab = "dashboard"
        st.rerun()
with n2:
    if st.button("📷  Batch Upload", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "batch" else "secondary"):
        st.session_state.active_tab = "batch"
        st.rerun()
with n3:
    if st.button("🔍  Research", use_container_width=True,
                 type="primary" if st.session_state.active_tab == "research" else "secondary"):
        st.session_state.active_tab = "research"
        st.rerun()
with n4:
    if st.button("↺  Refresh", use_container_width=True, type="secondary"):
        st.cache_data.clear()
        st.rerun()

# Row 2: Downloads + Clear
df_top = fetch_listings()
d1, d2, d3 = st.columns(3)
with d1:
    if not df_top.empty:
        csv_df = df_top.copy()
        if "created_at" in csv_df.columns:
            csv_df["created_at"] = csv_df["created_at"].astype(str)
        st.download_button(
            label="⬇️  Raw CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="listerai_inventory.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("⬇️  Raw CSV", use_container_width=True, disabled=True)
with d2:
    if not df_top.empty:
        st.download_button(
            label="🛒  eBay CSV",
            data=build_ebay_csv(df_top),
            file_name=f"listerai_ebay_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("🛒  eBay CSV", use_container_width=True, disabled=True)
with d3:
    if st.button("🗑️  Clear Batch", use_container_width=True, type="secondary",
                 disabled=df_top.empty):
        st.session_state.confirm_clear = True
        st.rerun()

st.markdown("<div class='page-content'>", unsafe_allow_html=True)

# ================================================================== #
#  TAB: BATCH UPLOAD
# ================================================================== #

if st.session_state.active_tab == "batch":

    st.markdown("<div class='section-label'>Batch Upload</div>", unsafe_allow_html=True)

    if "upload_session_id" not in st.session_state:
        st.session_state.upload_session_id = str(uuid.uuid4())
    if "batch_items" not in st.session_state:
        st.session_state.batch_items = []
    if "current_group_id" not in st.session_state:
        st.session_state.current_group_id = None

    total_batch   = len(st.session_state.batch_items)
    done_batch    = sum(1 for i in st.session_state.batch_items if i["status"] == "done")
    pending_batch = sum(1 for i in st.session_state.batch_items if i["status"] == "pending")
    total_photos  = sum(i.get("photo_count", 0) for i in st.session_state.batch_items)

    sc1, sc2, sc3, sc4 = st.columns(4)
    for col, val, label, color in [
        (sc1, total_batch,   "Items",      "#2196F3"),
        (sc2, pending_batch, "Processing", "#f59e0b"),
        (sc3, done_batch,    "Listed",     "#22c55e"),
        (sc4, total_photos,  "Photos",     "#a855f7"),
    ]:
        with col:
            st.markdown(f"""
            <div style='background:#141418; border:1px solid #1e1e28; border-top:2px solid {color};
            border-radius:10px; padding:0.75rem 1rem; margin-bottom:0.75rem;'>
                <div style='color:#ffffff; font-size:1.6rem; font-weight:700; letter-spacing:-0.03em; line-height:1;'>{val}</div>
                <div style='color:#4a4a5a; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:4px;'>{label}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()

    if st.session_state.current_group_id is None:
        st.markdown("""
        <div style='text-align:center; padding:2rem 0;'>
            <div style='font-size:1.8rem; margin-bottom:0.75rem;'>📦</div>
            <div style='color:#aaaacc; font-size:0.95rem; font-weight:500;'>Ready to scan</div>
            <div style='color:#4a4a5a; font-size:0.8rem; margin-top:0.4rem;'>Click New Item to start uploading photos</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        current_item_index = len(st.session_state.batch_items) + 1
        st.markdown(f"""
        <div class='batch-card active'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='color:#ffffff; font-size:0.85rem; font-weight:500;'>Item {current_item_index}</span>
                <span class='status-pill pill-active'>In progress</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='field-label'>Upload photos (up to 10)</div>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload photos", type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.current_group_id}",
            label_visibility="collapsed"
        )

        if uploaded_files and len(uploaded_files) > 10:
            st.warning("Maximum 10 photos. Only the first 10 will be used.")
            uploaded_files = uploaded_files[:10]

        if uploaded_files:
            st.markdown(
                f"<div style='color:#2196F3; font-size:0.75rem; margin-bottom:6px;'>"
                f"{len(uploaded_files)} photo(s) selected</div>", unsafe_allow_html=True
            )
            thumb_cols = st.columns(min(len(uploaded_files), 10))
            for col, f in zip(thumb_cols, uploaded_files):
                with col:
                    st.image(f, use_container_width=True)

        cond_col, qty_col = st.columns(2)
        with cond_col:
            st.markdown("<div class='field-label'>Condition</div>", unsafe_allow_html=True)
            item_condition = st.selectbox("Condition", ["used", "new"],
                key=f"item_cond_{st.session_state.current_group_id}", label_visibility="collapsed")
        with qty_col:
            st.markdown("<div class='field-label'>Quantity</div>", unsafe_allow_html=True)
            item_qty = st.number_input("Quantity", min_value=1, value=1, step=1,
                key=f"item_qty_{st.session_state.current_group_id}", label_visibility="collapsed")

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col2:
            if st.button("Done →", use_container_width=True, type="primary", disabled=not uploaded_files):
                with st.spinner("Uploading..."):
                    group_id    = st.session_state.current_group_id
                    photo_count = 0
                    for i, f in enumerate(uploaded_files[:10]):
                        try:
                            dt        = datetime.now()
                            filename  = f"{dt.strftime('%d%m%y')}_{dt.strftime('%H%M%S')}_{i}{os.path.splitext(f.name)[1].lower() or '.jpg'}"
                            supabase.storage.from_("part-photos").upload(
                                path=filename, file=f.read(),
                                file_options={"content-type": f.type or "image/jpeg", "upsert": "true"}
                            )
                            supabase.table("group_photos").insert({"group_id": group_id, "photo_id": filename}).execute()
                            photo_count += 1
                        except Exception as e:
                            st.error(f"Upload failed: {e}")

                    supabase.table("listing_groups").update({
                        "condition": item_condition, "quantity": item_qty, "status": "pending",
                    }).eq("id", group_id).execute()

                    st.session_state.batch_items.append({
                        "group_id": group_id, "condition": item_condition,
                        "qty": item_qty, "status": "pending", "photo_count": photo_count,
                    })
                    st.session_state.current_group_id = None
                    st.cache_data.clear()
                    st.rerun()

    if st.button("📦  New Item", use_container_width=True, type="secondary",
                 disabled=st.session_state.current_group_id is not None):
        try:
            result = supabase.table("listing_groups").insert({
                "session_id": st.session_state.upload_session_id,
                "status": "waiting", "quantity": 1, "condition": "used",
            }).execute()
            st.session_state.current_group_id = result.data[0]["id"]
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

    if st.session_state.batch_items:
        st.divider()
        st.markdown("<div class='section-label'>This session</div>", unsafe_allow_html=True)
        for i, item in enumerate(reversed(st.session_state.batch_items)):
            status     = item.get("status", "pending")
            pill_class = {"pending": "pill-processing", "done": "pill-done"}.get(status, "pill-active")
            pill_label = {"pending": "Processing...", "done": "Listed"}.get(status, status.title())
            card_class = {"pending": "processing", "done": "done"}.get(status, "")
            st.markdown(f"""
            <div class='batch-card {card_class}'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <div>
                        <span style='color:#ffffff; font-size:0.82rem; font-weight:500;'>Item {len(st.session_state.batch_items) - i}</span>
                        <span style='color:#4a4a5a; font-size:0.7rem; margin-left:8px;'>
                            {item.get("photo_count",0)} photos &nbsp;·&nbsp; {item.get("condition","used").title()} &nbsp;·&nbsp; Qty: {item.get("qty",1)}
                        </span>
                    </div>
                    <span class='status-pill {pill_class}'>{pill_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    if st.session_state.batch_items and st.session_state.current_group_id is None:
        st.divider()
        if st.button("🔄  New Session", use_container_width=True, type="secondary"):
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
                <div style='background:#141418; border:1px solid #1e1e28; border-top:2px solid {color};
                border-radius:10px; padding:0.85rem 1.1rem; margin-bottom:0.75rem;'>
                    <div style='color:#ffffff; font-size:1.8rem; font-weight:700; letter-spacing:-0.03em; line-height:1;'>{val}</div>
                    <div style='color:#4a4a5a; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.1em; margin-top:5px;'>{label}</div>
                    {sub_html}
                </div>""", unsafe_allow_html=True)

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
            has_dual   = price_used > 0 or price_new > 0

            if item_id and item_id not in st.session_state.quantities:
                st.session_state.quantities[item_id] = int(item.get("quantity", 0))

            current_qty = st.session_state.quantities.get(item_id, 0)
            flag_color  = "#f59e0b22" if price_note in ("new", "used") else "#1e1e28"

            st.markdown(
                f"<div style='background:#141418; border:1px solid {flag_color}; "
                f"border-radius:12px; padding:0.75rem; margin-bottom:0.5rem;'>",
                unsafe_allow_html=True
            )

            img_col, fields_col = st.columns([1, 4])

            with img_col:
                if url and image_exists(url):
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        st.markdown(
                            "<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:6px; "
                            "height:100px; display:flex; align-items:center; justify-content:center; "
                            "color:#4a4a5a; font-size:1.2rem;'>📷</div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div style='background:#0a0a0c; border:1px solid #1e1e28; border-radius:6px; "
                        "height:100px; display:flex; align-items:center; justify-content:center; "
                        "color:#4a4a5a; font-size:1.2rem;'>📷</div>", unsafe_allow_html=True)
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
                    new_price = st.number_input(
                        "Price", value=price, step=0.01, format="%.2f",
                        key=f"price_{item_id}", label_visibility="collapsed"
                    )
                    if round(new_price, 2) != round(price, 2):
                        update_field(item_id, "price", round(new_price, 2))
                        update_field(item_id, "price_note", "")
                        st.cache_data.clear()
                    if has_dual:
                        p_used_str = f"${price_used:.2f}" if price_used > 0 else "—"
                        p_new_str  = f"${price_new:.2f}"  if price_new  > 0 else "—"
                        st.markdown(
                            f"<div style='color:#4a4a5a; font-size:0.6rem;'>U:{p_used_str} N:{p_new_str}</div>",
                            unsafe_allow_html=True)
                    if price_note in ("new", "used"):
                        st.markdown(
                            f"<div style='color:#f59e0b; font-size:0.6rem;'>⚠ fallback to {price_note}</div>",
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
                            st.toast("Condition updated — update price manually for this item", icon="⚠️")
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
                            f"color:#ffffff; padding-top:5px;'>{current_qty}</div>", unsafe_allow_html=True)
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
                <div style='background:#141418; border:1px solid #1e1e28; border-radius:8px;
                padding:0.6rem 0.9rem; margin-bottom:0.4rem;'>
                    <div style='color:#4a4a5a; font-size:0.65rem; margin-bottom:3px;'>{submitted}</div>
                    <div style='color:#ffffff; font-size:0.82rem;'>{desc}</div>
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
                <div style='background:#141418; border:1px solid #1e1e28; border-top:2px solid {color};
                border-radius:10px; padding:0.85rem 1.1rem; margin-bottom:0.75rem;'>
                    <div style='color:#ffffff; font-size:1.2rem; font-weight:700; line-height:1;'>{val}</div>
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
                            <div style='background:#141418; border:1px solid {border_color};
                            border-radius:8px; padding:0.6rem 0.75rem; margin-top:6px; margin-bottom:4px;'>
                                <div style='color:#ffffff; font-size:0.75rem; font-weight:500;
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
                                    f"background:#1a1a22; border:1px solid #2a2a38; border-radius:6px; padding:5px; "
                                    f"color:#2196F3; font-size:0.72rem; text-decoration:none; margin-bottom:12px;'>"
                                    f"View on eBay ↗</a>",
                                    unsafe_allow_html=True
                                )

st.markdown("</div>", unsafe_allow_html=True)
