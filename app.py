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
    page_title="Lister AI",
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
        font-size: 0.85rem !important;
    }

    [data-testid="stSelectbox"] > div > div {
        background: #1a1a1f !important;
        border: 1px solid #2a2a32 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-size: 0.85rem !important;
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

    /* Item card styling */
    .item-card-container {
        background: #1a1a1f;
        border: 1px solid #2a2a32;
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    .item-card-container.flagged {
        border-color: #f59e0b44;
    }
    .field-label {
        color: #6b6b7b;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 2px;
        font-weight: 500;
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
    "price", "price_note", "condition", "quantity", "status", "created_at"
]

# ------------------------------------------------------------------ #
#  EMAIL
# ------------------------------------------------------------------ #

def send_issue_email(description: str, submitted_at: str):
    if not RESEND_API_KEY:
        return
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":    "Lister AI <onboarding@resend.dev>",
                "to":      [NOTIFY_EMAIL],
                "subject": "New Issue Submitted — Lister AI",
                "html":    f"""
                    <h2>New Issue Submitted</h2>
                    <p><strong>Submitted at:</strong> {submitted_at}</p>
                    <p><strong>Description:</strong></p>
                    <p>{description}</p>
                    <hr>
                    <p style="color:#999; font-size:12px;">Lister AI — Scanner System</p>
                """,
            }
        )
    except Exception as e:
        st.error(f"Email failed: {e}")

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

def build_ebay_csv(df: pd.DataFrame) -> bytes:
    output = io.StringIO()
    output.write('#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,\n')
    output.write('#INFO Action and Category ID are required fields. 1) Set Action to Draft 2) Please find the category ID for your listings here: https://pages.ebay.com/sellerinformation/news/categorychanges.html,,,,,,,,,,\n')
    output.write('#INFO After you\'ve successfully uploaded your draft from the Seller Hub Reports tab, complete your drafts to active listings here: https://www.ebay.com/sh/lst/drafts,,,,,,,,,,\n')
    output.write('#INFO,,,,,,,,,,\n')
    output.write('Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8),Custom label (SKU),Category ID,Title,UPC,Price,Quantity,Item photo URL,Condition ID,Description,Format\n')
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    for _, row in df.iterrows():
        sku            = str(row.get("photo_id", "")).rsplit(".", 1)[0]
        category_id    = str(int(row.get("ebay_category_id", 0))) if row.get("ebay_category_id") else ""
        title          = str(row.get("title", ""))[:80]
        price          = f"{float(row.get('price', 0)):.2f}"
        quantity       = str(int(row.get("quantity", 0)))
        pic_url        = photo_url(str(row.get("photo_id", "")))
        condition      = str(row.get("condition", "used")).strip().lower()
        ebay_condition = "1000" if condition == "new" else "3000"
        writer.writerow([
            "Draft", sku, category_id, title, "",
            price, quantity, pic_url, ebay_condition, "", "FixedPrice"
        ])
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
    if "price_note" not in df.columns:
        df["price_note"] = ""
    df["price_note"] = df["price_note"].fillna("")
    if "condition" not in df.columns:
        df["condition"] = "used"
    df["condition"] = df["condition"].fillna("used")
    if "price_low" in df.columns and "price_high" in df.columns:
        df["price_range"] = df.apply(
            lambda r: f"${r['price_low']:.2f} – ${r['price_high']:.2f}"
            if (r["price_low"] > 0 or r["price_high"] > 0) else "—",
            axis=1
        )
    return df

@st.cache_data(ttl=30)
def fetch_issues():
    result = (
        supabase.table("issues")
        .select("*")
        .order("submitted_at", desc=True)
        .execute()
    )
    if not result.data:
        return pd.DataFrame()
    df = pd.DataFrame(result.data)
    if "submitted_at" in df.columns:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce", utc=True)
    return df

# ------------------------------------------------------------------ #
#  HEADER
# ------------------------------------------------------------------ #

st.markdown("""
<div style="margin-bottom:0.5rem;">
    <h1 style="margin:0; font-size:1.6rem; font-weight:700; color:#ffffff; letter-spacing:-0.03em;">
        Lister AI
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
        <div style="font-size:0.85rem; margin-top:0.5rem;">Photos added via the app will appear here automatically</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # ---- METRICS ------------------------------------------------- #

    total_items = len(df)
    total_value = df["price"].sum() if "price" in df.columns else 0
    flagged     = df[df["price_note"].str.strip().str.lower() == "new"].shape[0]

    m1, m2, m3 = st.columns(3)
    m1.metric("Items in Batch", total_items)
    m2.metric("Batch Value",    f"${total_value:,.2f}")
    m3.metric("Price Flags",    flagged)

    st.divider()

    # ---- UNIFIED ITEM CARDS -------------------------------------- #

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
        cat_id     = int(item.get("ebay_category_id", 0) or 0)
        weight_oz  = float(item.get("weight_oz", 0.0) or 0.0)
        weight_lb  = float(item.get("weight_lb", 0.0) or 0.0)
        price_range = str(item.get("price_range", "—"))
        scanned    = item.get("created_at", "")

        if item_id and item_id not in st.session_state.quantities:
            st.session_state.quantities[item_id] = int(item.get("quantity", 0))

        current_qty = st.session_state.quantities.get(item_id, 0)
        url         = photo_url(pid)

        # Card border color
        flag_color = "#f59e0b44" if price_note == "new" else "#2a2a32"

        st.markdown(
            f"<div style='background:#1a1a1f; border:1px solid {flag_color}; "
            f"border-radius:14px; padding:1rem; margin-bottom:0.75rem;'>",
            unsafe_allow_html=True
        )

        # Two column layout: photo | fields
        img_col, fields_col = st.columns([1, 3])

        with img_col:
            if url and image_exists(url):
                try:
                    st.image(url, use_container_width=True)
                except Exception:
                    st.markdown(
                        "<div style='background:#0f0f11; border:1px solid #2a2a32; border-radius:8px; "
                        "height:140px; display:flex; align-items:center; justify-content:center; "
                        "color:#6b6b7b; font-size:1.5rem;'>📷</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.markdown(
                    "<div style='background:#0f0f11; border:1px solid #2a2a32; border-radius:8px; "
                    "height:140px; display:flex; align-items:center; justify-content:center; "
                    "color:#6b6b7b; font-size:1.5rem;'>📷</div>",
                    unsafe_allow_html=True
                )
            # SKU below photo
            sku_display = pid.rsplit(".", 1)[0] if pid else "—"
            st.markdown(
                f"<div style='color:#6b6b7b; font-size:0.65rem; text-align:center; "
                f"margin-top:4px;'>{sku_display}</div>",
                unsafe_allow_html=True
            )

        with fields_col:
            # Row 1: Title
            new_title = st.text_input(
                "Title",
                value=title,
                key=f"title_{item_id}",
                label_visibility="collapsed",
                placeholder="Title"
            )
            if new_title.strip() and new_title.strip() != title:
                update_field(item_id, "title", new_title.strip()[:80])
                st.cache_data.clear()

            # Row 2: Price | Condition | Quantity
            pc1, pc2, pc3 = st.columns([2, 2, 2])

            with pc1:
                st.markdown("<div class='field-label'>List Price</div>", unsafe_allow_html=True)
                new_price = st.number_input(
                    "Price",
                    value=price,
                    step=0.01,
                    format="%.2f",
                    key=f"price_{item_id}",
                    label_visibility="collapsed"
                )
                if round(new_price, 2) != round(price, 2):
                    update_field(item_id, "price", round(new_price, 2))
                    update_field(item_id, "price_note", "")
                    st.cache_data.clear()

                if price_note == "new":
                    st.markdown(
                        "<div style='color:#f59e0b; font-size:0.65rem; margin-top:2px;'>"
                        "⚠ no used listings found</div>",
                        unsafe_allow_html=True
                    )

            with pc2:
                st.markdown("<div class='field-label'>Condition</div>", unsafe_allow_html=True)
                new_cond = st.selectbox(
                    "Condition",
                    ["used", "new"],
                    index=1 if condition == "new" else 0,
                    key=f"cond_{item_id}",
                    label_visibility="collapsed"
                )
                if new_cond != condition:
                    update_field(item_id, "condition", new_cond)
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

            # Row 3: Category | Cat ID | Price range
            cc1, cc2, cc3 = st.columns([3, 1, 2])

            with cc1:
                st.markdown("<div class='field-label'>eBay Category</div>", unsafe_allow_html=True)
                new_cat = st.text_input(
                    "Category",
                    value=category,
                    key=f"cat_{item_id}",
                    label_visibility="collapsed"
                )
                if new_cat.strip() != category and new_cat.strip():
                    update_field(item_id, "ebay_category", new_cat.strip())
                    st.cache_data.clear()

            with cc2:
                st.markdown("<div class='field-label'>Cat. ID</div>", unsafe_allow_html=True)
                new_cat_id = st.number_input(
                    "Cat ID",
                    value=cat_id,
                    step=1,
                    key=f"catid_{item_id}",
                    label_visibility="collapsed"
                )
                if int(new_cat_id) != cat_id:
                    update_field(item_id, "ebay_category_id", int(new_cat_id))
                    st.cache_data.clear()

            with cc3:
                st.markdown("<div class='field-label'>Sold Price Range</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='color:#aaaacc; font-size:0.85rem; padding-top:6px;'>"
                    f"{price_range}</div>",
                    unsafe_allow_html=True
                )

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ---- FILTERS ------------------------------------------------- #

    with st.expander("🔍  Filter & Search", expanded=False):
        search = st.text_input("Search", placeholder="Search by title, SKU, or eBay category...", label_visibility="collapsed")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            min_price = st.number_input("Min price ($)", value=0.0, step=1.0)
        with col_p2:
            price_max_default = float(df["price"].max()) if "price" in df.columns and df["price"].max() > 0 else 9999.0
            max_price = st.number_input("Max price ($)", value=price_max_default, step=1.0)
        with col_p3:
            show_flagged = st.checkbox("Show flagged (new) only", value=False)

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
    if show_flagged:
        filtered = filtered[filtered["price_note"].str.strip().str.lower() == "new"]

    st.markdown(
        f"<p style='color:#6b6b7b; font-size:0.8rem; margin-bottom:0.5rem;'>"
        f"Showing {len(filtered)} of {total_items} items</p>",
        unsafe_allow_html=True
    )

    # ---- ACTIONS ------------------------------------------------- #

    col_export, col_ebay, col_clear = st.columns([2, 2, 1])

    with col_export:
        csv_df = filtered.copy()
        if "created_at" in csv_df.columns:
            csv_df["created_at"] = csv_df["created_at"].astype(str)
        csv_bytes = csv_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️  Export raw data CSV",
            data=csv_bytes,
            file_name="listerai_inventory.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_ebay:
        ebay_bytes = build_ebay_csv(filtered)
        st.download_button(
            label="🛒  Export to eBay draft CSV",
            data=ebay_bytes,
            file_name=f"listerai_ebay_drafts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
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

st.divider()

# ------------------------------------------------------------------ #
#  ISSUES
# ------------------------------------------------------------------ #

st.markdown("""
<p style='color:#6b6b7b; font-size:0.75rem; text-transform:uppercase;
letter-spacing:0.08em; font-weight:500; margin-bottom:1rem;'>Submitted Issues</p>
""", unsafe_allow_html=True)

issues_df = fetch_issues()

if issues_df.empty:
    st.markdown(
        "<p style='color:#6b6b7b; font-size:0.85rem;'>No issues submitted yet.</p>",
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
        <div style='background:#1a1a1f; border:1px solid #2a2a32; border-radius:10px;
        padding:1rem 1.2rem; margin-bottom:0.75rem;'>
            <div style='color:#6b6b7b; font-size:0.72rem; margin-bottom:0.4rem;'>{submitted}</div>
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

st.divider()

# ------------------------------------------------------------------ #
#  SUBMIT ISSUE
# ------------------------------------------------------------------ #

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
            st.success("✅ Issue submitted and email sent.")
            st.rerun()
        else:
            st.warning("Please enter a description before submitting.")
