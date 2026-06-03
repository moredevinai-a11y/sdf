# Telegram Question-File Scraper (Telethon)

A reusable Telethon-based scraper that walks a Telegram **channel or group**'s
message history and downloads only **theoretical question / exam / past-paper
documents** (PDF, DOCX, PPT/PPTX), applying linguistic filters to skip
practical/oral/spotting content, textbooks, lecture slides, summaries, religious
content, announcements, and all audio/video. Files are organized by module code
and tracked in a SQLite database so runs are **resumable** (already-downloaded
files are skipped).

Originally built for the medical channels `data_KA198` / `KASR_198`, but it works
on **any channel or group** your logged-in account can access — just pass the
URL/handle on the command line.

## Layout

```
kasr_scraper/
├── scraper.py          # main entry point: walk a whole channel/group history
├── scrape_index.py     # scrape one "index" message that links out to files
├── filters.py          # all keyword/filter/categorization rules (tune here)
├── inspect_channel.py  # dry diagnostic: print classify decisions for N messages
├── requirements.txt    # pinned deps
├── .env                # API_ID / API_HASH (NOT committed)
├── kasr_session.session# saved Telethon login session (NOT committed)
├── questions.db        # SQLite metadata (channel, msg id, file, module, url)
└── downloads/<channel_slug>/<MODULE>/questions/   # downloaded files
```

## One-time setup

```bash
cd ~/kasr_scraper
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create `.env` with your Telegram API credentials (from https://my.telegram.org →
API development tools). Either name works:

```
API_ID=123456
API_HASH=your_api_hash
```

(The current session also has these saved as the `TELEGRAM_API_ID` /
`TELEGRAM_API_HASH` secrets, which the script reads as a fallback.)

## Authentication

If a login session has already been saved in `kasr_session.session` (kept out of
git), no re-login is needed. To authenticate an account for the first time, or to
switch accounts, delete the session file and run:

```bash
.venv/bin/python scraper.py --login-only
```

It prompts for phone → login code → 2FA password (if set) at the terminal.

## Usage

```bash
# Scrape the default channels (data_KA198 then KASR_198):
.venv/bin/python scraper.py

# Scrape ANY other channel(s) / group(s) — pass URLs or @handles:
.venv/bin/python scraper.py https://t.me/some_channel @some_group

# Dry run (classify + print decisions, download nothing):
.venv/bin/python scraper.py --dry-run https://t.me/some_channel

# Only the most recent N messages (good for calibration):
.venv/bin/python scraper.py --limit 400 --dry-run https://t.me/some_channel

# Inspect raw classify decisions for the latest N messages of a channel:
.venv/bin/python inspect_channel.py https://t.me/some_channel 300
```

### Scraping a single "index" message that links out to files

Some channels post an **index / table-of-contents message** for a topic: a single
message whose body is a list of `https://t.me/<channel>/<msg_id>` links pointing
at the actual files (often in *other* channels). `scrape_index.py` resolves such
a message end-to-end:

```bash
.venv/bin/python scrape_index.py \
    --index-url https://t.me/FUTUREDOCTORS_198/2254 \
    --module INT-208
```

What it does:

- Reads every `t.me/<channel>/<id>` link in the index message.
- For a link that points **directly at a file**, downloads that file (plus its
  album siblings if it is part of a grouped media album).
- For a link that points at a **section header** (a text-only message), it walks
  forward and downloads the file(s) that follow it, stopping at the next header.
- Skips practical/oral/spotting, textbooks/notes, and admin/announcement noise
  via `filters.py`, then **forces** the module code you pass with `--module`
  (the index itself vouches that every file belongs to that module).
- De-duplicates identical files by MD5, records everything in `questions.db`,
  and writes a `MANIFEST.txt` listing each file with its Telegram link.
- Reports skipped files and dead/broken links so you can review them.

Options: `--index-url` (required), `--module CODE` (required, e.g. `NEU-205`),
`--slug NAME` (optional download subfolder name; defaults to `M<digits>_<channel>`).
Downloads land in `downloads/<slug>/<MODULE>/questions/`.

Note: filters are tuned for precision, so an occasional real question file can be
over-skipped when its caption coincidentally contains an excluded word (e.g. a
topic literally named "oral cavity" tripping the oral-exam filter). Review the
`skip(...)` lines it prints and re-fetch any false skip by message id.

Long runs are best backgrounded:

```bash
nohup .venv/bin/python -u scraper.py https://t.me/some_channel > /tmp/scrape.txt 2>&1 &
tail -f /tmp/scrape.txt
```

Because every download is recorded in `questions.db` with a
`UNIQUE(channel, message_id, file_name)` constraint, you can **stop and re-run at
any time** — it resumes without re-downloading.

## Adapting filters for a different topic/channel

All classification logic lives in `filters.py`. To reuse for a non-medical
channel, edit these lists near the top:

- `ALLOWED_EXTENSIONS` / `IMAGE_EXTENSIONS` / `BLOCKED_EXTENSIONS` — file types to
  keep / skip / never download. (Images are skipped by default; move them into
  `ALLOWED_EXTENSIONS` to also grab exam-paper screenshots.)
- `INCLUDE_KEYWORDS` — words that mark a file as a wanted question/exam file
  (Arabic + English supported; matching is case-insensitive and normalizes
  Eastern-Arabic numerals ٢٠٥ → 205).
- `EXCLUDE_PRACTICAL` — practical/oral/spotting terms to hard-skip.
- `EXCLUDE_FORBIDDEN` — textbooks/atlases/lectures/summaries to hard-skip.
- `NON_QUESTION` — religious/admin/announcement/seating noise to hard-skip.
- Module mapping (`MODULE_*` / `detect_module`) — change the module codes and the
  numbers/shortcodes that map to them.

Key design rule: **inclusion/exclusion is decided on the file's own name + its
own/album caption** (`own_text`); preceding-message context (`context_text`) is
used **only for module detection**. This prevents an unrelated neighboring
message's keyword from pulling in the wrong file.

## Querying results

```bash
.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("questions.db")
for r in c.execute("SELECT detected_module, COUNT(*) FROM questions GROUP BY detected_module ORDER BY 2 DESC"):
    print(r)
PY
```

## Packaging per-module downloads

```bash
cd downloads/<channel_slug>/<MODULE> && zip -r /tmp/<MODULE>.zip questions
```
