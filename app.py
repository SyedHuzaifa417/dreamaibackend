from flask import Flask,g, jsonify, request
from flask_cors import CORS
import os
import sqlite3
from database.db import init_db
import base64
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from google.cloud import vision_v1
from config import *
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import bcrypt
import proto

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

CORS(app) #, support_credentials=True) 

path_to_database = os.path.join(os.getcwd(),"database")
app.secret_key = 'supersecretkey'

app.config['SESSION_TYPE'] = 'filesystem'  # Use filesystem session storage
app.config['DATABASE'] = os.path.join(path_to_database,'user_data.db')  # Specify the database file
init_db(app.config['DATABASE'])

users_data_folder = os.path.join(path_to_database, 'UserData')

# Initialize the SQLite database connection
@app.before_request
def before_request():
    g.db_connection = sqlite3.connect(app.config['DATABASE'])

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db_connection'):
        g.db_connection.close()

def connect_to_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    return conn

def generate_otp():
    return str(random.randint(1000, 9999))

# ///////////////////////////////////////// USER AUTHENTICATION //////////////////////////////////////////

@app.route('/auth/login', methods=['POST'])
def api_login():

    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        conn = sqlite3.connect(app.config['DATABASE'])  # Get the database connection from the application context
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:

            cursor.execute('SELECT password FROM users WHERE email = ?', (email,))
            stored_hash = cursor.fetchone()[0]

            if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
                matching_user = cursor.fetchone()
                conn.close()
                #user_id = email.split('@')[0]
                username = matching_user[1]  # Assuming the name is the second column in the users table
                email = matching_user[2]
                profile_picture_blob = matching_user[4]
                
                if profile_picture_blob:
                    profile_picture_file = base64.b64encode(profile_picture_blob).decode('utf-8')
                else:
                    profile_picture_file = None

                # Decode bytes to string if not None
                return jsonify({'profile_picture': profile_picture_file, 'name': username, 'email': email}), 200

        else:
            return jsonify({'message': 'Invalid credentials.'}), 401

    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Login failed'}), 500
    
@app.route('/users/<string:email>', methods=['GET'])
def get_user_info(email):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT name, email, profile_picture, image_count, video_count, subscription_plan, subscription_start_date, subscription_end_date FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        conn.close()
        if existing_user:
            username, email, profile_picture_blob, image_count, video_count, subscription_plan, subscription_start_date, subscription_end_date  = existing_user
            if profile_picture_blob:
                profile_picture_base64 = base64.b64encode(profile_picture_blob).decode('utf-8')
            else:
                profile_picture_base64 = None
            
            # Decode bytes to string if not None
            response = {'profile_picture': profile_picture_base64, 
                        'name': username, 
                        'email': email,
                        'image_count': image_count,
                        'video_count': video_count,
                        'subscription_plan': subscription_plan,
                        'subscription_start_date': subscription_start_date,
                        'subscription_end_date': subscription_end_date
                        
                        }
            #print(response , ">>>>>userInfo")
            return jsonify(response), 200
        else:
            return jsonify({'message': 'User does not exist'}), 401
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error fetching user info'}), 500
    
@app.route('/users', methods=['GET'])
def api_get_users():
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        conn.close()
        user_list = []
        for user in users:
            user_dict = {
                'id': user[0],
                'name': user[1],
                'email': user[2],
            }
            user_list.append(user_dict)
        return jsonify(user_list), 200
    
    except Exception as e:
        print(str(e))        
        return jsonify({'message': 'failed to fetch user list'}), 500

@app.route('/users/<string:email>', methods=['DELETE'])
def api_delete_user(email):

    try:
        response = {}
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.execute("DELETE from users WHERE email = ?", (email,))
            conn.commit()
            conn.close()
            response = {'message': 'User deleted successfully'}
            return jsonify(response), 200

        else:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))        
        return jsonify({'message': 'User cannot be deleted'}), 500
    
@app.route('/users/<string:email>/password', methods=['PUT'])
def api_change_password(email):
    try:
        data = request.json  # Accept JSON payload
        reset_flag = int(data.get('reset_flag'))  # Default to 0 if not provided
        if not reset_flag:
            old_password = data.get('old_password')
            new_password = data.get('new_password')
        else:
            new_password = data.get('new_password')
            old_password = None  # No old password for reset

        salt = bcrypt.gensalt()
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        # Check if the user exists
        cursor.execute('SELECT password FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404

        elif  not(reset_flag):
            if bcrypt.checkpw(old_password.encode('utf-8'), row[0]):
                # Update the password
                cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_new_password, email))
                conn.commit()
                conn.close()
                return jsonify({'message': 'Password changed successfully'}), 200  
            else: 
                conn.close()
                return jsonify({'message': 'password does not match'}), 400

        elif reset_flag:
            
            # Update the password with the new password for the given username
            cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_new_password, email))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Password reset successfully'}), 201  


    except Exception as e:
        print(str(e))        
        return jsonify({'message': 'Error changing password'}), 500

@app.route('/users/<string:email>/reset-password', methods=['POST'])
def api_forget_password(email):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        # Check if the user exists
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404

        # Commit the transaction (though nothing is changed in this step)
        conn.commit()
        
        # Close the database connection
        conn.close()

        # Internal POST request to the second endpoint
        response = requests.post(f'http://127.0.0.1:8000/users/{email}/otp')
        if response.status_code == 200:
            return jsonify({'message': 'Password reset OTP sent'}), 200
        else:
            return jsonify({'message': 'Failed to sent Password reset OTP'}), 400

    except Exception as e:
        print(str(e))        
        return jsonify({'message': 'Error processing password reset request'}), 500

@app.route('/users', methods=['POST'])
def api_insert_user():
    try:
        data = request.json  # Accept JSON payload
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

        conn = sqlite3.connect(app.config['DATABASE'])  # Get the database connection from the application context
        cursor = conn.cursor()

        # Check if the user already exists
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return jsonify({'message': 'User with this email already exists'}), 400
        
        susbcription_validity = 'free'
        
        # Insert the user into the database
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({'message': 'User registered successfully'}), 201

    except Exception as e:
        print(str(e))
        return jsonify({'message': 'User registration failed'}), 500
    
@app.route('/users/<string:email>/otp', methods=['POST'])
def send_otp(email):
    try:
        otp = generate_otp()
        # Insert the OTP into the database
        conn = sqlite3.connect(app.config['DATABASE'])  # Get the database connection from the application context
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET otp = ? WHERE email = ?', (otp, email))
        conn.commit()

        to_email = email
        subject = 'OTP'
        body = f'Your OTP is: {otp}'

        # Set up the MIME
        message = MIMEMultipart()
        message['From'] = GMAIL_USER
        message['To'] = to_email
        message['Subject'] = subject
        
        # Attach the body with the msg instance
        message.attach(MIMEText(body, 'plain'))
        
        # Create SMTP session for sending the mail
        server = smtplib.SMTP('mail.devsort.net', 587)  # Use your SMTP server and port
        server.starttls()  # Enable security
        server.login(GMAIL_USER, GMAIL_PASSWORD)  # Login with email and password
        text = message.as_string()
        server.sendmail(GMAIL_USER, to_email, text)
        server.quit()
        conn.close()

        return jsonify({'message':'OTP sent Successfully'}), 200

    except Exception as e:
        print(f'Failed to send email. Error: {e}')
        return jsonify({'message': 'Failed to sent OTP'}), 500

@app.route('/users/<string:email>/verify-otp', methods=['POST'])
def verify_otp(email):
    try:
        otp = request.json.get('otp')  # Accepting OTP as part of JSON payload

        conn = sqlite3.connect(app.config['DATABASE'])  # Get the database connection from the application context
        cursor = conn.cursor()
        cursor.execute('SELECT otp FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()
        print(row)
        if row is None:
            return jsonify({'message': 'User does not exist'}), 404
        
        if row[0] == otp:
            return jsonify({'message': 'OTP verified'}), 200
        
        else:
            return jsonify({'message': 'OTP does not match'}), 400

    except Exception as e:
        print(f'Failed to match OTP. Error: {e}')
        return jsonify({'message': 'Failed to match OTP.'}), 500

@app.route('/users/<string:email>/profile-picture', methods=['POST'])
def upload_profile_picture(email):
    try:
        profile_picture = request.files['profile_picture'].read()
        # Store the profile picture in the database
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()

        if matching_user:
            cursor.execute('UPDATE users SET profile_picture = ? WHERE email = ?', (profile_picture, email))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Profile picture uploaded successfully'}), 200
        else:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error uploading profile picture'}), 500

@app.route('/users/<string:email>/profile-picture', methods=['DELETE'])
def remove_profile_picture(email):
    try:
        # Remove the profile picture from the database
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()

        if matching_user:
            cursor.execute('UPDATE users SET profile_picture = NULL WHERE email = ?', (email,))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Profile picture removed successfully'}), 200
        else:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error removing profile picture'}), 500

@app.route('/users/<string:email>/content-count', methods=['POST'])
def count_generated_content(email):
    try:
        data = request.json  # Use JSON for the request body
        content_type = data.get('content')  # 1 for image and 2 for video

        # Store the content count in the database
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()

        if matching_user:
            if content_type == 1:
                cursor.execute("SELECT image_count FROM users WHERE email = ?", (email,))
                image_count = cursor.fetchone()[0] + 1
                cursor.execute('UPDATE users SET image_count = ? WHERE email = ?', (image_count, email))
                conn.commit()
                conn.close()
                return jsonify({'message': 'Image count updated successfully'}), 200
            
            elif content_type == 2:
                cursor.execute("SELECT video_count FROM users WHERE email = ?", (email,))
                video_count = cursor.fetchone()[0] + 1
                cursor.execute('UPDATE users SET video_count = ? WHERE email = ?', (video_count, email))
                conn.commit()
                conn.close()
                return jsonify({'message': 'Video count updated successfully'}), 200
            
            else:
                conn.close()
                return jsonify({'message': 'Invalid content type provided'}), 400
        
        else:
            return jsonify({'message': 'User does not exist'}), 404

    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error updating content count'}), 500

@app.route('/users/<string:email>/check-content-image', methods=['POST'])
def check_content_image(email):
    try:
        # Read the image file from the request
        if 'gen_image_content' not in request.files:
            return jsonify({'message': 'No image file provided'}), 400
        
        contents = request.files['gen_image_content'].read()
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'message': 'User does not exist'}), 404

        client = vision_v1.ImageAnnotatorClient()

        requests = []

        image = {"content": contents}
        features = [
            {"type_": vision_v1.Feature.Type.SAFE_SEARCH_DETECTION},
        ]
        requests = [{"image": image, "features": features}]

        response = client.batch_annotate_images(requests=requests,)
        to_text = proto.Message.to_dict(response) # convert object to text
        check_flag = to_text['responses'][0]['safe_search_annotation']['adult']
        return jsonify({'message': check_flag}), 200 

    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error in checking image content'}), 500

@app.route('/subscription', methods=['GET'])
def subscription_plans():
    try:

        return jsonify({'message': subscription_plan}), 200

    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Errosr fetching subscription plan'}), 500


@app.route('/users/<string:email>/subscription', methods=['PUT'])
def add_subscription_plan(email):
    try:
        data = request.json  # Use JSON for data input
        plan = data.get('subscription_plan')

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()
        
        if matching_user:
            if plan in subscription_plan:
                # Get the current UTC date
                subscription_start_date = datetime.utcnow().date()

                if plan == "month":
                    subscription_end_date = subscription_start_date + relativedelta(months=1)
                elif plan == 'week':
                    subscription_end_date = subscription_start_date + timedelta(weeks=1)

                cursor.execute(
                    'UPDATE users SET subscription_plan = ?, subscription_start_date = ?, subscription_end_date = ? WHERE email = ?',
                    (plan, subscription_start_date, subscription_end_date, email)
                )

                conn.commit()
                conn.close()
                return jsonify({'message': 'Subscription Plan updated successfully'}), 200
            else: 
                conn.close()
                return jsonify({'message': 'Subscription Plan invalid'}), 400
            
        else:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error updating subscription plan'}), 500
    
@app.route('/users/<string:email>/subscription/validity', methods=['GET'])
def check_subscription_validity(email):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()
        
        if matching_user:
            cursor.execute("SELECT subscription_plan, subscription_end_date FROM users WHERE email = ?", (email,))
            subscription_data = cursor.fetchone()
            plan = subscription_data[0]


            if plan and plan in subscription_plan:
                image_valid = 0
                video_valid = 0

                current_date = datetime.utcnow().date()
                subscription_end_date = datetime.strptime(subscription_data[1], '%Y-%m-%d').date()

                # Check if the subscription has expired
                if current_date > subscription_end_date:
                    image_valid = 0
                    video_valid = 0
                else:
                    cursor.execute("SELECT image_count FROM users WHERE email = ?", (email,))
                    image_count = cursor.fetchone()[0]

                    if image_count < subscription_plan[plan][0]:
                        image_valid = 1
                    else:
                        image_valid = 0

                    cursor.execute("SELECT video_count FROM users WHERE email = ?", (email,))
                    video_count = cursor.fetchone()[0]

                    if video_count < subscription_plan[plan][1]:
                        video_valid = 1
                    else:
                        video_valid = 0
                conn.close()
                response = {
                    'image_plan_valid': image_valid,
                    'video_plan_valid': video_valid
                }
                return jsonify(response), 200
            
            else:
                conn.close()
                return jsonify({'message': 'Subscription Plan invalid'}), 400
            
        else:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'message': 'Error checking subscription validity'}), 500

@app.route('/')
def home():
    return "Welcome to the Home Page of Video Gen App!"

@app.route('/about')
def about():
    return "This is the About Page"

if __name__ == '__main__':
    app.run(debug=True)