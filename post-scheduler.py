"""
Jack and Blaze — Post Scheduler
Reads Slack for APPROVE/EDIT/REJECT replies, then calls Late API to schedule approved posts.

Two modes:
  python post-scheduler.py          — check approvals and schedule now
  python post-scheduler.py --force  — schedule all platforms (bypass approval check)

Triggered by:
  - auto-approver.yml (GitHub Actions, 6hrs after drafts sent)
  - Manually after Leslie replies in Slack
"""

import os, sys, json, re, requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LATE_API_KEY      = os.getenv("LATE_API_KEY", "sk_b94e7f028b4e06dea4c711ec397cc5ccbceb48006fa70bacca032e93cd643652")
SLACK_BOT_TOKEN   = os.getenv("SLACK_BOT_TOKEN", "xoxb-10698702847203-10810832598101-jVnvzawUDXHORUvmYiReUYuA")
SLACK_CHANNEL_ID  = os.getenv("SLACK_CHANNEL_ID", "C0ALP0Y1HK8")
FAST_IO_API_KEY   = os.getenv("FAST_IO_API_KEY", "xls09zxz4p56dzdsfozp4q12lm82v5ddoq47il2dbv44i78x7g")
FAST_IO_WORKSPACE = "4727745319403567135"
FAST_IO_FOLDER    = "23ont-mmmer-vypjf-sqxbl-36mpj-curk"

DATE = datetime.now().strftime("%Y-%m-%d")
FORCE = "--force" in sys.argv

# Platform → Late API account mapping
ACCOUNTS = {
    "instagram": "leswalters_",
    "tiktok":    "leswalters_",
    "facebook":  "leswalters_",
    "twitter":   "elmo086",
    "youtube":   "lesliew.e.walters",
}

# Optimal posting times (days from now, hour in 24hr CDT)
# Monday = 0, tuesday = 1, etc. from today
SCHEDULE = {
    "twitter":   {"days_offset": 0, "hour": 9,  "minute": 0},   # Monday 9am
    "instagram": {"days_offset": 1, "hour": 19, "minute": 0},   # Tuesday 7pm
    "tiktok":    {"days_offset": 1, "hour": 20, "minute": 0},   # Tuesday 8pm
    "facebook":  {"days_offset": 2, "hour": 14, "minute": 0},   # Wednesday 2pm
    "youtube":   {"days_offset": 3, "hour": 13, "minute": 0},   # Thursday 1pm
}


# ── Read Slack for Approvals ───────────────────────────────────────────────────

def read_slack_approvals() -> dict:
    """
    Reads Slack channel history (last 48hrs) and determines approval status
    for each platform. Returns dict: {platform: 'approved'|'rejected'|'edited'|'pending'}
    """
    oldest = str((datetime.now() - timedelta(hours=48)).timestamp())
    try:
        r = requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            params={"channel": SLACK_CHANNEL_ID, "oldest": oldest, "limit": 100},
            timeout=15
        )
        if not r.json().get("ok"):
            print(f"Slack error: {r.json().get('error')}")
            return {}
        messages = [m.get("text", "") for m in r.json().get("messages", [])]
        combined = "\n".join(messages).upper()
    except Exception as e:
        print(f"Slack read error: {e}")
        return {}

    # Check what Leslie replied
    platforms = ["instagram", "tiktok", "facebook", "twitter", "youtube"]
    approvals = {}

    # Check for blanket approval
    blanket_approved = any(w in combined for w in [
        "APPROVED ALL", "APPROVE ALL", "ALL APPROVED",
        "EVERYTHING APPROVED", "ALL GOOD", "APPROVE"
    ])

    for platform in platforms:
        if FORCE or blanket_approved:
            approvals[platform] = "approved"
        elif f"REJECT {platform.upper()}" in combined or f"REJECT\n" in combined:
            approvals[platform] = "rejected"
        elif f"EDIT" in combined and platform.upper() in combined:
            approvals[platform] = "edited"
        else:
            approvals[platform] = "pending"

    # Check draft-send-log to see if 6hr window has passed
    send_log = Path("draft-send-log.md")
    if send_log.exists() and not FORCE:
        content = send_log.read_text()
        # Find ISO timestamp
        match = re.search(r"Auto-approval deadline.*?(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)", content)
        if match:
            try:
                deadline = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
                now_utc = datetime.now().astimezone()
                if now_utc >= deadline:
                    # 6 hour window passed — auto-approve pending platforms
                    for platform in platforms:
                        if approvals[platform] == "pending":
                            approvals[platform] = "approved (auto 6hr)"
                            print(f"Auto-approving {platform} (6hr window expired)")
            except Exception as e:
                print(f"Deadline parse error: {e}")

    return approvals


# ── Read Weekly Drafts ─────────────────────────────────────────────────────────

def read_draft_content() -> dict:
    """Extract content for each platform from weekly-drafts.md"""
    # Try weekly drafts first, then friday author drafts
    for draft_file in ["weekly-drafts.md", f"weekly-drafts-{DATE}.md"]:
        if Path(draft_file).exists():
            content = Path(draft_file).read_text()
            break
    else:
        print("No draft file found. Run content-generator first.")
        return {}

    drafts = {}
    platforms = {
        "instagram": "INSTAGRAM",
        "tiktok": "TIKTOK",
        "facebook": "FACEBOOK",
        "twitter": "TWITTER/X",
        "youtube": "YOUTUBE"
    }

    for key, header in platforms.items():
        # Extract caption/post content
        match = re.search(
            rf"### {header}.*?(?:\*\*Caption:\*\*|\*\*Post:\*\*|\*\*Tweet:\*\*|Caption:|Post:)\s*(.+?)(?=\n\n|\*\*Image|\*\*Video|\*\*Tags|###|\Z)",
            content, re.DOTALL | re.IGNORECASE
        )
        if match:
            text = match.group(1).strip()
            # Remove markdown bold markers
            text = re.sub(r'\*\*', '', text)
            drafts[key] = text[:2000]
        else:
            # Fallback: grab everything under the platform header
            section = re.search(
                rf"### {header}(.*?)(?=###|\Z)",
                content, re.DOTALL | re.IGNORECASE
            )
            if section:
                drafts[key] = section.group(1).strip()[:2000]

    return drafts


# ── Call Late API ──────────────────────────────────────────────────────────────

def schedule_post(platform: str, content: str) -> dict:
    """Schedule a post via Late API"""
    # Calculate scheduled time
    sched = SCHEDULE.get(platform, {"days_offset": 1, "hour": 12, "minute": 0})
    post_time = datetime.now() + timedelta(days=sched["days_offset"])
    post_time = post_time.replace(hour=sched["hour"], minute=sched["minute"], second=0, microsecond=0)
    # Convert CDT (UTC-5) to UTC
    post_time_utc = post_time + timedelta(hours=5)
    scheduled_iso = post_time_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    payload = {
        "platform": platform if platform != "twitter" else "twitter",
        "account_id": ACCOUNTS[platform],
        "content": content,
        "scheduled_time": scheduled_iso
    }

    try:
        r = requests.post(
            "https://api.late.com/v1/posts",
            headers={
                "Authorization": f"Bearer {LATE_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        result = r.json()
        if r.ok:
            print(f"  Scheduled {platform} for {post_time.strftime('%a %b %d %I:%M%p CDT')}")
        else:
            print(f"  Late API error ({platform}): {r.status_code} — {r.text[:150]}")
        return {"platform": platform, "status": "scheduled" if r.ok else "failed",
                "scheduled_time": post_time.strftime("%a %b %d %I:%M%p CDT"),
                "response": r.status_code}
    except Exception as e:
        print(f"  Late API exception ({platform}): {e}")
        return {"platform": platform, "status": "error", "error": str(e)}


# ── Save Publish Log ───────────────────────────────────────────────────────────

def save_publish_log(results: list, approvals: dict):
    lines = [f"# Publish Log — {DATE}\n"]
    for r in results:
        platform = r["platform"]
        lines.append(f"## {platform.title()}")
        lines.append(f"- Approval: {approvals.get(platform, 'unknown')}")
        lines.append(f"- Status: {r.get('status', 'unknown')}")
        lines.append(f"- Scheduled: {r.get('scheduled_time', '—')}")
        lines.append(f"- API response: {r.get('response', '—')}")
        lines.append("")

    skipped = [p for p, s in approvals.items() if s in ("rejected", "edited", "pending")]
    published = [r for r in results if r.get("status") == "scheduled"]
    lines.append(f"## Summary\n{len(published)}/5 platforms scheduled.")
    if skipped:
        lines.append(f"Skipped: {', '.join(skipped)}")

    log_path = f"publish-log-{DATE}.md"
    Path(log_path).write_text("\n".join(lines))
    print(f"Publish log saved: {log_path}")

    # Upload to fast.io
    try:
        requests.post(
            "https://api.fast.io/v1/upload/text-file",
            headers={"Authorization": f"Bearer {FAST_IO_API_KEY}", "Content-Type": "application/json"},
            json={"profile_type": "workspace", "profile_id": FAST_IO_WORKSPACE,
                  "parent_node_id": FAST_IO_FOLDER, "filename": log_path,
                  "content": "\n".join(lines)},
            timeout=30
        )
        print(f"Publish log uploaded to fast.io")
    except Exception as e:
        print(f"fast.io upload error: {e}")


# ── Post Slack Summary ─────────────────────────────────────────────────────────

def post_slack_summary(results: list, approvals: dict):
    published = [r for r in results if r.get("status") == "scheduled"]
    failed = [r for r in results if r.get("status") == "failed"]
    skipped = [p for p, s in approvals.items() if s in ("rejected", "edited")]

    lines = [f"*Posts Scheduled — {DATE}* ✅\n"]
    for r in published:
        lines.append(f"✅ {r['platform'].title()} — {r.get('scheduled_time', '')}")
    for p in skipped:
        lines.append(f"⏭️ {p.title()} — {approvals[p]}")
    for r in failed:
        lines.append(f"❌ {r['platform'].title()} — API error (check publish-log-{DATE}.md)")

    lines.append(f"\n{len(published)}/5 platforms scheduled via Late API.")

    try:
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": SLACK_CHANNEL_ID, "text": "\n".join(lines)},
            timeout=15
        )
    except Exception as e:
        print(f"Slack summary error: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    print(f"=== Jack and Blaze Post Scheduler — {DATE} ===")
    print(f"Mode: {'FORCE (all platforms)' if FORCE else 'Approval check'}\n")

    # 1. Read approvals from Slack
    print("Reading Slack approvals...")
    approvals = read_slack_approvals()
    if not approvals:
        print("Could not read approvals. Check SLACK_BOT_TOKEN.")
        return

    print("Approval status:")
    for p, s in approvals.items():
        print(f"  {p}: {s}")

    # 2. Read draft content
    print("\nReading draft content...")
    drafts = read_draft_content()
    if not drafts:
        print("No drafts found. Cannot schedule.")
        return

    # 3. Schedule approved platforms
    print("\nScheduling via Late API...")
    results = []
    for platform, status in approvals.items():
        if "approved" in status.lower():
            content = drafts.get(platform, "")
            if content:
                result = schedule_post(platform, content)
                results.append(result)
            else:
                print(f"  No content found for {platform}")
                results.append({"platform": platform, "status": "no_content"})
        else:
            print(f"  Skipping {platform} ({status})")

    # 4. Save log + Slack summary
    save_publish_log(results, approvals)
    post_slack_summary(results, approvals)

    scheduled = sum(1 for r in results if r.get("status") == "scheduled")
    print(f"\n=== Done — {scheduled}/5 platforms scheduled ===")


if __name__ == "__main__":
    run()
