from flask import Flask, request, session, redirect, url_for, render_template, flash
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'harisjamalkhan111@gmail.com'
app.config['MAIL_PASSWORD'] = 'ochc zfwv socg nvft'  # Use the generated App Password

mail = Mail(app)

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form['email']
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['email'] = email

    msg = Message('Your OTP Code', sender='your-email@gmail.com', recipients=[email])
    msg.body = f'Your OTP code is {otp}'
    mail.send(msg)
    flash('OTP has been sent to your email.')
    return redirect(url_for('verify_otp'))

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp_route():
    if request.method == 'POST':
        otp = request.form['otp']
        if session.get('otp') == otp:
            flash('OTP verified successfully!')
            return redirect(url_for('success'))
        else:
            flash('Invalid OTP. Please try again.')
            return redirect(url_for('verify_otp'))
    return render_template('verify.html')

@app.route('/success')
def success():
    return 'OTP Verified Successfully!'

if __name__ == '__main__':
    app.run(debug=True, port=8002)
