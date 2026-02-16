import discord
from discord import ui
from config import TaskStatus, STATUS_COLORS, STATUS_EMOJIS
from datetime import datetime
import database
from database import calculate_penalty


def format_datetime(dt_str: str) -> str:
    """Format datetime string để hiển thị đẹp hơn."""
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%d/%m/%Y %H:%M")


def create_task_embed(task: dict) -> discord.Embed:
    """Tạo Embed hiển thị thông tin task."""
    status = task["status"]
    color = STATUS_COLORS.get(status, 0x3498db)
    emoji = STATUS_EMOJIS.get(status, "📋")

    embed = discord.Embed(
        title=f"{emoji} Task #{task['id']}: {task['description'][:50]}",
        description=task["description"] if len(task["description"]) > 50 else None,
        color=color,
    )

    embed.add_field(
        name="👤 Người thực hiện",
        value=f"<@{task['assignee_id']}>",
        inline=True,
    )
    embed.add_field(
        name="📋 Trạng thái",
        value=f"`{status}`",
        inline=True,
    )
    embed.add_field(
        name="👨‍💼 Người giao",
        value=f"<@{task['assigner_id']}>",
        inline=True,
    )
    embed.add_field(
        name="📅 Ngày bắt đầu",
        value=format_datetime(task["start_date"]),
        inline=True,
    )
    embed.add_field(
        name="⏰ Deadline",
        value=format_datetime(task["end_date"]),
        inline=True,
    )

    # Tính thời gian còn lại
    end_date = datetime.fromisoformat(task["end_date"])
    now = datetime.now()
    if status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
        if now > end_date:
            time_diff = now - end_date
            hours = int(time_diff.total_seconds() // 3600)
            embed.add_field(
                name="⚠️ Quá hạn",
                value=f"**{hours} giờ**",
                inline=True,
            )
        else:
            time_diff = end_date - now
            hours = int(time_diff.total_seconds() // 3600)
            days = hours // 24
            remaining_hours = hours % 24
            if days > 0:
                time_str = f"{days} ngày {remaining_hours} giờ"
            else:
                time_str = f"{hours} giờ"
            embed.add_field(
                name="⏳ Còn lại",
                value=time_str,
                inline=True,
            )

    # Hiển thị tiền phạt
    if task.get("excused"):
        embed.add_field(
            name="💰 Tiền phạt",
            value="~~Đã miễn phạt~~",
            inline=True,
        )
    elif status == TaskStatus.LATE:
        days_late, penalty = calculate_penalty(task["end_date"])
        embed.add_field(
            name="💰 Tiền phạt (đang tính)",
            value=f"**{days_late}** ngày trễ → **{penalty}k**",
            inline=True,
        )
    elif status == TaskStatus.DONE and task.get("completed_at"):
        end_date = datetime.fromisoformat(task["end_date"])
        completed_at = datetime.fromisoformat(task["completed_at"])
        if completed_at > end_date:
            days_late, penalty = calculate_penalty(task["end_date"], task["completed_at"])
            embed.add_field(
                name="💰 Tiền phạt (đã khóa)",
                value=f"**{days_late}** ngày trễ → **{penalty}k**",
                inline=True,
            )

    embed.set_footer(text=f"Cập nhật: {format_datetime(task['updated_at'])}")

    return embed


def create_task_list_embed(tasks: list, title: str, user: discord.User = None) -> list[discord.Embed]:
    """Tạo danh sách Embeds hiển thị các tasks theo nhóm status."""
    if not tasks:
        embed = discord.Embed(
            title=title,
            description="Không có task nào.",
            color=0x95a5a6,
        )
        if user:
            embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        return [embed]

    # Gom nhóm tasks theo status
    grouped = {}
    for task in tasks:
        status = task["status"]
        if status not in grouped:
            grouped[status] = []
        grouped[status].append(task)

    embeds = []

    # Header embed
    header_embed = discord.Embed(
        title=title,
        description=f"Tổng cộng: **{len(tasks)}** tasks",
        color=0x3498db,
    )
    if user:
        header_embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embeds.append(header_embed)

    # Status order
    status_order = [
        TaskStatus.LATE,
        TaskStatus.IN_PROGRESS,
        TaskStatus.TODO,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    ]

    for status in status_order:
        if status not in grouped:
            continue

        status_tasks = grouped[status]
        emoji = STATUS_EMOJIS.get(status, "📋")
        color = STATUS_COLORS.get(status, 0x3498db)

        embed = discord.Embed(
            title=f"{emoji} {status} ({len(status_tasks)})",
            color=color,
        )

        for task in status_tasks[:10]:  # Giới hạn 10 tasks mỗi status
            deadline = format_datetime(task["end_date"])
            embed.add_field(
                name=f"#{task['id']}: {task['description'][:30]}{'...' if len(task['description']) > 30 else ''}",
                value=f"👤 <@{task['assignee_id']}> | ⏰ {deadline}",
                inline=False,
            )

        if len(status_tasks) > 10:
            embed.set_footer(text=f"Và {len(status_tasks) - 10} tasks khác...")

        embeds.append(embed)

    return embeds


def create_penalty_embed(user: discord.User, tasks: list) -> discord.Embed:
    """Tạo embed hiển thị chi tiết phạt cho 1 user."""
    if not tasks:
        embed = discord.Embed(
            title=f"💰 Tiền phạt của {user.display_name}",
            description="Không có task trễ hạn nào!",
            color=0x2ecc71,
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        return embed

    total_penalty = 0
    description_lines = []

    for task in tasks:
        completed_at_str = task.get("completed_at")
        days_late, penalty = calculate_penalty(task["end_date"], completed_at_str)
        total_penalty += penalty

        status_label = "đã khóa" if task["status"] == TaskStatus.DONE else "đang tính"
        description_lines.append(
            f"**#{task['id']}**: {task['description'][:40]}\n"
            f"  ⏰ {days_late} ngày trễ → **{penalty}k** ({status_label})"
        )

    embed = discord.Embed(
        title=f"💰 Tiền phạt của {user.display_name}",
        description="\n\n".join(description_lines),
        color=0xe74c3c,
    )
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.add_field(
        name="💵 TỔNG PHẠT",
        value=f"**{total_penalty}k** ({total_penalty * 1000:,}đ)",
        inline=False,
    )
    return embed


def create_penalties_board_embed(penalty_data: list) -> discord.Embed:
    """Tạo embed bảng xếp hạng phạt team.

    penalty_data: list of (user_id, user_name, total_penalty, task_count)
    """
    if not penalty_data:
        return discord.Embed(
            title="💰 Bảng Xếp Hạng Phạt Team",
            description="Không có ai bị phạt! Team làm việc tốt lắm!",
            color=0x2ecc71,
        )

    description_lines = []
    medals = ["🥇", "🥈", "🥉"]

    for i, (user_id, user_name, total_penalty, task_count) in enumerate(penalty_data):
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        description_lines.append(
            f"{medal} <@{user_id}> — **{total_penalty}k** ({total_penalty * 1000:,}đ) | {task_count} task trễ"
        )

    embed = discord.Embed(
        title="💰 Bảng Xếp Hạng Phạt Team",
        description="\n".join(description_lines),
        color=0xe74c3c,
    )
    embed.set_footer(text="Công thức: Ngày 1 = 20k, mỗi ngày sau +10k | Tổng N ngày = 5N² + 15N (nghìn đồng)")
    return embed


class TaskStatusSelect(ui.Select):
    """Dropdown menu để chọn trạng thái task."""

    def __init__(self, task_id: int, current_status: str):
        self.task_id = task_id

        options = [
            discord.SelectOption(
                label="TODO",
                value=TaskStatus.TODO,
                emoji="📋",
                default=(current_status == TaskStatus.TODO),
                description="Chưa bắt đầu",
            ),
            discord.SelectOption(
                label="IN PROGRESS",
                value=TaskStatus.IN_PROGRESS,
                emoji="🔄",
                default=(current_status == TaskStatus.IN_PROGRESS),
                description="Đang thực hiện",
            ),
            discord.SelectOption(
                label="DONE",
                value=TaskStatus.DONE,
                emoji="✅",
                default=(current_status == TaskStatus.DONE),
                description="Hoàn thành",
            ),
            discord.SelectOption(
                label="CANCELLED",
                value=TaskStatus.CANCELLED,
                emoji="❌",
                default=(current_status == TaskStatus.CANCELLED),
                description="Đã hủy",
            ),
        ]

        super().__init__(
            placeholder="Chọn trạng thái mới...",
            options=options,
            custom_id=f"status_select_{task_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        new_status = self.values[0]
        task = await database.get_task_by_id(self.task_id)

        if not task:
            await interaction.response.send_message(
                "Task không tồn tại!", ephemeral=True
            )
            return

        # Kiểm tra quyền: chỉ người được giao hoặc người giao mới được cập nhật
        if interaction.user.id not in [task["assignee_id"], task["assigner_id"]]:
            await interaction.response.send_message(
                "Bạn không có quyền cập nhật task này!", ephemeral=True
            )
            return

        await database.update_task_status(self.task_id, new_status)

        # Ghi nhận thời điểm hoàn thành nếu chuyển sang DONE
        if new_status == TaskStatus.DONE:
            await database.mark_task_completed(self.task_id)

        updated_task = await database.get_task_by_id(self.task_id)

        # Cập nhật embed
        new_embed = create_task_embed(updated_task)
        new_view = TaskActionView(self.task_id, new_status)

        await interaction.response.edit_message(embed=new_embed, view=new_view)

        # Thông báo cập nhật
        emoji = STATUS_EMOJIS.get(new_status, "📋")
        await interaction.followup.send(
            f"{emoji} Task #{self.task_id} đã được cập nhật thành **{new_status}** bởi {interaction.user.mention}",
            ephemeral=False,
        )


class TaskActionView(ui.View):
    """View chứa các buttons và dropdown để thao tác với task."""

    def __init__(self, task_id: int, current_status: str):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.current_status = current_status

        # Thêm dropdown
        self.add_item(TaskStatusSelect(task_id, current_status))

    @ui.button(label="Start", style=discord.ButtonStyle.primary, emoji="▶️", row=1)
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_status(interaction, TaskStatus.IN_PROGRESS)

    @ui.button(label="Complete", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def complete_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_status(interaction, TaskStatus.DONE)

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._update_status(interaction, TaskStatus.CANCELLED)

    async def _update_status(self, interaction: discord.Interaction, new_status: str):
        task = await database.get_task_by_id(self.task_id)

        if not task:
            await interaction.response.send_message(
                "Task không tồn tại!", ephemeral=True
            )
            return

        # Kiểm tra quyền
        if interaction.user.id not in [task["assignee_id"], task["assigner_id"]]:
            await interaction.response.send_message(
                "Bạn không có quyền cập nhật task này!", ephemeral=True
            )
            return

        await database.update_task_status(self.task_id, new_status)

        # Ghi nhận thời điểm hoàn thành nếu chuyển sang DONE
        if new_status == TaskStatus.DONE:
            await database.mark_task_completed(self.task_id)

        updated_task = await database.get_task_by_id(self.task_id)

        # Cập nhật embed
        new_embed = create_task_embed(updated_task)
        new_view = TaskActionView(self.task_id, new_status)

        await interaction.response.edit_message(embed=new_embed, view=new_view)

        # Thông báo
        emoji = STATUS_EMOJIS.get(new_status, "📋")
        await interaction.followup.send(
            f"{emoji} Task #{self.task_id} đã được cập nhật thành **{new_status}** bởi {interaction.user.mention}",
            ephemeral=False,
        )


class TaskListView(ui.View):
    """View cho danh sách tasks với pagination."""

    def __init__(self, tasks: list, page: int = 0, per_page: int = 5):
        super().__init__(timeout=180)
        self.tasks = tasks
        self.page = page
        self.per_page = per_page
        self.total_pages = (len(tasks) - 1) // per_page + 1 if tasks else 1

        # Disable buttons nếu cần
        self.previous_page.disabled = page == 0
        self.next_page.disabled = page >= self.total_pages - 1

    def get_current_page_tasks(self) -> list:
        start = self.page * self.per_page
        end = start + self.per_page
        return self.tasks[start:end]

    @ui.button(label="◀️ Trước", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        self.page -= 1
        self.previous_page.disabled = self.page == 0
        self.next_page.disabled = False
        await self._update_message(interaction)

    @ui.button(label="Sau ▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        self.page += 1
        self.next_page.disabled = self.page >= self.total_pages - 1
        self.previous_page.disabled = False
        await self._update_message(interaction)

    async def _update_message(self, interaction: discord.Interaction):
        # Tạo embed mới cho trang hiện tại
        current_tasks = self.get_current_page_tasks()

        embed = discord.Embed(
            title=f"📋 Danh sách Tasks (Trang {self.page + 1}/{self.total_pages})",
            color=0x3498db,
        )

        for task in current_tasks:
            status = task["status"]
            emoji = STATUS_EMOJIS.get(status, "📋")
            deadline = format_datetime(task["end_date"])

            embed.add_field(
                name=f"{emoji} #{task['id']}: {task['description'][:40]}{'...' if len(task['description']) > 40 else ''}",
                value=f"👤 <@{task['assignee_id']}> | 📋 `{status}` | ⏰ {deadline}",
                inline=False,
            )

        await interaction.response.edit_message(embed=embed, view=self)
