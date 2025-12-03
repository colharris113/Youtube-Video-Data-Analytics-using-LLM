"""
YouTube Analytics API Authentication Manager

Handles OAuth 2.0 authentication for YouTube Analytics API access.
Provides token management, refresh, and secure storage.
"""

import os
import json
import pickle
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# Google OAuth libraries
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    print("[WARNING] Google auth libraries not installed. Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")

# Local imports
from config import validate_config


class AuthManager:
    """Manages OAuth 2.0 authentication for YouTube Analytics API."""

    # OAuth scopes required for YouTube Analytics API
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly'
    ]

    # Token storage file
    TOKEN_FILE = 'token.pickle'

    def __init__(self):
        """Initialize the authentication manager."""
        self.credentials: Optional[Credentials] = None
        self.youtube_service = None
        self.analytics_service = None
        self._lock = threading.Lock()

        # Check if Google auth libraries are available
        if not GOOGLE_AUTH_AVAILABLE:
            raise ImportError(
                "Google auth libraries not installed. "
                "Install with: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )

    def load_credentials(self) -> bool:
        """
        Load credentials from token file or initiate OAuth flow.

        Returns:
            bool: True if credentials are valid and loaded
        """
        with self._lock:
            # Try to load existing credentials
            if os.path.exists(self.TOKEN_FILE):
                try:
                    with open(self.TOKEN_FILE, 'rb') as token:
                        self.credentials = pickle.load(token)
                    print(f"[OK] Loaded credentials from {self.TOKEN_FILE}")
                except Exception as e:
                    print(f"[ERROR] Failed to load credentials: {e}")
                    self.credentials = None

            # Check if credentials need refresh
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self._save_credentials()
                    print("[OK] Credentials refreshed")
                except Exception as e:
                    print(f"[ERROR] Failed to refresh credentials: {e}")
                    self.credentials = None

            return self.credentials is not None and self.credentials.valid

    def _save_credentials(self):
        """Save credentials to token file."""
        if self.credentials:
            try:
                with open(self.TOKEN_FILE, 'wb') as token:
                    pickle.dump(self.credentials, token)
                print(f"[OK] Saved credentials to {self.TOKEN_FILE}")
            except Exception as e:
                print(f"[ERROR] Failed to save credentials: {e}")

    def authenticate(self) -> bool:
        """
        Perform OAuth 2.0 authentication flow.

        Returns:
            bool: True if authentication successful
        """
        # Check if we already have valid credentials
        if self.load_credentials():
            return True

        # Get OAuth credentials from environment or client_secret.json
        client_config = self._get_client_config()
        if not client_config:
            print("[ERROR] No OAuth client configuration found")
            print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file or provide client_secret.json")
            return False

        # Create OAuth flow
        try:
            flow = InstalledAppFlow.from_client_config(
                client_config,
                scopes=self.SCOPES
            )

            # Run the OAuth flow
            print("[INFO] Starting OAuth authentication...")
            print("[INFO] A browser window will open for authentication.")
            print("[INFO] If no browser opens, check the console for the authorization URL.")

            self.credentials = flow.run_local_server(
                port=8501,  # Streamlit default port
                authorization_prompt_message="Please visit this URL to authorize the application:",
                success_message="Authentication successful! You can close this window.",
                open_browser=True
            )

            # Save credentials
            self._save_credentials()
            print("[OK] Authentication successful")
            return True

        except Exception as e:
            print(f"[ERROR] Authentication failed: {e}")
            return False

    def _get_client_config(self) -> Optional[Dict[str, Any]]:
        """
        Get OAuth client configuration from environment or file.

        Returns:
            Optional[Dict]: Client configuration dictionary
        """
        # Try environment variables first
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

        if client_id and client_secret:
            print("[INFO] Using OAuth credentials from environment variables")
            return {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": [redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }

        # Try client_secret.json file
        if os.path.exists("client_secret.json"):
            try:
                with open("client_secret.json", "r") as f:
                    config = json.load(f)
                print("[INFO] Using OAuth credentials from client_secret.json")
                return config
            except Exception as e:
                print(f"[ERROR] Failed to load client_secret.json: {e}")

        return None

    def get_youtube_service(self):
        """Get authenticated YouTube Data API service."""
        if not self.credentials:
            if not self.authenticate():
                return None

        if not self.youtube_service:
            try:
                self.youtube_service = build('youtube', 'v3', credentials=self.credentials, cache_discovery=False)
                print("[OK] YouTube Data API service created")
            except Exception as e:
                print(f"[ERROR] Failed to create YouTube service: {e}")
                return None

        return self.youtube_service

    def get_analytics_service(self):
        """Get authenticated YouTube Analytics API service."""
        if not self.credentials:
            if not self.authenticate():
                return None

        if not self.analytics_service:
            try:
                self.analytics_service = build('youtubeAnalytics', 'v2', credentials=self.credentials, cache_discovery=False)
                print("[OK] YouTube Analytics API service created")
            except Exception as e:
                print(f"[ERROR] Failed to create Analytics service: {e}")
                return None

        return self.analytics_service

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.load_credentials()

    def get_auth_status(self) -> Dict[str, Any]:
        """Get authentication status information."""
        status = {
            "authenticated": False,
            "credentials_loaded": False,
            "credentials_valid": False,
            "scopes": [],
            "expires_at": None,
            "google_auth_available": GOOGLE_AUTH_AVAILABLE
        }

        if self.credentials:
            status["credentials_loaded"] = True
            status["credentials_valid"] = self.credentials.valid
            status["authenticated"] = self.credentials.valid
            status["scopes"] = self.credentials.scopes if self.credentials.scopes else []

            if self.credentials.expiry:
                status["expires_at"] = self.credentials.expiry.isoformat()
                status["expires_in"] = (self.credentials.expiry - datetime.utcnow()).total_seconds()

        return status

    def logout(self):
        """Remove stored credentials."""
        with self._lock:
            self.credentials = None
            self.youtube_service = None
            self.analytics_service = None

            if os.path.exists(self.TOKEN_FILE):
                try:
                    os.remove(self.TOKEN_FILE)
                    print(f"[OK] Removed credentials file: {self.TOKEN_FILE}")
                except Exception as e:
                    print(f"[ERROR] Failed to remove credentials file: {e}")

            print("[OK] Logged out successfully")


# Singleton instance
_auth_manager_instance = None

def get_auth_manager() -> AuthManager:
    """Get the singleton AuthManager instance."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


if __name__ == "__main__":
    # Test the authentication manager
    print("Testing AuthManager...")

    # Check if Google auth libraries are available
    if not GOOGLE_AUTH_AVAILABLE:
        print("ERROR: Google auth libraries not installed.")
        print("Install with: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        exit(1)

    # Validate configuration
    if not validate_config():
        print("Configuration validation failed")
        exit(1)

    # Test authentication
    auth_manager = get_auth_manager()

    if auth_manager.is_authenticated():
        print("Already authenticated")
    else:
        print("Not authenticated, starting OAuth flow...")
        if auth_manager.authenticate():
            print("Authentication successful!")
        else:
            print("Authentication failed")
            exit(1)

    # Get authentication status
    status = auth_manager.get_auth_status()
    print("\nAuthentication Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    # Test service creation
    youtube_service = auth_manager.get_youtube_service()
    if youtube_service:
        print("\nYouTube Data API service created successfully")

    analytics_service = auth_manager.get_analytics_service()
    if analytics_service:
        print("YouTube Analytics API service created successfully")

    print("\nAuthManager test completed successfully!")