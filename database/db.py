import sqlite3

def init_db(path_to_database):
    conn = sqlite3.connect(path_to_database)
    cursor = conn.cursor()
    ('''
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
    cursor.execute("SELECT * FROM users")
    UseRows = cursor.fetchall()
    #for row in UseRows :
    #    print(f"userData>>> id : {row[0]} | Name: {row[1]} | Email: {row[2]} | Password: {row[3]}")
   
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
