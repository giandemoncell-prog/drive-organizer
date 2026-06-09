"""
Esporta catalogo Drive: struttura + elenco file con metadati.
Output: drive_catalog_YYYYMMDD.csv e drive_catalog_YYYYMMDD.json
"""
import csv, json, os, sys
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()
TODAY = datetime.now().strftime("%Y%m%d")
OUT_CSV  = f"logs/drive_catalog_{TODAY}.csv"
OUT_JSON = f"logs/drive_catalog_{TODAY}.json"

def list_children(pid):
    items, token = [], None
    while True:
        kw = dict(
            q=f"'{pid}' in parents and trashed=false",
            fields="files(id,name,mimeType,size,modifiedTime,fileExtension,owners)",
            pageSize=200,
        )
        if token:
            kw["pageToken"] = token
        r = svc.files().list(**kw).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return items

def scan_folder(folder_id, path=""):
    rows = []
    for item in list_children(folder_id):
        item_path = f"{path}/{item['name']}" if path else item["name"]
        if item["mimeType"] == "application/vnd.google-apps.folder":
            rows.extend(scan_folder(item["id"], item_path))
        else:
            owned = any(o.get("me") for o in item.get("owners", []))
            rows.append({
                "id":        item["id"],
                "name":      item["name"],
                "path":      item_path,
                "folder":    path or "/",
                "ext":       item.get("fileExtension", ""),
                "mime":      item["mimeType"],
                "size_kb":   round(int(item.get("size", 0)) / 1024, 1),
                "modified":  (item.get("modifiedTime") or "")[:10],
                "owned_by_me": owned,
            })
    return rows

# Scansiona solo le 4 cartelle top-level
print("Scansione Drive in corso…")
root_folders = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)", pageSize=200,
).execute().get("files", [])

TOP = ["01_📂Documenti_Personali", "02_📂Casa_e_Immobili",
       "03_📂Scuola_e_Didattica", "04_📂Progetti_e_Social"]
nmap = {f["name"]: f["id"] for f in root_folders}

all_rows = []
for top in TOP:
    fid = nmap.get(top)
    if not fid:
        print(f"  [SKIP] {top}")
        continue
    print(f"  📂 {top}…", end=" ", flush=True)
    rows = scan_folder(fid, top)
    all_rows.extend(rows)
    print(f"{len(rows)} file")

os.makedirs("logs", exist_ok=True)

# CSV
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["name","path","folder","ext","size_kb","modified","owned_by_me","id","mime"])
    w.writeheader()
    w.writerows(all_rows)

# JSON (senza id/mime per leggibilità)
clean = [{k: v for k, v in r.items() if k not in ("id","mime")} for r in all_rows]
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({"generated": TODAY, "total": len(all_rows), "files": clean}, f,
              ensure_ascii=False, indent=2)

print(f"\n✅ Catalogo esportato: {len(all_rows)} file")
print(f"   CSV:  {OUT_CSV}")
print(f"   JSON: {OUT_JSON}")
