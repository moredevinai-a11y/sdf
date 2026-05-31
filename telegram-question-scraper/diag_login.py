"""Diagnostic: request a Telegram login code and report how it is delivered."""

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv("/home/ubuntu/kasr_scraper/.env")
API_ID = int(os.environ.get("API_ID") or os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ.get("API_HASH") or os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]


async def main():
    client = TelegramClient("/home/ubuntu/kasr_scraper/kasr_session", API_ID, API_HASH)
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"ALREADY_AUTHORIZED as {me.first_name} (@{me.username})")
        await client.disconnect()
        return
    try:
        sent = await client.send_code_request(PHONE)
        print("SENT_CODE_OK")
        print("type     :", type(sent.type).__name__)
        print("full type:", sent.type)
        nt = getattr(sent, "next_type", None)
        print("next_type:", type(nt).__name__ if nt else None)
    except Exception as e:
        print("SEND_CODE_ERROR:", type(e).__name__, e)
    await client.disconnect()


asyncio.run(main())
