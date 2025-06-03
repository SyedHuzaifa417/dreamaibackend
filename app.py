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
from dotenv import load_dotenv
import replicate
import time
from functools import wraps
import stripe
import json

load_dotenv() # take environment variables from .env.

stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

CORS(app) #, support_credentials=True) 

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

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
        cursor.execute("""
            SELECT name, email, profile_picture, 
                   daily_image_count, daily_video_minutes,
                   subscription_plan, subscription_duration,
                   subscription_start_date, subscription_end_date,
                   subscription_status, last_reset_date
            FROM users 
            WHERE email = ?
        """, (email,))
        existing_user = cursor.fetchone()
        conn.close()
        
        if existing_user:
            (username, email, profile_picture_blob, 
             daily_images, daily_videos,
             subscription_plan, subscription_duration,
             subscription_start_date, subscription_end_date,
             subscription_status, last_reset) = existing_user
            
            if profile_picture_blob:
                profile_picture_base64 = base64.b64encode(profile_picture_blob).decode('utf-8')
            else:
                profile_picture_base64 = None
            
            # Get subscription limits if there's an active subscription
            limits = None
            if subscription_plan and subscription_duration and subscription_status == 'active':
                limits = SUBSCRIPTION_PLANS[subscription_plan][subscription_duration]
            
            # Check if we need to reset daily counts
            if last_reset:
                last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
                today = datetime.utcnow().date()
                if last_reset < today:
                    daily_images = 0
                    daily_videos = 0
                    conn = sqlite3.connect(app.config['DATABASE'])
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE users 
                        SET daily_image_count = 0,
                            daily_video_minutes = 0,
                            last_reset_date = ?
                        WHERE email = ?
                    ''', (today, email))
                    conn.commit()
                    conn.close()
            
            response = {
                'profile_picture': profile_picture_base64,
                'name': username,
                'email': email,
                'usage': {
                    'images': daily_images,
                    'video_minutes': daily_videos
                },
                'subscription': {
                    'plan': subscription_plan,
                    'duration': subscription_duration,
                    'status': subscription_status,
                    'start_date': subscription_start_date,
                    'end_date': subscription_end_date,
                    'limits': limits if limits else {
                        'images_per_day': 0,
                        'video_minutes_per_day': 0
                    }
                }
            }
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

@app.route('/users/<string:email>/create-password', methods=['POST'])
def api_create_password(email):
    try:
        data = request.json
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({'message': 'New password is required'}), 400

        salt = bcrypt.gensalt()
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404

        cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_new_password, email))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Password created successfully'}), 200

    except Exception as e:
        print(str(e))        
        return jsonify({'message': 'Error creating password'}), 500


@app.route('/users/<string:email>/profile-picture', methods=['POST'])
def upload_profile_picture(email):
    try:
        if 'profile_picture' not in request.files:
            return jsonify({'message': 'No profile picture file provided'}), 400
            
        profile_picture = request.files['profile_picture']
        if not profile_picture.filename:
            return jsonify({'message': 'No selected file'}), 400
            
        try:
            profile_picture_data = profile_picture.read()
            if not profile_picture_data:
                return jsonify({'message': 'Empty file received'}), 400
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return jsonify({'message': 'Error reading file'}), 400

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()

        if not matching_user:
            conn.close()
            return jsonify({'message': 'User does not exist'}), 404

        try:
            cursor.execute('UPDATE users SET profile_picture = ? WHERE email = ?', (profile_picture_data, email))
            conn.commit()
            
            cursor.execute("SELECT profile_picture FROM users WHERE email = ?", (email,))
            updated_picture = cursor.fetchone()
            
            if updated_picture and updated_picture[0]:
                conn.close()
                return jsonify({'message': 'Profile picture uploaded successfully'}), 200
            else:
                conn.close()
                return jsonify({'message': 'Profile picture was not saved correctly'}), 500
                
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            conn.close()
            return jsonify({'message': 'Database error while saving profile picture'}), 500
        
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")
        return jsonify({'message': f'Error uploading profile picture: {str(e)}'}), 500

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
        return jsonify({
            'status': 'success',
            'plans': SUBSCRIPTION_PLANS,
            'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY
        }), 200
    except Exception as e:
        print(str(e))
        return jsonify({'status': 'error', 'message': 'Error fetching subscription plans'}), 500


@app.route('/users/<string:email>/subscription', methods=['PUT'])
def add_subscription_plan(email):
    try:
        data = request.json
        plan_type = data.get('plan_type')  # basic, standard, professional
        duration = data.get('duration')  # weekly, monthly, yearly

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()
        
        if matching_user:
            if plan_type in SUBSCRIPTION_PLANS and duration in SUBSCRIPTION_PLANS[plan_type]:
                # Get the current UTC date
                subscription_start_date = datetime.utcnow().date()

                if duration == "monthly":
                    subscription_end_date = subscription_start_date + relativedelta(months=1)
                elif duration == 'weekly':
                    subscription_end_date = subscription_start_date + timedelta(weeks=1)
                elif duration == 'yearly':
                    subscription_end_date = subscription_start_date + relativedelta(years=1)

                cursor.execute(
                    'UPDATE users SET subscription_plan = ?, subscription_duration = ?, subscription_start_date = ?, subscription_end_date = ? WHERE email = ?',
                    (plan_type, duration, subscription_start_date, subscription_end_date, email)
                )

                conn.commit()
                conn.close()
                return jsonify({'status': 'success', 'message': 'Subscription Plan updated successfully'}), 200
            else: 
                conn.close()
                return jsonify({'status': 'error', 'message': 'Invalid subscription plan or duration'}), 400
            
        else:
            conn.close()
            return jsonify({'status': 'error', 'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'status': 'error', 'message': 'Error updating subscription plan'}), 500
    
@app.route('/users/<string:email>/subscription/validity', methods=['GET'])
def check_subscription_validity(email):
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        matching_user = cursor.fetchone()
        
        if matching_user:
            cursor.execute("SELECT subscription_plan, subscription_duration, subscription_end_date, daily_image_count, daily_video_minutes FROM users WHERE email = ?", (email,))
            subscription_data = cursor.fetchone()
            plan_type, duration, end_date, daily_images, daily_videos = subscription_data

            if plan_type and duration and plan_type in SUBSCRIPTION_PLANS and duration in SUBSCRIPTION_PLANS[plan_type]:
                image_valid = 0
                video_valid = 0

                current_date = datetime.utcnow().date()
                subscription_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

                # Check if the subscription has expired
                if current_date > subscription_end_date:
                    image_valid = 0
                    video_valid = 0
                else:
                    plan_limits = SUBSCRIPTION_PLANS[plan_type][duration]
                    
                    # Check image limits
                    if plan_limits['images_per_day'] == -1 or daily_images < plan_limits['images_per_day']:
                        image_valid = 1
                    else:
                        image_valid = 0

                    # Check video limits
                    if daily_videos < plan_limits['video_minutes_per_day']:
                        video_valid = 1
                    else:
                        video_valid = 0

                conn.close()
                response = {
                    'status': 'success',
                    'image_plan_valid': image_valid,
                    'video_plan_valid': video_valid,
                    'daily_usage': {
                        'images': daily_images,
                        'video_minutes': daily_videos
                    },
                    'limits': {
                        'images_per_day': plan_limits['images_per_day'],
                        'video_minutes_per_day': plan_limits['video_minutes_per_day']
                    }
                }
                return jsonify(response), 200
            
            else:
                conn.close()
                return jsonify({'status': 'error', 'message': 'Invalid subscription plan'}), 400
            
        else:
            conn.close()
            return jsonify({'status': 'error', 'message': 'User does not exist'}), 404
        
    except Exception as e:
        print(str(e))
        return jsonify({'status': 'error', 'message': 'Error checking subscription validity'}), 500

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        email = request.headers.get('X-User-Email')
        if not email:
            return jsonify({'message': 'Login required'}), 401
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'message': 'Invalid user'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/generate-image', methods=['POST'])
@login_required
def generate_image():
    try:
        email = request.headers.get('X-User-Email')
        data = request.json
        prompt = data.get('prompt', '')
        aspect_ratio = data.get('aspect_ratio', '1:1')
        num_inference_steps = min(data.get('num_inference_steps', 4), 4)
        seed = data.get('seed', None)  
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # Check subscription validity and usage limits
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_plan, subscription_duration, subscription_status,
                   subscription_end_date, daily_image_count, last_reset_date
            FROM users 
            WHERE email = ?
        """, (email,))
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
            
        plan, duration, status, end_date, daily_images, last_reset = user_data
        
        # Check if subscription is active
        if not plan or not duration or status != 'active':
            conn.close()
            return jsonify({'message': 'No active subscription'}), 403
            
        # Check subscription end date
        current_date = datetime.utcnow().date()
        subscription_end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        if not subscription_end_date or current_date > subscription_end_date:
            conn.close()
            return jsonify({'message': 'Subscription has expired'}), 403
            
        # Check daily reset
        if last_reset:
            last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
            if last_reset < current_date:
                daily_images = 0
                cursor.execute('''
                    UPDATE users 
                    SET daily_image_count = 0,
                        last_reset_date = ?
                    WHERE email = ?
                ''', (current_date, email))
                conn.commit()
        
        # Check usage limits
        plan_limits = SUBSCRIPTION_PLANS[plan][duration]
        if plan_limits['images_per_day'] != -1 and daily_images >= plan_limits['images_per_day']:
            conn.close()
            return jsonify({'message': 'Daily image limit reached'}), 403

        valid_aspect_ratios = ['1:1', '16:9', '9:16', '4:3', '3:4']
        if aspect_ratio not in valid_aspect_ratios:
            return jsonify({
                'status': 'error',
                'message': f'Invalid aspect ratio. Must be one of: {", ".join(valid_aspect_ratios)}'
            }), 400

        input_params = {
            "prompt": prompt,
            "go_fast": True,
            "megapixels": "1",
            "num_outputs": 1,
            "aspect_ratio": aspect_ratio,
            "output_format": "webp",
            "output_quality": 80,
            "num_inference_steps": num_inference_steps
        }

        if seed is not None:
            input_params["seed"] = seed

        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input=input_params
        )

        if output and isinstance(output, list) and len(output) > 0:
            image_url = str(output[0]) if output[0] else None
            
            if image_url:
                # Update image count
                cursor.execute('UPDATE users SET daily_image_count = daily_image_count + 1 WHERE email = ?', (email,))
                conn.commit()
                conn.close()
                
                return jsonify({
                    'status': 'success',
                    'image_url': image_url,
                    'parameters_used': {
                        'prompt': prompt,
                        'aspect_ratio': aspect_ratio,
                        'num_inference_steps': num_inference_steps,
                        'seed': seed
                    }
                }), 200
            else:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': 'Generated image URL is invalid'
                }), 500
        else:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate image'
            }), 500

    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/generate-video', methods=['POST'])
@login_required
def generate_video():
    try:
        email = request.headers.get('X-User-Email')
        data = request.json
        prompt = data.get('prompt', '')
        
        # Check subscription validity and usage limits
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_plan, subscription_duration, subscription_status,
                   subscription_end_date, daily_video_minutes, last_reset_date
            FROM users 
            WHERE email = ?
        """, (email,))
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
            
        plan, duration, status, end_date, daily_videos, last_reset = user_data
        
        # Check if subscription is active
        if not plan or not duration or status != 'active':
            conn.close()
            return jsonify({'message': 'No active subscription'}), 403
            
        # Check subscription end date
        current_date = datetime.utcnow().date()
        subscription_end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        if not subscription_end_date or current_date > subscription_end_date:
            conn.close()
            return jsonify({'message': 'Subscription has expired'}), 403
            
        # Check daily reset
        if last_reset:
            last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
            if last_reset < current_date:
                daily_videos = 0
                cursor.execute('''
                    UPDATE users 
                    SET daily_video_minutes = 0,
                        last_reset_date = ?
                    WHERE email = ?
                ''', (current_date, email))
                conn.commit()

        fast_mode = data.get('fast_mode', 'Balanced')
        if fast_mode not in ['Balanced', 'Speed', 'Quality']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid fast_mode. Must be one of: Balanced, Speed, Quality'
            }), 400

        num_frames = min(data.get('num_frames', 81), 81)  
        aspect_ratio = data.get('aspect_ratio', '16:9')
        if aspect_ratio not in ['16:9', '9:16', '1:1', '4:3', '3:4']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid aspect_ratio. Must be one of: 16:9, 9:16, 1:1, 4:3, 3:4'
            }), 400

        sample_shift = min(max(data.get('sample_shift', 5), 1), 10)  
        sample_steps = min(max(data.get('sample_steps', 30), 20), 50) 
        frames_per_second = min(max(data.get('frames_per_second', 16), 8), 30)  
        sample_guide_scale = min(max(data.get('sample_guide_scale', 5), 1), 20) 

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # Calculate video duration in minutes
        video_duration = (num_frames / frames_per_second) / 60  # Convert to minutes
        
        # Check video usage limits
        plan_limits = SUBSCRIPTION_PLANS[plan][duration]
        if daily_videos + video_duration > plan_limits['video_minutes_per_day']:
            conn.close()
            return jsonify({'message': 'Daily video minutes limit would be exceeded'}), 403

        input_params = {
            "prompt": prompt,
            "fast_mode": fast_mode,
            "lora_scale": 1,
            "num_frames": num_frames,
            "aspect_ratio": aspect_ratio,
            "sample_shift": sample_shift,
            "sample_steps": sample_steps,
            "frames_per_second": frames_per_second,
            "sample_guide_scale": sample_guide_scale
        }

        prediction = replicate.predictions.create(
            version="wavespeedai/wan-2.1-t2v-480p",
            input=input_params
        )

        while prediction.status not in ["succeeded", "failed", "canceled"]:
            prediction.reload()
            time.sleep(1)  

        if prediction.status == "succeeded":
            # Get the output URL
            video_url = prediction.output
            if video_url:
                # Update video minutes count
                cursor.execute('UPDATE users SET daily_video_minutes = daily_video_minutes + ? WHERE email = ?', 
                             (video_duration, email))
                conn.commit()
                conn.close()
                
                return jsonify({
                    'status': 'success',
                    'video_url': video_url,
                    'prediction_id': prediction.id,
                    'parameters_used': {
                        'prompt': prompt,
                        'fast_mode': fast_mode,
                        'num_frames': num_frames,
                        'aspect_ratio': aspect_ratio,
                        'sample_shift': sample_shift,
                        'sample_steps': sample_steps,
                        'frames_per_second': frames_per_second,
                        'sample_guide_scale': sample_guide_scale
                    }
                }), 200
            else:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': 'Video generation completed but no URL was returned'
                }), 500
        elif prediction.status == "failed":
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Video generation failed: {prediction.error}'
            }), 500
        else:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Video generation was {prediction.status}'
            }), 500

    except Exception as e:
        print(f"Error generating video: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error during video generation: {str(e)}'
        }), 500

@app.route('/api/image-to-video', methods=['POST'])
@login_required
def image_to_video():
    try:
        email = request.headers.get('X-User-Email')
        
        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image file provided'}), 400
            
        image_file = request.files['image']
        if not image_file.filename:
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400

        try:
            image_data = image_file.read()
            if not image_data:
                return jsonify({'status': 'error', 'message': 'Empty file received'}), 400
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Error reading file'}), 400

        prompt = request.form.get('prompt')
        if not prompt:
            return jsonify({'status': 'error', 'message': 'Prompt is required'}), 400

        max_area = request.form.get('max_area', '720x1280')
        fast_mode = request.form.get('fast_mode', 'Balanced')
        lora_scale = min(max(float(request.form.get('lora_scale', 1)), 0.1), 2)
        num_frames = min(int(request.form.get('num_frames', 81)), 81)
        sample_shift = min(max(int(request.form.get('sample_shift', 5)), 1), 10)
        sample_steps = min(max(int(request.form.get('sample_steps', 30)), 20), 50)
        frames_per_second = min(max(int(request.form.get('frames_per_second', 16)), 8), 30)
        sample_guide_scale = min(max(int(request.form.get('sample_guide_scale', 5)), 1), 20)

        if fast_mode not in ['Balanced', 'Speed', 'Quality']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid fast_mode. Must be one of: Balanced, Speed, Quality'
            }), 400

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_plan, subscription_duration, subscription_status,
                   subscription_end_date, daily_video_minutes, last_reset_date
            FROM users 
            WHERE email = ?
        """, (email,))
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
            
        plan, duration, status, end_date, daily_videos, last_reset = user_data
        
        if not plan or not duration or status != 'active':
            conn.close()
            return jsonify({'message': 'No active subscription'}), 403
            
        # Check subscription end date
        current_date = datetime.utcnow().date()
        subscription_end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        if not subscription_end_date or current_date > subscription_end_date:
            conn.close()
            return jsonify({'message': 'Subscription has expired'}), 403
            
        if last_reset:
            last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
            if last_reset < current_date:
                daily_videos = 0
                cursor.execute('''
                    UPDATE users 
                    SET daily_video_minutes = 0,
                        last_reset_date = ?
                    WHERE email = ?
                ''', (current_date, email))
                conn.commit()

        video_duration = (num_frames / frames_per_second) / 60  
        plan_limits = SUBSCRIPTION_PLANS[plan][duration]
        if daily_videos + video_duration > plan_limits['video_minutes_per_day']:
            conn.close()
            return jsonify({'message': 'Daily video minutes limit would be exceeded'}), 403

        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f'temp_{int(time.time())}_{image_file.filename}')
        
        try:
            with open(temp_file_path, 'wb') as f:
                f.write(image_data)
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_url = f"data:image/{image_file.content_type};base64,{image_base64}"

            input_params = {
                "image": image_url,
                "prompt": prompt,
                "max_area": max_area,
                "fast_mode": fast_mode,
                "lora_scale": lora_scale,
                "num_frames": num_frames,
                "sample_shift": sample_shift,
                "sample_steps": sample_steps,
                "frames_per_second": frames_per_second,
                "sample_guide_scale": sample_guide_scale
            }

            prediction = replicate.predictions.create(
                version="wavespeedai/wan-2.1-i2v-720p",
                input=input_params
            )

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                prediction.reload()
                time.sleep(1)  

            if prediction.status == "succeeded":
                video_url = prediction.output
                if video_url:
                    cursor.execute('UPDATE users SET daily_video_minutes = daily_video_minutes + ? WHERE email = ?', 
                                 (video_duration, email))
                    conn.commit()
                    conn.close()
                    
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                    
                    return jsonify({
                        'status': 'success',
                        'video_url': video_url,
                        'prediction_id': prediction.id,
                        'parameters_used': input_params
                    }), 200
                else:
                    conn.close()
                    return jsonify({
                        'status': 'error',
                        'message': 'Video generation completed but no URL was returned'
                    }), 500
            elif prediction.status == "failed":
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Video generation failed: {prediction.error}'
                }), 500
            else:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': f'Video generation was {prediction.status}'
                }), 500

        finally:
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass

    except Exception as e:
        print(f"Error generating image-to-video: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error during image-to-video generation: {str(e)}'
        }), 500

@app.route('/api/image-to-image', methods=['POST'])
@login_required
def image_to_image():
    try:
        email = request.headers.get('X-User-Email')
        
        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image file provided'}), 400
            
        image_file = request.files['image']
        if not image_file.filename:
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400

        try:
            image_data = image_file.read()
            if not image_data:
                return jsonify({'status': 'error', 'message': 'Empty file received'}), 400
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Error reading file'}), 400

        prompt = request.form.get('prompt')
        if not prompt:
            return jsonify({'status': 'error', 'message': 'Prompt is required'}), 400

        go_fast = request.form.get('go_fast', 'true').lower() == 'true'
        guidance = min(max(float(request.form.get('guidance', 3.5)), 1), 20)
        megapixels = request.form.get('megapixels', '1')
        num_outputs = min(int(request.form.get('num_outputs', 1)), 4)
        aspect_ratio = request.form.get('aspect_ratio', '1:1')
        output_format = request.form.get('output_format', 'webp')
        output_quality = min(max(int(request.form.get('output_quality', 80)), 1), 100)
        prompt_strength = min(max(float(request.form.get('prompt_strength', 0.8)), 0), 1)
        num_inference_steps = min(max(int(request.form.get('num_inference_steps', 28)), 1), 50)

        valid_aspect_ratios = ['1:1', '16:9', '9:16', '4:3', '3:4']
        if aspect_ratio not in valid_aspect_ratios:
            return jsonify({
                'status': 'error',
                'message': f'Invalid aspect ratio. Must be one of: {", ".join(valid_aspect_ratios)}'
            }), 400

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_plan, subscription_duration, subscription_status,
                   subscription_end_date, daily_image_count, last_reset_date
            FROM users 
            WHERE email = ?
        """, (email,))
        user_data = cursor.fetchone()
        
        if not user_data:
            conn.close()
            return jsonify({'message': 'User not found'}), 404
            
        plan, duration, status, end_date, daily_images, last_reset = user_data
        
        if not plan or not duration or status != 'active':
            conn.close()
            return jsonify({'message': 'No active subscription'}), 403
            
        current_date = datetime.utcnow().date()
        subscription_end_date = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        if not subscription_end_date or current_date > subscription_end_date:
            conn.close()
            return jsonify({'message': 'Subscription has expired'}), 403
            
        if last_reset:
            last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
            if last_reset < current_date:
                daily_images = 0
                cursor.execute('''
                    UPDATE users 
                    SET daily_image_count = 0,
                        last_reset_date = ?
                    WHERE email = ?
                ''', (current_date, email))
                conn.commit()
        
        plan_limits = SUBSCRIPTION_PLANS[plan][duration]
        if plan_limits['images_per_day'] != -1 and daily_images >= plan_limits['images_per_day']:
            conn.close()
            return jsonify({'message': 'Daily image limit reached'}), 403

        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f'temp_{int(time.time())}_{image_file.filename}')
        
        try:
            with open(temp_file_path, 'wb') as f:
                f.write(image_data)
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_url = f"data:image/{image_file.content_type};base64,{image_base64}"

            input_params = {
                "prompt": prompt,
                "go_fast": go_fast,
                "image": image_url,
                "guidance": guidance,
                "megapixels": megapixels,
                "num_outputs": num_outputs,
                "aspect_ratio": aspect_ratio,
                "output_format": output_format,
                "output_quality": output_quality,
                "prompt_strength": prompt_strength,
                "num_inference_steps": num_inference_steps
            }

            output = replicate.run(
                "black-forest-labs/flux-dev",
                input=input_params
            )

            if output and isinstance(output, list) and len(output) > 0:
                image_url = str(output[0]) if output[0] else None
                
                if image_url:
                    cursor.execute('UPDATE users SET daily_image_count = daily_image_count + 1 WHERE email = ?', (email,))
                    conn.commit()
                    conn.close()
                    
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                    
                    return jsonify({
                        'status': 'success',
                        'image_url': image_url,
                        'parameters_used': input_params
                    }), 200
                else:
                    conn.close()
                    return jsonify({
                        'status': 'error',
                        'message': 'Generated image URL is invalid'
                    }), 500
            else:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to generate image'
                }), 500

        finally:
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except:
                pass

    except Exception as e:
        print(f"Error generating image-to-image: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ////////////////////////////////// subscription endpoints ///////////////////////////////////////

@app.route('/subscription/plans', methods=['GET'])
def get_subscription_plans():
    try:
        return jsonify({
            'status': 'success',
            'plans': SUBSCRIPTION_PLANS,
            'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY
        }), 200
    except Exception as e:
        print(f"Error fetching subscription plans: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/subscription/webhook', methods=['POST'])
def stripe_webhook():
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            print(f"Invalid payload: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
           
            print(f"Invalid signature: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400

        print(f"Processing webhook event: {event['type']}")
        
        if event['type'] == 'checkout.session.completed':
            handle_checkout_session_completed(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
          
            subscription = event['data']['object']['subscription']
            if subscription:
                handle_subscription_updated(stripe.Subscription.retrieve(subscription))
        elif event['type'] == 'invoice.payment_failed':
          
            subscription = event['data']['object']['subscription']
            if subscription:
                handle_subscription_updated(stripe.Subscription.retrieve(subscription))
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/subscription/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        data = request.json
        email = request.headers.get('X-User-Email')
        plan_type = data.get('plan_type')  # basic, standard, professional
        duration = data.get('duration')  # weekly, monthly, yearly
        
        if not plan_type or not duration:
            return jsonify({'status': 'error', 'message': 'Plan type and duration are required'}), 400
            
        if plan_type not in SUBSCRIPTION_PLANS or duration not in SUBSCRIPTION_PLANS[plan_type]:
            return jsonify({'status': 'error', 'message': 'Invalid plan type or duration'}), 400

        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT stripe_customer_id, stripe_subscription_id, subscription_status FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        
        customer_id = None
        current_subscription_id = None
        current_status = None

        if result:
            stored_customer_id = result[0]
            current_subscription_id = result[1]
            current_status = result[2]

            try:
                if stored_customer_id:
                    customer = stripe.Customer.retrieve(stored_customer_id)
                    customer_id = customer.id
            except stripe.error.InvalidRequestError:
                customer_id = None
            except Exception as e:
                print(f"Error retrieving customer: {str(e)}")
                customer_id = None

        if not customer_id:
            try:
                customer = stripe.Customer.create(
                    email=email,
                    metadata={'migrated_from_test': 'true'}  
                )
                customer_id = customer.id
                # Update the database with the new customer ID
                cursor.execute("UPDATE users SET stripe_customer_id = ? WHERE email = ?", (customer_id, email))
                conn.commit()
            except Exception as e:
                print(f"Error creating new customer: {str(e)}")
                conn.close()
                return jsonify({'status': 'error', 'message': 'Error creating customer account'}), 500

        if current_subscription_id and current_status == 'active':
            try:
                # Cancel the current subscription immediately
                stripe.Subscription.delete(current_subscription_id)
                print(f"Cancelled existing subscription {current_subscription_id}")
            except stripe.error.StripeError as e:
                print(f"Error cancelling existing subscription: {str(e)}")
             
        price_id = STRIPE_PRICE_IDS[plan_type][duration]
        if not price_id:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Invalid price ID for the selected plan'}), 400

        try:
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='{FRONTEND_URL}/account?session_id={CHECKOUT_SESSION_ID}&status=success',
                cancel_url='{FRONTEND_URL}/subscriptions?status=cancelled',
                metadata={
                    'user_email': email,
                    'plan_type': plan_type,
                    'duration': duration,
                    'previous_subscription_id': current_subscription_id
                }
            )
            
            conn.close()
            return jsonify({
                'status': 'success',
                'session_id': checkout_session.id,
                'url': checkout_session.url
            }), 200

        except stripe.error.StripeError as e:
            print(f"Stripe error creating checkout session: {str(e)}")
            conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 400

    except Exception as e:
        print(f"Error creating checkout session: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_checkout_session_completed(session):
    try:
        print("Starting to handle checkout session completed")
        email = session['metadata']['user_email']
        plan_type = session['metadata']['plan_type']
        duration = session['metadata']['duration']
        subscription_id = session['subscription']
        previous_subscription_id = session['metadata'].get('previous_subscription_id')
        
        print(f"Processing subscription for user: {email}")
        print(f"Plan: {plan_type}, Duration: {duration}")
        print(f"Subscription ID: {subscription_id}")
        print(f"Previous Subscription ID: {previous_subscription_id}")
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        start_date = datetime.utcnow().date()
        if duration == 'weekly':
            end_date = start_date + timedelta(weeks=1)
        elif duration == 'monthly':
            end_date = start_date + relativedelta(months=1)
        else:  
            end_date = start_date + relativedelta(years=1)
            
        print(f"Setting subscription dates - Start: {start_date}, End: {end_date}")
        
        if previous_subscription_id:
            cursor.execute('''
                UPDATE subscription_history 
                SET status = 'cancelled',
                    end_date = ?
                WHERE stripe_subscription_id = ?
            ''', (start_date, previous_subscription_id))
        
        cursor.execute('''
            UPDATE users 
            SET subscription_plan = ?,
                subscription_duration = ?,
                subscription_status = 'active',
                stripe_subscription_id = ?,
                subscription_start_date = ?,
                subscription_end_date = ?,
                last_reset_date = ?,
                daily_image_count = 0,
                daily_video_minutes = 0
            WHERE email = ?
        ''', (plan_type, duration, subscription_id, start_date, end_date, start_date, email))
        
        # Add to subscription history
        cursor.execute('''
            INSERT INTO subscription_history 
            (user_email, subscription_plan, subscription_duration, stripe_subscription_id, start_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (email, plan_type, duration, subscription_id, start_date, 'active'))
        
        conn.commit()
        
        cursor.execute('''
            SELECT subscription_plan, subscription_duration, subscription_status, 
                   subscription_start_date, subscription_end_date
            FROM users 
            WHERE email = ?
        ''', (email,))
        result = cursor.fetchone()
        print(f"Updated user data: {result}")
        
        conn.close()
        print("Successfully completed subscription update")
        
    except Exception as e:
        print(f"Error handling checkout session completed: {str(e)}")
        raise e

def handle_subscription_updated(subscription):
    try:
        subscription_id = subscription['id']
        status = subscription['status']
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        if status == 'active':
            cursor.execute('''
                UPDATE users 
                SET subscription_status = 'active'
                WHERE stripe_subscription_id = ?
            ''', (subscription_id,))
        elif status == 'past_due':
            cursor.execute('''
                UPDATE users 
                SET subscription_status = 'past_due'
                WHERE stripe_subscription_id = ?
            ''', (subscription_id,))
            
        cursor.execute('''
            UPDATE subscription_history 
            SET status = ?
            WHERE stripe_subscription_id = ?
        ''', (status, subscription_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error handling subscription updated: {str(e)}")
        raise e

def handle_subscription_deleted(subscription):
    try:
        subscription_id = subscription['id']
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET subscription_status = 'inactive',
                subscription_plan = NULL,
                subscription_duration = NULL,
                stripe_subscription_id = NULL,
                subscription_end_date = ?
            WHERE stripe_subscription_id = ?
        ''', (datetime.utcnow().date(), subscription_id))
        
        # Update subscription history
        cursor.execute('''
            UPDATE subscription_history 
            SET status = 'cancelled',
                end_date = ?
            WHERE stripe_subscription_id = ?
        ''', (datetime.utcnow().date(), subscription_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error handling subscription deleted: {str(e)}")
        raise e

@app.route('/subscription/status', methods=['GET'])
@login_required
def get_subscription_status():
    try:
        email = request.headers.get('X-User-Email')
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute('''
            SELECT subscription_plan, subscription_duration, subscription_status,
                   subscription_start_date, subscription_end_date, daily_image_count,
                   daily_video_minutes, last_reset_date
            FROM users 
            WHERE email = ?
        ''', (email,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
            
        plan, duration, status, start_date, end_date, daily_images, daily_videos, last_reset = result
        
        if last_reset:
            last_reset = datetime.strptime(last_reset, '%Y-%m-%d').date()
            today = datetime.utcnow().date()
            if last_reset < today:
                conn = sqlite3.connect(app.config['DATABASE'])
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET daily_image_count = 0,
                        daily_video_minutes = 0,
                        last_reset_date = ?
                    WHERE email = ?
                ''', (today, email))
                conn.commit()
                conn.close()
                daily_images = 0
                daily_videos = 0
        
        if not plan or not duration:
            return jsonify({
                'status': 'success',
                'subscription': {
                    'status': 'inactive',
                    'plan': None,
                    'duration': None,
                    'start_date': None,
                    'end_date': None,
                    'daily_usage': {
                        'images': 0,
                        'video_minutes': 0
                    }
                }
            }), 200
            
        plan_limits = SUBSCRIPTION_PLANS[plan][duration]
        
        return jsonify({
            'status': 'success',
            'subscription': {
                'status': status,
                'plan': plan,
                'duration': duration,
                'start_date': start_date,
                'end_date': end_date,
                'limits': {
                    'images_per_day': plan_limits['images_per_day'],
                    'video_minutes_per_day': plan_limits['video_minutes_per_day']
                },
                'daily_usage': {
                    'images': daily_images,
                    'video_minutes': daily_videos
                }
            }
        }), 200
        
    except Exception as e:
        print(f"Error getting subscription status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    try:
        email = request.headers.get('X-User-Email')
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("SELECT stripe_subscription_id FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            return jsonify({'status': 'error', 'message': 'No active subscription found'}), 404
            
        subscription_id = result[0]
        
        # Cancel the subscription at period end
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Subscription will be cancelled at the end of the billing period'
        }), 200
        
    except Exception as e:
        print(f"Error cancelling subscription: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def home():
    return "Welcome to the Home Page of Video Gen App!"

@app.route('/about')
def about():
    return "This is the About Page"

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)