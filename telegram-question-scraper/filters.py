"""Linguistic filtering and module categorization for the KASR_198 scraper.

Handles:
- Allowed/forbidden file-type detection.
- Inclusion keyword matching (theoretical questions/exams).
- Exclusion of practical/oral/spotting content.
- Exclusion of forbidden heavy material (textbooks, lecture slides, summaries).
- Module categorization (NEU-205 ... PAT-210) supporting English shortcodes,
  Western numerals and Eastern-Arabic numerals.
- Question category typing (MCQ / Written / Past Papers).
"""

from __future__ import annotations

import re

# --- File type rules -------------------------------------------------------

# Document question files only. Exam-paper images (JPG/PNG) are intentionally
# excluded for now per the user's request to "skip question photos".
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt"}

# Image extensions that would otherwise be exam-paper screenshots. Kept separate
# so they are simply skipped (counted as skipped file types) rather than blocked.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Extensions we must never download (audio/video and other heavy/irrelevant media).
BLOCKED_EXTENSIONS = {
    ".mp3", ".m4a", ".ogg", ".oga", ".opus", ".wav", ".aac", ".flac",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".3gp", ".m4v",
    ".zip", ".rar", ".7z",  # archives often bundle textbooks; skip by default
    ".apk", ".exe",
}

# --- Keyword sets ----------------------------------------------------------
# All matching is done on text that has been lower-cased and had Eastern-Arabic
# numerals normalized to Western numerals.

INCLUDE_KEYWORDS = [
    # Arabic
    "سؤال", "أسئلة", "اسئلة", "امتحان", "امتحانات", "نظري", "تحريري", "ريتن",
    "امسكيور", "امتحان تحريري", "امتحان الراوند", "أسئلة القسم", "اسئلة القسم",
    "أسئلة السنوات السابقة", "اسئلة السنوات السابقة", "امتحانات سابقة",
    "امتحانات قديمة", "فاينال", "ميدتيرم", "ميد تيرم", "كويز",
    "نموذج اجابة", "نموذج إجابة", "تجميعة أسئلة", "تجميعة اسئلة",
    # English / transliterated
    "mcq", "mcqs", "quiz", "past paper", "past papers", "theory", "theoretical",
    "written", "final", "midterm", "mid term", "round exam", "exam", "exams",
    "questions", "question", "eoy", "eom", "end of module", "end of year",
    "previous year", "previous years", "model answer", "previous exam",
    "assessment", "self assessment", "formative", "summative", "workbook",
    "solved", "unsolved", "answered", "q&a",
]

# Practical / clinical content to strictly exclude.
EXCLUDE_PRACTICAL = [
    "عملي", "العملي", "امتحان العملي", "سلايدات عملي", "شفوي", "جارات", "أوسبي",
    "اوسبي",
    "practical", "ospe", "oral", "museum", "jars", "spotting", "station",
    "identification", "spot",
]

# Non-question material that should be hard-skipped based on the file's OWN name
# / caption, even if an album caption mentions exams (religious posts, exam
# announcements, seating numbers, schedules, orientation docs, results).
EXCLUDE_NON_QUESTION = [
    # Religious
    "سورة", "الكهف", "القران", "القرآن", "قران", "surah", "quran", "kahf",
    "أذكار", "اذكار", "دعاء",
    # Seating numbers / schedules / announcements / orientation / results
    "ارقام الجلوس", "أرقام الجلوس", "رقم الجلوس", "جلوس", "seating",
    "توزيعة", "توزيعه", "توزيع", "اعلان", "إعلان", "announcement",
    "orientation", "اورنتيشن", "جدول", "جداول", "schedule", "timetable",
    "نتيجة", "نتائج", "result", "results", "كنترول", "control",
    # Reference / study aids (not question files)
    "drug index", "ilos", "study guide", "log book", "logbook", "portfolio",
    "كشف غياب", "غياب", "انذار", "إنذار", "حرمان", "study plan",
]

# Heavy / non-question material to exclude (textbooks, slides, summaries, lectures).
EXCLUDE_FORBIDDEN = [
    "كتاب", "الكتاب", "كتب", "بوك", "محاضرة", "محاضرات", "سلايد", "سلايدات",
    "ملزمة", "ملازم", "ملخص", "ملخصات", "شرح", "مذكرة", "مذكرات", "نوت",
    "textbook", "text book", "book", "lecture", "lectures", "slide", "slides",
    "presentation", "ppt notes", "summary", "summaries", "notes", "handout",
    "handouts", "reference", "guyton", "snell", "davidson", "kumar",
    # Common anatomy/medical atlases & textbooks seen in the channel.
    "atlas", "netter", "sobotta", "grays anatomy", "gray's anatomy",
    "chaurasia",
]

# --- Module categorization -------------------------------------------------
# Priority order matters; first match wins.
MODULES = [
    ("NEU-205", ["neu"], ["205"]),
    ("DIG-206", ["dig"], ["206"]),
    ("END-207", ["end"], ["207"]),
    ("INT-208", ["int"], ["208"]),
    ("PSY-213", ["psy"], ["213"]),
    ("PAT-210", ["pat"], ["210"]),
]

UNCATEGORIZED = "Uncategorized_General"

# Eastern-Arabic (٠-٩) and Extended-Arabic/Persian (۰-۹) digit translation.
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_DIGIT_TRANS = {ord(a): str(i) for i, a in enumerate(_ARABIC_DIGITS)}
_DIGIT_TRANS.update({ord(p): str(i) for i, p in enumerate(_PERSIAN_DIGITS)})

# Arabic tashkeel (diacritics) U+064B..U+0652, superscript alef U+0670, and the
# tatweel/kashida U+0640 are stripped so keyword matching is robust to
# decorative spellings like "سُـورة".
_DIACRITICS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "\u0640\u0670"
_DIACRITIC_TRANS = {ord(c): None for c in _DIACRITICS}


def normalize(text: str | None) -> str:
    """Lower-case, drop Arabic diacritics/tatweel, convert Arabic/Persian
    numerals to Western numerals, and turn filename separators (``_ - . /``)
    into spaces so keywords like "drug index" match "Drug_Index"."""
    if not text:
        return ""
    text = text.translate(_DIGIT_TRANS).translate(_DIACRITIC_TRANS).lower()
    return re.sub(r"[_\-./\\]+", " ", text)


def get_extension(file_name: str | None) -> str:
    if not file_name:
        return ""
    m = re.search(r"(\.[A-Za-z0-9]{1,5})$", file_name.strip())
    return m.group(1).lower() if m else ""


def is_allowed_extension(file_name: str | None) -> bool:
    return get_extension(file_name) in ALLOWED_EXTENSIONS


def is_blocked_extension(file_name: str | None) -> bool:
    return get_extension(file_name) in BLOCKED_EXTENSIONS


def _contains_any(text: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        if kw in text:
            return kw
    return None


def matches_include(text: str) -> str | None:
    return _contains_any(text, INCLUDE_KEYWORDS)


def matches_practical(text: str) -> str | None:
    return _contains_any(text, EXCLUDE_PRACTICAL)


def matches_forbidden(text: str) -> str | None:
    return _contains_any(text, EXCLUDE_FORBIDDEN)


def matches_non_question(text: str) -> str | None:
    return _contains_any(text, EXCLUDE_NON_QUESTION)


def detect_module(text: str) -> str:
    """Return the module code for the given (already normalized) text."""
    for code, shortcodes, numbers in MODULES:
        for sc in shortcodes:
            if re.search(r"\b" + re.escape(sc) + r"\b", text):
                return code
        for num in numbers:
            if re.search(r"\b" + re.escape(num) + r"\b", text):
                return code
    return UNCATEGORIZED


def detect_category(text: str) -> str:
    """Classify the question file as MCQ / Written / Past Papers."""
    mcq_kw = ["mcq", "mcqs", "quiz", "كويز", "امسكيور", "اختيار", "اختيارات"]
    written_kw = ["written", "ريتن", "تحريري", "essay", "مقالي", "مقال"]
    past_kw = [
        "past paper", "past papers", "امتحانات سابقة", "امتحانات قديمة",
        "السنوات السابقة", "أسئلة السنوات", "اسئلة السنوات", "previous",
    ]
    if _contains_any(text, mcq_kw):
        return "MCQ"
    if _contains_any(text, written_kw):
        return "Written"
    if _contains_any(text, past_kw):
        return "Past Papers"
    # Default for theoretical question files without an explicit sub-type.
    return "Past Papers"


def classify(own_text: str, context_text: str = "") -> dict:
    """Decide whether to download and how to categorize.

    The include/exclude decision is based on the file's OWN text (file name +
    its own / album caption). ``context_text`` (the preceding admin / section
    header) is used ONLY to help detect the module code. This keeps precision
    high in a bulk file dump, where an exam-themed section header would
    otherwise bleed onto adjacent revision notes, atlases and lecture files.

    Returns a dict with keys: download (bool), reason (str),
    module (str), category (str), matched_include (str|None).
    """
    own = normalize(own_text)
    full = normalize(f"{own_text}\n{context_text}")
    module = detect_module(full)

    def skip(reason: str) -> dict:
        return {"download": False, "reason": reason, "module": module,
                "category": None, "matched_include": None}

    # Hard non-question skip (religious posts, announcements, seating numbers,
    # schedules, orientation, results, reference aids).
    non_q = matches_non_question(own)
    if non_q:
        return skip(f"excluded:non_question:{non_q}")

    # Practical / clinical content.
    practical = matches_practical(own)
    if practical:
        return skip(f"excluded:practical:{practical}")

    include = matches_include(own)
    forbidden = matches_forbidden(own)

    # Heavy material (textbooks/atlases/notes/slides) is excluded unless the
    # file is clearly an exam/question file too (e.g. "MCQ notes").
    if forbidden and not include:
        return skip(f"excluded:forbidden:{forbidden}")

    if not include:
        return skip("no_include_match")

    return {
        "download": True,
        "reason": f"included:{include}",
        "module": module,
        "category": detect_category(own),
        "matched_include": include,
    }
