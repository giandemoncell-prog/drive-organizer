import os
try:
    import certifi
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

import sys
sys.path.insert(0, "D:\\DRIVE_ORGANIZER")
from drive_organizer.auth.google_auth import get_drive_service
from googleapiclient.errors import HttpError

svc = get_drive_service()

FOLDERS = [
    ("1wJvNcMEYybvQrrXC9nJxF21ZklCWR7G5", "PDF"),
    ("1g8f6zrscprrEiDCIJuLhJSVD-ZMQGnKA", "Fogli"),
    ("1GuujjoYnmFyjow9fUC3RfSYXeEL-NUQA", "Documenti"),
    ("1fYe8XQ_y3sDZoE06OnDN0m7ozWB-kFNF", "Gemini Gems"),
]


def list_recursive(folder_id, folder_name, depth=0):
    """List all contents recursively. Returns total item count."""
    indent = "  " * depth
    total = 0
    try:
        page_token = None
        while True:
            resp = svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            items = resp.get("files", [])
            for item in items:
                total += 1
                kind = "DIR" if item["mimeType"] == "application/vnd.google-apps.folder" else "FILE"
                print(f"{indent}  [{kind}] {item['name']} ({item['id']})")
                if kind == "DIR":
                    total += list_recursive(item["id"], item["name"], depth + 1)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except HttpError as e:
        print(f"{indent}  ERROR listing contents: {e}")
    return total


for folder_id, folder_name in FOLDERS:
    print(f"\n{'='*60}")
    print(f"Folder: {folder_name} ({folder_id})")
    print(f"{'='*60}")

    # Step 1: list contents recursively
    print("Listing contents (recursive):")
    count = list_recursive(folder_id, folder_name)
    if count == 0:
        print("  (empty — safe to trash)")
    else:
        print(f"  WARNING: {count} item(s) found inside!")

    # Step 2: trash the root folder
    print(f"Trashing '{folder_name}'...")
    try:
        result = svc.files().update(
            fileId=folder_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()
        trashed = result.get("trashed", False)
        name_check = result.get("name", folder_name)
        print(f"  OK — trashed={trashed}, name='{name_check}'")
    except HttpError as e:
        print(f"  ERROR trashing: {e}")

print(f"\n{'='*60}")
print("Done.")
