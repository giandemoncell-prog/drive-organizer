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
    ("1FVhK5ksq2T5R10NpzRSyTd5F9fqjYGXh", "Fatture"),
    ("1X9yqAnjxGxd5ONH06cTg47CY0SL9fyZ8", "Contratti"),
    ("1THNg3zXCV6ZgmLqguSzpv2JjGlJwO34r", "Clienti"),
    ("1SYK7XhKcjA6TR9xvBz0Y2KhAKePB0W7C", "Altro"),
]

def list_contents_recursive(folder_id, folder_name, depth=0):
    """Recursively list folder contents for safety check."""
    indent = "  " * depth
    print(f"{indent}[DIR] {folder_name} (id={folder_id})")
    try:
        page_token = None
        total_items = 0
        while True:
            resp = svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=100,
            ).execute()
            items = resp.get("files", [])
            for item in items:
                mime = item.get("mimeType", "")
                size = item.get("size", "")
                is_folder = mime == "application/vnd.google-apps.folder"
                if is_folder:
                    total_items += list_contents_recursive(item["id"], item["name"], depth + 1)
                else:
                    size_str = f" ({size} bytes)" if size else ""
                    print(f"{indent}  [FILE] {item['name']}{size_str}")
                    total_items += 1
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return total_items
    except HttpError as e:
        print(f"{indent}  ERROR listing contents: {e}")
        return -1

def trash_folder(folder_id, folder_name):
    """Trash a single folder."""
    try:
        result = svc.files().update(
            fileId=folder_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()
        trashed = result.get("trashed", False)
        print(f"  -> TRASHED: {folder_name} (id={folder_id}) | trashed={trashed}")
        return True
    except HttpError as e:
        print(f"  -> ERROR trashing {folder_name} (id={folder_id}): {e}")
        return False

print("=" * 60)
print("BATCH 3 — TRASH RESIDUAL ROOT FOLDERS")
print("=" * 60)

for folder_id, folder_name in FOLDERS:
    print(f"\n--- Processing: {folder_name} ---")
    print("Step 1: Listing contents recursively...")
    file_count = list_contents_recursive(folder_id, folder_name)
    if file_count > 0:
        print(f"  WARNING: Found {file_count} non-folder file(s) inside! Skipping trash for safety.")
        continue
    elif file_count < 0:
        print("  WARNING: Could not verify contents. Skipping trash for safety.")
        continue
    else:
        print(f"  OK: No files found (only empty subdirs or empty). Safe to trash.")

    print("Step 2: Trashing folder...")
    trash_folder(folder_id, folder_name)

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
