"""Telegram theoretical-question scraper (reusable across channels/groups).

Connects to one or more Telegram channels/groups, walks the message history,
and downloads ONLY theoretical question / exam / past-paper documents (PDF,
DOCX, PPT(X)) that pass the linguistic filters in filters.py. Practical / oral /
spotting content, textbooks, lecture slides, summaries, religious/admin noise
and all audio/video are skipped. Downloads are organized per channel by module
code and tracked in a SQLite database (questions.db) so runs are resumable.

The default targets are data_KA198 and KASR_198, but any channel/group your
logged-in account can access works — just pass its URL/@handle as an argument.

Usage:
  python scraper.py --login-only                 # just authenticate / create session
  python scraper.py                              # scrape the default channels
  python scraper.py https://t.me/foo @bar        # scrape arbitrary channels/groups
  python scraper.py --limit 200 <channel>        # only the most recent N messages
  python scraper.py --dry-run <channel>          # classify only, download nothing

See README.md for tuning filters.py to a different topic/channel.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    DocumentAttributeFilename,
    MessageMediaDocument,
    MessageMediaPhoto,
)

import filters

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_BASE = BASE_DIR / "downloads"
DB_PATH = BASE_DIR / "questions.db"
SESSION_PATH = BASE_DIR / "kasr_session"

# Default channels to scrape (order matters: data_KA198 is the primary file dump).
DEFAULT_CHANNELS = [
    "https://t.me/data_KA198",
    "https://t.me/KASR_198",
]


def channel_slug(channel: str) -> str:
    """Derive a filesystem-safe folder name from a channel URL/handle."""
    slug = channel.rstrip("/").split("/")[-1]
    return slug.lstrip("@") or "channel"

# How many preceding non-file messages to keep as admin/announcement context
# for module detection.
CONTEXT_WINDOW = 3


def load_credentials() -> tuple[int, str]:
    load_dotenv(BASE_DIR / ".env")
    api_id = os.environ.get("API_ID") or os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("API_HASH") or os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit(
            "Missing API_ID/API_HASH. Populate .env or set TELEGRAM_API_ID / "
            "TELEGRAM_API_HASH environment variables."
        )
    return int(api_id), api_hash


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            message_id INTEGER,
            date TEXT,
            file_name TEXT,
            file_path TEXT,
            category TEXT,
            detected_module TEXT,
            message_url TEXT,
            UNIQUE(channel, message_id, file_name)
        )
        """
    )
    conn.commit()
    return conn


def already_downloaded(conn: sqlite3.Connection, channel: str, message_id: int, file_name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM questions WHERE channel=? AND message_id=? AND file_name=?",
        (channel, message_id, file_name),
    )
    return cur.fetchone() is not None


def record(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO questions
            (channel, message_id, date, file_name, file_path, category, detected_module, message_url)
        VALUES (:channel, :message_id, :date, :file_name, :file_path, :category, :detected_module, :message_url)
        """,
        row,
    )
    conn.commit()


def get_file_name(message) -> str | None:
    """Best-effort file name for a document or photo message."""
    media = message.media
    if isinstance(media, MessageMediaDocument) and message.document:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
        # Fall back to mime-based extension.
        mime = message.document.mime_type or ""
        ext = {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
        }.get(mime, "")
        return f"doc_{message.id}{ext}" if ext else f"doc_{message.id}"
    if isinstance(media, MessageMediaPhoto):
        return f"photo_{message.id}.jpg"
    return None


def is_audio_or_video(message) -> bool:
    if isinstance(message.media, MessageMediaDocument) and message.document:
        mime = (message.document.mime_type or "").lower()
        if mime.startswith("audio/") or mime.startswith("video/"):
            return True
    return False


async def with_backoff(coro_factory, *, what: str, max_attempts: int = 6):
    """Run an awaitable factory with FloodWait-aware exponential backoff + jitter."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return await coro_factory()
        except FloodWaitError as e:
            wait = e.seconds + random.uniform(1, 5)
            print(f"  [FloodWait] sleeping {wait:.0f}s on {what} (telegram asked {e.seconds}s)")
            await asyncio.sleep(wait)
        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            if attempt >= max_attempts:
                raise
            backoff = min(2 ** attempt, 60) + random.uniform(0, 3)
            print(f"  [retry {attempt}/{max_attempts}] {what}: {e!r}; sleeping {backoff:.0f}s")
            await asyncio.sleep(backoff)


async def interactive_login(client: TelegramClient) -> None:
    """Authenticate the client, prompting for phone/code/2FA at the terminal."""
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already authorized as {me.first_name} (@{me.username}).")
        return
    print(">>> Telegram login required.")
    phone = input("Enter your phone number (international format, e.g. +20...): ").strip()
    await client.send_code_request(phone)
    code = input("Enter the login code Telegram just sent you: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except Exception as e:  # SessionPasswordNeededError or others
        from telethon.errors import SessionPasswordNeededError

        if isinstance(e, SessionPasswordNeededError):
            pw = input("Two-step verification is enabled. Enter your 2FA password: ").strip()
            await client.sign_in(password=pw)
        else:
            raise
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (@{me.username}).")


async def scrape_channel(client, conn, channel: str, limit: int | None,
                         dry_run: bool) -> dict:
    slug = channel_slug(channel)
    download_root = DOWNLOAD_BASE / slug
    download_root.mkdir(parents=True, exist_ok=True)

    entity = await client.get_entity(channel)
    channel_username = getattr(entity, "username", None)

    stats = {"channel": slug, "scanned": 0, "downloaded": 0, "skipped_filter": 0,
             "skipped_av": 0, "skipped_type": 0, "already": 0, "by_module": {}}
    context_buffer: list[str] = []

    async def process_media(message, album_caption: str) -> None:
        """Classify a single media message and download it if it qualifies."""
        if is_audio_or_video(message):
            stats["skipped_av"] += 1
            return

        file_name = get_file_name(message)
        if file_name is None:
            return
        if filters.is_blocked_extension(file_name):
            stats["skipped_av"] += 1
            return
        if not filters.is_allowed_extension(file_name):
            stats["skipped_type"] += 1
            return

        own_text = f"{file_name}\n{message.message or ''}\n{album_caption}"
        context_text = " \n ".join(context_buffer)
        result = filters.classify(own_text, context_text)

        if not result["download"]:
            stats["skipped_filter"] += 1
            return

        module = result["module"]
        category = result["category"]

        if not dry_run and already_downloaded(conn, slug, message.id, file_name):
            stats["already"] += 1
            stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
            return

        dest_dir = download_root / module / "questions"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name

        msg_url = (
            f"https://t.me/{channel_username}/{message.id}"
            if channel_username
            else f"{channel}/{message.id}"
        )

        print(f"[{message.id}] {module} / {category} :: {file_name} ({result['reason']})")

        if not dry_run:
            saved = await with_backoff(
                lambda: client.download_media(message, file=str(dest_path)),
                what=f"download msg {message.id}",
            )
            final_path = str(saved) if saved else str(dest_path)
            await asyncio.sleep(random.uniform(0.3, 0.9))  # gentle pacing
        else:
            final_path = str(dest_path)

        if dry_run:
            stats["downloaded"] += 1
            stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
            return

        record(conn, {
            "channel": slug,
            "message_id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "file_name": file_name,
            "file_path": final_path,
            "category": category,
            "detected_module": module,
            "message_url": msg_url,
        })

        stats["downloaded"] += 1
        stats["by_module"][module] = stats["by_module"].get(module, 0) + 1

    # Album (grouped media) buffering: members of a media album share a single
    # caption, so we collect contiguous members and apply the combined caption
    # to every file in the group.
    album_buffer: list = []
    current_group_id = None

    async def flush_album() -> None:
        nonlocal album_buffer, current_group_id
        if not album_buffer:
            return
        caption = "\n".join(m.message for m in album_buffer if m.message)
        for m in album_buffer:
            await process_media(m, caption)
        album_buffer = []
        current_group_id = None

    async for message in client.iter_messages(entity, limit=limit):
        stats["scanned"] += 1
        gid = getattr(message, "grouped_id", None)

        if message.media is None:
            await flush_album()
            if message.message:
                context_buffer.append(message.message)
                context_buffer[:] = context_buffer[-CONTEXT_WINDOW:]
            continue

        if gid is not None:
            if gid == current_group_id:
                album_buffer.append(message)
            else:
                await flush_album()
                current_group_id = gid
                album_buffer = [message]
            continue

        # Standalone media message.
        await flush_album()
        await process_media(message, "")

    await flush_album()
    return stats


async def scrape(channels: list[str], limit: int | None, dry_run: bool) -> list[dict]:
    api_id, api_hash = load_credentials()
    conn = init_db()
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await interactive_login(client)
    all_stats = []
    try:
        for channel in channels:
            print(f"\n######## Scraping {channel} ########")
            stats = await scrape_channel(client, conn, channel, limit, dry_run)
            print_summary(stats)
            all_stats.append(stats)
    finally:
        await client.disconnect()
        conn.close()
    return all_stats


def print_summary(stats: dict) -> None:
    print(f"\n========= SUMMARY [{stats.get('channel', '')}] =========")
    print(f"Messages scanned     : {stats['scanned']}")
    print(f"Files downloaded     : {stats['downloaded']}")
    print(f"Already in DB        : {stats['already']}")
    print(f"Skipped (filter)     : {stats['skipped_filter']}")
    print(f"Skipped (audio/video): {stats['skipped_av']}")
    print(f"Skipped (file type)  : {stats['skipped_type']}")
    print("Per-module question files:")
    order = ["NEU-205", "DIG-206", "END-207", "INT-208", "PSY-213", "PAT-210",
             filters.UNCATEGORIZED]
    for code in order:
        print(f"  {code:<20}: {stats['by_module'].get(code, 0)}")
    print("=========================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reusable Telegram theoretical-question scraper")
    parser.add_argument("--login-only", action="store_true", help="Only authenticate, then exit")
    parser.add_argument("--limit", type=int, default=None, help="Max number of recent messages to scan")
    parser.add_argument("--dry-run", action="store_true", help="Classify only; do not download")
    parser.add_argument("channels", nargs="*", default=None,
                        help="Channel URLs/handles to scrape (default: data_KA198, KASR_198)")
    args = parser.parse_args()
    channels = args.channels if args.channels else DEFAULT_CHANNELS

    if args.login_only:
        async def _login():
            api_id, api_hash = load_credentials()
            client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
            await interactive_login(client)
            await client.disconnect()

        asyncio.run(_login())
        return

    asyncio.run(scrape(channels, args.limit, args.dry_run))


if __name__ == "__main__":
    main()
