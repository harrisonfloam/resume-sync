"""
Sync resumes from Google Drive to Dropbox in PDF form.
"""

import os
import io
import json
import shutil
import re
from datetime import datetime, timedelta
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.files import WriteMode
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account


def is_in_github_action(verbose=False):
    """Return True if executing in Github Action"""
    
    check = os.environ.get('GITHUB_ACTIONS') == 'true'
    
    if check and verbose:
        print("====== Executing with GitHub Actions. ======")
    
    return check

def get_drive_instance_sa():
    """Uses Google service account credentials to create a Google Drive API instance."""   
    creds = None
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    
    print ("====== Authenticating Google credentials. ======")
    
    if is_in_github_action():
        GOOGLE_SA_KEY = os.environ.get("GOOGLE_SA_KEY")
        
        key = json.loads(GOOGLE_SA_KEY)
        try:
            creds = service_account.Credentials.from_service_account_file(key, SCOPES)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            creds = None
            
    else:   # Running locally
        try:
            creds = service_account.Credentials.from_service_account_file('google-service-account.json', scopes=SCOPES)
        except Exception as e:
            print(f"Error loading service account credentials: {e}")
            return None
        
    try:
        drive_instance = build("drive", "v3", credentials=creds)
        print("Authenticated.")
        return drive_instance
    except HttpError as error:
        print(f"An error occurred creating a Google Drive API instance: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
    
def get_drive_instance():
    """Uses current Google credentials to create a Google Drive API instance. Uses OAuth2 refresh token if available. 
    Prompts user for authentication if needed when not running in GitHub Actions."""
    #BUG: refresh token expires after 1 week
    creds = None
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    
    print ("====== Authenticating Google credentials. ======")
    
    if is_in_github_action():
        GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN')

        # Use refresh token if available
        token = json.loads(GOOGLE_TOKEN)
        creds = Credentials.from_authorized_user_info(token, SCOPES)
        
        # If there are no (valid) credentials available, attempt to refresh the token.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("Credentials expired. Attempting refresh.")
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
        
    else:
        # Use refresh token if available
        if os.path.exists("google-token.json"):
            try:
                creds = Credentials.from_authorized_user_file("google-token.json", SCOPES)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                creds = None
            
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("Credentials expired. Attempting refresh.")
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
            # Initiate OAuth flow if needed
            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file("google-creds.json", SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("google-token.json", "w") as token:
                token.write(creds.to_json())
                
    try:
        drive_instance = build("drive", "v3", credentials=creds)
        print("Authenticated.")
        return drive_instance
    except HttpError as error:
        print(f"An error occurred creating a Google Drive API instance: {error}")

def get_dropbox_instance():
    """Uses current Dropbox Credentials to create an API instance. Uses OAuth2 refresh token if available. 
    Prompts user for authentication if needed when not running in GitHub Actions."""
    # creds = None
    
    print("====== Authenticating Dropbox credentials. ======")
    
    if is_in_github_action():
        DROPBOX_CREDS = os.environ.get('DROPBOX_CREDS')
        DROPBOX_TOKEN = os.environ.get('DROPBOX_TOKEN')
        
        # Use refresh token if available
        APP_KEY = json.loads(DROPBOX_CREDS)['APP_KEY']
        token = json.loads(DROPBOX_TOKEN)
        refresh_token = token.get('refresh_token')
        dropbox_instance = dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=APP_KEY)
        
        print("Authenticated.")
        return dropbox_instance
        
    else:
        # Get app key
        with open('dropbox-creds.json', 'r') as creds_file:
            APP_KEY = json.load(creds_file)['APP_KEY']
        # Get refresh token if available
        if os.path.exists("dropbox-token.json"):
            with open('dropbox-token.json', 'r') as token_file:
                token = json.load(token_file)
                refresh_token = token.get('refresh_token')
                dropbox_instance = dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=APP_KEY)
                
                print("Authenticated.")
                return dropbox_instance
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
                dropbox_instance = dropbox.Dropbox(oauth2_refresh_token=oauth_result.refresh_token, app_key=APP_KEY)
                
                print("Authenticated.")
                return dropbox_instance
            except Exception as error:
                print(f"An error occurred creating a Dropbox API instance: {error}")
                exit(1)

def get_recently_modified_resumes(drive_instance):
    """Download files modified in the past week from /Resumes and /Resumes/Targeted."""
    # Calculate one week ago date
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    one_week_ago_str = one_week_ago.isoformat() + 'Z'  # Format for Google Drive API

    print("====== Downloading recently modified resumes from Google Docs. ======")
    try:
        # Folder IDs
        resume_folder_id = '1FQAXueyM20GCbD4g1fn4EZjV4XawAGkC'
        targeted_folder_id = '1bXW8_I_x7__gu30XbmmqdftH_fNyst2-'
        cover_letters_folder_id = '17CQ5vN6mZci6PSdkjyZYvBEEK6RQd23y'
        
        # Get files
        query = f"(parents = '{resume_folder_id}' or parents = '{targeted_folder_id}' or parents = '{cover_letters_folder_id}') and " \
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
                print(f"{item['name']} (Modified: {item['modifiedTime']})")
                
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
                elif item['parents'][0] == cover_letters_folder_id:
                    folderpath = 'Resume/Cover Letters'
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
    print("====== Uploading recently modified resumes to Dropbox. ======")
    
    local_directory = 'temp_pdf'

    for root, dirs, files in os.walk(local_directory):
        for filename in files:
            # Get filepaths
            local_filepath = os.path.join(root, filename)
            dropbox_filepath = local_filepath.replace('\\','/').replace(local_directory, '')            
            
            with open(local_filepath, "rb") as f:
                try:
                    dropbox_instance.files_upload(f.read(), dropbox_filepath, mode=WriteMode('overwrite'))
                    print(f"Uploaded {filename} to Dropbox path: {dropbox_filepath}")
                except Exception as e:
                    print(f"Failed to upload {filename}. Error: {e}")
                    
def clean_up_dropbox(dropbox_instance):
    """Overwrite old copies of identical resumes on Dropbox."""
    print("====== Updating old versions on Dropbox. ======")
    
    local_directory = 'temp_pdf'
    date_pattern = r'\(([^)]+)\)'
    update_made = False

    # List files in Dropbox folder
    files_in_resume = dropbox_instance.files_list_folder('/Resume').entries  # /Resume
    files_in_targeted = dropbox_instance.files_list_folder('/Resume/Targeted').entries # /Resume/Targeted
    files_in_dropbox = files_in_resume + files_in_targeted
    
    # Process local files and compare
    # TODO: Refactor for readability...
    for root, dirs, files in os.walk(local_directory):
        for local_filename in files:
            # Extract date from local files
            content_in_parentheses = re.search(date_pattern, local_filename)
            if content_in_parentheses:
                content_match = content_in_parentheses.group(1)
                date_match = content_match.split(',')[0]
                
                local_date = datetime.strptime(date_match.strip(), "%b %Y") # Convert to datetime
                local_filename_stripped = local_filename.replace(date_match, "")

                for dbx_file in files_in_dropbox:
                    if isinstance(dbx_file, dropbox.files.FileMetadata):
                        # Extract date from dropbox files
                        dbx_filename = dbx_file.name
                        dbx_content_in_parentheses = re.search(date_pattern, dbx_filename)
                        if dbx_content_in_parentheses:
                            dbx_content_match = dbx_content_in_parentheses.group(1)
                            dbx_date_match = dbx_content_match.split(',')[0]
                            
                            dbx_date = datetime.strptime(dbx_date_match.strip(), "%b %Y") # Convert to datetime
                            dbx_filename_stripped = dbx_filename.replace(dbx_date_match, "")
                        
                            # Compare and delete older file
                            if dbx_filename_stripped == local_filename_stripped and local_date > dbx_date:
                                try:
                                    dropbox_instance.files_delete_v2(dbx_file.path_lower)
                                    update_made = True
                                    print(f"Updated {dbx_filename} to {local_filename} on Dropbox.")
                                except Exception as e:
                                    print(f"Failed to delete {dbx_file.name}. Error: {e}")
    if not update_made:
        print("No files to update.")

def delete_temp_files():
    """Delete contents of /temp_pdf"""
    folder = 'temp_pdf'
    
    if os.path.exists(folder):
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
    is_in_github_action(verbose=True)
    
    # Initialize instances
    drive_instance = get_drive_instance_sa()
    dropbox_instance = get_dropbox_instance()
    
    # Download Google Drive resumes modified within the past week as PDF
    get_recently_modified_resumes(drive_instance)
    
    # Upload PDFs to Dropbox
    upload_resumes_to_dropbox(dropbox_instance)
    
    # Clean up Dropbox
    clean_up_dropbox(dropbox_instance)
    
    # Delete downloaded PDFs from working directory
    delete_temp_files()
    
    
def test_auth():
    is_in_github_action(verbose=True)
    
    # Initialize instances
    _ = get_drive_instance_sa()
    _ = get_dropbox_instance()
    
if __name__ == "__main__":
    sync()
    # test_auth()