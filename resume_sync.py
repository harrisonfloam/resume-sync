import dropbox
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json


def sync():
    with open('google-service-creds.json') as f:
        google_credentials = service_account.Credentials.from_service_account_info(json.load(f))

    with open('dropbox-creds.json') as f:
        dropbox_token = json.load(f).get('token')
        
    dbx = dropbox.Dropbox(dropbox_token)
    print(dbx.users_get_current_account())
    
    
if __name__ == "__main__":
    sync()