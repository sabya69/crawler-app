from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector
from crawler import crawl, reset_state, get_crawl_report


app = Flask(__name__)
app.secret_key = '031204'
# ------------------ ADMIN LOGIN ------------------ #
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Simple hardcoded check (replace with DB check if needed)
        if username == 'SABYASACHI' and password == '031204':
            session['admin_logged_in'] = True
            return redirect('/admin_dashboard')
        else:
            return render_template('admin_login.html', error='Invalid credentials')

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')
    return render_template('admin_dashboard.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect('/')


# ------------------ DATABASE SETUP ------------------ #
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="031204",  # change if needed
        database="feedback_db"
    )

# ------------------ CRAWLER ROUTES ------------------ #
@app.route('/', methods=['GET', 'POST'])
def index():
    results = {}
    if request.method == 'POST':
        url = request.form.get('url')
        depth = int(request.form.get('depth', 2))

        reset_state()
        crawl(url, depth)

        report = get_crawl_report()
        results = {
            "broken_links": report["broken_links"],
            "markup_issues": report["markup_issues"],
            "visited_urls": report["visited_urls"]
        }

    return render_template('index.html', results=results)
@app.route('/crawl_thankyou')
def crawl_thankyou():
    return render_template('crawl_thankyou.html')
    return redirect('/crawl_thankyou')

# ------------------ FEEDBACK ROUTES ------------------ #
@app.route('/feedback')
def feedback_form():
    return render_template('feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    name = request.form.get('name')
    email = request.form.get('email')
    experience = request.form.get('experience')
    rating = request.form.get('rating')
    suggestions = request.form.get('suggestions')

    if not all([name, email, experience, rating]):
        return "Please fill in all required fields!", 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """
            INSERT INTO feedbacks (name, email, experience, rating, suggestions)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (name, email, experience, rating, suggestions))
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return "Error saving feedback!", 500

    return render_template('thankyou.html')

# ------------------ MAIN ENTRY ------------------ #
if __name__ == '__main__':
    app.run(debug=True)
