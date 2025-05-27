import sqlite3

def init_db(path_to_database):
    conn = sqlite3.connect(path_to_database)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        profile_picture BLOB,
        otp TEXT,
        image_count INTEGER DEFAULT 0,
        video_count INTEGER DEFAULT 0,
        subscription_plan TEXT,
        subscription_duration TEXT,
        subscription_status TEXT DEFAULT 'inactive',
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        subscription_start_date TEXT,
        subscription_end_date TEXT,
        last_reset_date TEXT,
        daily_image_count INTEGER DEFAULT 0,
        daily_video_minutes INTEGER DEFAULT 0
    )
    ''')
    
    # Create a table for subscription history
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscription_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        subscription_plan TEXT NOT NULL,
        subscription_duration TEXT NOT NULL,
        stripe_subscription_id TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT,
        status TEXT NOT NULL,
        FOREIGN KEY (user_email) REFERENCES users(email)
    )
    ''')
    
    conn.commit()
    conn.close()


import sqlite3

# Connect to SQLite database
# conn = sqlite3.connect('example.db')
# cursor = conn.cursor()

# # Step 1: Rename the existing table
# cursor.execute('''
#     ALTER TABLE my_table RENAME TO my_table_old
# ''')

# # Step 2: Create a new table with the desired column modification (e.g., renaming a column)
# cursor.execute('''
#     CREATE TABLE my_table (
#         id INTEGER PRIMARY KEY,
#         age INTEGER DEFAULT 0,
#         salary INTEGER DEFAULT 0,
#         new_column_name INTEGER DEFAULT 0
#     )
# ''')

# # Step 3: Copy the data from the old table to the new table
# cursor.execute('''
#     INSERT INTO my_table (id, age, salary)
#     SELECT id, age, salary FROM my_table_old
# ''')

# # Step 4: Drop the old table
# cursor.execute('DROP TABLE my_table_old')

# # Commit the changes and close the connection
# conn.commit()
# conn.close()
