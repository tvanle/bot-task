import hashlib
import hmac
import json
from aiohttp import web
from datetime import datetime
from typing import Optional
import discord

from config import GITHUB_WEBHOOK_SECRET, GITHUB_CHANNEL_ID


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Xác thực webhook signature từ GitHub."""
    if not signature or not secret:
        return True  # Bỏ qua nếu không config secret

    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse ISO date từ GitHub thành format đẹp."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return date_str


def create_issue_embed(data: dict, action: str) -> discord.Embed:
    """Tạo embed cho issue event."""
    issue = data.get("issue", {})
    repo = data.get("repository", {})
    sender = data.get("sender", {})

    # Màu theo action
    colors = {
        "opened": 0x2ecc71,      # Green
        "closed": 0xe74c3c,      # Red
        "reopened": 0xf39c12,    # Orange
        "assigned": 0x3498db,    # Blue
        "unassigned": 0x95a5a6,  # Gray
        "labeled": 0x9b59b6,     # Purple
        "edited": 0xf1c40f,      # Yellow
    }

    # Emoji theo action
    emojis = {
        "opened": "🆕",
        "closed": "✅",
        "reopened": "🔄",
        "assigned": "👤",
        "unassigned": "👋",
        "labeled": "🏷️",
        "edited": "✏️",
    }

    color = colors.get(action, 0x7289da)
    emoji = emojis.get(action, "📋")

    embed = discord.Embed(
        title=f"{emoji} Issue #{issue.get('number')}: {issue.get('title', 'No title')}",
        url=issue.get("html_url"),
        color=color,
    )

    # Repository info
    embed.set_author(
        name=repo.get("full_name", "Unknown Repo"),
        url=repo.get("html_url"),
        icon_url=repo.get("owner", {}).get("avatar_url"),
    )

    # Action info
    embed.add_field(
        name="📌 Action",
        value=f"`{action.upper()}`",
        inline=True,
    )

    # State
    state = issue.get("state", "unknown")
    state_emoji = "🟢" if state == "open" else "🔴"
    embed.add_field(
        name="📊 State",
        value=f"{state_emoji} `{state.upper()}`",
        inline=True,
    )

    # Người thực hiện action
    embed.add_field(
        name="👨‍💻 By",
        value=f"[{sender.get('login', 'Unknown')}]({sender.get('html_url', '')})",
        inline=True,
    )

    # Assignees
    assignees = issue.get("assignees", [])
    if assignees:
        assignee_list = ", ".join(
            [f"[{a.get('login')}]({a.get('html_url')})" for a in assignees]
        )
        embed.add_field(
            name="👤 Assignees",
            value=assignee_list,
            inline=False,
        )

    # Labels
    labels = issue.get("labels", [])
    if labels:
        label_list = ", ".join([f"`{l.get('name')}`" for l in labels])
        embed.add_field(
            name="🏷️ Labels",
            value=label_list,
            inline=False,
        )

    # Milestone (có thể chứa deadline)
    milestone = issue.get("milestone")
    if milestone:
        due_date = parse_date(milestone.get("due_on"))
        milestone_text = f"**{milestone.get('title')}**"
        if due_date:
            milestone_text += f"\n⏰ Due: {due_date}"
        embed.add_field(
            name="🎯 Milestone",
            value=milestone_text,
            inline=True,
        )

    # Body (giới hạn 200 ký tự)
    body = issue.get("body", "")
    if body and action == "opened":
        if len(body) > 200:
            body = body[:200] + "..."
        embed.add_field(
            name="📝 Description",
            value=body,
            inline=False,
        )

    # Timestamps
    created_at = parse_date(issue.get("created_at"))
    if created_at:
        embed.set_footer(text=f"Created: {created_at}")

    return embed


def create_push_embed(data: dict) -> discord.Embed:
    """Tạo embed cho push event."""
    repo = data.get("repository", {})
    pusher = data.get("pusher", {})
    commits = data.get("commits", [])
    ref = data.get("ref", "").replace("refs/heads/", "")

    embed = discord.Embed(
        title=f"🚀 Push to `{ref}`",
        url=data.get("compare"),
        color=0x6e5494,
    )

    embed.set_author(
        name=repo.get("full_name", "Unknown Repo"),
        url=repo.get("html_url"),
        icon_url=repo.get("owner", {}).get("avatar_url"),
    )

    embed.add_field(
        name="👨‍💻 Pusher",
        value=pusher.get("name", "Unknown"),
        inline=True,
    )

    embed.add_field(
        name="📊 Commits",
        value=f"`{len(commits)}` commit(s)",
        inline=True,
    )

    # Hiển thị tối đa 5 commits
    if commits:
        commit_list = []
        for commit in commits[:5]:
            sha = commit.get("id", "")[:7]
            msg = commit.get("message", "").split("\n")[0][:50]
            url = commit.get("url", "")
            commit_list.append(f"[`{sha}`]({url}) {msg}")

        if len(commits) > 5:
            commit_list.append(f"*...và {len(commits) - 5} commits khác*")

        embed.add_field(
            name="📝 Changes",
            value="\n".join(commit_list),
            inline=False,
        )

    return embed


def create_pr_embed(data: dict, action: str) -> discord.Embed:
    """Tạo embed cho pull request event."""
    pr = data.get("pull_request", {})
    repo = data.get("repository", {})
    sender = data.get("sender", {})

    colors = {
        "opened": 0x2ecc71,
        "closed": 0xe74c3c,
        "merged": 0x6f42c1,
        "review_requested": 0x3498db,
    }

    # Check if merged
    if action == "closed" and pr.get("merged"):
        action = "merged"

    color = colors.get(action, 0x7289da)

    emojis = {
        "opened": "🆕",
        "closed": "❌",
        "merged": "🔀",
        "review_requested": "👀",
    }
    emoji = emojis.get(action, "📋")

    embed = discord.Embed(
        title=f"{emoji} PR #{pr.get('number')}: {pr.get('title', 'No title')}",
        url=pr.get("html_url"),
        color=color,
    )

    embed.set_author(
        name=repo.get("full_name", "Unknown Repo"),
        url=repo.get("html_url"),
        icon_url=repo.get("owner", {}).get("avatar_url"),
    )

    embed.add_field(
        name="📌 Action",
        value=f"`{action.upper()}`",
        inline=True,
    )

    embed.add_field(
        name="👨‍💻 Author",
        value=f"[{sender.get('login', 'Unknown')}]({sender.get('html_url', '')})",
        inline=True,
    )

    embed.add_field(
        name="🔀 Branch",
        value=f"`{pr.get('head', {}).get('ref')}` → `{pr.get('base', {}).get('ref')}`",
        inline=True,
    )

    # Reviewers
    reviewers = pr.get("requested_reviewers", [])
    if reviewers:
        reviewer_list = ", ".join(
            [f"[{r.get('login')}]({r.get('html_url')})" for r in reviewers]
        )
        embed.add_field(
            name="👀 Reviewers",
            value=reviewer_list,
            inline=False,
        )

    # Assignees
    assignees = pr.get("assignees", [])
    if assignees:
        assignee_list = ", ".join(
            [f"[{a.get('login')}]({a.get('html_url')})" for a in assignees]
        )
        embed.add_field(
            name="👤 Assignees",
            value=assignee_list,
            inline=False,
        )

    return embed


class GitHubWebhookHandler:
    """Handler cho GitHub webhooks."""

    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.app.router.add_post("/webhook/github", self.handle_webhook)
        self.app.router.add_get("/health", self.health_check)
        self.runner = None

    async def start(self, host: str = "0.0.0.0", port: int = 8080):
        """Start webhook server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host, port)
        await site.start()
        print(f"GitHub Webhook server started on http://{host}:{port}")

    async def stop(self):
        """Stop webhook server."""
        if self.runner:
            await self.runner.cleanup()

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok", "bot": str(self.bot.user)})

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Xử lý webhook từ GitHub."""
        try:
            # Đọc payload
            payload = await request.read()

            # Verify signature
            signature = request.headers.get("X-Hub-Signature-256", "")
            if GITHUB_WEBHOOK_SECRET and not verify_signature(payload, signature, GITHUB_WEBHOOK_SECRET):
                return web.Response(status=401, text="Invalid signature")

            # Parse JSON
            data = json.loads(payload)
            event = request.headers.get("X-GitHub-Event", "")

            # Lấy channel để gửi thông báo
            channel = self.bot.get_channel(GITHUB_CHANNEL_ID)
            if not channel:
                print(f"Channel {GITHUB_CHANNEL_ID} not found!")
                return web.json_response({"status": "error", "message": "Channel not found"})

            # Xử lý theo loại event
            embed = None
            mention = None

            if event == "issues":
                action = data.get("action", "")
                embed = create_issue_embed(data, action)

                # Mention assignees khi được assign
                if action == "assigned":
                    assignee = data.get("assignee", {})
                    # Tìm Discord user theo GitHub username (nếu có mapping)
                    mention = f"🔔 **{assignee.get('login')}** đã được assign issue này!"

            elif event == "push":
                embed = create_push_embed(data)

            elif event == "pull_request":
                action = data.get("action", "")
                embed = create_pr_embed(data, action)

                if action == "review_requested":
                    reviewers = data.get("pull_request", {}).get("requested_reviewers", [])
                    if reviewers:
                        names = ", ".join([f"**{r.get('login')}**" for r in reviewers])
                        mention = f"👀 {names} được yêu cầu review PR này!"

            elif event == "ping":
                # GitHub gửi ping khi setup webhook
                return web.json_response({
                    "status": "ok",
                    "message": "Pong! Webhook connected successfully."
                })

            # Gửi embed nếu có
            if embed:
                content = mention if mention else None
                await channel.send(content=content, embed=embed)

            return web.json_response({"status": "ok"})

        except Exception as e:
            print(f"Webhook error: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)
