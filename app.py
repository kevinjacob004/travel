from flask import Flask, render_template, request, redirect, session, url_for  # Ensure url_for is included
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from datetime import timedelta
from datetime import datetime

import MySQLdb.cursors


app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'kevin_2004@vijay'
app.config['MYSQL_DB'] = 'travel_agency'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

@app.route('/')
def home():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT * FROM DESTINATION')
    destinations = cur.fetchall()
    cur.execute('SELECT * FROM PACKAGES')
    packages = cur.fetchall()
    return render_template('home.html', destinations=destinations, packages=packages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('SELECT * FROM USERS WHERE user_email = %s', (email,))
        user_data = cur.fetchone()
        
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            session['loggedin'] = True
            session['user_id'] = user_data['user_id']
            session['user_name'] = user_data['user_name']
            session['user_email'] = user_data['user_email']  # Make sure this is set here
            session.permanent = True
            return redirect('/')
        else:
            return render_template('login.html', error='Incorrect email or password')
    
    return render_template('login.html')





# @app.route('/signup', methods=['GET', 'POST'])
# def signup():
#     if request.method == 'POST':
#         name = request.form['name']
#         email = request.form['email']
#         password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
#         cur = mysql.connection.cursor()
#         cur.execute('INSERT INTO USERS (user_name, user_email, password, user_role) VALUES (%s, %s, %s, %s)', 
#                     (name, email, password, 'user'))
#         mysql.connection.commit()
#         return redirect('/login')
#     return render_template('signup.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        # Check if email already exists
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('SELECT * FROM USERS WHERE user_email = %s', (email,))
        account = cur.fetchone()

        if account:  # If account with this email exists
            error = 'Email already registered. Please use a different one.'
            return render_template('signup.html', error=error)
        else:
            # If email is unique, insert new user
            cur.execute('INSERT INTO USERS (user_name, user_email, password, user_role) VALUES (%s, %s, %s, %s)', 
                        (name, email, password, 'user'))
            mysql.connection.commit()
            return redirect('/login')
    return render_template('signup.html',page='signup')



# Add the route for bookings
@app.route('/bookings', methods=['GET', 'POST'])
def bookings():
    if 'loggedin' not in session:  # Ensure the user is logged in
        return redirect('/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        package_id = request.form.get('package_id')

        # Fetch the selected package details
        cur.execute('SELECT * FROM PACKAGES WHERE package_id = %s', (package_id,))
        package = cur.fetchone()

        if not package:
            return "Package not found", 404

        # Insert booking details into BOOKINGS table and retrieve booking ID
        cur.execute('''
            INSERT INTO BOOKINGS (user_id, package_id, booking_date, status) 
            VALUES (%s, %s, NOW(), 'pending')
        ''', (session['user_id'], package_id))
        mysql.connection.commit()
        
        # Get the last inserted booking ID
        booking_id = cur.lastrowid

        # Redirect to the payment page with booking_id
        return redirect(url_for('payment', booking_id=booking_id))

    # If it's a GET request, show the available packages for booking
    cur.execute('SELECT * FROM PACKAGES')
    packages = cur.fetchall()
    cur.close()
    
    return render_template('bookings.html', packages=packages)

@app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    if 'loggedin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch booking and package amount by joining BOOKINGS and PACKAGES
    cur.execute('''
        SELECT p.price
        FROM BOOKINGS b
        JOIN PACKAGES p ON b.package_id = p.package_id
        WHERE b.booking_id = %s
    ''', (booking_id,))
    result = cur.fetchone()

    if not result:
        return "Booking not found", 404

    amount = result['price']

    if request.method == 'POST':
        cur.execute('INSERT INTO PAYMENTS (booking_id, amount, payment_date, status) VALUES (%s, %s, NOW(), %s)',
                    (booking_id, amount, 'confirmed'))
        cur.execute('UPDATE BOOKINGS SET status = %s WHERE booking_id = %s', ('confirmed', booking_id))
        mysql.connection.commit()

        return redirect(url_for('confirmation', booking_id=booking_id))

    return render_template('payment.html', booking_id=booking_id, amount=amount)





@app.route('/confirmation/<int:booking_id>')
def confirmation(booking_id):
    if 'loggedin' in session:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Update query to join with USERS table to get user details
        cur.execute('''
            SELECT b.booking_date, b.status, p.name AS package_name, p.price AS package_price, 
                   u.user_name, u.user_email
            FROM BOOKINGS b
            JOIN PACKAGES p ON b.package_id = p.package_id
            JOIN PAYMENTS py ON py.booking_id = b.booking_id
            JOIN USERS u ON b.user_id = u.user_id  -- Join with USERS table
            WHERE b.booking_id = %s
        ''', (booking_id,))
        
        booking_details = cur.fetchone()
        cur.close()
        
        if not booking_details:
            return "Booking not found", 404  # Handle if booking is not found
        
        # Pass the booking details to the template
        return render_template('confirmation.html', booking=booking_details)
    else:
        return redirect('/login')



@app.route('/reviews', methods=['POST'])
def reviews():
    if 'loggedin' in session:
        package_id = request.form['package_id']
        rating = request.form['rating']
        comment = request.form['comment']
        user_id = session['user_id']

        cur = mysql.connection.cursor()
        cur.execute('INSERT INTO REVIEWS (user_id, package_id, rating, comment) VALUES (%s, %s, %s, %s)', 
                    (user_id, package_id, rating, comment))
        mysql.connection.commit()
        return redirect('/bookings')  # Redirect after review submission
    return redirect('/login')  # Redirect if not logged in


@app.route('/logout')
def logout():
    # Remove user session data
    session.pop('loggedin', None)
    session.pop('user_id', None)
    session.pop('user_name', None)
    # Redirect to the home page after logging out
    return redirect(url_for('home'))


@app.route('/booking-history', methods=['GET'])
def booking_history():
    if 'loggedin' in session:
        user_id = session['user_id']
        
        # Fetch user's booking history with correct status
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute('''
            SELECT b.booking_id, p.name, p.price, b.booking_date, b.status
            FROM BOOKINGS b
            JOIN PACKAGES p ON b.package_id = p.package_id
            WHERE b.user_id = %s
        ''', (user_id,))
        
        bookings = cur.fetchall()
        cur.close()
        
        return render_template('booking_history.html', bookings=bookings)
    else:
        return redirect('/login')


if __name__ == "__main__":
    app.run(debug=True)
