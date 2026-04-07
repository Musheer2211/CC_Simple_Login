from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
import json

app = Flask(__name__)
app.secret_key = "change-this-to-a-secret-key"

DATABASE = "users.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    
    # Users table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    # OAuth clients (apps that want to use our OAuth server)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            client_secret TEXT NOT NULL,
            app_name TEXT NOT NULL,
            redirect_uris TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    # Authorization codes (short-lived, single-use)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS authorization_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            redirect_uri TEXT NOT NULL,
            scope TEXT,
            state TEXT,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES oauth_clients(client_id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    
    # Access tokens (medium-lived)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS access_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            scope TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES oauth_clients(client_id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    
    # Refresh tokens (long-lived)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES oauth_clients(client_id),
            FOREIGN KEY(user_id) REFERENCES users(id)
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


# ============================================================================
# OAuth 2.0 Helper Functions
# ============================================================================

def generate_authorization_code(length=32):
    """Generate a cryptographically secure authorization code."""
    return secrets.token_urlsafe(length)


def generate_access_token(length=32):
    """Generate a cryptographically secure access token."""
    return secrets.token_urlsafe(length)


def generate_refresh_token(length=48):
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(length)


def validate_client(client_id, client_secret):
    """Validate OAuth client credentials."""
    conn = get_db_connection()
    client = conn.execute(
        "SELECT * FROM oauth_clients WHERE client_id = ?", (client_id,)
    ).fetchone()
    conn.close()
    
    if not client:
        return None
    
    if client["client_secret"] != client_secret:
        return None
    
    return client


def validate_authorization_code(code, client_id, redirect_uri):
    """Validate authorization code (must be unused and not expired)."""
    conn = get_db_connection()
    auth_code = conn.execute(
        "SELECT * FROM authorization_codes WHERE code = ? AND client_id = ? AND redirect_uri = ?",
        (code, client_id, redirect_uri)
    ).fetchone()
    conn.close()
    
    if not auth_code:
        return None
    
    if auth_code["used"]:
        return None
    
    if datetime.fromisoformat(auth_code["expires_at"]) < datetime.now():
        return None
    
    return auth_code


def mark_authorization_code_used(code):
    """Mark authorization code as used (prevent reuse)."""
    conn = get_db_connection()
    conn.execute("UPDATE authorization_codes SET used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()


def validate_access_token(token):
    """Validate access token and return user info if valid."""
    conn = get_db_connection()
    access_token = conn.execute(
        "SELECT * FROM access_tokens WHERE token = ?", (token,)
    ).fetchone()
    
    if not access_token:
        conn.close()
        return None
    
    if datetime.fromisoformat(access_token["expires_at"]) < datetime.now():
        conn.close()
        return None
    
    user = conn.execute(
        "SELECT id, username, email FROM users WHERE id = ?", 
        (access_token["user_id"],)
    ).fetchone()
    conn.close()
    
    return user


def validate_refresh_token(token, client_id):
    """Validate refresh token and return if valid."""
    conn = get_db_connection()
    refresh_token = conn.execute(
        "SELECT * FROM refresh_tokens WHERE token = ? AND client_id = ?",
        (token, client_id)
    ).fetchone()
    
    if not refresh_token:
        conn.close()
        return None
    
    if refresh_token["revoked"]:
        conn.close()
        return None
    
    if datetime.fromisoformat(refresh_token["expires_at"]) < datetime.now():
        conn.close()
        return None
    
    conn.close()
    return refresh_token


def require_access_token(f):
    """Decorator to require valid access token in Authorization header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing_token"}), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        user = validate_access_token(token)
        
        if not user:
            return jsonify({"error": "invalid_token"}), 401
        
        request.oauth_user = user
        return f(*args, **kwargs)
    
    return decorated_function


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
            
            # Check if user was trying to do OAuth login
            if session.get("oauth_login_pending"):
                session.pop("oauth_login_pending", None)
                return redirect(url_for("oauth_user_login"))
            
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


# ============================================================================
# OAuth 2.0 User Login (for regular users, not OAuth apps)
# ============================================================================

@app.route("/oauth/user-login")
def oauth_user_login():
    """Start OAuth login flow for regular users."""
    # If user is already logged in, skip to approval
    if "user_id" in session:
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        session["oauth_redirect"] = url_for("oauth_user_callback", _external=True)
        
        # User is logged in, proceed directly to authorization
        auth_url = (
            f"{url_for('oauth_authorize', _external=True)}"
            f"?client_id=__internal_user_login__"
            f"&redirect_uri={session['oauth_redirect']}"
            f"&scope=profile+email"
            f"&state={state}"
        )
        return redirect(auth_url)
    
    # User is not logged in, show login form with oauth pending flag
    session["oauth_login_pending"] = True
    return redirect(url_for("login"))


@app.route("/oauth/user-callback")
def oauth_user_callback():
    """Handle OAuth callback from user login flow."""
    # Verify state parameter for CSRF protection
    state = request.args.get("state")
    if state != session.get("oauth_state"):
        flash("Security error: State mismatch. Please try logging in again.", "error")
        return redirect(url_for("login"))
    
    # Get authorization code
    code = request.args.get("code")
    if not code:
        flash("Login failed: No authorization code received.", "error")
        return redirect(url_for("login"))
    
    # Exchange code for access token (internal process, no external call)
    conn = get_db_connection()
    
    # Validate and use the authorization code
    auth_code_record = conn.execute(
        "SELECT * FROM authorization_codes WHERE code = ? AND used = 0",
        (code,)
    ).fetchone()
    
    if not auth_code_record:
        conn.close()
        flash("Login failed: Invalid or expired authorization code.", "error")
        return redirect(url_for("login"))
    
    if datetime.fromisoformat(auth_code_record["expires_at"]) < datetime.now():
        conn.close()
        flash("Login failed: Authorization code expired.", "error")
        return redirect(url_for("login"))
    
    # Mark code as used
    conn.execute("UPDATE authorization_codes SET used = 1 WHERE code = ?", (code,))
    
    # Get user info
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (auth_code_record["user_id"],)
    ).fetchone()
    
    conn.commit()
    conn.close()
    
    if not user:
        flash("Login failed: User not found.", "error")
        return redirect(url_for("login"))
    
    # Set user session
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    if user["email"]:
        session["email"] = user["email"]
    
    flash(f"Welcome, {user['username']}! You are logged in via OAuth.", "success")
    return redirect(url_for("dashboard"))


# ============================================================================
# OAuth 2.0 Server Endpoints
# ============================================================================

@app.route("/oauth/authorize", methods=["GET", "POST"])
def oauth_authorize():
    """Authorization endpoint - Step 1 of OAuth flow."""
    if request.method == "GET":
        # Redirect from client app asking for authorization
        client_id = request.args.get("client_id")
        redirect_uri = request.args.get("redirect_uri")
        state = request.args.get("state", "")
        scope = request.args.get("scope", "profile email")
        
        if not client_id or not redirect_uri:
            return "Missing required parameters: client_id, redirect_uri", 400
        
        # Special case: Internal user login (skip client validation)
        if client_id == "__internal_user_login__":
            # This is an internal OAuth flow for user login
            # Skip client validation, just check redirect_uri is from current site
            if not redirect_uri.startswith(request.host_url):
                return "Invalid redirect_uri", 400
            
            # If user is not logged in, redirect to login
            if "user_id" not in session:
                session["oauth_pending"] = {
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "state": state,
                    "scope": scope,
                    "is_user_login": True
                }
                return redirect(url_for("login"))
            
            # User is already logged in, proceed to approval
            # For user login, auto-approve (don't show consent screen)
            oauth_data = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": scope,
                "is_user_login": True
            }
            
            # Generate authorization code
            auth_code = generate_authorization_code()
            expires_at = datetime.now() + timedelta(minutes=10)
            
            conn = get_db_connection()
            conn.execute(
                """
                INSERT INTO authorization_codes 
                (code, client_id, user_id, redirect_uri, scope, state, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (auth_code, client_id, session["user_id"], redirect_uri, scope, state, expires_at.isoformat())
            )
            conn.commit()
            conn.close()
            
            # Redirect back with code
            redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
            return redirect(redirect_url)
        
        # Regular OAuth client flow
        # Validate client
        conn = get_db_connection()
        client = conn.execute(
            "SELECT * FROM oauth_clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        conn.close()
        
        if not client:
            return "Invalid client_id", 400
        
        # Check if redirect_uri is valid for this client
        allowed_uris = client["redirect_uris"].split(",")
        if redirect_uri not in allowed_uris:
            return "Invalid redirect_uri for this client", 400
        
        # If user is not logged in, redirect to login
        if "user_id" not in session:
            session["oauth_pending"] = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": scope
            }
            return redirect(url_for("login"))
        
        # Show consent screen (user is logged in)
        session["oauth_pending"] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope
        }
        return render_template(
            "oauth_consent.html",
            client_name=client["app_name"],
            scopes=scope.split()
        )
    
    # POST - User approved consent
    if "user_id" not in session:
        return "User not authenticated", 401
    
    oauth_data = session.get("oauth_pending")
    if not oauth_data:
        return "No pending authorization", 400
    
    client_id = oauth_data["client_id"]
    redirect_uri = oauth_data["redirect_uri"]
    state = oauth_data["state"]
    scope = oauth_data["scope"]
    
    # Generate authorization code
    auth_code = generate_authorization_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO authorization_codes 
        (code, client_id, user_id, redirect_uri, scope, state, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (auth_code, client_id, session["user_id"], redirect_uri, scope, state, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    
    # Clear pending OAuth data
    session.pop("oauth_pending", None)
    
    # Redirect back to client with authorization code
    redirect_url = f"{redirect_uri}?code={auth_code}&state={state}"
    return redirect(redirect_url)


@app.route("/oauth/token", methods=["POST"])
def oauth_token():
    """Token endpoint - Exchange authorization code for access token."""
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")
    code = request.form.get("code")
    redirect_uri = request.form.get("redirect_uri")
    grant_type = request.form.get("grant_type", "authorization_code")
    
    if not client_id or not client_secret:
        return jsonify({"error": "invalid_client"}), 401
    
    # Validate client
    client = validate_client(client_id, client_secret)
    if not client:
        return jsonify({"error": "invalid_client"}), 401
    
    if grant_type == "authorization_code":
        # Authorization code flow
        if not code or not redirect_uri:
            return jsonify({"error": "invalid_request"}), 400
        
        # Validate authorization code
        auth_code_record = validate_authorization_code(code, client_id, redirect_uri)
        if not auth_code_record:
            return jsonify({"error": "invalid_grant"}), 400
        
        # Mark code as used
        mark_authorization_code_used(code)
        
        # Generate access and refresh tokens
        access_token = generate_access_token()
        refresh_token = generate_refresh_token()
        
        access_expires = datetime.now() + timedelta(hours=1)
        refresh_expires = datetime.now() + timedelta(days=30)
        
        conn = get_db_connection()
        
        # Store access token
        conn.execute(
            """
            INSERT INTO access_tokens (token, client_id, user_id, scope, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (access_token, client_id, auth_code_record["user_id"], 
             auth_code_record["scope"], access_expires.isoformat())
        )
        
        # Store refresh token
        conn.execute(
            """
            INSERT INTO refresh_tokens (token, client_id, user_id, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (refresh_token, client_id, auth_code_record["user_id"], 
             refresh_expires.isoformat())
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh_token,
            "scope": auth_code_record["scope"]
        })
    
    elif grant_type == "refresh_token":
        # Refresh token flow
        refresh_token = request.form.get("refresh_token")
        if not refresh_token:
            return jsonify({"error": "invalid_request"}), 400
        
        # Validate refresh token
        refresh_record = validate_refresh_token(refresh_token, client_id)
        if not refresh_record:
            return jsonify({"error": "invalid_grant"}), 400
        
        # Generate new access token
        new_access_token = generate_access_token()
        access_expires = datetime.now() + timedelta(hours=1)
        
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO access_tokens (token, client_id, user_id, scope, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_access_token, client_id, refresh_record["user_id"], 
             "profile email", access_expires.isoformat())
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh_token,
            "scope": "profile email"
        })
    
    else:
        return jsonify({"error": "unsupported_grant_type"}), 400


@app.route("/oauth/userinfo", methods=["GET"])
@require_access_token
def oauth_userinfo():
    """User info endpoint - Return user data for valid access token."""
    user = request.oauth_user
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "email": user["email"]
    })


# ============================================================================
# Admin Endpoints - Register OAuth Clients
# ============================================================================

@app.route("/admin/clients", methods=["GET", "POST"])
def admin_clients():
    """Admin page to register new OAuth clients."""
    if request.method == "POST":
        app_name = request.form.get("app_name", "").strip()
        redirect_uris = request.form.get("redirect_uris", "").strip()
        
        if not app_name or not redirect_uris:
            flash("App name and redirect URIs are required.", "error")
            return redirect(url_for("admin_clients"))
        
        # Generate client credentials
        client_id = f"client_{secrets.token_hex(8)}"
        client_secret = secrets.token_urlsafe(32)
        
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO oauth_clients (client_id, client_secret, app_name, redirect_uris)
                VALUES (?, ?, ?, ?)
                """,
                (client_id, client_secret, app_name, redirect_uris)
            )
            conn.commit()
            flash(
                f"OAuth Client registered! ID: {client_id} | Secret: {client_secret}",
                "success"
            )
        except Exception as e:
            flash(f"Error registering client: {str(e)}", "error")
        finally:
            conn.close()
        
        return redirect(url_for("admin_clients"))
    
    # GET - Show registered clients
    conn = get_db_connection()
    clients = conn.execute(
        "SELECT client_id, app_name, redirect_uris, created_at FROM oauth_clients ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    
    return render_template("admin_clients.html", clients=clients)


@app.route("/oauth/info", methods=["GET"])
def oauth_info():
    """OAuth server information endpoint."""
    return jsonify({
        "authorization_endpoint": url_for("oauth_authorize", _external=True),
        "token_endpoint": url_for("oauth_token", _external=True),
        "userinfo_endpoint": url_for("oauth_userinfo", _external=True),
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "scope_supported": ["profile", "email"]
    })


if __name__ == "__main__":
    app.run(debug=True,port = 8000,host="0.0.0.0")
