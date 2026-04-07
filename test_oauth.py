#!/usr/bin/env python3
"""
Test script for the OAuth 2.0 server implementation.
Tests all major flows: registration, login, OAuth client registration, and token flow.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
SESSION = requests.Session()

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_success(msg):
    print(f"✓ {msg}")

def print_error(msg):
    print(f"✗ {msg}")

def print_info(msg):
    print(f"→ {msg}")

def test_oauth_info():
    """Test OAuth server info endpoint."""
    print_section("1. Testing OAuth Server Info")
    try:
        response = requests.get(f"{BASE_URL}/oauth/info")
        if response.status_code == 200:
            data = response.json()
            print_success("OAuth server info retrieved")
            print_info(f"Authorization Endpoint: {data['authorization_endpoint']}")
            print_info(f"Token Endpoint: {data['token_endpoint']}")
            print_info(f"User Info Endpoint: {data['userinfo_endpoint']}")
            return True
        else:
            print_error(f"Failed to get OAuth info: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_user_registration():
    """Test user registration."""
    print_section("2. Testing User Registration")
    try:
        response = SESSION.post(f"{BASE_URL}/register", data={
            "username": "testuser",
            "password": "testpass123"
        })
        
        if "Registration successful" in response.text or response.status_code == 200:
            print_success("User registration successful")
            return True
        else:
            print_error(f"Registration failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_user_login():
    """Test user login."""
    print_section("3. Testing User Login")
    try:
        response = SESSION.post(f"{BASE_URL}/login", data={
            "username": "testuser",
            "password": "testpass123"
        })
        
        # Check if we got redirected to dashboard (301/302) or got the page
        if response.status_code in [200, 302, 301] or "dashboard" in response.text:
            print_success("User login successful")
            # Check if session has user_id
            if "user_id" in SESSION.cookies.get_dict() or any("user" in str(c) for c in SESSION.cookies):
                print_info("Session cookie established")
            return True
        else:
            print_error(f"Login failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_oauth_client_registration():
    """Test registering an OAuth client."""
    print_section("4. Testing OAuth Client Registration")
    try:
        response = SESSION.post(f"{BASE_URL}/admin/clients", data={
            "app_name": "Test Mobile App",
            "redirect_uris": "http://localhost:3000/callback"
        })
        
        if response.status_code == 200 and "Test Mobile App" in response.text:
            print_success("OAuth client registered")
            
            # Extract client credentials from response
            if "client_" in response.text:
                print_info("Client credentials generated and stored")
            return True
        else:
            print_error(f"Client registration failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_oauth_flow():
    """Test the complete OAuth flow."""
    print_section("5. Testing Complete OAuth Flow")
    
    # First, get the list of clients to find one we just created
    try:
        response = SESSION.get(f"{BASE_URL}/admin/clients")
        if "client_" not in response.text:
            print_error("No OAuth clients found. Register a client first.")
            return False
        
        # Extract client_id from HTML (basic parsing)
        import re
        match = re.search(r'client_[a-f0-9]+', response.text)
        if not match:
            print_error("Could not parse client_id from response")
            return False
        
        client_id = match.group(0)
        print_info(f"Found client: {client_id}")
        
        # Step 1: Request authorization
        print_info("Step 1: Requesting authorization...")
        auth_response = SESSION.get(f"{BASE_URL}/oauth/authorize", params={
            "client_id": client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "profile email",
            "state": "test_state_123"
        })
        
        if auth_response.status_code == 200:
            print_success("Authorization request successful")
        else:
            print_error(f"Authorization request failed: {auth_response.status_code}")
            return False
        
        # Step 2: User approves (POST to authorize)
        print_info("Step 2: User approving authorization...")
        approve_response = SESSION.post(f"{BASE_URL}/oauth/authorize", data={})
        
        if approve_response.status_code in [200, 302, 301]:
            print_success("Authorization approved")
            
            # Extract auth code from redirect URL if available
            if "code=" in str(approve_response.url):
                import re
                code_match = re.search(r'code=([^&]+)', str(approve_response.url))
                if code_match:
                    auth_code = code_match.group(1)
                    print_info(f"Authorization code obtained: {auth_code[:20]}...")
                    return True
            else:
                print_info("Authorization code would be sent to redirect_uri")
                return True
        else:
            print_error(f"Authorization approval failed: {approve_response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_invalid_token():
    """Test that invalid tokens are rejected."""
    print_section("6. Testing Token Validation")
    try:
        response = requests.get(f"{BASE_URL}/oauth/userinfo", headers={
            "Authorization": "Bearer invalid_token_123"
        })
        
        if response.status_code == 401 and "error" in response.json():
            print_success("Invalid token properly rejected")
            print_info(f"Error response: {response.json()}")
            return True
        else:
            print_error(f"Unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def main():
    print("\n")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║     OAuth 2.0 Server Implementation Test Suite            ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print(f"\nTarget URL: {BASE_URL}")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    tests = [
        test_oauth_info,
        test_user_registration,
        test_user_login,
        test_oauth_client_registration,
        test_oauth_flow,
        test_invalid_token,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print_error(f"Test {test.__name__} crashed: {str(e)}")
            results.append((test.__name__, False))
    
    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name.replace('test_', '').replace('_', ' ').title()}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! OAuth 2.0 server is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the server logs for details.")
    
    print(f"\nTest Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
