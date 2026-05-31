"""QR-code based Telegram login for the KASR_198 scraper.

Generates a QR code that the user scans from the Telegram app
(Settings -> Devices -> Link Desktop Device). Regenerates the QR when it
expires and handles 2FA passwords.
"""

import asyncio
import os

import qrcode
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

BASE = "/home/ubuntu/kasr_scraper"
load_dotenv(f"{BASE}/.env")
API_ID = int(os.environ.get("API_ID") or os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ.get("API_HASH") or os.environ["TELEGRAM_API_HASH"]
QR_PNG = f"{BASE}/qr_login.png"


def render_qr(url: str) -> None:
    img = qrcode.make(url)
    img.save(QR_PNG)
    # Also print an ASCII version to the terminal for quick inspection.
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)
    print(f"[QR saved to {QR_PNG}]", flush=True)


async def main():
    client = TelegramClient(f"{BASE}/kasr_session", API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"ALREADY_AUTHORIZED as {me.first_name} (@{me.username})", flush=True)
        await client.disconnect()
        return

    qr = await client.qr_login()
    render_qr(qr.url)
    print("WAITING_FOR_SCAN", flush=True)

    while True:
        try:
            await qr.wait(timeout=30)
            break
        except asyncio.TimeoutError:
            await qr.recreate()
            print("QR_EXPIRED_REGENERATED", flush=True)
            render_qr(qr.url)
        except SessionPasswordNeededError:
            print("NEEDS_2FA_PASSWORD", flush=True)
            pw = input("Enter your Telegram 2FA password: ").strip()
            await client.sign_in(password=pw)
            break

    me = await client.get_me()
    print(f"LOGIN_SUCCESS as {me.first_name} (@{me.username})", flush=True)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
