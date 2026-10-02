import sqlite3

DATABASE = "parking.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # Parking slots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)

    # Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            vehicle_number TEXT
        )
    """)

    # Bookings
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

    # Create 20 parking slots
    for i in range(1, 21):
        slot = f"P{i:02d}"

        cursor.execute("""
            INSERT OR IGNORE INTO parking_slots
            (slot_number, status)
            VALUES (?, 'Available')
        """, (slot,))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    print("Database created successfully!")