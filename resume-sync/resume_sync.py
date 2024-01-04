"""
Sync resumes from Google Drive to Dropbox in PDF form.
"""


import os
import dropbox
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

def is_in_github_action():
    """Return True if executing in Github Action"""
    return os.environ.get('GITHUB_ACTIONS') == 'true'
    
def get_google_creds():
    """Get current Google credentials. Uses OAuth2 refresh token if available. Prompts user for authentication if needed when not running in GitHub Actions."""
    creds = None
    if is_in_github_action():
        #TODO: handle getting creds from secrets if running in a github action
        pass
    else:
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        
        # Use refresh token if available
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())

    return creds


def get_dropbox_creds():
    # Get Dropbox credentials
    with open('dropbox-creds.json') as f:
        dropbox_creds = json.load(f).get('token')


def sync():
    google_creds = get_google_creds()
    dropbox_creds = get_dropbox_creds()
    
    # If filename is passed in, only get that file TODO: leave this blank for now
    
    # If not, get any files in /Resume or /Resume/Targeted changed in the past week
    
    # Get PDFs - do we need to save them in the wdir temporarily?
    
    # Upload PDFs to Dropbox
    
    # - make sure resumes from /Targeted go back into /Targeted in Dropbox
    
    
if __name__ == "__main__":
    get_google_creds()