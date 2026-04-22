import streamlit as st
from datetime import datetime, timedelta
import sqlite3

# Database setup
conn = sqlite3.connect('trips.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips (id INTEGER PRIMARY KEY, entry_date TEXT, exit_date TEXT)''')
conn.commit()

def get_trips():
    c.execute('SELECT entry_date, exit_date FROM trips')
    rows = c.fetchall()
    trips = [(datetime.strptime(e, '%Y-%m-%d').date(), datetime.strptime(x, '%Y-%m-%d').date()) for e, x in rows]
    return sorted(trips, key=lambda t: t[1])  # Sort by exit date

def get_trips_with_ids():
    c.execute('SELECT id, entry_date, exit_date FROM trips')
    rows = c.fetchall()
    trips = [(row[0], datetime.strptime(row[1], '%Y-%m-%d').date(), datetime.strptime(row[2], '%Y-%m-%d').date()) for row in rows]
    return sorted(trips, key=lambda t: t[2])  # Sort by exit date

def add_trip(entry, exit_date):
    c.execute('INSERT INTO trips (entry_date, exit_date) VALUES (?, ?)', (entry.strftime('%Y-%m-%d'), exit_date.strftime('%Y-%m-%d')))
    conn.commit()

def delete_trip(trip_id):
    c.execute('DELETE FROM trips WHERE id = ?', (trip_id,))
    conn.commit()

def update_trip(trip_id, new_entry, new_exit):
    c.execute('UPDATE trips SET entry_date = ?, exit_date = ? WHERE id = ?', (new_entry.strftime('%Y-%m-%d'), new_exit.strftime('%Y-%m-%d'), trip_id))
    conn.commit()

# Load trips
st.session_state.trips = get_trips()

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

# Sidebar menu with trips
with st.sidebar:
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
                    if "edit_trip_id" in st.session_state:
                        del st.session_state.edit_trip_id
                    st.rerun()
        st.markdown("---")
    
    trips_with_ids = get_trips_with_ids()
    if trips_with_ids:
        for i, (trip_id, e, x) in enumerate(trips_with_ids):
            trip_text = f"Trip {i+1}: {e} to {x}"
            st.markdown(trip_text)
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

def calculate_days_per_month(trips, start_date, months_count=6):
    """Calculate total days spent in Schengen for each month"""
    import calendar
    import pandas as pd
    
    monthly_data = []
    current_date = start_date
    
    # Go back to the start date
    for i in range(months_count):
        month_start = current_date - timedelta(days=30*i)
        # Get first day of the month
        month_start = month_start.replace(day=1)
        # Get last day of the month
        _, last_day = calendar.monthrange(month_start.year, month_start.month)
        month_end = month_start.replace(day=last_day)
        
        total_days = 0
        for entry, exit_date in trips:
            # Check if trip overlaps with this month
            start = max(entry, month_start)
            end = min(exit_date, month_end)
            if start <= end:
                total_days += (end - start).days + 1
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'days': total_days
        })
    
    # Reverse to show in chronological order
    monthly_data.reverse()
    return pd.DataFrame(monthly_data)

# Calculate total stay
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
    """Calculate stay including a hypothetical trip in the future"""
    if hypothetical_days == 0:
        return calculate_stay(trips, control_date)
    
    # Create hypothetical trip
    hyp_exit = hypothetical_entry + timedelta(days=hypothetical_days - 1)
    
    # Combine existing trips with hypothetical
    all_trips = trips + [(hypothetical_entry, hyp_exit)]
    
    # Calculate with rolling window
    window_start = control_date - timedelta(days=180)
    total_days = 0
    for entry, exit in all_trips:
        start = max(entry, window_start)
        end = min(exit, control_date)
        if start <= end:
            total_days += (end - start).days + 1
    return total_days

def get_trips_in_window(trips, control_date, hypothetical_entry=None, hypothetical_days=0):
    """Get trips that fall within the 180-day rolling window for a given control date"""
    window_start = control_date - timedelta(days=180)
    trips_in_window = []
    
    # Check existing trips
    for entry, exit in trips:
        start = max(entry, window_start)
        end = min(exit, control_date)
        if start <= end:
            days_in_window = (end - start).days + 1
            trips_in_window.append((entry, exit, days_in_window, "existing"))
    
    # Check hypothetical trip if provided
    if hypothetical_entry and hypothetical_days > 0:
        hyp_exit = hypothetical_entry + timedelta(days=hypothetical_days - 1)
        start = max(hypothetical_entry, window_start)
        end = min(hyp_exit, control_date)
        if start <= end:
            days_in_window = (end - start).days + 1
            trips_in_window.append((hypothetical_entry, hyp_exit, days_in_window, "planned"))
    
    return trips_in_window

total_days = calculate_stay(st.session_state.trips, control_date)

st.subheader(f"Total Days in Schengen in last 180 days: {total_days}")

# Progress bar for 90 days
progress = min(total_days / 90, 1.0)
st.progress(progress)

# Color-coded alerts
if total_days < 75:
    st.success(f"Safe Zone: {total_days} days used out of 90")
elif total_days <= 90:
    st.warning(f"Warning Zone: {total_days} days used out of 90 - Getting close!")
else:
    st.error(f"Danger Zone: {total_days} days used out of 90 - Overstay!")

# Monthly breakdown chart
st.markdown("---")
st.subheader("📊 Monthly Breakdown (Last 6 Months)")
monthly_df = calculate_days_per_month(st.session_state.trips, control_date, months_count=6)

if not monthly_df.empty and monthly_df['days'].sum() > 0:
    # Create bar chart with explicit chronological ordering
    import altair as alt
    month_order = monthly_df['month'].tolist()
    chart = alt.Chart(monthly_df).mark_bar(color="#1f77b4").encode(
        x=alt.X('month', sort=month_order, title='Month'),
        y=alt.Y('days', title='Days in Schengen')
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True)
    
    # Display as table
    st.dataframe(monthly_df, use_container_width=True)
else:
    st.info("No trips recorded yet for the past 6 months.")

# Future planning section
st.markdown("---")
st.subheader("🔮 Future Planning (Next 3 Months)")

# Get next 3 months
today = datetime.today().date()
next_months = []
for i in range(1, 4):
    month_date = today + timedelta(days=30*i)
    next_months.append(month_date)

# Create columns for input
col1, col2, col3 = st.columns(3)

with col1:
    days_month1 = st.number_input(
        f"Days in {next_months[0].strftime('%B %Y')}",
        min_value=0,
        max_value=31,
        value=0,
        key="month1_days"
    )

with col2:
    days_month2 = st.number_input(
        f"Days in {next_months[1].strftime('%B %Y')}",
        min_value=0,
        max_value=31,
        value=0,
        key="month2_days"
    )

with col3:
    days_month3 = st.number_input(
        f"Days in {next_months[2].strftime('%B %Y')}",
        min_value=0,
        max_value=31,
        value=0,
        key="month3_days"
    )

# Calculate projected total with rolling 180-day window
# For each month, the 180-day window rolls forward
projected_months = []

# Month 1 (May projection)
month1_control_date = next_months[0]
month1_window_start = month1_control_date - timedelta(days=180)
projected_month1 = calculate_projected_stay(st.session_state.trips, month1_control_date, next_months[0], days_month1)
month1_trips = get_trips_in_window(st.session_state.trips, month1_control_date, next_months[0], days_month1)
projected_months.append(("Month 1", next_months[0].strftime('%B %Y'), projected_month1, month1_window_start, month1_control_date, month1_trips))

# Month 2 (June projection) - cumulative days
month2_control_date = next_months[1]
month2_window_start = month2_control_date - timedelta(days=180)
combined_days_month2 = days_month1 + days_month2
projected_month2 = calculate_projected_stay(st.session_state.trips, month2_control_date, next_months[0], combined_days_month2)
month2_trips = get_trips_in_window(st.session_state.trips, month2_control_date, next_months[0], combined_days_month2)
projected_months.append(("Month 2", next_months[1].strftime('%B %Y'), projected_month2, month2_window_start, month2_control_date, month2_trips))

# Month 3 (July projection) - cumulative days
month3_control_date = next_months[2]
month3_window_start = month3_control_date - timedelta(days=180)
combined_days_month3 = days_month1 + days_month2 + days_month3
projected_month3 = calculate_projected_stay(st.session_state.trips, month3_control_date, next_months[0], combined_days_month3)
month3_trips = get_trips_in_window(st.session_state.trips, month3_control_date, next_months[0], combined_days_month3)
projected_months.append(("Month 3", next_months[2].strftime('%B %Y'), projected_month3, month3_window_start, month3_control_date, month3_trips))

# Display projection analysis
st.markdown("### 📊 Projection Analysis (Rolling 180-Day Window)")

col_proj1, col_proj2 = st.columns(2)
with col_proj1:
    st.metric("Current Days Used", total_days, f"out of 90")
with col_proj2:
    st.metric("Current Window", f"{window_start.strftime('%b %d')} - {control_date.strftime('%b %d')}")

# Display each month's projection with rolling window
for month_label, month_name, projected_days, win_start, win_end, month_trips in projected_months:
    st.markdown(f"#### {month_label}: {month_name}")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Days Used", projected_days, f"out of 90")
    with col_m2:
        st.metric("Rolling Window", f"{win_start.strftime('%b %d')} - {win_end.strftime('%b %d')}")
    
    # Display trips considered for this calculation
    st.markdown("**📍 Trips Considered in This Window:**")
    if month_trips:
        for trip_entry, trip_exit, days_count, trip_type in month_trips:
            if trip_type == "planned":
                st.markdown(f"  - 🔵 **Planned:** {trip_entry} to {trip_exit} ({days_count} days in window)")
            else:
                st.markdown(f"  - ✓ **Existing:** {trip_entry} to {trip_exit} ({days_count} days in window)")
    else:
        st.markdown("  - *(No trips in this window)*")
    
    # Status indicator
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
