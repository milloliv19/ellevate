"""
Streamlit control center for the matching workflow.
Credentials: configure in .streamlit/secrets.toml (e.g. connections.gsheets).
"""
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

from match_maker_automated import run_matching_workflow
import requests

# SET THIS TO TRUE TO TEST WITHOUT CREDENTIALS
TEST_MODE = True

st.set_page_config(page_title="Match Maker Control Center", layout="wide")
st.title("Match Maker Control Center")

# ---------------------------------------------------------------------------
# Data connection: load from Google Sheets
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_sheet_data():
    """Load from Sheets, or return Mock Data if testing."""

    if TEST_MODE:
        # Same format as Google Sheets: array of arrays (header row + data rows)
        participants_header = [
            "Timestamp",
            "Email Address",
            "Please provide your preferred first and last name.",
            "What is your office location?",
            "Superpower",
            "Growth Zone",
        ]
        participants_rows = [
            ["1/21/2026 14:55:00", "alice@test.com", "Alice Smith", "London", "Wine Evaluation", "Crochet"],
            ["1/21/2026 14:56:00", "bob@test.com", "Bob Jones", "London", "Baking", "Running"],
            ["1/21/2026 14:57:00", "charlie@test.com", "Charlie Brown", "New York", "Juggling", "Reading"],
            ["1/21/2026 14:58:00", "diana@test.com", "Diana Prince", "London", "Leadership", "Meditation"],
            ["1/21/2026 14:59:00", "edward@test.com", "Edward Nigma", "Remote", "Puzzles", "Chess"],
        ]
        mock_participants = pd.DataFrame(participants_rows, columns=participants_header)

        history_header = ["Person A (Email)", "Person B (Email)", "Match Date"]
        history_rows = [["alice@test.com", "bob@test.com", "2024-01-01"]]
        mock_history = pd.DataFrame(history_rows, columns=history_header)
        return mock_participants, mock_history

    # Original GSheets logic (runs when TEST_MODE is False)
    conn = st.connection("gsheets", type=GSheetsConnection)
    participants_df = conn.read(worksheet="Participants", ttl=300)
    history_df = conn.read(worksheet="MatchHistory", ttl=300)
    return participants_df, history_df

# This part stays exactly as it was
try:
    participants_df, history_df = load_sheet_data()
except Exception as e:
    st.error(f"Could not load data. Error: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Normalize column names for the matcher (expects 'email', 'name')
# Sheet columns may be 'Email'/'Name' or 'email'/'name'
# ---------------------------------------------------------------------------
def normalize_participant_columns(df):
    """Ensure we have lowercase 'email' and 'name' for the matcher.
    Handles both short names and Google Form-style headers (Email Address, preferred first and last name).
    """
    df = df.copy()
    col_map = {}
    for c in df.columns:
        c_lower = str(c).strip().lower()
        if c_lower in ("email", "email address"):
            col_map[c] = "email"
        elif c_lower == "name" or "preferred first and last name" in c_lower:
            col_map[c] = "name"
    df = df.rename(columns=col_map)
    return df

participants_df = normalize_participant_columns(participants_df)
if "email" not in participants_df.columns or "name" not in participants_df.columns:
    st.error("Participants sheet must include 'Email' and 'Name' columns (any case).")
    st.stop()

# Add Include checkbox column; default True for everyone
if "Include" not in participants_df.columns:
    participants_df["Include"] = True

# ---------------------------------------------------------------------------
# Participant review: table with Include checkbox
# ---------------------------------------------------------------------------
st.header("1. Participant Review")
st.caption("Uncheck anyone to exclude (e.g. on PTO). Then run Generate Matches.")

edited_df = st.data_editor(
    participants_df,
    column_config={
        "Include": st.column_config.CheckboxColumn("Include", default=True),
        "email": st.column_config.TextColumn("Email"),
        "name": st.column_config.TextColumn("Name"),
    },
    hide_index=True,
    use_container_width=True,
)

included_df = edited_df[edited_df["Include"] == True].drop(columns=["Include"], errors="ignore")
active_participants = included_df.to_dict("records")
# Normalize so matcher sees 'email' and 'name'; keep full record for Tray
def to_participant(r):
    r = {k: v for k, v in r.items() if v is not None and str(v).strip() != ""}
    email = str(r.get("email", "")).strip()
    name = str(r.get("name", "")).strip()
    if not email:
        return None
    r["email"], r["name"] = email, name
    return r
active_participants = [p for p in (to_participant(r) for r in active_participants) if p]

st.caption(f"{len(active_participants)} participant(s) included.")

# ---------------------------------------------------------------------------
# Raw MatchHistory for the matcher (list of dicts with Person A/B (Email))
# ---------------------------------------------------------------------------
raw_history = history_df.to_dict("records") if not history_df.empty else []

# ---------------------------------------------------------------------------
# Generate Matches button
# ---------------------------------------------------------------------------
st.header("2. Run Matching")
if st.button("Generate Matches", type="primary"):
    if len(active_participants) < 2:
        st.warning("Include at least 2 participants to generate matches.")
    else:
        with st.spinner("Running matching workflow…"):
            try:
                results = run_matching_workflow(active_participants, raw_history)
                st.session_state["match_results"] = results
                st.session_state["match_results_generated"] = True
                st.success("Matches generated. Review below and push to Tray when ready.")
            except Exception as e:
                st.error(f"Matching failed: {e}")
                st.session_state["match_results_generated"] = False

# ---------------------------------------------------------------------------
# Preview results (pairs and triads)
# ---------------------------------------------------------------------------
st.header("3. Preview Results")
if st.session_state.get("match_results_generated") and st.session_state.get("match_results"):
    results = st.session_state["match_results"]
    pairs = [r for r in results if r.get("match_type") == "pair"]
    triads = [r for r in results if r.get("match_type") == "triad"]

    if pairs:
        st.subheader("Pairs")
        for i, m in enumerate(pairs, 1):
            a, b = m.get("person_a", {}), m.get("person_b", {})
            st.markdown(f"**{i}.** {a.get('name', a.get('email', '?'))} ↔ {b.get('name', b.get('email', '?'))}")
    if triads:
        st.subheader("Triads")
        for i, m in enumerate(triads, 1):
            a, b, c = m.get("person_a", {}), m.get("person_b", {}), m.get("person_c", {})
            st.markdown(f"**{i}.** {a.get('name', '?')} · {b.get('name', '?')} · {c.get('name', '?')}")

    st.caption(f"Total: {len(pairs)} pair(s), {len(triads)} triad(s).")
else:
    st.info("Generate matches above to see results here.")

# ---------------------------------------------------------------------------
# Push to Tray
# ---------------------------------------------------------------------------
st.header("4. Push to Tray")
webhook_url = st.secrets.get("tray_webhook_url") or st.secrets.get("TRAY_WEBHOOK_URL")

if st.button("Push to Tray", type="secondary"):
    if not st.session_state.get("match_results"):
        st.warning("Please generate matches in Step 2 first.")
    elif not webhook_url and not TEST_MODE:
        st.error("No Tray webhook URL configured. Add it to secrets.")
    else:
        results = st.session_state["match_results"]
        
        # --- PREPARE THE DATA FOR TRAY ---
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        history_updates = []

        for m in results:
            # 1. Standard Pair (A & B)
            history_updates.append({
                "Person A (Email)": m['person_a']['email'],
                "Person B (Email)": m['person_b']['email'],
                "Match Date": today
            })
            
            # 2. Handle Triad connections (A-C and B-C)
            if m['match_type'] == "triad":
                history_updates.append({
                    "Person A (Email)": m['person_a']['email'], 
                    "Person B (Email)": m['person_c']['email'], 
                    "Match Date": today
                })
                history_updates.append({
                    "Person A (Email)": m['person_b']['email'], 
                    "Person B (Email)": m['person_c']['email'], 
                    "Match Date": today
                })

        # The "Full Payload" contains everything Tray needs
        full_payload = {
            "matches": results,           
            "history_rows": history_updates 
        }

        if TEST_MODE:
            st.info("🧪 **Test Mode Active:** Showing JSON payload instead of sending to Tray.")
            st.json(full_payload)
            st.code(f"Target URL: {webhook_url if webhook_url else 'None configured'}")
        else:
            with st.spinner("Sending to Tray..."):
                try:
                    # Send the combined payload
                    r = requests.post(webhook_url, json=full_payload, timeout=30)
                    r.raise_for_status()
                    st.balloons()
                    st.success("Successfully pushed to Tray! Emails are being sent and history is updating.")
                except requests.RequestException as e:
                    st.error(f"Push failed: {e}")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")
