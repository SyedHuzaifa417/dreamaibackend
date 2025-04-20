import sqlite3

# Connect to SQLite database
conn = sqlite3.connect('/home/ubuntu/pyth-3.12-user-auth/database/user_data.db')
cursor = conn.cursor()

# # Step 1: Rename the existing table
cursor.execute('''
    ALTER TABLE users RENAME TO temp_users_table
''')
#cursor.execute('DROP TABLE users')

# Step 2: Create a new table with the desired column modification (e.g., renaming a column)
cursor.execute('''
    CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            profile_picture BLOB,
            otp TEXT,
            image_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            subscription_plan TEXT,
            subscription_validity TEXT,
            subscription_start_date TEXT,
            subscription_end_date TEXT

   
    )
''')

# Step 3: Copy the data from the old table to the new table
cursor.execute('''
    INSERT INTO users (id, name, email, password, profile_picture, otp, image_count, video_count, subscription_plan, subscription_validity)
    SELECT id, name, email, password, profile_picture, otp, image_count, video_count, subscription_plan, subscription_validity FROM temp_users_table
''')





# Step 4: Drop the old table
cursor.execute('DROP TABLE temp_users_table')

# Commit the changes and close the connection
conn.commit()
conn.close()
