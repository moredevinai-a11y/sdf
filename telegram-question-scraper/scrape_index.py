"""Download all question files referenced by a Telegram "index" message that
links out to specific messages in other channels.

The index message (e.g. https://t.me/FUTUREDOCTORS_198/2250) is treated as an
authoritative list for ONE module, so every document it reaches is a wanted
question file for that module. Each link points either directly to a file, or
to a section header whose file(s) follow it (single, album, or multi-file run).
We resolve headers to their files, skip practical/textbook/non-question items,
force the given module code, dedupe exact duplicates, and record everything in
questions.db plus a MANIFEST.txt with per-file Telegram links.

Usage:
  python scrape_index.py --index-url https://t.me/CHANNEL/MSGID --module DIG-206
"""
import argparse, asyncio, hashlib, os, re, sqlite3
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

import filters

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
API_ID = int(os.environ.get("API_ID") or os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ.get("API_HASH") or os.environ["TELEGRAM_API_HASH"]
DB = BASE / "questions.db"
LOOKAHEAD = 15
PAT = re.compile(r"https?://t\.me/([^/]+)/(\d+)")


def fname(m):
    if m and isinstance(m.media, MessageMediaDocument) and m.document:
        for a in m.document.attributes:
            if isinstance(a, DocumentAttributeFilename):
                return a.file_name
        ext = ".pdf" if (m.document.mime_type or "") == "application/pdf" else ""
        return f"doc_{m.id}{ext}"
    return None


def has_doc(m):
    return m is not None and isinstance(m.media, MessageMediaDocument) and m.document is not None


def is_header(m):
    return m is not None and m.media is None and bool((m.message or "").strip())


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, message_id INTEGER,
            date TEXT, file_name TEXT, file_path TEXT, category TEXT,
            detected_module TEXT, message_url TEXT,
            UNIQUE(channel, message_id, file_name))""")
    conn.commit()
    return conn


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-url", required=True)
    ap.add_argument("--module", required=True, help="forced module code, e.g. DIG-206")
    ap.add_argument("--slug", default=None, help="download subfolder name")
    args = ap.parse_args()

    mm = PAT.match(args.index_url.strip())
    idx_chan, idx_id = mm.group(1), int(mm.group(2))
    module = args.module
    slug = args.slug or f"M{re.sub(r'[^0-9]', '', module) or module}_{idx_chan}"
    dest = BASE / "downloads" / slug / module / "questions"
    dest.mkdir(parents=True, exist_ok=True)

    c = TelegramClient("kasr_session", API_ID, API_HASH)
    await c.connect()
    assert await c.is_user_authorized(), "not authorized"
    conn = init_db()

    idx_ent = await c.get_entity(idx_chan)
    idx = await c.get_messages(idx_ent, ids=idx_id)
    text = idx.message or ""
    links, seen = [], set()
    for u in re.findall(r"https?://t\.me/[^\s]+", text):
        u = u.strip().rstrip(").,")
        m2 = PAT.match(u)
        if m2 and u not in seen:
            seen.add(u)
            links.append((m2.group(1), int(m2.group(2))))
    print(f"index {idx_chan}/{idx_id} -> {len(links)} links, module={module}")

    ent_cache, to_dl, chosen, dead = {}, [], set(), []
    for chan, mid in links:
        if chan not in ent_cache:
            try:
                ent_cache[chan] = await c.get_entity(chan)
                print(f"  channel {chan}: ACCESS OK")
            except Exception as e:
                ent_cache[chan] = None
                print(f"  channel {chan}: NO ACCESS -> {e!r}")
        ent = ent_cache[chan]
        if ent is None:
            dead.append(f"https://t.me/{chan}/{mid} (no access)")
            continue
        target = await c.get_messages(ent, ids=mid)
        if target is None:
            dead.append(f"https://t.me/{chan}/{mid} (deleted/missing)")
            continue
        if has_doc(target):
            members = [target]
            gid = getattr(target, "grouped_id", None)
            if gid:
                for m in await c.get_messages(ent, ids=list(range(mid + 1, mid + LOOKAHEAD))):
                    if has_doc(m) and getattr(m, "grouped_id", None) == gid:
                        members.append(m)
                    else:
                        break
            for m in members:
                if (chan, m.id) not in chosen:
                    chosen.add((chan, m.id)); to_dl.append((chan, m))
        else:
            for m in await c.get_messages(ent, ids=list(range(mid + 1, mid + LOOKAHEAD))):
                if m is None:
                    continue
                if is_header(m):
                    break
                if has_doc(m) and (chan, m.id) not in chosen:
                    chosen.add((chan, m.id)); to_dl.append((chan, m))
    print(f"resolved {len(to_dl)} candidate files; {len(dead)} dead links")

    hashes = {}
    dl = skipped = already = dup = 0
    for chan, m in to_dl:
        fn = fname(m)
        if not fn or not filters.is_allowed_extension(fn):
            skipped += 1; continue
        own_n = filters.normalize(f"{fn}\n{m.message or ''}")
        if filters.matches_non_question(own_n):
            skipped += 1; print(f"  skip(non-q) {chan}/{m.id} {fn}"); continue
        if filters.matches_practical(own_n):
            skipped += 1; print(f"  skip(practical) {chan}/{m.id} {fn}"); continue
        if filters.matches_forbidden(own_n) and not filters.matches_include(own_n):
            skipped += 1; print(f"  skip(textbook) {chan}/{m.id} {fn}"); continue
        if conn.execute("SELECT 1 FROM questions WHERE channel=? AND message_id=? AND file_name=?",
                        (chan, m.id, fn)).fetchone():
            already += 1; continue
        saved = await c.download_media(m, file=str(dest / f"{chan}_{m.id}_{fn}"))
        h = hashlib.md5(Path(saved).read_bytes()).hexdigest()
        if h in hashes:
            os.remove(saved); dup += 1
            print(f"  dup {chan}/{m.id} {fn} == {hashes[h]}"); continue
        hashes[h] = f"{chan}/{m.id}"
        cat = filters.detect_category(own_n)
        conn.execute("""INSERT OR IGNORE INTO questions
            (channel,message_id,date,file_name,file_path,category,detected_module,message_url)
            VALUES (?,?,?,?,?,?,?,?)""",
            (chan, m.id, m.date.isoformat() if m.date else None, fn, str(saved), cat,
             module, f"https://t.me/{chan}/{m.id}"))
        conn.commit(); dl += 1
        print(f"  DL [{cat}] {chan}/{m.id} :: {fn}")

    print(f"\nDONE downloaded={dl} already={already} dup={dup} skipped={skipped}")
    if dead:
        print("DEAD LINKS:")
        for d in dead:
            print("  ", d)
    await c.disconnect(); conn.close()


asyncio.run(main())
