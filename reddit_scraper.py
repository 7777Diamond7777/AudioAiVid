"""
Reddit complaint scraper — music, software engineering, AI audio, data analytics.
Outputs: reddit_report.html + reddit_complaints.csv

SETUP (one-time, ~2 minutes):
  1. Log into Reddit → https://www.reddit.com/prefs/apps
  2. Click "create another app" → choose type: script
  3. Name it anything, redirect URI: http://localhost:8080
  4. Copy the client_id (short string under the app name) and client_secret
  5. Create a file named .env in this directory with:
       REDDIT_CLIENT_ID=your_client_id_here
       REDDIT_CLIENT_SECRET=your_client_secret_here

Then run:  python3 reddit_scraper.py
"""

import os
import csv
import time
import html
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

try:
    import praw
except ImportError:
    raise SystemExit("Missing dependency: pip3 install praw python-dotenv")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env vars may already be set in the shell environment

# ── Config ────────────────────────────────────────────────────────────────────

SUBREDDITS = {
    # Music AI / Suno / AI tools
    "SunoAI":              "Music AI / AI Video",
    "udiomusic":           "Music AI / AI Video",
    "aivideo":             "Music AI / AI Video",
    "StableDiffusion":     "Music AI / AI Video",
    "MediaSynthesis":      "Music AI / AI Video",
    # Music production
    "WeAreTheMusicMakers": "Music Production",
    "musicproduction":     "Music Production",
    "audioengineering":    "Music Production",
    "edmproduction":       "Music Production",
    "singing":             "Music Production",
    # Software engineering
    "cscareerquestions":   "Software Engineering",
    "softwareengineering": "Software Engineering",
    "ExperiencedDevs":     "Software Engineering",
    "programming":         "Software Engineering",
    "devops":              "Software Engineering",
    # Data / Analytics
    "datascience":         "Data / Analytics",
    "dataengineering":     "Data / Analytics",
    "analytics":           "Data / Analytics",
    "learnmachinelearning":"Data / Analytics",
    "MachineLearning":     "Data / Analytics",
}

COMPLAINT_KEYWORDS = [
    "frustrated", "annoying", "broken", "bug", "issue", "problem",
    "hate", "terrible", "awful", "worst", "fails", "doesn't work",
    "can't", "impossible", "wish they", "why can't", "please fix",
    "need help", "rant", "ugh", "disappointing", "useless", "slow",
    "crash", "error", "missing feature", "limitation", "workaround",
    "painful", "nightmare", "stuck", "garbage", "trash", "unusable",
    "keeps breaking", "still not fixed", "anyone else", "complaint",
    "upset", "ruined", "sucks", "blows", "regret", "glitch",
    "not working", "help me", "why does", "why is it", "how do i fix",
]

POSTS_PER_SUB = 75    # per sort (hot + new)
MIN_SCORE     = 1

OUTPUT_HTML = Path("reddit_report.html")
OUTPUT_CSV  = Path("reddit_complaints.csv")

CATEGORY_COLORS = {
    "Music AI / AI Video":    "#7c3aed",
    "Music Production":       "#db2777",
    "Software Engineering":   "#0369a1",
    "Data / Analytics":       "#047857",
}

# ── Reddit client ─────────────────────────────────────────────────────────────

def make_reddit() -> praw.Reddit:
    client_id     = os.getenv("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        raise SystemExit(
            "\n[ERROR] Missing Reddit credentials.\n"
            "Create a .env file with:\n"
            "  REDDIT_CLIENT_ID=your_id\n"
            "  REDDIT_CLIENT_SECRET=your_secret\n\n"
            "Get credentials at: https://www.reddit.com/prefs/apps\n"
            "Choose type 'script', redirect URI: http://localhost:8080\n"
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="AudioAiVid-ComplaintScraper/1.0 (research script)",
    )

# ── Helpers ───────────────────────────────────────────────────────────────────

def complaint_score(text: str) -> int:
    lower = text.lower()
    return sum(1 for kw in COMPLAINT_KEYWORDS if kw in lower)


def parse_submission(sub, category: str) -> dict | None:
    if sub.score < MIN_SCORE or sub.stickied:
        return None

    selftext = (sub.selftext or "").replace("\n", " ").strip()
    combined = f"{sub.title} {selftext}"
    cscore   = complaint_score(combined)
    created  = datetime.fromtimestamp(sub.created_utc, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "subreddit":       sub.subreddit.display_name,
        "category":        category,
        "title":           sub.title,
        "score":           sub.score,
        "num_comments":    sub.num_comments,
        "complaint_score": cscore,
        "url":             f"https://www.reddit.com{sub.permalink}",
        "date":            created,
        "flair":           sub.link_flair_text or "",
        "snippet":         selftext[:300],
    }

# ── Scrape ────────────────────────────────────────────────────────────────────

def scrape(reddit: praw.Reddit) -> list[dict]:
    posts    = []
    seen_ids = set()

    for sub_name, category in SUBREDDITS.items():
        print(f"  r/{sub_name} ...")
        subreddit = reddit.subreddit(sub_name)

        for feed in (subreddit.hot(limit=POSTS_PER_SUB), subreddit.new(limit=POSTS_PER_SUB)):
            try:
                for submission in feed:
                    if submission.id in seen_ids:
                        continue
                    seen_ids.add(submission.id)
                    parsed = parse_submission(submission, category)
                    if parsed:
                        posts.append(parsed)
            except Exception as e:
                print(f"    [WARN] {sub_name}: {e}")

    posts.sort(key=lambda p: (p["complaint_score"], p["score"]), reverse=True)
    return posts

# ── CSV ───────────────────────────────────────────────────────────────────────

def write_csv(posts: list[dict]) -> None:
    fields = ["date", "category", "subreddit", "complaint_score",
              "score", "num_comments", "title", "flair", "snippet", "url"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(posts)
    print(f"  CSV  → {OUTPUT_CSV}  ({len(posts)} rows)")

# ── HTML ──────────────────────────────────────────────────────────────────────

def badge(category: str) -> str:
    color = CATEGORY_COLORS.get(category, "#555")
    return f'<span class="badge" style="background:{color}">{html.escape(category)}</span>'


def score_bar(n: int, max_n: int) -> str:
    if max_n == 0:
        return "<span>0</span>"
    pct   = min(100, int(n / max_n * 100))
    color = "#ef4444" if pct >= 66 else "#f59e0b" if pct >= 33 else "#10b981"
    return (
        f'<div class="bar-wrap" title="{n} complaint signals">'
        f'<div class="bar" style="width:{pct}%;background:{color}"></div>'
        f'<span>{n}</span></div>'
    )


def write_html(posts: list[dict]) -> None:
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(posts)
    with_complaints = sum(1 for p in posts if p["complaint_score"] > 0)
    max_cscore      = max((p["complaint_score"] for p in posts), default=1)
    cat_counts      = Counter(p["category"] for p in posts if p["complaint_score"] > 0)

    rows_html = ""
    for p in posts:
        cs        = p["complaint_score"]
        row_class = "hot" if cs >= 3 else "warm" if cs >= 1 else "cool"
        snippet   = html.escape(p["snippet"]) if p["snippet"] else "<em>—</em>"
        rows_html += f"""
        <tr class="{row_class}">
          <td>{html.escape(p['date'])}</td>
          <td>{badge(p['category'])}</td>
          <td class="sub-cell">r/{html.escape(p['subreddit'])}</td>
          <td>{score_bar(cs, max_cscore)}</td>
          <td class="title-cell"><a href="{html.escape(p['url'])}" target="_blank" rel="noopener">{html.escape(p['title'])}</a></td>
          <td>{html.escape(p['flair'])}</td>
          <td class="num">{p['score']:,}</td>
          <td class="num">{p['num_comments']:,}</td>
          <td class="snippet">{snippet}</td>
        </tr>"""

    summary_cards = ""
    for cat, color in CATEGORY_COLORS.items():
        count = cat_counts.get(cat, 0)
        summary_cards += f"""
        <div class="card" style="border-top:4px solid {color}">
          <div class="card-label">{html.escape(cat)}</div>
          <div class="card-num" style="color:{color}">{count}</div>
          <div class="card-sub">posts with complaint signals</div>
        </div>"""

    cat_options = "".join(
        f'<option value="{c}">{html.escape(c)}</option>' for c in CATEGORY_COLORS
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reddit Complaint Radar — {now}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;font-size:14px}}
header{{padding:2rem;background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:1px solid #1e293b}}
header h1{{font-size:1.8rem;font-weight:700;color:#a78bfa}}
header p{{color:#94a3b8;margin-top:.4rem}}
.summary{{display:flex;gap:1rem;padding:1.5rem 2rem;flex-wrap:wrap}}
.card{{background:#1e293b;border-radius:10px;padding:1.2rem 1.5rem;flex:1;min-width:160px}}
.card-label{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.card-num{{font-size:2rem;font-weight:800;margin:.3rem 0}}
.card-sub{{font-size:.75rem;color:#64748b}}
.total-card{{border-top:4px solid #a78bfa!important}}
.controls{{padding:.75rem 2rem;display:flex;gap:.75rem;flex-wrap:wrap;align-items:center;background:#1e293b;border-bottom:1px solid #334155}}
.controls input,.controls select{{background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:.4rem .8rem;font-size:.875rem}}
.controls label{{color:#94a3b8;font-size:.8rem;display:flex;align-items:center;gap:.4rem}}
#search-box{{width:260px}}
table{{width:100%;border-collapse:collapse}}
thead th{{background:#1e293b;padding:.6rem 1rem;text-align:left;color:#64748b;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0;z-index:10}}
tbody tr{{border-bottom:1px solid #1e293b;transition:background .1s}}
tbody tr:hover{{background:#1e293b}}
tbody tr.hot{{border-left:3px solid #ef4444}}
tbody tr.warm{{border-left:3px solid #f59e0b}}
tbody tr.cool{{border-left:3px solid #334155}}
td{{padding:.55rem 1rem;vertical-align:top}}
.badge{{display:inline-block;padding:.2rem .5rem;border-radius:4px;font-size:.7rem;font-weight:600;color:#fff;white-space:nowrap}}
.bar-wrap{{display:flex;align-items:center;gap:.4rem;min-width:90px}}
.bar-wrap .bar{{height:8px;border-radius:4px;min-width:2px}}
.bar-wrap span{{font-size:.8rem;color:#94a3b8;min-width:1ch}}
.title-cell a{{color:#93c5fd;text-decoration:none}}
.title-cell a:hover{{text-decoration:underline}}
.snippet{{color:#64748b;font-size:.8rem;max-width:300px}}
.sub-cell{{color:#94a3b8;white-space:nowrap}}
.num{{text-align:right;color:#94a3b8;white-space:nowrap}}
.table-wrap{{overflow:auto;max-height:calc(100vh - 300px)}}
footer{{padding:1rem 2rem;color:#334155;font-size:.75rem;border-top:1px solid #1e293b}}
</style>
</head>
<body>
<header>
  <h1>Reddit Complaint Radar</h1>
  <p>Music AI · Music Production · Software Engineering · Data Analytics &nbsp;·&nbsp; Generated {now}</p>
</header>
<div class="summary">
  <div class="card total-card">
    <div class="card-label">Total posts scraped</div>
    <div class="card-num" style="color:#a78bfa">{total:,}</div>
    <div class="card-sub">{with_complaints:,} have complaint signals</div>
  </div>
  {summary_cards}
</div>
<div class="controls">
  <label>Search <input id="search-box" type="text" placeholder="keyword…"></label>
  <label>Category
    <select id="cat-filter">
      <option value="">All categories</option>
      {cat_options}
    </select>
  </label>
  <label>Min complaint score
    <select id="score-filter">
      <option value="0">Any</option>
      <option value="1">≥ 1</option>
      <option value="2">≥ 2</option>
      <option value="3">≥ 3</option>
      <option value="5">≥ 5</option>
    </select>
  </label>
  <span id="count-label" style="color:#64748b;font-size:.8rem;margin-left:auto"></span>
</div>
<div class="table-wrap">
<table id="main-table">
  <thead>
    <tr>
      <th>Date</th><th>Category</th><th>Subreddit</th>
      <th>Complaint ▼</th><th>Title</th><th>Flair</th>
      <th>↑Score</th><th>Comments</th><th>Snippet</th>
    </tr>
  </thead>
  <tbody id="tbody">{rows_html}</tbody>
</table>
</div>
<footer>
  Reddit public API via PRAW · personal research only ·
  {total:,} posts across {len(SUBREDDITS)} subreddits · {now}
</footer>
<script>
const rows = Array.from(document.querySelectorAll('#tbody tr'));
const label = document.getElementById('count-label');
function filter() {{
  const q        = document.getElementById('search-box').value.toLowerCase();
  const cat      = document.getElementById('cat-filter').value.toLowerCase();
  const minScore = parseInt(document.getElementById('score-filter').value) || 0;
  let visible = 0;
  rows.forEach(row => {{
    const text   = row.textContent.toLowerCase();
    const barSpan = row.querySelector('.bar-wrap span');
    const cscore  = barSpan ? parseInt(barSpan.textContent) || 0 : 0;
    const show    = (!q || text.includes(q)) &&
                   (!cat || text.includes(cat)) &&
                   cscore >= minScore;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  label.textContent = visible + ' posts shown';
}}
document.getElementById('search-box').addEventListener('input', filter);
document.getElementById('cat-filter').addEventListener('change', filter);
document.getElementById('score-filter').addEventListener('change', filter);
filter();
</script>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  HTML → {OUTPUT_HTML}  ({total} posts)")

# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reddit = make_reddit()
    print(f"Scraping {len(SUBREDDITS)} subreddits (hot + new, up to {POSTS_PER_SUB} each)...")
    posts = scrape(reddit)
    print(f"\nCollected {len(posts)} unique posts. Writing outputs...")
    write_csv(posts)
    write_html(posts)
    print("\nDone! Open reddit_report.html in your browser.")
