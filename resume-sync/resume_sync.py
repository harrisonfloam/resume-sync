"""
Sync resumes from Google Drive to Dropbox in PDF form.
"""


import os
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

def is_in_github_action():
    """Return True if executing in Github Action"""
    return os.environ.get('GITHUB_ACTIONS') == 'true'
    
def get_drive_instance():
    """Uses current Google credentials to create a Google Drive API instance. Uses OAuth2 refresh token if available. 
    Prompts user for authentication if needed when not running in GitHub Actions."""
    creds = None
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    
    if is_in_github_action():
        #TODO: handle getting creds from secrets if running in a github action
        pass
    else:
        # Use refresh token if available
        if os.path.exists("google-token.json"):
            creds = Credentials.from_authorized_user_file("google-token.json", SCOPES)
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("google-creds.json", SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("google-token.json", "w") as token:
                token.write(creds.to_json())
    try:
        return build("drive", "v3", credentials=creds)
    except HttpError as error:
        print(f"An error occurred creating a Google Drive API instance: {error}")


def get_dropbox_instance():
    """Uses current Dropbox Credentials to create an API instance. Uses OAuth2 refresh token if available. 
    Prompts user for authentication if needed when not running in GitHub Actions."""
    # creds = None
    
    if is_in_github_action():
        #TODO: handle getting creds from secrets if running in a github action
        pass
    else:
        # Get app key
        with open('dropbox-creds.json', 'r') as creds_file:
            APP_KEY = json.load(creds_file)['APP_KEY']
        # Get refresh token if available
        if os.path.exists("dropbox-token.json"):
            with open('dropbox-token.json', 'r') as token_file:
                token = json.load(token_file)
                refresh_token = token.get('refresh_token')
                return dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=APP_KEY)
        else:
            # Start OAuth flow
            auth_flow = DropboxOAuth2FlowNoRedirect(consumer_key=APP_KEY, use_pkce=True, token_access_type='offline')
            authorize_url = auth_flow.start()
            print("1. Go to: " + authorize_url)
            print("2. Click 'Allow' (you might have to log in first).")
            print("3. Copy the authorization code.")
            auth_code = input("Enter the authorization code here: ").strip()

            try:
                oauth_result = auth_flow.finish(auth_code)
                with open('dropbox-token.json', 'w') as token_file:
                    json.dump({'refresh_token': oauth_result.refresh_token}, token_file)
                return dropbox.Dropbox(oauth2_refresh_token=oauth_result.refresh_token, app_key=APP_KEY)
            except Exception as error:
                print(f"An error occurred creating a Dropbox API instance: {error}")
                exit(1)



def sync():
    drive_instance = get_drive_instance()
    dropbox_instance = get_dropbox_instance()
    
    # If filename is passed in, only get that file TODO: leave this blank for now
    
    # If not, get any files in /Resume or /Resume/Targeted changed in the past week
    try:
        # Call the Drive v3 API
        results = (
            drive_instance.files()
            .list(q="mimeType='application/vnd.google-apps.folder'", pageSize=10)
            .execute()
        )
        items = results.get("files", [])

        if not items:
            print("No files found.")
            return
        print("Files:")
        for item in items:
            print(f"{item['name']} ({item['id']})")
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f"An error occurred: {error}")
    
    # Get PDFs - do we need to save them in the wdir temporarily?
    
    # Upload PDFs to Dropbox
    
    # - make sure resumes from /Targeted go back into /Targeted in Dropbox
    
    
if __name__ == "__main__":
    sync()