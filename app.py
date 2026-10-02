import streamlit as st
import sqlite3
import math
import pandas as pd
from datetime import datetime


# =========================================================
# SMARTPARK 360
# INTELLIGENT PARKING MANAGEMENT SYSTEM
# =========================================================

st.set_page_config(
    page_title="SmartPark 360",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATABASE = "parking.db"
RATE_PER_HOUR = 20


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    return sqlite3.connect(DATABASE)


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_number TEXT,
            vehicle_number TEXT,
            booking_date TEXT,
            entry_time TEXT,
            exit_time TEXT,
            fee REAL DEFAULT 0,
            status TEXT DEFAULT 'Reserved'
        )
    """)

    for i in range(1, 21):

        slot = f"P{i:02d}"

        cursor.execute("""
            INSERT OR IGNORE INTO parking_slots
            (slot_number, status)
            VALUES (?, 'Available')
        """, (slot,))

    conn.commit()
    conn.close()


initialize_database()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def get_slots():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.slot_number,
            p.status,

            (
                SELECT b.id
                FROM bookings b
                WHERE b.slot_number = p.slot_number
                AND b.status IN ('Reserved', 'Occupied')
                ORDER BY b.id DESC
                LIMIT 1
            ),

            (
                SELECT b.vehicle_number
                FROM bookings b
                WHERE b.slot_number = p.slot_number
                AND b.status IN ('Reserved', 'Occupied')
                ORDER BY b.id DESC
                LIMIT 1
            ),

            (
                SELECT b.entry_time
                FROM bookings b
                WHERE b.slot_number = p.slot_number
                AND b.status = 'Occupied'
                ORDER BY b.id DESC
                LIMIT 1
            )

        FROM parking_slots p
        ORDER BY p.id
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows


def book_slot(slot_number, vehicle_number):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM parking_slots
        WHERE slot_number = ?
    """, (slot_number,))

    result = cursor.fetchone()

    if not result:

        conn.close()
        return False, "Slot not found."

    if result[0] != "Available":

        conn.close()
        return False, "This slot is not available."

    cursor.execute("""
        SELECT id
        FROM bookings
        WHERE vehicle_number = ?
        AND status IN ('Reserved', 'Occupied')
    """, (vehicle_number,))

    if cursor.fetchone():

        conn.close()
        return False, "This vehicle already has an active booking."

    booking_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO bookings
        (
            vehicle_number,
            slot_number,
            booking_date,
            status
        )
        VALUES (?, ?, ?, 'Reserved')
    """, (
        vehicle_number,
        slot_number,
        booking_date
    ))

    cursor.execute("""
        UPDATE parking_slots
        SET status = 'Reserved'
        WHERE slot_number = ?
    """, (slot_number,))

    conn.commit()
    conn.close()

    return True, "Slot reserved successfully."


def check_in(booking_id, slot_number):

    conn = get_connection()
    cursor = conn.cursor()

    entry_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        UPDATE bookings
        SET
            status = 'Occupied',
            entry_time = ?
        WHERE id = ?
        AND status = 'Reserved'
    """, (
        entry_time,
        booking_id
    ))

    cursor.execute("""
        UPDATE parking_slots
        SET status = 'Occupied'
        WHERE slot_number = ?
    """, (slot_number,))

    conn.commit()
    conn.close()


def cancel_booking(booking_id, slot_number):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bookings
        SET status = 'Cancelled'
        WHERE id = ?
        AND status = 'Reserved'
    """, (booking_id,))

    cursor.execute("""
        UPDATE parking_slots
        SET status = 'Available'
        WHERE slot_number = ?
    """, (slot_number,))

    conn.commit()
    conn.close()


def check_out(
    booking_id,
    slot_number,
    entry_time
):

    conn = get_connection()
    cursor = conn.cursor()

    exit_datetime = datetime.now()

    try:

        entry_datetime = datetime.strptime(
            entry_time,
            "%Y-%m-%d %H:%M:%S"
        )

        seconds = max(
            0,
            (
                exit_datetime - entry_datetime
            ).total_seconds()
        )

        duration_hours = max(
            1,
            math.ceil(seconds / 3600)
        )

        duration_minutes = max(
            0,
            math.ceil(seconds / 60)
        )

        fee = duration_hours * RATE_PER_HOUR

    except Exception:

        duration_minutes = 60
        duration_hours = 1
        fee = RATE_PER_HOUR

    exit_time = exit_datetime.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        UPDATE bookings
        SET
            status = 'Completed',
            exit_time = ?,
            fee = ?
        WHERE id = ?
        AND status = 'Occupied'
    """, (
        exit_time,
        fee,
        booking_id
    ))

    cursor.execute("""
        UPDATE parking_slots
        SET status = 'Available'
        WHERE slot_number = ?
    """, (slot_number,))

    conn.commit()
    conn.close()

    return (
        exit_time,
        duration_minutes,
        duration_hours,
        fee
    )


def get_active_booking(vehicle_number):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            vehicle_number,
            slot_number,
            booking_date,
            entry_time,
            exit_time,
            fee,
            status
        FROM bookings
        WHERE vehicle_number = ?
        AND status IN ('Reserved', 'Occupied')
        ORDER BY id DESC
        LIMIT 1
    """, (
        vehicle_number.upper(),
    ))

    result = cursor.fetchone()

    conn.close()

    return result


def get_booking_history(
    search="",
    status_filter="All"
):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            vehicle_number,
            slot_number,
            booking_date,
            entry_time,
            exit_time,
            fee,
            status
        FROM bookings
        WHERE 1=1
    """

    params = []

    if search.strip():

        query += """
            AND (
                vehicle_number LIKE ?
                OR slot_number LIKE ?
            )
        """

        value = f"%{search.strip().upper()}%"

        params.extend([
            value,
            value
        ])

    if status_filter != "All":

        query += """
            AND status = ?
        """

        params.append(status_filter)

    query += """
        ORDER BY id DESC
    """

    cursor.execute(
        query,
        params
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def get_analytics():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM bookings"
    )

    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE status = 'Completed'
    """)

    completed = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE status = 'Cancelled'
    """)

    cancelled = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE status = 'Reserved'
    """)

    reserved = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE status = 'Occupied'
    """)

    occupied = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(fee), 0)
        FROM bookings
        WHERE status = 'Completed'
    """)

    revenue = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            slot_number,
            COUNT(*)
        FROM bookings
        GROUP BY slot_number
        ORDER BY slot_number
    """)

    slot_usage = cursor.fetchall()

    conn.close()

    return (
        total,
        completed,
        cancelled,
        reserved,
        occupied,
        revenue,
        slot_usage
    )


# =========================================================
# TIME FUNCTIONS
# =========================================================

def duration_text(entry_time):

    if not entry_time:
        return "-"

    try:

        start = datetime.strptime(
            entry_time,
            "%Y-%m-%d %H:%M:%S"
        )

        seconds = max(
            0,
            (
                datetime.now() - start
            ).total_seconds()
        )

        minutes = int(seconds // 60)

        hours = minutes // 60
        mins = minutes % 60

        if hours > 0:

            return f"{hours}h {mins}m"

        return f"{mins}m"

    except Exception:

        return "-"


def duration_from_times(
    entry_time,
    exit_time
):

    if not entry_time or not exit_time:
        return "-"

    try:

        start = datetime.strptime(
            entry_time,
            "%Y-%m-%d %H:%M:%S"
        )

        end = datetime.strptime(
            exit_time,
            "%Y-%m-%d %H:%M:%S"
        )

        minutes = max(
            0,
            int(
                (
                    end - start
                ).total_seconds() // 60
            )
        )

        hours = minutes // 60
        mins = minutes % 60

        if hours > 0:

            return f"{hours}h {mins}m"

        return f"{mins}m"

    except Exception:

        return "-"


def display_time(value):

    if not value:
        return "-"

    try:

        return datetime.strptime(
            value,
            "%Y-%m-%d %H:%M:%S"
        ).strftime(
            "%d %b %Y • %I:%M %p"
        )

    except Exception:

        return value


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("🅿️ SmartPark 360")

    st.caption(
        "Intelligent Parking Management"
    )

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Parking",
            "My Booking",
            "Booking History",
            "Analytics"
        ]
    )

    st.divider()

    st.success("● System Online")

    st.caption(
        "Software Project"
    )

    st.caption(
        "Python • Streamlit • SQLite"
    )


# =========================================================
# MAIN HEADER
# =========================================================

st.title("🅿️ SmartPark 360")

st.caption(
    "Intelligent Parking Management System "
    "• Smart • Simple • Efficient"
)

st.success("● SYSTEM ONLINE")

st.divider()


# =========================================================
# PARKING DATA
# =========================================================

slots = get_slots()

total_slots = len(slots)

available_count = sum(
    slot[1] == "Available"
    for slot in slots
)

reserved_count = sum(
    slot[1] == "Reserved"
    for slot in slots
)

occupied_count = sum(
    slot[1] == "Occupied"
    for slot in slots
)

occupancy_percentage = (

    round(
        (
            (
                reserved_count
                + occupied_count
            )
            / total_slots
        ) * 100
    )

    if total_slots > 0

    else 0
)


# =========================================================
# PARKING MAP
# =========================================================

def show_parking_map(
    show_actions=True
):

    current_slots = get_slots()

    for i in range(
        0,
        len(current_slots),
        4
    ):

        columns = st.columns(4)

        for j, column in enumerate(columns):

            if i + j >= len(current_slots):
                break

            (
                slot_number,
                status,
                booking_id,
                vehicle,
                entry_time
            ) = current_slots[i + j]

            with column:

                # AVAILABLE
                if status == "Available":

                    st.success(
                        f"🟢 {slot_number}\n\n"
                        "AVAILABLE"
                    )

                # RESERVED
                elif status == "Reserved":

                    st.warning(
                        f"🟠 {slot_number}\n\n"
                        f"RESERVED\n\n"
                        f"🚘 {vehicle}"
                    )

                    if show_actions:

                        b1, b2 = st.columns(2)

                        with b1:

                            if st.button(
                                "Check-In",
                                key=f"checkin_{booking_id}",
                                use_container_width=True
                            ):

                                check_in(
                                    booking_id,
                                    slot_number
                                )

                                st.success(
                                    "Vehicle checked in."
                                )

                                st.rerun()

                        with b2:

                            if st.button(
                                "Cancel",
                                key=f"cancel_{booking_id}",
                                use_container_width=True
                            ):

                                cancel_booking(
                                    booking_id,
                                    slot_number
                                )

                                st.success(
                                    "Booking cancelled."
                                )

                                st.rerun()

                # OCCUPIED
                else:

                    st.error(
                        f"🔴 {slot_number}\n\n"
                        f"OCCUPIED\n\n"
                        f"🚘 {vehicle}\n\n"
                        f"Entry: "
                        f"{display_time(entry_time)}\n\n"
                        f"⏱ "
                        f"{duration_text(entry_time)}"
                    )

                    if show_actions:

                        if st.button(
                            "🏁 Check-Out",
                            key=f"checkout_{booking_id}",
                            use_container_width=True
                        ):

                            result = get_active_booking(
                                vehicle
                            )

                            if (
                                result
                                and result[4]
                            ):

                                (
                                    exit_time,
                                    duration_minutes,
                                    duration_hours,
                                    fee
                                ) = check_out(
                                    booking_id,
                                    slot_number,
                                    result[4]
                                )

                                st.session_state[
                                    "last_checkout"
                                ] = {

                                    "vehicle":
                                        vehicle,

                                    "slot":
                                        slot_number,

                                    "entry":
                                        result[4],

                                    "exit":
                                        exit_time,

                                    "minutes":
                                        duration_minutes,

                                    "hours":
                                        duration_hours,

                                    "fee":
                                        fee
                                }

                                st.rerun()


# =========================================================
# CHECKOUT RECEIPT
# =========================================================

if "last_checkout" in st.session_state:

    receipt = st.session_state[
        "last_checkout"
    ]

    st.success(
        "Parking session completed successfully."
    )

    st.subheader(
        "🧾 Last Check-Out Receipt"
    )

    r1, r2, r3, r4 = st.columns(4)

    with r1:

        st.metric(
            "Vehicle",
            receipt["vehicle"]
        )

    with r2:

        st.metric(
            "Slot",
            receipt["slot"]
        )

    with r3:

        st.metric(
            "Duration",
            f'{receipt["hours"]} hour(s)'
        )

    with r4:

        st.metric(
            "Parking Fee",
            f'₹{receipt["fee"]:.2f}'
        )

    st.write(
        f'Entry: {display_time(receipt["entry"])}'
    )

    st.write(
        f'Exit: {display_time(receipt["exit"])}'
    )

    if st.button(
        "Close Receipt"
    ):

        del st.session_state[
            "last_checkout"
        ]

        st.rerun()

    st.divider()


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.header("Parking Overview")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🅿️ Total Slots",
            total_slots
        )

    with c2:

        st.metric(
            "🟢 Available",
            available_count
        )

    with c3:

        st.metric(
            "🟠 Reserved",
            reserved_count
        )

    with c4:

        st.metric(
            "🔴 Occupied",
            occupied_count
        )

    st.divider()

    st.header("Live Parking Map")

    st.caption(
        "Green = Available | "
        "Orange = Reserved | "
        "Red = Occupied"
    )

    show_parking_map(
        show_actions=True
    )

    st.divider()

    st.header("Current Occupancy")

    st.progress(
        occupancy_percentage / 100
    )

    st.write(
        f"Parking utilization: "
        f"**{occupancy_percentage}%**"
    )

    st.divider()

    st.header("Quick Reservation")

    available_slots = [

        slot[0]

        for slot in get_slots()

        if slot[1] == "Available"

    ]

    if available_slots:

        q1, q2, q3 = st.columns(
            [1, 1, 0.7]
        )

        with q1:

            selected_slot = st.selectbox(
                "Available Slot",
                available_slots
            )

        with q2:

            vehicle_number = st.text_input(
                "Vehicle Number",
                placeholder="AP09SV0928"
            )

        with q3:

            st.write("")

            if st.button(
                "Reserve Slot",
                use_container_width=True
            ):

                vehicle_number = (
                    vehicle_number
                    .strip()
                    .upper()
                )

                if not vehicle_number:

                    st.warning(
                        "Enter vehicle number."
                    )

                else:

                    success, message = book_slot(
                        selected_slot,
                        vehicle_number
                    )

                    if success:

                        st.success(
                            message
                        )

                        st.rerun()

                    else:

                        st.error(
                            message
                        )

    else:

        st.warning(
            "No parking slots are currently available."
        )

    st.divider()

    st.header("Parking Summary")

    (
        total,
        completed,
        cancelled,
        reserved,
        occupied,
        revenue,
        usage
    ) = get_analytics()

    s1, s2, s3, s4 = st.columns(4)

    with s1:

        st.metric(
            "Total Bookings",
            total
        )

    with s2:

        st.metric(
            "Completed",
            completed
        )

    with s3:

        st.metric(
            "Cancelled",
            cancelled
        )

    with s4:

        st.metric(
            "Revenue",
            f"₹{revenue:.0f}"
        )


# =========================================================
# PARKING PAGE
# =========================================================

elif page == "Parking":

    st.header("Parking Management")

    st.info(
        "Reserve → Check-In → Occupied → "
        "Check-Out → Fee → Available"
    )

    st.subheader("Live Parking Map")

    show_parking_map(
        show_actions=True
    )

    st.divider()

    st.subheader("Reserve a Parking Slot")

    available_slots = [

        slot[0]

        for slot in get_slots()

        if slot[1] == "Available"

    ]

    if available_slots:

        c1, c2 = st.columns(2)

        with c1:

            selected_slot = st.selectbox(
                "Select Slot",
                available_slots
            )

        with c2:

            vehicle_number = st.text_input(
                "Vehicle Number",
                placeholder="AP09SV0928"
            )

        if st.button(
            "🚗 Reserve Parking Slot",
            use_container_width=True
        ):

            vehicle_number = (
                vehicle_number
                .strip()
                .upper()
            )

            if not vehicle_number:

                st.warning(
                    "Please enter vehicle number."
                )

            else:

                success, message = book_slot(
                    selected_slot,
                    vehicle_number
                )

                if success:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )

    else:

        st.warning(
            "No available slots."
        )


# =========================================================
# MY BOOKING
# =========================================================

elif page == "My Booking":

    st.header("My Booking")

    vehicle = st.text_input(
        "Enter Vehicle Number",
        placeholder="AP09SV0928"
    )

    if st.button(
        "🔍 Search Booking",
        use_container_width=True
    ):

        if not vehicle.strip():

            st.warning(
                "Enter a vehicle number."
            )

        else:

            booking = get_active_booking(
                vehicle.strip().upper()
            )

            if booking:

                (
                    booking_id,
                    vehicle,
                    slot,
                    booking_date,
                    entry,
                    exit_time,
                    fee,
                    status
                ) = booking

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "Vehicle",
                        vehicle
                    )

                with c2:

                    st.metric(
                        "Parking Slot",
                        slot
                    )

                with c3:

                    st.metric(
                        "Status",
                        status
                    )

                st.divider()

                if status == "Reserved":

                    st.info(
                        "Your slot is reserved. "
                        "Check in when the vehicle arrives."
                    )

                    b1, b2 = st.columns(2)

                    with b1:

                        if st.button(
                            "🚗 Check-In",
                            use_container_width=True
                        ):

                            check_in(
                                booking_id,
                                slot
                            )

                            st.success(
                                "Vehicle checked in."
                            )

                            st.rerun()

                    with b2:

                        if st.button(
                            "❌ Cancel Booking",
                            use_container_width=True
                        ):

                            cancel_booking(
                                booking_id,
                                slot
                            )

                            st.success(
                                "Booking cancelled."
                            )

                            st.rerun()

                elif status == "Occupied":

                    st.subheader(
                        "Current Parking Session"
                    )

                    st.write(
                        f"**Entry Time:** "
                        f"{display_time(entry)}"
                    )

                    st.write(
                        f"**Current Duration:** "
                        f"{duration_text(entry)}"
                    )

                    st.write(
                        f"**Parking Rate:** "
                        f"₹{RATE_PER_HOUR}/hour"
                    )

                    st.divider()

                    if st.button(
                        "🏁 Check-Out & Calculate Fee",
                        use_container_width=True
                    ):

                        (
                            exit_time,
                            duration_minutes,
                            duration_hours,
                            fee
                        ) = check_out(
                            booking_id,
                            slot,
                            entry
                        )

                        st.session_state[
                            "last_checkout"
                        ] = {

                            "vehicle":
                                vehicle,

                            "slot":
                                slot,

                            "entry":
                                entry,

                            "exit":
                                exit_time,

                            "minutes":
                                duration_minutes,

                            "hours":
                                duration_hours,

                            "fee":
                                fee
                        }

                        st.rerun()

            else:

                st.info(
                    "No active booking found."
                )


# =========================================================
# BOOKING HISTORY
# =========================================================

elif page == "Booking History":

    st.header("Booking History")

    c1, c2 = st.columns(2)

    with c1:

        search = st.text_input(
            "Search Vehicle or Slot",
            placeholder="AP09SV0928 or P01"
        )

    with c2:

        status_filter = st.selectbox(
            "Filter by Status",
            [
                "All",
                "Reserved",
                "Occupied",
                "Completed",
                "Cancelled"
            ]
        )

    history = get_booking_history(
        search,
        status_filter
    )

    if history:

        data = []

        for row in history:

            (
                booking_id,
                vehicle,
                slot,
                booking_date,
                entry,
                exit_time,
                fee,
                status
            ) = row

            if exit_time:

                duration = duration_from_times(
                    entry,
                    exit_time
                )

            elif status == "Occupied":

                duration = duration_text(
                    entry
                )

            else:

                duration = "-"

            data.append({

                "ID":
                    booking_id,

                "Vehicle":
                    vehicle,

                "Slot":
                    slot,

                "Date":
                    booking_date,

                "Entry":
                    display_time(entry),

                "Exit":
                    display_time(exit_time),

                "Duration":
                    duration,

                "Fee":
                    f"₹{fee:.2f}",

                "Status":
                    status
            })

        df = pd.DataFrame(data)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 Download Booking History",

            data=df.to_csv(
                index=False
            ),

            file_name=
                "SmartPark_Booking_History.csv",

            mime="text/csv",

            use_container_width=True
        )

    else:

        st.info(
            "No booking history found."
        )


# =========================================================
# ANALYTICS
# =========================================================

elif page == "Analytics":

    st.header("Parking Analytics")

    (
        total,
        completed,
        cancelled,
        reserved,
        occupied,
        revenue,
        slot_usage
    ) = get_analytics()

    # -------------------------
    # ANALYTICS METRICS
    # -------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Total Bookings",
            total
        )

    with c2:

        st.metric(
            "Completed",
            completed
        )

    with c3:

        st.metric(
            "Cancelled",
            cancelled
        )

    c4, c5, c6 = st.columns(3)

    with c4:

        st.metric(
            "Reserved",
            reserved
        )

    with c5:

        st.metric(
            "Occupied",
            occupied
        )

    with c6:

        st.metric(
            "Total Revenue",
            f"₹{revenue:.2f}"
        )

    st.divider()

    # =====================================================
    # DONUT CHART
    # =====================================================

    st.subheader("Booking Status")

    status_chart = pd.DataFrame({

        "Status": [
            "Completed",
            "Reserved",
            "Occupied",
            "Cancelled"
        ],

        "Bookings": [
            completed,
            reserved,
            occupied,
            cancelled
        ]

    })

    # Only display the chart when there is data
    if status_chart["Bookings"].sum() > 0:

        st.vega_lite_chart(
            status_chart,

            {
                "mark": {
                    "type": "arc",
                    "innerRadius": 75
                },

                "encoding": {

                    "theta": {
                        "field": "Bookings",
                        "type": "quantitative"
                    },

                    "color": {
                        "field": "Status",
                        "type": "nominal"
                    },

                    "tooltip": [

                        {
                            "field": "Status",
                            "type": "nominal"
                        },

                        {
                            "field": "Bookings",
                            "type": "quantitative"
                        }

                    ]
                },

                "width": "container",

                "height": 350
            },

            use_container_width=True
        )

    else:

        st.info(
            "No booking data available for the chart yet."
        )

    st.divider()

    # =====================================================
    # LINE GRAPH
    # =====================================================

    st.subheader("Parking Slot Usage")

    if slot_usage:

        slot_chart = pd.DataFrame({

            "Slot": [
                x[0]
                for x in slot_usage
            ],

            "Bookings": [
                x[1]
                for x in slot_usage
            ]

        })

        st.line_chart(
            slot_chart,
            x="Slot",
            y="Bookings",
            use_container_width=True
        )

    else:

        st.info(
            "No slot usage data yet."
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "🅿️ SmartPark 360 | "
    "Intelligent Parking Management System | "
    "Python • Streamlit • SQLite | "
    "Parking Rate: ₹20/hour"
)