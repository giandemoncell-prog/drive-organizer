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
    ("1gwSIx-WvkmLQdWhRmx6CGaoJOT6W59Bp", "Video"),
    ("1YWnnPXVcR70u5UMFMr6KrcLtN931xvNH", "Viaggi"),
    ("1EowN7pEiyCeu3_Q3_5Z2Mw2l-BgDskWk", "Sviluppo"),
    ("1qd8SLdtx4u57BySEp3aGO0_QklAB7GBQ", "Personale"),
]


def list_contents_recursive(folder_id, folder_name, depth=0):
    """List all contents recursively, return total non-trashed item count."""
    indent = "  " * depth
    total = 0
    try:
        page_token = None
        while True:
            resp = svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            ).execute()
            items = resp.get("files", [])
            for item in items:
                total += 1
                mime = item["mimeType"]
                icon = "[DIR]" if mime == "application/vnd.google-apps.folder" else "[FILE]"
                print(f"{indent}  {icon} {item['name']} ({item['id']})")
                if mime == "application/vnd.google-apps.folder":
                    sub_count = list_contents_recursive(item["id"], item["name"], depth + 1)
                    total += sub_count
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except HttpError as e:
        print(f"{indent}  ERROR listing {folder_name}: {e}")
    return total


def trash_folder(folder_id, folder_name):
    print(f"\n{'='*60}")
    print(f"Processing: {folder_name} ({folder_id})")
    print(f"{'='*60}")

    # Step 1: List contents recursively
    print(f"\n[1] Listing contents of '{folder_name}'...")
    total_items = list_contents_recursive(folder_id, folder_name)
    if total_items == 0:
        print("    (empty — no non-trashed items found)")
    else:
        print(f"\n    TOTAL non-trashed items found: {total_items}")

    # Step 2: Confirm and trash
    print(f"\n[2] Trashing '{folder_name}'...")
    try:
        result = svc.files().update(
            fileId=folder_id,
            body={"trashed": True},
            supportsAllDrives=True,
            fields="id, name, trashed",
        ).execute()
        trashed = result.get("trashed", False)
        name = result.get("name", folder_name)
        fid = result.get("id", folder_id)
        if trashed:
            print(f"    OK: '{name}' ({fid}) successfully moved to Trash.")
        else:
            print(f"    WARNING: API call succeeded but 'trashed' field is False for '{name}' ({fid}).")
    except HttpError as e:
        print(f"    ERROR trashing '{folder_name}': {e}")


if __name__ == "__main__":
    print("Starting batch trash of residual Drive folders (batch 1)...")
    for fid, fname in FOLDERS:
        trash_folder(fid, fname)
    print(f"\n{'='*60}")
    print("Done.")
