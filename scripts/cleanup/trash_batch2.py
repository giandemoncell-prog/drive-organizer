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
    ("1Q-09bP7YNLD2_737M9NN-EbDidVrE3R9", "Lavoro"),
    ("1g9I40xNnP8VbXldOcD9N7v_N_Pw6tctq", "Foto"),
    ("1Wyn0pZikMWFUil0p2osIvnuthFjc-0TH", "Formazione"),
    ("1Fr164MKhmxYiMAkxW2zb1da01HvHzQ-T", "Finanza"),
]


def list_recursive(folder_id, folder_name, indent=0):
    """List all contents of a folder recursively."""
    prefix = "  " * indent
    try:
        page_token = None
        total_items = 0
        while True:
            resp = svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            items = resp.get("files", [])
            total_items += len(items)
            for item in items:
                is_folder = item["mimeType"] == "application/vnd.google-apps.folder"
                kind = "[DIR]" if is_folder else "[FILE]"
                print(f"{prefix}  {kind} {item['name']} ({item['id']})")
                if is_folder:
                    list_recursive(item["id"], item["name"], indent + 1)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return total_items
    except HttpError as e:
        print(f"{prefix}  ERROR listing contents: {e}")
        return -1


def trash_folder(folder_id, folder_name):
    print(f"\n{'='*60}")
    print(f"Processing: {folder_name} ({folder_id})")
    print(f"{'='*60}")

    # Step 1: List contents recursively
    print(f"Contents of '{folder_name}':")
    count = list_recursive(folder_id, folder_name)
    if count == 0:
        print("  (empty)")
    elif count > 0:
        print(f"  => Total items found: {count}")
    else:
        print("  => Could not list contents (see error above)")

    # Step 2: Trash the root folder
    print(f"\nTrashing '{folder_name}'...")
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
            print(f"  SUCCESS: '{name}' (id={fid}) has been moved to Trash.")
        else:
            print(f"  WARNING: API call succeeded but trashed=False for '{name}' (id={fid}).")
    except HttpError as e:
        print(f"  FAILED to trash '{folder_name}': {e}")


if __name__ == "__main__":
    print("Drive Organizer — Batch 2 folder cleanup")
    print(f"Account: giandemoncell@gmail.com")
    print(f"Folders to trash: {len(FOLDERS)}")

    for fid, fname in FOLDERS:
        trash_folder(fid, fname)

    print(f"\n{'='*60}")
    print("Done.")
