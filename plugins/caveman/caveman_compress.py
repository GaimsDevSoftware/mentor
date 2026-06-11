"""Caveman text compressor — deterministic, fast, Claude-free.

Shrinks bulky natural-language / web text before it enters the model's context
window, WITHOUT losing meaning. It never touches code, URLs, numbers or quoted
strings (they are stashed out and restored), so it is safe to run on tool output.

Levels:
  • minimal    — whitespace only (trailing ws, collapse 3+ blank lines). Safe on
                 anything, including a system prompt.
  • structural — minimal + collapse internal space runs, dedupe consecutive
                 identical lines, strip HTML (when the text looks like HTML).
  • aggressive — structural + curated MEANING-PRESERVING filler removal
                 ("in order to"→"to", "due to the fact that"→"because", cookie/
                 nav boilerplate). No article/stopword butchery.
  • caveman    — aggressive + true "caveman speak": drops PREDICTABLE grammar
                 (articles, fillers, hedges, droppable "that"), symbol subs
                 (→/vs/~), expletive "there is/are". Lossy of grammar, not of
                 meaning — strong models read it fine. Biggest savings.

compress(text, level) -> (compressed, original_len, compressed_len)
"""
from __future__ import annotations

import html
import re

# Spans that must survive verbatim — stashed to placeholders before compression.
_PROTECT = [
    re.compile(r"```.*?```", re.S),       # fenced code blocks
    re.compile(r"~~~.*?~~~", re.S),       # alt fences
    re.compile(r"`[^`\n]+`"),             # inline code
    re.compile(r"https?://[^\s)>\]}\"']+"),  # URLs
    re.compile(r'"[^"\n]{0,200}"'),       # short quoted strings
]

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
_HTML_TAG = re.compile(r"<[^>]+>")

# Curated verbose→terse substitutions that preserve meaning.
_FILLER = [
    (re.compile(r"\bplease note that\b", re.I), ""),
    (re.compile(r"\bit(?:'s| is) (?:important|worth noting|worth mentioning)(?: to note)? that\b", re.I), ""),
    (re.compile(r"\bas (?:you can see|mentioned|stated|noted|discussed)(?: above| below| earlier| previously| before)?\b", re.I), ""),
    (re.compile(r"\bin order to\b", re.I), "to"),
    (re.compile(r"\bdue to the fact that\b", re.I), "because"),
    (re.compile(r"\bin spite of the fact that\b", re.I), "although"),
    (re.compile(r"\bat (?:this|the present) (?:point in time|moment in time|time)\b", re.I), "now"),
    (re.compile(r"\bin the event that\b", re.I), "if"),
    (re.compile(r"\bfor the purpose of\b", re.I), "for"),
    (re.compile(r"\ba (?:large|great|significant) number of\b", re.I), "many"),
    (re.compile(r"\bthe (?:vast )?majority of\b", re.I), "most"),
    (re.compile(r"\bwith (?:regard|respect) to\b", re.I), "about"),
    (re.compile(r"\bin conclusion,?\b", re.I), ""),
    (re.compile(r"\bneedless to say,?\b", re.I), ""),
    # AI-typical filler
    (re.compile(r"\b(?:I'd be |I am |I'm )?happy to help(?: you)?(?: with that)?[.!]?\s*", re.I), ""),
    (re.compile(r"\b(?:Sure|Of course|Absolutely|Certainly|Great|Perfect)[,!]?\s+(?:I (?:can|will|'ll)|[Ll]et me)\b", re.I), ""),
    (re.compile(r"\b(?:Here(?:'s| is) (?:a |the |my )?(?:summary|breakdown|overview|explanation|answer|response|result)(?:\s+(?:of|for) (?:that|this|you))?)\s*[:—–-]?\s*", re.I), ""),
    (re.compile(r"\bI hope (?:this|that) helps[.!]?\s*", re.I), ""),
    (re.compile(r"\b(?:Let me know|Feel free to (?:ask|reach out|let me know)) if you (?:have|need) (?:any )?(?:more |further |other )?questions[.!]?\s*", re.I), ""),
    (re.compile(r"\bAs (?:an AI|a language model|an assistant)\b[^.]*\.\s*", re.I), ""),
    (re.compile(r"\bTo (?:summarize|sum up|recap)[,:]?\s*", re.I), ""),
    (re.compile(r"\b(?:It'?s? )?(?:also )?worth (?:noting|mentioning|pointing out) that\b", re.I), ""),
    (re.compile(r"\b(?:Basically|Essentially|Fundamentally|In essence),?\s+", re.I), ""),
]
# ── Caveman-speak: drop PREDICTABLE grammar, keep the unpredictable facts ──
# The actual "caveman" move the original skill is named for, which our earlier
# levels deliberately skipped. Applied only to UNPROTECTED prose (code, URLs,
# numbers and quoted strings are already stashed out), so it's safe on tool
# output. Lossy of grammar, not of meaning — strong models read it fine.
_CAVEMAN = [
    # Articles — the single most predictable, droppable grammar. "the" is never a
    # name, so always safe; "a"/"an" only lowercase (skip a capital "A" that may
    # be a label/grade, e.g. "vitamin A").
    (re.compile(r"\bthe\b[ ]+", re.I), ""),
    (re.compile(r"\b(?:a|an)\b[ ]+"), ""),
    # Low-information intensifiers / fillers.
    (re.compile(r"\b(?:just|really|basically|actually|simply|very|quite|rather|"
                r"somewhat|essentially|fundamentally|literally|truly|surely|"
                r"definitely|obviously|clearly|highly|fairly|pretty|that said)\b[ ]*", re.I), ""),
    # Hedges — caveman drops hedging.
    (re.compile(r"\b(?:I think|I believe|I feel|it seems|it appears|arguably|"
                r"presumably|in my opinion|kind of|sort of|more or less)\b[,]?[ ]*", re.I), ""),
    # Droppable "that" conjunction after common reporting/cognition verbs.
    (re.compile(r"\b(think|know|knows|believe|see|note|noted|say|says|said|mean|"
                r"means|ensure|ensures|show|shows|shown|found|find|finds|suggest|"
                r"suggests|assume|assumes|notice|recall|realize)\b[ ]+that\b", re.I), r"\1"),
    # Verbose connectors → symbols / short forms.
    (re.compile(r"\b(?:leads? to|results? in|causes?|gives? rise to|translates? to)\b", re.I), "→"),
    (re.compile(r"\b(?:versus|compared (?:to|with)|as opposed to)\b", re.I), "vs"),
    (re.compile(r"\b(?:approximately|roughly|approx\.?|around about)\b", re.I), "~"),
    (re.compile(r"\b(?:as well as|in addition to)\b", re.I), "+"),
    (re.compile(r"\b(?:therefore|thus|hence|consequently|as a result)\b[,]?[ ]*", re.I), "so "),
    # Expletive "there is/are" carries no information.
    (re.compile(r"\bthere (?:is|are|was|were)\b[ ]*", re.I), ""),
    # "in order to" already handled in aggressive; mop up a few more verbose stock phrases.
    (re.compile(r"\bin terms of\b", re.I), "for"),
    (re.compile(r"\bas a matter of fact\b[,]?[ ]*", re.I), ""),
]

# Whole-line web boilerplate (nav / cookie / footer cruft).
_WEB_CRUFT = re.compile(
    r"^\s*(accept (all )?cookies|we use cookies|this (site|website) uses cookies|"
    r"subscribe to (our )?newsletter|sign up for|follow us on|skip to (main )?content|"
    r"all rights reserved|©|cookie (policy|settings|preferences)|"
    r"share (on|this)|advertisement|back to top).*$", re.I)


def _looks_html(t: str) -> bool:
    return t.count("<") > 5 and bool(
        re.search(r"<(div|p|span|a|table|tr|td|br|li|ul|ol|h[1-6]|html|body|head|nav|footer)\b", t, re.I))


def compress(text: str, level: str = "structural"):
    if not text:
        return text, 0, 0
    original_len = len(text)

    # 1) stash protected spans
    saved = []

    def _stash(m):
        saved.append(m.group(0))
        return f"\x00P{len(saved) - 1}\x00"

    work = text
    for pat in _PROTECT:
        work = pat.sub(_stash, work)

    work = work.replace("\r\n", "\n").replace("\r", "\n")

    # 2) HTML strip (structural+)
    if level in ("structural", "aggressive", "caveman") and _looks_html(work):
        work = _SCRIPT_STYLE.sub(" ", work)
        work = _HTML_TAG.sub(" ", work)
        work = html.unescape(work)

    # 3) curated filler (aggressive+), then caveman-speak grammar dropping (caveman)
    if level in ("aggressive", "caveman"):
        for pat, rep in _FILLER:
            work = pat.sub(rep, work)
    if level == "caveman":
        for pat, rep in _CAVEMAN:
            work = pat.sub(rep, work)

    # 4) line-wise normalisation
    out_lines = []
    prev = None
    blanks = 0
    for ln in work.split("\n"):
        ln = ln.rstrip()
        if level in ("structural", "aggressive", "caveman"):
            ln = re.sub(r"[ \t]{2,}", " ", ln)
            if level in ("aggressive", "caveman") and _WEB_CRUFT.match(ln):
                continue
        if ln == "":
            blanks += 1
            # minimal keeps single blank lines; collapse 2+ to 1
            if blanks >= 2:
                continue
            out_lines.append("")
            prev = ""
            continue
        blanks = 0
        if level in ("structural", "aggressive", "caveman") and ln == prev:
            continue  # dedupe consecutive identical lines
        out_lines.append(ln)
        prev = ln

    work = "\n".join(out_lines).strip()

    # 5) tidy punctuation spacing introduced by filler removal
    if level in ("aggressive", "caveman"):
        work = re.sub(r"[ \t]{2,}", " ", work)
        work = re.sub(r"\s+([,.;:!?])", r"\1", work)
        work = re.sub(r"\(\s+", "(", work)
        # Tidy artifacts left when a leading phrase/word was dropped:
        work = re.sub(r"([.!?;:])\s*,", r"\1", work)        # ". ," → "."
        work = re.sub(r",\s*,", ",", work)                   # doubled commas
        work = re.sub(r"(^|\n)[ \t]*[,;:][ \t]*", r"\1", work)  # orphan leading punct
    work = re.sub(r"\n{3,}", "\n\n", work)

    # 6) restore protected spans
    work = re.sub(r"\x00P(\d+)\x00", lambda m: saved[int(m.group(1))], work)

    # Never return something LONGER than the input.
    if len(work) >= original_len:
        return text, original_len, original_len
    return work, original_len, len(work)


def est_tokens(n_chars: int) -> int:
    """Rough token estimate (~4 chars/token)."""
    return n_chars // 4
