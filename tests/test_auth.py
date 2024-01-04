"""
Testing methods for Google and Dropbox authentication.
"""


import dropbox
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json


def test():
    
    # Get Google credentials
    with open('google-service-creds.json') as f:
        google_creds = service_account.Credentials.from_service_account_info(json.load(f))

    # Get Dropbox credentials
    with open('dropbox-creds.json') as f:
        dropbox_token = json.load(f).get('token')
    dbx = dropbox.Dropbox(dropbox_token)
    
    # Test Dropbox
    print(dbx.users_get_current_account())
    
    try:
        service = build("drive", "v3", credentials=google_creds)

        # Call the Drive v3 API
        results = (
            service.files()
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
        
if __name__ == "__main__":
    test()