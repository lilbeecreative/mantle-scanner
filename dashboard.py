import streamlit as st
import pandas as pd
import os
import csv
import io
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ------------------------------------------------------------------ #
#  SETUP
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Mantle Inventory",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .stApp { background-color: #0f0f11; }
    .block-container { padding: 2rem 2.5rem 2rem 2.5rem; max-width: 1400px; }

    [data-testid="metric-container"] {
        background: #1a1a1f;
        border: 1px solid #2a2a32;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
    }
    [data-testid="metric-container"] label {
        color: #6b6b7b !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 500;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.9rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    hr { border-color: #2a2a32 !important; margin: 1.5rem 0; }

    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2a2a32 !important;
    }

    [data-testid="baseButton-secondary"] {
        background: #1a1a1f !important;
        border: 1px solid #2a2a32 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    [data-testid="baseButton-secondary"]:hover {
        border-color: #4a4a5a !important;
        background: #22222a !important;
    }
    [data-testid="baseButton-primary"] {
        background: #e63946 !important;
        border: none !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }

    [data-testid="stExpander"] {
        background: #1a1a1f !important;
        border: 1px solid #2a2a32 !important;
        border-radius: 12px !important;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background: #1a1a1f !important;
        border: 1px solid #2a2a32 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    [data-testid="stAlert"] {
        background: #2a1a1f !important;
        border: 1px solid #5a2a32 !important;
        border-radius: 10px !important;
        color: #ffaaaa !important;
    }

    [data-testid="baseButton-download"] {
        background: #1a1a1f !important;
        border: 1px solid #2a2a32 !important;
        color: #aaaacc !important;
        border-radius: 8px !important;
    }

    /* Stepper buttons */
    .stepper-minus button, .stepper-plus button {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        padding: 0 !important;
        min-height: 2rem !important;
        height: 2rem !important;
        width: 2rem !important;
        border-radius: 50% !important;
    }
    .stepper-minus button {
        color: #e63946 !important;
        border-color: #e63946 !important;
    }
    .stepper-plus button {
        color: #32d74b !important;
        border-color: #32d74b !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase() -> Client:
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase     = get_supabase()
SUPABASE_URL = os.getenv("SUPABASE_URL")

ARCHIVE_FILE    = "mantle_archive.csv"
ARCHIVE_HEADERS = [
    "batch_cleared_at", "id", "photo_id", "title", "ebay_category",
    "ebay_category_id", "weight_oz", "weight_lb", "price_low", "price_high",
    "price", "quantity", "status", "created_at"
]

EBAY_HEADER  = "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)"
EBAY_COLUMNS = [
    EBAY_HEADER, "Custom label (SKU)", "Category ID", "Title",
    "UPC", "Price", "Quantity", "Item photo URL",
    "Condition ID", "Description", "Format",
]

# ------------------------------------------------------------------ #
#  HELPERS
# ------------------------------------------------------------------ #

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
    if not photo_id or photo_id in ("0", ""):
        return ""
    return f"{SUPABASE_URL}/storage/v1/object/public/part-photos/{photo_id}"

@st.cache_data(ttl=300)
def image_exists(url: str) -> bool:
    if not url:
        return False
    try:
        r = requests.head(url, timeout=4)
        return r.status_code == 200
    except Exception:
        return False

def update_quantity(item_id: str, qty: int):
    """Write quantity change to Supabase."""
    try:
        supabase.table("listings").update({"quantity": qty}).eq("id", item_id).execute()
    except Exception as e:
        st.error(f"Failed to update quantity: {e}")

def build_ebay_csv(df: pd.DataFrame) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US"])
    writer.writerow(["#INFO Action and Category ID are required fields. 1) Set Action to Draft 2) Please find the category ID for your listings here: https://pages.ebay.com/sellerinformation/news/categorychanges.html"])
    writer.writerow(["#INFO After you've successfully uploaded your draft from the Seller Hub Reports tab, complete your drafts to active listings here: https://www.ebay.com/sh/lst/drafts"])
    writer.writerow(["#INFO"])
    writer.writerow(EBAY_COLUMNS)
    for _, row in df.iterrows():
        sku         = str(row.get("photo_id", "")).rsplit(".", 1)[0]
        category_id = str(int(row.get("ebay_category_id", 0))) if row.get("ebay_category_id") else ""
        title       = str(row.get("title", ""))[:80]
        price       = f"{float(row.get('price', 0)):.2f}"
        quantity    = str(int(row.get("quantity", 0)))
        pic_url     = photo_url(str(row.get("photo_id", "")))
        writer.writerow(["Draft", sku, category_id, title, "", price, quantity, pic_url, "1000", "", "FixedPrice"])
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
    for col in ["price", "price_low", "price_high", "weight_oz", "weight_lb", "ebay_category_id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    if "quantity" not in df.columns:
        df["quantity"] = 0
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    if "price_low" in df.columns and "price_high" in df.columns:
        df["price_range"] = df.apply(
            lambda r: f"${r['price_low']:.2f} – ${r['price_high']:.2f}"
            if (r["price_low"] > 0 or r["price_high"] > 0) else "—",
            axis=1
        )
    return df

# ------------------------------------------------------------------ #
#  HEADER
# ------------------------------------------------------------------ #

st.markdown("""
<div style="margin-bottom:0.5rem;">
    <h1 style="margin:0; font-size:1.6rem; font-weight:700; color:#ffffff; letter-spacing:-0.03em;">
        Mantle Hydraulics
    </h1>
    <p style="margin:0; color:#6b6b7b; font-size:0.85rem; margin-top:2px;">
        Current batch — scanned items only
    </p>
</div>
""", unsafe_allow_html=True)

_, refresh_col = st.columns([11, 1])
with refresh_col:
    if st.button("↺", help="Refresh data"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ------------------------------------------------------------------ #
#  DATA
# ------------------------------------------------------------------ #

df = fetch_listings()

if df.empty:
    st.markdown("""
    <div style="text-align:center; padding: 4rem 0; color:#6b6b7b;">
        <div style="font-size:2.5rem; margin-bottom:1rem;">📭</div>
        <div style="font-size:1.1rem; font-weight:500; color:#aaaacc;">No items in current batch</div>
        <div style="font-size:0.85rem; margin-top:0.5rem;">Photos added to Supabase will appear here automatically</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---- METRICS ---------------------------------------------------- #

total_items = len(df)
total_value = df["price"].sum() if "price" in df.columns else 0

m1, m2 = st.columns(2)
m1.metric("Items in Batch", total_items)
m2.metric("Batch Value",    f"${total_value:,.2f}")

st.divider()

# ---- PHOTO GALLERY WITH QUANTITY STEPPERS ----------------------- #

st.markdown(
    "<p style='color:#6b6b7b; font-size:0.75rem; text-transform:uppercase; "
    "letter-spacing:0.08em; font-weight:500; margin-bottom:1rem;'>Item Gallery</p>",
    unsafe_allow_html=True
)

PLACEHOLDER = """
<div style='background:#1a1a1f; border:1px solid #2a2a32; border-radius:8px;
height:140px; display:flex; flex-direction:column; align-items:center;
justify-content:center; color:#6b6b7b;'>
<div style='font-size:1.8rem;'>📷</div>
<div style='font-size:0.7rem; margin-top:4px;'>No image</div>
</div>
"""

# Keep quantity state in session so steppers are responsive
if "quantities" not in st.session_state:
    st.session_state.quantities = {}

# Seed from DB values on first load
for _, item in df.iterrows():
    item_id = str(item.get("id", ""))
    if item_id and item_id not in st.session_state.quantities:
        st.session_state.quantities[item_id] = int(item.get("quantity", 0))

COLS_PER_ROW = 5
rows = [df.iloc[i:i+COLS_PER_ROW] for i in range(0, len(df), COLS_PER_ROW)]

for row_df in rows:
    cols = st.columns(COLS_PER_ROW)
    for col, (_, item) in zip(cols, row_df.iterrows()):
        item_id = str(item.get("id", ""))
        with col:
            # Photo
            pid = str(item.get("photo_id", ""))
            url = photo_url(pid)
            if url and image_exists(url):
                st.image(url, use_container_width=True)
            else:
                st.markdown(PLACEHOLDER, unsafe_allow_html=True)

            # Title and price
            title = str(item.get("title", "Unknown"))
            price = float(item.get("price", 0.0))
            st.markdown(
                f"<div style='color:#aaaacc; font-size:0.72rem; margin-top:0.3rem; "
                f"overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' "
                f"title='{title}'>{title}</div>"
                f"<div style='color:#ffffff; font-size:0.85rem; font-weight:600; "
                f"margin-top:0.1rem;'>${price:.2f}</div>",
                unsafe_allow_html=True
            )

            # Quantity stepper — minus | count | plus
            current_qty = st.session_state.quantities.get(item_id, 0)
            q_col1, q_col2, q_col3 = st.columns([1, 1, 1])

            with q_col1:
                st.markdown('<div class="stepper-minus">', unsafe_allow_html=True)
                if st.button("−", key=f"minus_{item_id}", use_container_width=True):
                    new_qty = max(0, current_qty - 1)
                    st.session_state.quantities[item_id] = new_qty
                    update_quantity(item_id, new_qty)
                    st.cache_data.clear()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with q_col2:
                st.markdown(
                    f"<div style='text-align:center; font-size:1rem; font-weight:600; "
                    f"color:#ffffff; padding-top:4px;'>{current_qty}</div>",
                    unsafe_allow_html=True
                )

            with q_col3:
                st.markdown('<div class="stepper-plus">', unsafe_allow_html=True)
                if st.button("+", key=f"plus_{item_id}", use_container_width=True):
                    new_qty = current_qty + 1
                    st.session_state.quantities[item_id] = new_qty
                    update_quantity(item_id, new_qty)
                    st.cache_data.clear()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ---- FILTERS ---------------------------------------------------- #

with st.expander("🔍  Filter & Search", expanded=False):
    search = st.text_input("", placeholder="Search by title, SKU, or eBay category...")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        min_price = st.number_input("Min price ($)", value=0.0, step=1.0)
    with col_p2:
        price_max_default = float(df["price"].max()) if "price" in df.columns and df["price"].max() > 0 else 9999.0
        max_price = st.number_input("Max price ($)", value=price_max_default, step=1.0)

filtered = df.copy()
if search:
    mask = (
        filtered.get("title", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("photo_id", pd.Series()).astype(str).str.contains(search, case=False, na=False) |
        filtered.get("ebay_category", pd.Series()).astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]
if "price" in filtered.columns:
    filtered = filtered[(filtered["price"] >= min_price) & (filtered["price"] <= max_price)]

st.markdown(
    f"<p style='color:#6b6b7b; font-size:0.8rem; margin-bottom:0.5rem;'>"
    f"Showing {len(filtered)} of {total_items} items</p>",
    unsafe_allow_html=True
)

# ---- TABLE ------------------------------------------------------ #

display_cols = {
    "photo_id":         st.column_config.TextColumn("SKU", width="small"),
    "title":            st.column_config.TextColumn("Title", width="large"),
    "ebay_category":    st.column_config.TextColumn("eBay Category", width="large"),
    "ebay_category_id": st.column_config.NumberColumn("Cat. ID", format="%d", width="small"),
    "weight_oz":        st.column_config.NumberColumn("oz", format="%.1f", width="small"),
    "weight_lb":        st.column_config.NumberColumn("lb", format="%.2f", width="small"),
    "price_range":      st.column_config.TextColumn("Price Range", width="medium"),
    "price":            st.column_config.NumberColumn("List Price", format="$%.2f", width="small"),
    "quantity":         st.column_config.NumberColumn("Qty", format="%d", width="small"),
    "status":           st.column_config.TextColumn("Status", width="small"),
    "created_at":       st.column_config.DatetimeColumn("Scanned", format="MMM D h:mm a", width="medium"),
}

visible     = {k: v for k, v in display_cols.items() if k in filtered.columns}
always_hide = {"id", "price_low", "price_high", "description"}
hidden      = [c for c in filtered.columns if c not in visible and c not in always_hide]

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True,
    column_config={
        **visible,
        **{c: None for c in always_hide},
        **{c: None for c in hidden},
    },
)

st.divider()

# ---- ACTIONS ---------------------------------------------------- #

col_export, col_ebay, col_clear = st.columns([2, 2, 1])

with col_export:
    csv_df = filtered.copy()
    if "created_at" in csv_df.columns:
        csv_df["created_at"] = csv_df["created_at"].astype(str)
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️  Export raw data CSV",
        data=csv_bytes,
        file_name="mantle_inventory.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_ebay:
    ebay_bytes = build_ebay_csv(filtered)
    st.download_button(
        label="🛒  Export to eBay draft CSV",
        data=ebay_bytes,
        file_name=f"mantle_ebay_drafts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
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
        st.warning(f"Archive all **{total_items}** items and clear this batch?")
        y, n = st.columns(2)
        with y:
            if st.button("✅  Confirm", use_container_width=True, type="primary"):
                try:
                    append_to_archive(df)
                    all_ids = df["id"].dropna().astype(str).tolist() if "id" in df.columns else []
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