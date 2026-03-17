from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "change-this-to-a-secret-key"

DATABASE = "users.db"

# OAuth Configuration
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    client_kwargs={'scope': 'openid profile email'},
    authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
    token_url='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
)


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            google_id TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT
        )
        """
    )
    conn.commit()
    conn.close()


# Some Flask versions may not expose before_first_request in the app instance.
# Use a simple flag + before_request hook to ensure the DB is initialized once.
DB_INIT_DONE = False


@app.before_request
def ensure_db_initialized():
    global DB_INIT_DONE
    if not DB_INIT_DONE:
        init_db()
        DB_INIT_DONE = True


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already taken.", "error")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html", username=session.get("username"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/login/google")
def login_google():
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/authorize/google")
def authorize_google():
    try:
        token = google.authorize_access_token()
        user_data = token.get('userinfo')
        
        if not user_data:
            flash("Failed to retrieve user information from Google.", "error")
            return redirect(url_for("login"))
        
        google_id = user_data.get('sub')
        email = user_data.get('email')
        name = user_data.get('name', email.split('@')[0])
        
        conn = get_db_connection()
        
        # Check if user exists by google_id
        user = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
        
        if user:
            # Existing user - update session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            conn.close()
            return redirect(url_for("dashboard"))
        
        # New user - create account
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, email, google_id) VALUES (?, ?, ?)",
                (name, email, google_id)
            )
            conn.commit()
            user_id = cursor.lastrowid
            
            session['user_id'] = user_id
            session['username'] = name
            session['email'] = email
            
            flash(f"Welcome {name}! You've been signed up via Google.", "success")
            conn.close()
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError as e:
            conn.close()
            flash("An account with this email already exists.", "error")
            return redirect(url_for("login"))
    
    except Exception as e:
        flash(f"An error occurred during Google login: {str(e)}", "error")
        return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True,port = 8000)
