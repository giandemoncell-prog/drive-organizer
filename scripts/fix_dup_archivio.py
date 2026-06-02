import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

r = svc.files().list(
    q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false and name='99_📂Archivio'",
    fields="files(id,name)",
    pageSize=10,
).execute()

folders = r.get("files", [])
print(f"Trovate {len(folders)} cartelle '99_📂Archivio'")

counts = []
for f in folders:
    kids = svc.files().list(
        q=f"'{f['id']}' in parents and trashed=false",
        fields="files(id,name,mimeType)", pageSize=200,
    ).execute().get("files", [])
    counts.append((f["id"], len(kids), kids))
    print(f"  ID {f['id'][:12]}…: {len(kids)} figli")

# main = più contenuto, secondary = meno
counts.sort(key=lambda x: -x[1])
main_id, main_count, _ = counts[0]
sec_id, sec_count, sec_kids = counts[1]

print(f"\nPrincipale: {main_id[:12]}… ({main_count} figli)")
print(f"Secondaria: {sec_id[:12]}… ({sec_count} figli) — sposto e elimino")

for item in sec_kids:
    svc.files().update(
        fileId=item["id"],
        addParents=main_id,
        removeParents=sec_id,
        fields="id",
    ).execute()
    k = "📁" if item["mimeType"] == "application/vnd.google-apps.folder" else "📄"
    print(f"  {k} {item['name']} → principale")
    time.sleep(0.15)

# verifica vuota
kids_left = svc.files().list(
    q=f"'{sec_id}' in parents and trashed=false",
    fields="files(id)", pageSize=10,
).execute().get("files", [])

if not kids_left:
    svc.files().delete(fileId=sec_id).execute()
    print(f"\n🗑  Secondaria eliminata.")
else:
    print(f"\n[WARN] Secondaria ancora con {len(kids_left)} elementi — non eliminata.")

print("✅ Done.")
