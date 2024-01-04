"""
Sync resumes from Google Drive to Dropbox in PDF form.
"""


import os
import io
import json
import shutil
from datetime import date, datetime, timedelta
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.files import WriteMode
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

def is_in_github_action():
    """Return True if executing in Github Action"""
    
    check = os.environ.get('GITHUB_ACTIONS') == 'true'
    
    if check:
        print("====== Executing with GitHub Actions. ======")
    
    return check
    
def get_drive_instance():
    """Uses current Google credentials to create a Google Drive API instance. Uses OAuth2 refresh token if available. 
    Prompts user for authentication if needed when not running in GitHub Actions."""
    creds = None
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    
    if is_in_github_action():
        #TODO: handle getting creds from secrets if running in a github action
        GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN')

        # Use refresh token if available
        token = json.loads(GOOGLE_TOKEN)
        creds = Credentials.from_authorized_user_info(token, SCOPES)
        
        # If there are no (valid) credentials available, attempt to refresh the token.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                print("Error: User authentication required, please run locally to refresh Google credentials.")        
        
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
                
    print ("====== Authenticated Google credentials. ======")
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
        DROPBOX_CREDS = os.environ.get('DROPBOX_CREDS')
        DROPBOX_TOKEN = os.environ.get('DROPBOX_TOKEN')
        
        # Use refresh token if available
        APP_KEY = json.load(DROPBOX_CREDS)['APP_KEY']
        token = json.load(DROPBOX_TOKEN)
        refresh_token = token.get('refresh_token')
        return dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=APP_KEY)
        
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
                
    print("====== Authenticated Dropbox credentials. ======")

def get_recently_modified_resumes(drive_instance):
    """Download files modified in the past week from /Resumes and /Resumes/Targeted."""
    # Calculate one week ago date
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    one_week_ago_str = one_week_ago.isoformat() + 'Z'  # Format for Google Drive API

    print("====== Downloading recently modified resumes from Google Docs ======")
    try:
        # Folder IDs
        resume_folder_id = '1FQAXueyM20GCbD4g1fn4EZjV4XawAGkC'
        targeted_folder_id = '1bXW8_I_x7__gu30XbmmqdftH_fNyst2-'
        #TODO: add cover letters
        
        # Get files
        query = f"(parents = '{resume_folder_id}' or parents = '{targeted_folder_id}') and " \
                f"modifiedTime > '{one_week_ago_str}'and " \
                f"mimeType != 'application/vnd.google-apps.folder'"
        fields = "files(id, name, modifiedTime, parents)"
        results = drive_instance.files().list(q=query, pageSize=10, fields=fields).execute()
        items = results.get("files", [])

        # Download files to /temp_pdf
        if not items:
            print("No files found in the past week.")
        else:
            print("Files modified in the past week:")
            for item in items:
                print(f"{item['name']} (Modified: {item['modifiedTime']}, ID: {item['id']}, Parent: {item['parents'][0]})")
                
                request = drive_instance.files().export(fileId=item['id'], mimeType='application/pdf')
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                
                while not done:
                    status, done = downloader.next_chunk()
                
                fh.seek(0)
                
                # Create filepaths
                if item['parents'][0] == resume_folder_id:
                    folderpath = 'Resume'
                elif item['parents'][0] == targeted_folder_id:
                    folderpath = 'Resume/Targeted'
                else:
                    raise FileNotFoundError(f"FileId {item['id']} with parent {item['parents'][0]} does not match /Resume or /Targeted.")
                filepath = f"temp_pdf/{folderpath}/{item['name']}"
                
                # Write PDFs to temp folder
                os.makedirs(f"temp_pdf/{folderpath}", exist_ok=True)    # Create directories
                with open(f"{filepath}.pdf", 'wb') as f:
                    f.write(fh.read())
                    
    except HttpError as error:
        print(f"An error occurred downloading files from Google Docs: {error}")
        
def upload_resumes_to_dropbox(dropbox_instance):
    """Upload all files in /temp_pdf to Dropbox, preserving directory structure."""
    print("====== Uploading recently modified resumes to Dropbox ======")
    
    local_directory = "temp_pdf"

    for root, dirs, files in os.walk(local_directory):
        for filename in files:
            # Get filepaths
            local_filepath = os.path.join(root, filename)
            dropbox_filepath = local_filepath.replace('\\','/').replace('temp_pdf', '')            
            
            with open(local_filepath, "rb") as f:
                try:
                    dropbox_instance.files_upload(f.read(), dropbox_filepath, mode=WriteMode('overwrite'))
                    print(f"Uploaded {filename} to Dropbox path: {dropbox_filepath}")
                except Exception as e:
                    print(f"Failed to upload {filename}. Error: {e}")
    
def delete_temp_files():
    """Delete contents of /temp_pdf"""
    folder = 'temp_pdf'

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        try:
            if os.path.isfile(filepath) or os.path.islink(filepath):
                os.unlink(filepath)
            elif os.path.isdir(filepath):
                shutil.rmtree(filepath)
        except Exception as e:
            print(f'Failed to delete {filepath}. Reason: {e}')
            
    print("====== Temporary PDFs deleted successfully. ======")

def sync():
    drive_instance = get_drive_instance()
    dropbox_instance = get_dropbox_instance()
    
    # If filename is passed in, only get that file TODO: leave this blank for now
    
    # If not, get any files in /Resume or /Resume/Targeted changed in the past week
    get_recently_modified_resumes(drive_instance)
    
    # Upload PDFs to Dropbox
    # upload_resumes_to_dropbox(dropbox_instance)
    
    delete_temp_files()
    
    
if __name__ == "__main__":
    sync()