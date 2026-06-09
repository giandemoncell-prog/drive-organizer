import sys
sys.path.insert(0, 'D:/DRIVE_ORGANIZER')
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()
print("Svuotamento cestino Drive (giandemoncell@gmail.com)...")
svc.files().emptyTrash().execute()
print("Fatto.")
