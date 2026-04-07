#!/usr/bin/env python3
"""
Example OAuth 2.0 Client Application
Demonstrates how to integrate with the local OAuth 2.0 server.

This is a simple Flask app that uses the OAuth server for authentication.
"""

from flask import Flask, redirect, url_for, session, render_template_string, request
import requests
import secrets
from functools import wraps

app = Flask(__name__)
app.secret_key = "client_secret_key_change_me"

# OAuth Server Configuration
OAUTH_SERVER = "http://localhost:8000"
CLIENT_ID = "client_a1b2c3d4e5f6g7h8"  # Change this to your registered client_id
CLIENT_SECRET = "your_client_secret_here"  # Change this to your client_secret
REDIRECT_URI = "http://localhost:3000/callback"

def require_login(f):
    """Decorator to require user to be logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login")
def login():
    """Redirect to OAuth server for authentication."""
    # Generate state to prevent CSRF attacks
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    
    # Redirect to OAuth server's authorization endpoint
    auth_url = (
        f"{OAUTH_SERVER}/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=profile+email"
        f"&state={state}"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    """Handle OAuth callback from authorization server."""
    
    # Verify state parameter to prevent CSRF
    state = request.args.get("state")
    if state != session.get("oauth_state"):
        return "State mismatch - possible CSRF attack", 403
    
    # Get authorization code
    code = request.args.get("code")
    if not code:
        return "Missing authorization code", 400
    
    # Exchange authorization code for tokens
    try:
        token_response = requests.post(
            f"{OAUTH_SERVER}/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        
        if token_response.status_code != 200:
            return f"Token exchange failed: {token_response.text}", 400
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        # Get user info using access token
        userinfo_response = requests.get(
            f"{OAUTH_SERVER}/oauth/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if userinfo_response.status_code != 200:
            return "Failed to get user info", 400
        
        user_info = userinfo_response.json()
        
        # Store user info and tokens in session
        session["user"] = {
            "id": user_info["id"],
            "username": user_info["username"],
            "email": user_info["email"]
        }
        session["access_token"] = access_token
        session["refresh_token"] = refresh_token
        
        return redirect(url_for("dashboard"))
        
    except Exception as e:
        return f"Error during token exchange: {str(e)}", 500

@app.route("/dashboard")
@require_login
def dashboard():
    """Protected dashboard - only accessible to logged-in users."""
    user = session.get("user", {})
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 2rem; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .card {{ 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 2rem; 
                background-color: #f9f9f9;
                margin-bottom: 1.5rem;
            }}
            .user-info {{ margin: 1rem 0; }}
            .user-info strong {{ color: #333; }}
            button {{
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }}
            button:hover {{ background-color: #da190b; }}
            .token-section {{
                background-color: #e8f5e9;
                border-left: 4px solid #4CAF50;
                padding: 1rem;
                border-radius: 4px;
                margin-top: 1.5rem;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to the OAuth 2.0 Client Example!</h1>
            
            <div class="card">
                <h2>Your Profile</h2>
                <div class="user-info">
                    <strong>ID:</strong> {user.get('id', 'N/A')}<br>
                    <strong>Username:</strong> {user.get('username', 'N/A')}<br>
                    <strong>Email:</strong> {user.get('email', 'N/A')}<br>
                </div>
                
                <div class="token-section">
                    <strong>Access Token (Bearer):</strong><br>
                    <code>{session.get('access_token', 'N/A')[:50]}...</code><br>
                    <strong>Refresh Token:</strong><br>
                    <code>{session.get('refresh_token', 'N/A')[:50]}...</code>
                </div>
                
                <button onclick="location.href='{{ url_for('logout') }}'">Logout</button>
            </div>
            
            <div class="card">
                <h3>How This Works</h3>
                <ol>
                    <li>You clicked "Login" and were redirected to the OAuth server</li>
                    <li>You authenticated with your credentials</li>
                    <li>You approved access to your profile and email</li>
                    <li>The OAuth server sent you back here with an authorization code</li>
                    <li>This app exchanged the code for access and refresh tokens</li>
                    <li>We used the access token to fetch your user information</li>
                </ol>
            </div>
            
            <div class="card">
                <h3>Test Refresh Token</h3>
                <p>
                    <a href="{{ url_for('refresh_token') }}" style="color: #2196F3; text-decoration: none;">
                        Click here to refresh your access token
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/refresh-token")
@require_login
def refresh_token():
    """Demonstrate token refresh flow."""
    refresh_token = session.get("refresh_token")
    
    if not refresh_token:
        return "No refresh token available", 400
    
    try:
        # Exchange refresh token for new access token
        token_response = requests.post(
            f"{OAUTH_SERVER}/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
        )
        
        if token_response.status_code != 200:
            return f"Token refresh failed: {token_response.text}", 400
        
        tokens = token_response.json()
        
        # Update session with new access token
        session["access_token"] = tokens.get("access_token")
        session["refresh_token"] = tokens.get("refresh_token")
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Token Refreshed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .success {{ 
                    background-color: #d4edda; 
                    border: 1px solid #c3e6cb;
                    border-radius: 4px;
                    padding: 1rem;
                    color: #155724;
                }}
                code {{ 
                    background-color: #f5f5f5; 
                    padding: 0.2rem 0.4rem; 
                    border-radius: 3px;
                    font-family: monospace;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">
                    <h2>✓ Token Refreshed Successfully!</h2>
                    <p>Your access token has been renewed using the refresh token.</p>
                    <p><strong>New Access Token:</strong><br>
                       <code>{new_access_token}</code></p>
                    <p><a href="{dashboard_url}">Back to Dashboard</a></p>
                </div>
            </div>
        </body>
        </html>
        """.format(
            new_access_token=tokens.get("access_token", "")[:50] + "...",
            dashboard_url=url_for("dashboard")
        )
        return render_template_string(html)
        
    except Exception as e:
        return f"Error refreshing token: {str(e)}", 500

@app.route("/logout")
def logout():
    """Logout user and clear session."""
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║  OAuth 2.0 Client Example Application                ║
    ║  Running on http://localhost:3000                     ║
    ║                                                        ║
    ║  Configuration:                                        ║
    ║  - CLIENT_ID: {client_id}
    ║  - REDIRECT_URI: {redirect_uri}
    ║  - OAuth Server: {server}
    ║                                                        ║
    ║  IMPORTANT:                                            ║
    ║  Make sure to update CLIENT_ID and CLIENT_SECRET      ║
    ║  in this file with your registered credentials!       ║
    ║  Register a client at http://localhost:8000/admin/    ║
    ║  clients first.                                        ║
    ╚════════════════════════════════════════════════════════╝
    """.format(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        server=OAUTH_SERVER
    ))
    
    app.run(debug=True, port=3000, host="0.0.0.0")
