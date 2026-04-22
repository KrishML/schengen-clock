import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import hashlib

# ── Database setup ────────────────────────────────────────────────────────────
conn = sqlite3.connect('trips.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT    UNIQUE NOT NULL,
        password TEXT    NOT NULL
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS trips (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL DEFAULT 0,
        entry_date TEXT    NOT NULL,
        exit_date  TEXT    NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Migration: add user_id column to trips if it doesn't exist yet
existing_columns = [row[1] for row in c.execute('PRAGMA table_info(trips)').fetchall()]
if 'user_id' not in existing_columns:
    c.execute('ALTER TABLE trips ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0')

conn.commit()

# ── Auth helpers ──────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str) -> bool:
    """Returns True on success, False if username already exists."""
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                  (username.strip(), hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username: str, password: str):
    """Returns user row (id, username) or None."""
    c.execute('SELECT id, username FROM users WHERE username = ? AND password = ?',
              (username.strip(), hash_password(password)))
    return c.fetchone()

# ── Login / Register screen ───────────────────────────────────────────────────
def show_auth_screen():
    st.title("Schengen Visa Tracker")
    st.subheader("Please log in to continue")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                user = login_user(username, password)
                if user:
                    st.session_state.user_id = user[0]
                    st.session_state.username = user[1]
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Register")
            if submitted:
                if not new_username or not new_password:
                    st.error("Username and password cannot be empty.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif register_user(new_username, new_password):
                    st.success("Account created! You can now log in.")
                else:
                    st.error("Username already taken. Please choose another.")

# ── Guard: show auth screen if not logged in ──────────────────────────────────
if "user_id" not in st.session_state:
    show_auth_screen()
    st.stop()

# ── From here on the user is authenticated ────────────────────────────────────
CURRENT_USER_ID = st.session_state.user_id

# ── Trip DB helpers (scoped to current user) ──────────────────────────────────
def get_trips():
    c.execute('SELECT entry_date, exit_date FROM trips WHERE user_id = ?', (CURRENT_USER_ID,))
    rows = c.fetchall()
    trips = [(datetime.strptime(e, '%Y-%m-%d').date(),
              datetime.strptime(x, '%Y-%m-%d').date()) for e, x in rows]
    return sorted(trips, key=lambda t: t[1])

def get_trips_with_ids():
    c.execute('SELECT id, entry_date, exit_date FROM trips WHERE user_id = ?', (CURRENT_USER_ID,))
    rows = c.fetchall()
    trips = [(row[0],
              datetime.strptime(row[1], '%Y-%m-%d').date(),
              datetime.strptime(row[2], '%Y-%m-%d').date()) for row in rows]
    return sorted(trips, key=lambda t: t[2])

def add_trip(entry, exit_date):
    c.execute('INSERT INTO trips (user_id, entry_date, exit_date) VALUES (?, ?, ?)',
              (CURRENT_USER_ID, entry.strftime('%Y-%m-%d'), exit_date.strftime('%Y-%m-%d')))
    conn.commit()

def delete_trip(trip_id):
    c.execute('DELETE FROM trips WHERE id = ? AND user_id = ?', (trip_id, CURRENT_USER_ID))
    conn.commit()

def update_trip(trip_id, new_entry, new_exit):
    c.execute('UPDATE trips SET entry_date = ?, exit_date = ? WHERE id = ? AND user_id = ?',
              (new_entry.strftime('%Y-%m-%d'), new_exit.strftime('%Y-%m-%d'),
               trip_id, CURRENT_USER_ID))
    conn.commit()

# ── Load trips ────────────────────────────────────────────────────────────────
st.session_state.trips = get_trips()

# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("Schengen Visa Tracker")

# Control Date
control_date = st.date_input("Control Date", datetime.today().date())
window_start = control_date - timedelta(days=180)

st.markdown(f"""\n### 📅 180-Day Reference Window
**From:** {window_start.strftime('%B %d, %Y')}  
**To:** {control_date.strftime('%B %d, %Y')}
""")

# Form to add trip
with st.form("add_trip"):
    st.subheader("Add a Trip")
    entry = st.date_input("Entry Date")
    exit_date = st.date_input("Exit Date")
    submitted = st.form_submit_button("Add Trip")
    if submitted:
        if entry <= exit_date:
            add_trip(entry, exit_date)
            st.session_state.trips = get_trips()
            st.success("Trip added!")
        else:
            st.error("Exit date must be after entry date")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👤 Logged in as **{st.session_state.username}**")
    if st.button("Logout"):
        for key in ["user_id", "username", "trips", "edit_trip_id", "edit_entry", "edit_exit"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown("---")
    st.subheader("Your Trips")

    # Edit form (show at top if editing)
    if "edit_trip_id" in st.session_state:
        st.markdown("---")
        st.subheader("✏️ Edit Trip")
        with st.form("edit_trip"):
            new_entry = st.date_input("Entry Date", st.session_state.edit_entry)
            new_exit = st.date_input("Exit Date", st.session_state.edit_exit)
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Changes"):
                    if new_entry <= new_exit:
                        update_trip(st.session_state.edit_trip_id, new_entry, new_exit)
                        st.session_state.trips = get_trips()
                        del st.session_state.edit_trip_id
                        st.success("Trip updated!")
                        st.rerun()
                    else:
                        st.error("Exit date must be after entry date")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.pop("edit_trip_id", None)
                    st.rerun()
        st.markdown("---")

    trips_with_ids = get_trips_with_ids()
    if trips_with_ids:
        for i, (trip_id, e, x) in enumerate(trips_with_ids):
            st.markdown(f"Trip {i+1}: {e} to {x}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit", key=f"edit_{trip_id}"):
                    st.session_state.edit_trip_id = trip_id
                    st.session_state.edit_entry = e
                    st.session_state.edit_exit = x
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{trip_id}"):
                    delete_trip(trip_id)
                    st.session_state.trips = get_trips()
                    st.success("Trip deleted!")
                    st.rerun()
    else:
        st.info("No trips added yet")

# ── Calculation helpers ───────────────────────────────────────────────────────
def calculate_days_per_month(trips, start_date, months_count=6):
    """Calculate total days spent in Schengen for each month."""
    import calendar
    import pandas as pd

    monthly_data = []
    for i in range(months_count):
        month_start = (start_date - timedelta(days=30 * i)).replace(day=1)
        _, last_day = calendar.monthrange(month_start.year, month_start.month)
        month_end = month_start.replace(day=last_day)

        total_days = 0
        for entry, exit_date in trips:
            start = max(entry, month_start)
            end = min(exit_date, month_end)
            if start <= end:
                total_days += (end - start).days + 1

        monthly_data.append({'month': month_start.strftime('%b %Y'), 'days': total_days})

    monthly_data.reverse()  # chronological order
    return pd.DataFrame(monthly_data)

def calculate_stay(trips, control_date):
    window_start = control_date - timedelta(days=180)
    total_days = 0
    for entry, exit in trips:
        start = max(entry, window_start)
        end = min(exit, control_date)
        if start <= end:
            total_days += (end - start).days + 1
    return total_days

def calculate_projected_stay(trips, control_date, hypothetical_entry, hypothetical_days):
    if hypothetical_days == 0:
        return calculate_stay(trips, control_date)
    hyp_exit = hypothetical_entry + timedelta(days=hypothetical_days - 1)
    all_trips = trips + [(hypothetical_entry, hyp_exit)]
    window_start = control_date - timedelta(days=180)
    total_days = 0
    for entry, exit in all_trips:
        start = max(entry, window_start)
        end = min(exit, control_date)
        if start <= end:
            total_days += (end - start).days + 1
    return total_days

def get_trips_in_window(trips, control_date, hypothetical_entry=None, hypothetical_days=0):
    window_start = control_date - timedelta(days=180)
    trips_in_window = []
    for entry, exit in trips:
        start = max(entry, window_start)
        end = min(exit, control_date)
        if start <= end:
            trips_in_window.append((entry, exit, (end - start).days + 1, "existing"))
    if hypothetical_entry and hypothetical_days > 0:
        hyp_exit = hypothetical_entry + timedelta(days=hypothetical_days - 1)
        start = max(hypothetical_entry, window_start)
        end = min(hyp_exit, control_date)
        if start <= end:
            trips_in_window.append((hypothetical_entry, hyp_exit, (end - start).days + 1, "planned"))
    return trips_in_window

# ── Stats ─────────────────────────────────────────────────────────────────────
total_days = calculate_stay(st.session_state.trips, control_date)

st.subheader(f"Total Days in Schengen in last 180 days: {total_days}")

progress = min(total_days / 90, 1.0)
st.progress(progress)

if total_days < 75:
    st.success(f"Safe Zone: {total_days} days used out of 90")
elif total_days <= 90:
    st.warning(f"Warning Zone: {total_days} days used out of 90 - Getting close!")
else:
    st.error(f"Danger Zone: {total_days} days used out of 90 - Overstay!")

# ── Monthly breakdown chart ───────────────────────────────────────────────────
st.markdown("---")
st.subheader("📊 Monthly Breakdown (Last 6 Months)")
monthly_df = calculate_days_per_month(st.session_state.trips, control_date, months_count=6)

if not monthly_df.empty and monthly_df['days'].sum() > 0:
    import altair as alt
    month_order = monthly_df['month'].tolist()
    chart = alt.Chart(monthly_df).mark_bar(color="#1f77b4").encode(
        x=alt.X('month', sort=month_order, title='Month'),
        y=alt.Y('days', title='Days in Schengen')
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(monthly_df, use_container_width=True)
else:
    st.info("No trips recorded yet for the past 6 months.")

# ── Future planning ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🔮 Future Planning (Next 3 Months)")

today = datetime.today().date()
next_months = [today + timedelta(days=30 * i) for i in range(1, 4)]

col1, col2, col3 = st.columns(3)
with col1:
    days_month1 = st.number_input(f"Days in {next_months[0].strftime('%B %Y')}", min_value=0, max_value=31, value=0, key="month1_days")
with col2:
    days_month2 = st.number_input(f"Days in {next_months[1].strftime('%B %Y')}", min_value=0, max_value=31, value=0, key="month2_days")
with col3:
    days_month3 = st.number_input(f"Days in {next_months[2].strftime('%B %Y')}", min_value=0, max_value=31, value=0, key="month3_days")

projected_months = []

month1_control_date = next_months[0]
month1_window_start = month1_control_date - timedelta(days=180)
projected_month1 = calculate_projected_stay(st.session_state.trips, month1_control_date, next_months[0], days_month1)
month1_trips = get_trips_in_window(st.session_state.trips, month1_control_date, next_months[0], days_month1)
projected_months.append(("Month 1", next_months[0].strftime('%B %Y'), projected_month1, month1_window_start, month1_control_date, month1_trips))

month2_control_date = next_months[1]
month2_window_start = month2_control_date - timedelta(days=180)
projected_month2 = calculate_projected_stay(st.session_state.trips, month2_control_date, next_months[0], days_month1 + days_month2)
month2_trips = get_trips_in_window(st.session_state.trips, month2_control_date, next_months[0], days_month1 + days_month2)
projected_months.append(("Month 2", next_months[1].strftime('%B %Y'), projected_month2, month2_window_start, month2_control_date, month2_trips))

month3_control_date = next_months[2]
month3_window_start = month3_control_date - timedelta(days=180)
projected_month3 = calculate_projected_stay(st.session_state.trips, month3_control_date, next_months[0], days_month1 + days_month2 + days_month3)
month3_trips = get_trips_in_window(st.session_state.trips, month3_control_date, next_months[0], days_month1 + days_month2 + days_month3)
projected_months.append(("Month 3", next_months[2].strftime('%B %Y'), projected_month3, month3_window_start, month3_control_date, month3_trips))

st.markdown("### 📊 Projection Analysis (Rolling 180-Day Window)")

col_proj1, col_proj2 = st.columns(2)
with col_proj1:
    st.metric("Current Days Used", total_days, "out of 90")
with col_proj2:
    st.metric("Current Window", f"{window_start.strftime('%b %d')} - {control_date.strftime('%b %d')}")

for month_label, month_name, projected_days, win_start, win_end, month_trips in projected_months:
    st.markdown(f"#### {month_label}: {month_name}")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Days Used", projected_days, "out of 90")
    with col_m2:
        st.metric("Rolling Window", f"{win_start.strftime('%b %d')} - {win_end.strftime('%b %d')}")

    st.markdown("**📍 Trips Considered in This Window:**")
    if month_trips:
        for trip_entry, trip_exit, days_count, trip_type in month_trips:
            if trip_type == "planned":
                st.markdown(f"  - 🔵 **Planned:** {trip_entry} to {trip_exit} ({days_count} days in window)")
            else:
                st.markdown(f"  - ✓ **Existing:** {trip_entry} to {trip_exit} ({days_count} days in window)")
    else:
        st.markdown("  - *(No trips in this window)*")

    if projected_days < 75:
        st.success(f"✅ Safe: {projected_days} days - Well within limits")
    elif projected_days <= 90:
        st.warning(f"⚠️ Warning: {projected_days} days - Close to the 90-day limit!")
    elif projected_days <= 100:
        st.error(f"🚨 Danger: {projected_days} days - You will exceed the 90-day limit by {projected_days - 90} days!")
    else:
        st.error(f"🚨 Critical: {projected_days} days - Significant overstay of {projected_days - 90} days!")

    if projected_days > 90:
        st.info(f"💡 **Recommendation:** Reduce stay by {projected_days - 90} days to stay compliant.")
    st.markdown("---")
