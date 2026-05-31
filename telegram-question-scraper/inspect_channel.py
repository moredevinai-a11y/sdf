"""Inspect how files are posted in KASR_198 to calibrate the filters.

Dumps, for each media message in the scanned window: id, grouped_id, file
name, own caption, the nearest preceding text message, and the current
classify decision.
"""

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient

import filters
from scraper import get_file_name, is_audio_or_video

BASE = "/home/ubuntu/kasr_scraper"
load_dotenv(f"{BASE}/.env")
API_ID = int(os.environ.get("API_ID") or os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ.get("API_HASH") or os.environ["TELEGRAM_API_HASH"]
LIMIT = int(os.environ.get("INSPECT_LIMIT", "400"))


async def main():
    client = TelegramClient(f"{BASE}/kasr_session", API_ID, API_HASH)
    await client.connect()
    entity = await client.get_entity("https://t.me/KASR_198")

    last_text = ""
    rows = []
    async for m in client.iter_messages(entity, limit=LIMIT):
        if m.media is None:
            if m.message:
                last_text = m.message.replace("\n", " ")[:60]
            continue
        if is_audio_or_video(m):
            continue
        fn = get_file_name(m)
        if fn is None or not filters.is_allowed_extension(fn):
            continue
        cap = (m.message or "").replace("\n", " ")[:50]
        res = filters.classify(f"{fn}\n{m.message or ''}", last_text)
        rows.append((m.id, m.grouped_id, res["download"], res["reason"], fn[:38], cap, last_text[:40]))

    print(f"Total allowed-type media in last {LIMIT}: {len(rows)}")
    dl = sum(1 for r in rows if r[2])
    print(f"Would download (own-text only): {dl}\n")
    print("id     | grp | DL | reason                         | file | caption | prev_text")
    for r in rows:
        grp = "G" if r[1] else "-"
        print(f"{r[0]:>6} | {grp}  | {'Y' if r[2] else 'n'} | {r[3][:30]:30} | {r[4]:38} | {r[5]:50} | {r[6]}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
