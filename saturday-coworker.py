"""
Jack and Blaze — Saturday AI Coworker
Automatically starts all pipeline agents every Saturday.
Runs via GitHub Actions at 8am UTC every Saturday.

Requirements: pip install anthropic requests python-dotenv feedparser
"""

import os, json, smtplib, feedparser, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ── Credentials ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "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")
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "elmo00086@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "gfor opqd vviz nrdo")
BLOGGER_EMAIL      = "elmo00086.books@blogger.com"
SLACK_BOT_TOKEN    = os.getenv("SLACK_BOT_TOKEN", "xoxb-10698702847203-10810832598101-jVnvzawUDXHORUvmYiReUYuA")
SLACK_CHANNEL_ID   = os.getenv("SLACK_CHANNEL_ID", "C0ALP0Y1HK8")
FAST_IO_API_KEY    = os.getenv("FAST_IO_API_KEY", "xls09zxz4p56dzdsfozp4q12lm82v5ddoq47il2dbv44i78x7g")
FAST_IO_WORKSPACE  = "4727745319403567135"
FAST_IO_FOLDER     = "23ont-mmmer-vypjf-sqxbl-36mpj-curk"
PAYHIP_LINK        = "https://payhip.com/LeslieweWalters"

DATE        = datetime.now().strftime("%Y-%m-%d")
FRIDAY_DATE = (datetime.now() + timedelta(days=(4 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")
AUTO_APPROVE_TIME = (datetime.now() + timedelta(hours=6)).strftime("%I:%M %p CDT")

THEMES = [
    "Character Spotlight — Jack",
    "Character Spotlight — Blaze",
    "World-building / Lore Drop",
    "Behind the Scenes / Author Life",
    "Reader Engagement / Community",
    "Book Excerpt or Mood Board"
]

FRIDAY_TOPICS = [
    "Behind-the-scenes writing process",
    "Perseverance + authenticity",
    "Gaming + photography + storytelling",
    "Personal stories + young adult dreams",
    "Reader spotlights + community"
]

AUTHOR_BRAND = """
Author: Leslie Walters | Genre: YA Fantasy + Poetry
Brand: Blending the thrill of YA fiction with the emotional depth of poetry.
Draws from: video games, photography, real-life experiences.
Themes: authenticity, courage, hope, chasing dreams.
Taglines: "Where adventure meets the heart." | "Fuel your dreams with every page."
Buy link: https://payhip.com/LeslieweWalters
Handles: Instagram/TikTok @leswalters_ | Twitter/X @elmo086 | YouTube @lesliew.e.walters
"""

RSS_FEEDS = [
    "https://www.reddit.com/r/YAlit/.rss",
    "https://www.reddit.com/r/Fantasy/.rss",
    "https://www.reddit.com/r/poetry/.rss",
]


def get_week_info():
    start = datetime(2026, 3, 23)
    weeks_elapsed = (datetime.now() - start).days // 7
    week_num = (weeks_elapsed % len(THEMES)) + 1
    theme = THEMES[(weeks_elapsed) % len(THEMES)]
    friday_topic = FRIDAY_TOPICS[(weeks_elapsed) % len(FRIDAY_TOPICS)]
    return week_num, theme, friday_topic


def read_performance_report() -> str:
    """Read last week's performance report for content-generator instructions."""
    if Path("performance-report-latest.md").exists():
        return Path("performance-report-latest.md").read_text()[:3000]
    return "No performance report yet — use default brand guidelines."


def slack_post(message: str):
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": SLACK_CHANNEL_ID, "text": message},
            timeout=15
        )
        ok = r.json().get("ok", False)
        print(f"Slack: {'OK' if ok else r.json().get('error')}")
        return r.json().get("ts", "")
    except Exception as e:
        print(f"Slack error: {e}")
        return ""


def upload_to_fastio(filename: str, content: str):
    try:
        r = requests.post(
            "https://api.fast.io/v1/upload/text-file",
            headers={"Authorization": f"Bearer {FAST_IO_API_KEY}", "Content-Type": "application/json"},
            json={"profile_type": "workspace", "profile_id": FAST_IO_WORKSPACE,
                  "parent_node_id": FAST_IO_FOLDER, "filename": filename, "content": content},
            timeout=30
        )
        print(f"fast.io {'OK' if r.ok else 'FAILED'}: {filename}")
    except Exception as e:
        print(f"fast.io error ({filename}): {e}")


# ── Step 1: Generate Weekly Content ───────────────────────────────────────────

def generate_weekly_content(week_num, theme, performance_notes):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=4000,
        messages=[{"role": "user", "content": f"""Generate weekly social media content for Jack and Blaze.

{AUTHOR_BRAND}

Week {week_num} Theme: {theme}
Date: {DATE}

Last week's performance feedback (APPLY THESE):
{performance_notes}

Generate one post per platform with the exact structure below.
Save as weekly-drafts.md format:

# Weekly Content Drafts — {DATE}
## Theme: {theme}

### INSTAGRAM
**Caption:** [150-300 words, story-driven, ends with question, applies performance feedback]
[10-15 hashtags including #JackAndBlaze #YAFantasy]
**Image Prompt:** [Detailed DALL-E/Canva AI prompt, cinematic YA fantasy, 4:5 ratio, no text/watermarks]

### TIKTOK
**Caption:** [Short punchy hook in first line, 3-5 sentences, 5-8 hashtags]
**Video Concept:** [Shot-by-shot 15-30 second breakdown]
**Audio:** [Specific trending sound or music style]

### FACEBOOK
**Post:** [200-400 words, conversational, community question at end, 3-5 hashtags]
**Image Prompt:** [Warm author-brand aesthetic with fantasy elements, 16:9]

### TWITTER/X
**Tweet:** [Max 280 chars, punchy/mysterious, 1-2 hashtags]
**Image Prompt:** [Minimal bold typography quote card, fantasy background]

### YOUTUBE
**Description:** [150-300 words with hook, content outline, CTA to subscribe]
**Tags:** [10 SEO tags]
**Video Outline:** [Timestamped sections 0:00-end]
**Audio:** [Music style + voiceover tone]
"""}])
    content = msg.content[0].text.strip()
    Path("weekly-drafts.md").write_text(content)
    upload_to_fastio(f"weekly-drafts-{DATE}.md", content)
    print(f"Weekly content generated ({len(content)} chars)")
    return content


# ── Step 2: Generate Friday Author Posts ──────────────────────────────────────

def generate_friday_posts(friday_topic):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=2500,
        messages=[{"role": "user", "content": f"""Generate Friday author brand posts for Leslie Walters.

{AUTHOR_BRAND}

This Friday's topic: {friday_topic}
Friday date: {FRIDAY_DATE}

Generate 3 posts (Facebook, Instagram, Twitter/X) that spotlight Leslie as a person and author.
ALWAYS include payhip.com/LeslieweWalters in at least one post per platform.
These should feel like they come FROM Leslie — warm, real, relatable.

Format:
# Friday Author Post Drafts — {FRIDAY_DATE}
## Topic: {friday_topic}

### FACEBOOK
**Post:** [200-400 words, warm/personal, ends with CTA]
**Buy Link:** {PAYHIP_LINK}
[3-5 hashtags]
**Image Prompt:** [Warm author lifestyle, bookstagram aesthetic, 16:9]

### INSTAGRAM
**Caption:** [150-250 words, emotional hook first line, CTA: link in bio]
[10-15 hashtags including #AuthorLife #YAFantasy #JackAndBlaze #IndieAuthor]
**Image Prompt:** [Bookstagram flat lay, warm tones, cozy creative, 4:5]

### TWITTER/X
**Tweet 1:** [Genuine/punchy, max 280 chars, 1-2 hashtags]
**Tweet 2:** [Includes {PAYHIP_LINK}, max 280 chars]
**Image Prompt:** [Quote card, minimal, gold on dark fantasy background]
"""}])
    content = msg.content[0].text.strip()
    Path(f"friday-author-drafts-{FRIDAY_DATE}.md").write_text(content)
    upload_to_fastio(f"friday-author-drafts-{FRIDAY_DATE}.md", content)
    print("Friday author posts generated")
    return content


# ── Step 3: Generate Blog Post + Email to Blogger ─────────────────────────────

def pull_trending_topics():
    topics = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                topics.append(entry.title)
        except Exception:
            pass
    return topics[:15] or ["Why YA Fantasy Feels Like Home for Lost Souls"]


def generate_and_publish_blog():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    topics = pull_trending_topics()
    topics_text = "\n".join(f"- {t}" for t in topics)

    topic_msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=200,
        messages=[{"role": "user", "content": f"Pick ONE blog title for a YA fantasy/poetry author from these trends. Reply with ONLY the title.\n{topics_text}"}])
    topic = topic_msg.content[0].text.strip()

    post_msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=3000,
        messages=[{"role": "user", "content": f"""Write a blog post for Leslie Walters, YA fantasy and poetry author.

{AUTHOR_BRAND}
Topic: "{topic}"

STRUCTURE (HTML for Blogger):
1. Personal intro (2-3 sentences, first person, warm + genuine)
2. <h2>Main section with keyword</h2> + 2-3 paragraphs
3. <h2>Second section</h2> + 2-3 paragraphs
4. <h2>Third section</h2> + 2-3 paragraphs
5. Original poem (8-16 lines) in <blockquote><em>...</em></blockquote>
6. <h2>Final Thoughts</h2> — opinionated take
7. CTA: "Grab <em>Jack and Blaze</em> at <a href='{PAYHIP_LINK}'>{PAYHIP_LINK}</a>"

RULES: Human voice. Personal detail (gaming/photography/writing). Opinionated. Short paragraphs.

After --- separator:
META_DESCRIPTION: [150-160 chars]
TAGS: [5-8 tags]
EXCERPT: [50 words]
"""}])

    raw = post_msg.content[0].text
    parts = raw.split("---")
    post_html = parts[0].strip()
    meta = {}
    if len(parts) > 1:
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()

    Path(f"blog-post-{DATE}.md").write_text(f"# {topic}\n\n{post_html}")
    upload_to_fastio(f"blog-post-{DATE}.md", f"# {topic}\n\n{post_html}")

    # Email to Blogger
    published = False
    if GMAIL_APP_PASSWORD:
        try:
            email_msg = MIMEMultipart("alternative")
            email_msg["Subject"] = topic
            email_msg["From"]    = GMAIL_ADDRESS
            email_msg["To"]      = BLOGGER_EMAIL
            email_msg.attach(MIMEText(meta.get("EXCERPT", ""), "plain"))
            email_msg.attach(MIMEText(f"<!DOCTYPE html><html><body>{post_html}</body></html>", "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.sendmail(GMAIL_ADDRESS, BLOGGER_EMAIL, email_msg.as_string())
            published = True
            print(f"Blog published: {topic}")
        except Exception as e:
            print(f"Blog email error: {e}")

    return topic, published


# ── Step 4: Send Drafts to Slack ──────────────────────────────────────────────

def send_drafts_to_slack(theme, week_num, friday_topic):
    weekly = Path("weekly-drafts.md").read_text() if Path("weekly-drafts.md").exists() else ""
    friday = Path(f"friday-author-drafts-{FRIDAY_DATE}.md").read_text() if Path(f"friday-author-drafts-{FRIDAY_DATE}.md").exists() else ""

    # Opening message
    slack_post(f"*Saturday Coworker started all agents — {DATE}* 🤖\n\nWeek {week_num}: *{theme}*\nAuto-approves at: *{AUTO_APPROVE_TIME}*\n\nDrafts coming below — reply APPROVE | EDIT: [notes] | REJECT per platform.")

    # Send weekly drafts (split by platform)
    platforms = ["INSTAGRAM", "TIKTOK", "FACEBOOK", "TWITTER/X", "YOUTUBE"]
    for platform in platforms:
        import re
        match = re.search(rf"### {platform}(.*?)(?=### [A-Z]|\Z)", weekly, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()[:2000]
            slack_post(f"*DRAFT — {platform}*\nWeek {week_num}: {theme} | Auto-approves: {AUTO_APPROVE_TIME}\n\n{content}\n\nReply: APPROVE | EDIT: [notes] | REJECT")

    # Friday author drafts
    if friday:
        slack_post(f"*FRIDAY AUTHOR POSTS — {FRIDAY_DATE}*\nTopic: {friday_topic}\n\n{friday[:1500]}\n\nReply: APPROVE | EDIT: [notes] | REJECT")

    # Write draft send log
    log = f"# Draft Send Log\nDate: {DATE}\nTime (ISO): {datetime.utcnow().isoformat()}Z\nAuto-approval deadline (ISO): {(datetime.utcnow() + timedelta(hours=6)).isoformat()}Z\nPlatforms: Instagram, TikTok, Facebook, Twitter/X, YouTube\nChannel: {SLACK_CHANNEL_ID}\n"
    Path("draft-send-log.md").write_text(log)
    upload_to_fastio(f"draft-send-log-{DATE}.md", log)


# ── Step 5: Saturday Summary ──────────────────────────────────────────────────

def post_saturday_summary(theme, week_num, friday_topic, blog_topic, blog_published):
    slack_post(f"""*Saturday Coworker — {DATE}* 🤖✅

All agents started. Here's what ran this morning:

✅ Weekly content drafted (Week {week_num}: {theme})
✅ Blog post {"published to Blogger" if blog_published else "saved locally"}: "{blog_topic}"
✅ Friday author posts drafted ({friday_topic})
✅ All drafts sent to Slack

*Auto-approval window:* 6 hours from now ({AUTO_APPROVE_TIME})
If no reply — everything publishes automatically.

*This week's publishing schedule:*
Mon — Twitter/X 9am
Tue — Instagram 7pm + TikTok 8pm
Wed — Facebook 2pm
Thu — YouTube 1pm
Fri — Author brand posts (FB/IG/X)
Daily — Blog post (GitHub Actions)

Canva images need to be generated separately — run media-generator or say "generate this week's images" in Claude Code. 🎨""")


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    print(f"=== Saturday AI Coworker — {DATE} ===\n")
    week_num, theme, friday_topic = get_week_info()
    print(f"Week {week_num}: {theme}")
    print(f"Friday topic: {friday_topic}\n")

    perf = read_performance_report()

    print("Generating weekly content...")
    generate_weekly_content(week_num, theme, perf)

    print("Generating Friday author posts...")
    generate_friday_posts(friday_topic)

    print("Writing + publishing blog post...")
    blog_topic, blog_published = generate_and_publish_blog()

    print("Sending drafts to Slack...")
    send_drafts_to_slack(theme, week_num, friday_topic)

    print("Posting Saturday summary...")
    post_saturday_summary(theme, week_num, friday_topic, blog_topic, blog_published)

    print(f"\n=== Saturday Coworker Complete — {DATE} ===")


if __name__ == "__main__":
    run()
