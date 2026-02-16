import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
NOTIFICATION_CHANNEL_ID = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))

# GitHub Webhook Configuration
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITHUB_CHANNEL_ID = int(os.getenv("GITHUB_CHANNEL_ID", "0")) or NOTIFICATION_CHANNEL_ID
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

# Reminder Configuration
REMINDER_MINUTES_BEFORE = int(os.getenv("REMINDER_MINUTES_BEFORE", "60"))

# Database
DATABASE_PATH = "tasks.db"

# Penalty Configuration (đơn vị: nghìn đồng)
BASE_PENALTY = 20       # Phạt ngày đầu tiên: 20k
PENALTY_INCREMENT = 10  # Mỗi ngày sau tăng thêm: 10k

# Task Status
class TaskStatus:
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    LATE = "LATE"

# Status Colors for Embeds
STATUS_COLORS = {
    TaskStatus.TODO: 0x3498db,        # Blue
    TaskStatus.IN_PROGRESS: 0xf39c12,  # Orange/Yellow
    TaskStatus.DONE: 0x2ecc71,         # Green
    TaskStatus.CANCELLED: 0x95a5a6,    # Gray
    TaskStatus.LATE: 0xe74c3c,         # Red
}

# Status Emojis
STATUS_EMOJIS = {
    TaskStatus.TODO: "📋",
    TaskStatus.IN_PROGRESS: "🔄",
    TaskStatus.DONE: "✅",
    TaskStatus.CANCELLED: "❌",
    TaskStatus.LATE: "⚠️",
}
