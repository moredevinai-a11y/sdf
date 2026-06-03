# Beginner's Guide: Download Telegram files with this tool

This is written for someone who has **never used Python or GitHub**. Just follow
the steps in order. Copy each grey command, paste it into the black/blue
terminal window, and press **Enter**.

You will only do Parts 1–5 **once**. After that, you just repeat Part 6 whenever
you want to download files.

---

## Part 1 — Install two free programs (once)

1. **Python** — go to https://www.python.org/downloads/ → click the big yellow
   "Download Python" button → run the installer.
   - **Windows users:** on the first install screen, tick the box that says
     **"Add Python to PATH"** before clicking Install. This is important.
2. **Git** — go to https://git-scm.com/downloads → download for your system →
   run the installer → keep clicking "Next" with the default options.

After both are installed, **restart your computer** once.

---

## Part 2 — Open the terminal

This is the window where you type commands.

- **Windows:** press the Start button, type `powershell`, press Enter.
- **Mac:** press `Cmd + Space`, type `terminal`, press Enter.

A window with a blinking cursor opens. That's where every command below goes.

---

## Part 3 — Get your two Telegram keys (once)

1. Go to https://my.telegram.org and log in with your phone number.
2. Click **"API development tools"**.
3. In the form, type any title (for example `myapp`) and any short name, then
   submit.
4. You will see two values:
   - **api_id** — a number (like `1234567`)
   - **api_hash** — a long mix of letters and numbers
5. Keep this page open — you'll copy these in Part 5.

---

## Part 4 — Download the tool

Copy this block, paste it into the terminal, press Enter:

```
git clone https://github.com/moredevinai-a11y/sdf.git
```

Then go into the folder:

```
cd sdf/telegram-question-scraper
```

Now install the tool. **Use the block for your system:**

**Windows:**
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**Mac:**
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Wait until it finishes (it downloads a few things).

---

## Part 5 — Tell the tool your keys (once)

You need to create a small file called `.env` with your two keys from Part 3.

**Windows** — paste this, but replace the example values with YOUR own:
```
notepad .env
```
Notepad opens and asks to create the file → click **Yes**. Type these two lines
(use your real numbers), then save and close Notepad:
```
API_ID=1234567
API_HASH=paste_your_long_hash_here
```

**Mac** — paste this (replace with your real values):
```
printf "API_ID=1234567\nAPI_HASH=paste_your_long_hash_here\n" > .env
```

---

## Part 5b — Log in to Telegram (once)

Paste the block for your system:

**Windows:**
```
.venv\Scripts\python scraper.py --login-only
```
**Mac:**
```
.venv/bin/python scraper.py --login-only
```

It will ask you, right there in the terminal:
1. **Your phone number** — type it with country code, e.g. `+20100...`, Enter.
2. **The login code** — Telegram sends you a code (look in the Telegram app, in
   the chat called "Telegram"). Type it, Enter.
3. **2FA password** — only if you set one. Type it, Enter.

When it finishes without errors, you are logged in for good.

---

## Part 6 — Download files (repeat this any time)

There are **two ways**, depending on what you have.

### Way A — You have ONE message that contains a list of links

(This is what was used to get modules 205–210.)

1. In Telegram, open that message → tap/click it → choose **"Copy Message
   Link"**. You now have a link like `https://t.me/SomeChannel/2254`.
2. Paste the block for your system, replacing the link and the label:

**Windows:**
```
.venv\Scripts\python scrape_index.py --index-url https://t.me/SomeChannel/2254 --module MYLABEL
```
**Mac:**
```
.venv/bin/python scrape_index.py --index-url https://t.me/SomeChannel/2254 --module MYLABEL
```

- Replace `https://t.me/SomeChannel/2254` with your copied link.
- Replace `MYLABEL` with any name you want for the files, e.g. `NEU-205`.

### Way B — You want a WHOLE channel or group

Get the channel link (e.g. `https://t.me/SomeChannel`) and paste:

**Windows:**
```
.venv\Scripts\python scraper.py https://t.me/SomeChannel
```
**Mac:**
```
.venv/bin/python scraper.py https://t.me/SomeChannel
```

---

## Part 7 — Find your downloaded files

Inside the `sdf/telegram-question-scraper` folder there is now a **`downloads`**
folder. Your files are inside it, sorted into subfolders. There is also a
**`MANIFEST.txt`** file that lists every download with its Telegram link.

To open the folder quickly:
- **Windows:** type `explorer downloads` and press Enter.
- **Mac:** type `open downloads` and press Enter.

---

## Group vs Message link — which one do I use?

There are two situations. Pick the one that matches what you have.

### A) Scrape a whole GROUP or CHANNEL

Use this when you want **everything** from an entire group/channel.

1. **Get the link:** in Telegram, open the group/channel → tap its name at the
   top → you'll see a link like `https://t.me/SomeGroup` (or an `@SomeGroup`
   handle). You must already be a member.
2. **Run it** (Windows users: swap `.venv/bin/python` for `.venv\Scripts\python`):
   ```
   .venv/bin/python scraper.py https://t.me/SomeGroup
   ```
   It reads every message in that group, keeps the question/exam files, skips
   practical/textbook/noise, and saves them into `downloads`.

Optional extras:
```
.venv/bin/python scraper.py --dry-run https://t.me/SomeGroup            # preview only, downloads nothing
.venv/bin/python scraper.py --limit 400 --dry-run https://t.me/SomeGroup # test on the latest 400 messages
.venv/bin/python scraper.py https://t.me/GroupA https://t.me/GroupB      # several at once
```

### B) Scrape from a single MESSAGE LINK

Use this when **one message** contains a list of links to the actual files
(often files that live in other channels) — this is exactly what was used to get
modules 205–210.

1. **Copy the message link:** in Telegram, tap/right-click that specific message
   → **"Copy Message Link"**. You get something like
   `https://t.me/FUTUREDOCTORS_198/2254` (channel name + message number).
2. **Run it** (Windows users: swap `.venv/bin/python` for `.venv\Scripts\python`):
   ```
   .venv/bin/python scrape_index.py --index-url https://t.me/FUTUREDOCTORS_198/2254 --module NEU-205
   ```
   - Replace the link with the one you copied.
   - Replace `NEU-205` with any label you want stamped on the files.

   It opens that one message, follows every link inside it, downloads the files
   (handling photo albums and "header → files below it" sections), removes
   duplicates, and writes a `MANIFEST.txt` listing each file with its link.

### Quick comparison

| You have… | Use | Command |
|---|---|---|
| A whole group/channel | `scraper.py` | `scraper.py https://t.me/SomeGroup` |
| One message full of links | `scrape_index.py` | `scrape_index.py --index-url https://t.me/CHANNEL/MSGID --module LABEL` |

Either way, results land in `downloads/.../questions/` with a `MANIFEST.txt`.

---

## If something goes wrong

- **"python is not recognized" (Windows)** → Python wasn't added to PATH.
  Reinstall Python and tick "Add Python to PATH", then restart.
- **It asks you to log in again** → just repeat Part 5b.
- **A link says "dead/missing"** → that message was deleted, OR you are not a
  member of that channel. Join the channel in Telegram, then run the command
  again.
- **Telegram says "wait X seconds"** → it's a temporary limit. Wait, then run
  the same command again — it continues where it left off.

---

## The short version (after the one-time setup)

```
cd sdf/telegram-question-scraper
.venv/bin/python scrape_index.py --index-url https://t.me/CHANNEL/MESSAGEID --module MYLABEL
```
(Windows: use `.venv\Scripts\python` instead of `.venv/bin/python`.)
