"""
Ristruttura 06_📂Scuola_e_Didattica e 07_📂Viaggi_e_Hobby.

06 — consolida 23 microcartelle in 5 macro-gruppi:
  📚 Libro_IA_KDP
  🎓 DSA_e_Inclusione
  👨‍🏫 Pratiche_Docente
  📝 Materiali_Didattici
  📦 Varie_Scuola

07 — raggruppa per tema:
  ✈️ Viaggi
  🎵 Bachata_e_Social     (ADS, social bachata)
  📖 Scrittura_e_Progetti (romanzo, idee)
  🎮 Hobby_Vari
"""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import certifi
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

from googleapiclient.errors import HttpError
from drive_organizer.auth.google_auth import get_drive_service

svc = get_drive_service()

# ─── helpers ─────────────────────────────────────────────────────────────────

def root_map():
    r = svc.files().list(
        q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,name)", pageSize=200,
    ).execute()
    return {f["name"]: f["id"] for f in r.get("files", [])}


def list_sub(parent_id, folders_only=True):
    q = f"'{parent_id}' in parents and trashed=false"
    if folders_only:
        q += " and mimeType='application/vnd.google-apps.folder'"
    r = svc.files().list(q=q, fields="files(id,name,mimeType)", pageSize=200).execute()
    return r.get("files", [])


def get_or_create(name, parent_id, _cache={}):
    key = (name, parent_id)
    if key not in _cache:
        existing = [f for f in list_sub(parent_id) if f["name"] == name]
        _cache[key] = existing[0]["id"] if existing else svc.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                  "parents": [parent_id]}, fields="id").execute()["id"]
        if not existing:
            print(f"    📁+ {name}")
    return _cache[key]


def move(item_id, from_p, to_p):
    if from_p == to_p:
        return
    svc.files().update(fileId=item_id, addParents=to_p,
                       removeParents=from_p, fields="id").execute()


def move_sub(name, subs_map, from_p, to_p, label=""):
    fid = subs_map.get(name)
    if not fid:
        print(f"  [skip] {name}")
        return
    move(fid, from_p, to_p)
    print(f"  ↳ {name} → {label or to_p[:8]}")
    time.sleep(0.12)


def merge_subs(src_names, subs_map, dst_id, dst_label, parent_id):
    """Sposta il contenuto di più subfolder in dst, elimina le shell vuote."""
    for name in src_names:
        fid = subs_map.get(name)
        if not fid:
            continue
        kids = list_sub(fid, folders_only=False)
        for kid in kids:
            move(kid["id"], fid, dst_id)
            time.sleep(0.10)
        # elimina se vuota
        if not list_sub(fid, folders_only=False):
            svc.files().delete(fileId=fid).execute()
            print(f"  🗑  {name} (fusa in {dst_label})")


def print_tree(parent_id, indent=2):
    subs = list_sub(parent_id)
    for f in sorted(subs, key=lambda x: x["name"]):
        kids = list_sub(f["id"])
        print(" " * indent + f"📁 {f['name']}" +
              (f"  [{len(kids)} sotto]" if kids else ""))
        for k in sorted(kids, key=lambda x: x["name"]):
            print(" " * (indent + 3) + f"└─ {k['name']}")


# ═══════════════════════════════════════════════════════════════════
# 06_📂Scuola_e_Didattica
# ═══════════════════════════════════════════════════════════════════
nmap = root_map()
SCUOLA = nmap.get("06_📂Scuola_e_Didattica")
if not SCUOLA:
    print("ERRORE: 06_📂Scuola_e_Didattica non trovata"); sys.exit(1)

subs = {f["name"]: f["id"] for f in list_sub(SCUOLA)}
print(f"\n{'='*60}")
print(f"06_📂Scuola_e_Didattica — {len(subs)} sottocartelle da consolidare")

# Macro-cartelle
KDP    = get_or_create("📚 Libro_IA_KDP",     SCUOLA)
DSA    = get_or_create("🎓 DSA_e_Inclusione", SCUOLA)
PRAT   = get_or_create("👨‍🏫 Pratiche_Docente", SCUOLA)
MAT    = get_or_create("📝 Materiali_Didattici", SCUOLA)
VARIE  = get_or_create("📦 Varie_Scuola",     SCUOLA)

# Libro IA / KDP
print("\n  📚 → Libro_IA_KDP")
for n in ["Manoscritto KDP"]:
    move_sub(n, subs, SCUOLA, KDP, "Libro_IA_KDP")

# DSA e Inclusione
print("\n  🎓 → DSA_e_Inclusione")
for n in ["Verifiche PEI", "Prompts DSA", "Materiali DSA",
          "Piani Educativi", "Progetti Educativi", "Interviste Studenti"]:
    move_sub(n, subs, SCUOLA, DSA, "DSA_e_Inclusione")

# Pratiche Docente
print("\n  👨‍🏫 → Pratiche_Docente")
for n in ["Titoli Precedenza", "Dati e Titoli", "Circolari",
          "Moduli e Domande", "Contratti Lavoro", "Documenti Demontis",
          "Documenti Amministrativi", "Ritiro e Restituzione"]:
    move_sub(n, subs, SCUOLA, PRAT, "Pratiche_Docente")

# Materiali Didattici — fonde i duplicati
print("\n  📝 → Materiali_Didattici (merge)")
# Sposta il contenuto di "Materiali Didattici" e "Risorse Didattiche" in MAT
merge_subs(["Materiali Didattici", "Risorse Didattiche"], subs, MAT,
           "Materiali_Didattici", SCUOLA)
for n in ["Esercizi", "Lezioni", "Geografia", "Disegni Tecnici"]:
    move_sub(n, subs, SCUOLA, MAT, "Materiali_Didattici")

# Varie
print("\n  📦 → Varie_Scuola")
for n in ["Raspberry Pi", "Dati", "Dati e Titoli"]:
    move_sub(n, subs, SCUOLA, VARIE, "Varie_Scuola")

print("\n  Struttura finale 06:")
print_tree(SCUOLA)

# ═══════════════════════════════════════════════════════════════════
# 07_📂Viaggi_e_Hobby
# ═══════════════════════════════════════════════════════════════════
VIAGGI = nmap.get("07_📂Viaggi_e_Hobby")
if not VIAGGI:
    print("ERRORE: 07_📂Viaggi_e_Hobby non trovata"); sys.exit(1)

subs7 = {f["name"]: f["id"] for f in list_sub(VIAGGI)}
print(f"\n{'='*60}")
print(f"07_📂Viaggi_e_Hobby — sottocartelle attuali:")
for n in subs7:
    print(f"  - {n}")

# Leggi i nomi DOPO il nested organizer (potrebbe aver creato nuove)
# Macro-cartelle
VIAG   = get_or_create("✈️ Viaggi",              VIAGGI)
BVMUS  = get_or_create("🎵 Bachata_e_Social",     VIAGGI)
SCRIT  = get_or_create("📖 Scrittura_e_Progetti", VIAGGI)
HOBBY  = get_or_create("🎮 Hobby_Vari",           VIAGGI)

# Mapping per nomi tipici che il nested organizer potrebbe aver creato
VIAGGI_SUBS = ["Canarie", "Lanzarote", "Voli", "Hotel", "Prenotazioni",
               "Biglietti", "Vacanze", "Viaggio", "Vacanza",
               "Gran Canaria", "Tenerife", "Ibiza", "Booking",
               "Volo", "Boarding Pass", "E-ticket", "Altri files",
               "Documenti Viaggio", "Itinerari"]
SOCIAL_SUBS = ["ADS Canali Social", "Social", "Facebook", "Instagram",
               "Ads", "Pubblicità", "Canali Social", "Bachata Vibes Music"]
SCRITT_SUBS = ["Anno Zero", "Romanzo", "Scrittura", "Narrativa",
               "Libro", "Cronache", "Fantasy", "Lead Magnet", "Blog"]
HOBBY_SUBS  = ["Hobby", "Sport", "Cucina", "Fotografia", "Film",
               "Meditazione", "Musica", "Interessi", "Personale"]

print("\n  ✈️ → Viaggi")
for n in VIAGGI_SUBS:
    if n in subs7:
        move_sub(n, subs7, VIAGGI, VIAG, "Viaggi")

print("\n  🎵 → Bachata_e_Social")
for n in SOCIAL_SUBS:
    if n in subs7:
        move_sub(n, subs7, VIAGGI, BVMUS, "Bachata_e_Social")

print("\n  📖 → Scrittura_e_Progetti")
for n in SCRITT_SUBS:
    if n in subs7:
        move_sub(n, subs7, VIAGGI, SCRIT, "Scrittura_e_Progetti")

print("\n  🎮 → Hobby_Vari (resto)")
# Tutto ciò che non è ancora stato mosso
subs7_now = {f["name"]: f["id"] for f in list_sub(VIAGGI)}
moved_names = set(VIAGGI_SUBS + SOCIAL_SUBS + SCRITT_SUBS + HOBBY_SUBS +
                  ["✈️ Viaggi", "🎵 Bachata_e_Social", "📖 Scrittura_e_Progetti", "🎮 Hobby_Vari"])
for name, fid in subs7_now.items():
    if name not in moved_names:
        move(fid, VIAGGI, HOBBY)
        print(f"  ↳ {name} → Hobby_Vari")
        time.sleep(0.12)

# Rimuovi macro-categorie vuote
for macro_id, macro_name in [(VIAG,"✈️ Viaggi"),(BVMUS,"🎵 Bachata_e_Social"),
                              (SCRIT,"📖 Scrittura_e_Progetti"),(HOBBY,"🎮 Hobby_Vari")]:
    if not list_sub(macro_id, folders_only=False):
        svc.files().delete(fileId=macro_id).execute()
        print(f"  🗑  {macro_name} (vuota, rimossa)")

print("\n  Struttura finale 07:")
print_tree(VIAGGI)
print("\n✅ Ristrutturazione completata.")
