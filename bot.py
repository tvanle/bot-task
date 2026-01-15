import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

import database
from config import (
    DISCORD_TOKEN,
    NOTIFICATION_CHANNEL_ID,
    REMINDER_MINUTES_BEFORE,
    TaskStatus,
    STATUS_EMOJIS,
)
from views import (
    create_task_embed,
    create_task_list_embed,
    TaskActionView,
    TaskListView,
)


class TaskBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        """Được gọi khi bot khởi động."""
        await database.init_db()
        print("Database initialized!")

        # Sync slash commands
        await self.tree.sync()
        print("Slash commands synced!")

        # Start background task
        self.reminder_task.start()
        print("Reminder task started!")

    async def on_ready(self):
        print(f"Bot is ready! Logged in as {self.user}")
        print(f"Connected to {len(self.guilds)} guild(s)")

        # Set activity
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="your tasks | /assign"
            )
        )

    @tasks.loop(minutes=5)
    async def reminder_task(self):
        """Background task kiểm tra deadline và gửi nhắc nhở."""
        try:
            # Lấy channel thông báo
            channel = self.get_channel(NOTIFICATION_CHANNEL_ID)
            if not channel:
                return

            now = datetime.now()
            reminder_threshold = now + timedelta(minutes=REMINDER_MINUTES_BEFORE)

            # Kiểm tra tasks sắp hết hạn
            pending_tasks = await database.get_pending_tasks_near_deadline(
                REMINDER_MINUTES_BEFORE
            )

            for task in pending_tasks:
                end_date = datetime.fromisoformat(task["end_date"])

                # Nếu sắp hết hạn (trong khoảng reminder)
                if now < end_date <= reminder_threshold:
                    time_remaining = end_date - now
                    minutes_remaining = int(time_remaining.total_seconds() // 60)

                    if minutes_remaining <= REMINDER_MINUTES_BEFORE:
                        await channel.send(
                            f"⚠️ <@{task['assignee_id']}> ơi, task **#{task['id']}: {task['description'][:50]}** "
                            f"sắp hết hạn trong **{minutes_remaining} phút** nữa!"
                        )
                        await database.mark_reminder_sent(task["id"])

            # Kiểm tra tasks quá hạn
            overdue_tasks = await database.get_overdue_tasks()

            for task in overdue_tasks:
                if task["status"] != TaskStatus.LATE:
                    # Cập nhật status thành LATE
                    await database.update_task_status(task["id"], TaskStatus.LATE)

                    # Gửi cảnh báo
                    await channel.send(
                        f"🚨 **CẢNH BÁO!** Task **#{task['id']}: {task['description'][:50]}** "
                        f"đã **QUÁ HẠN**!\n"
                        f"👤 Người thực hiện: <@{task['assignee_id']}>\n"
                        f"👨‍💼 Người giao: <@{task['assigner_id']}>"
                    )

                    # Cập nhật message gốc nếu có
                    if task["message_id"] and task["channel_id"]:
                        try:
                            msg_channel = self.get_channel(task["channel_id"])
                            if msg_channel:
                                message = await msg_channel.fetch_message(
                                    task["message_id"]
                                )
                                updated_task = await database.get_task_by_id(task["id"])
                                embed = create_task_embed(updated_task)
                                view = TaskActionView(task["id"], TaskStatus.LATE)
                                await message.edit(embed=embed, view=view)
                        except discord.NotFound:
                            pass

        except Exception as e:
            print(f"Error in reminder task: {e}")

    @reminder_task.before_loop
    async def before_reminder_task(self):
        await self.wait_until_ready()


bot = TaskBot()


# ==================== SLASH COMMANDS ====================


@bot.tree.command(name="assign", description="Giao việc cho một thành viên")
@app_commands.describe(
    user="Người được giao việc",
    description="Mô tả công việc",
    start_date="Ngày bắt đầu (DD/MM/YYYY hoặc DD/MM/YYYY HH:MM)",
    end_date="Deadline (DD/MM/YYYY hoặc DD/MM/YYYY HH:MM)",
)
async def assign_task(
    interaction: discord.Interaction,
    user: discord.Member,
    description: str,
    start_date: str,
    end_date: str,
):
    """Lệnh giao việc cho một thành viên."""
    # Parse dates
    try:
        # Hỗ trợ cả 2 format
        for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%Y"]:
            try:
                start_dt = datetime.strptime(start_date, fmt)
                if fmt == "%d/%m/%Y":
                    start_dt = start_dt.replace(hour=9, minute=0)
                break
            except ValueError:
                continue
        else:
            raise ValueError("Invalid start_date format")

        for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%Y"]:
            try:
                end_dt = datetime.strptime(end_date, fmt)
                if fmt == "%d/%m/%Y":
                    end_dt = end_dt.replace(hour=18, minute=0)
                break
            except ValueError:
                continue
        else:
            raise ValueError("Invalid end_date format")

    except ValueError:
        await interaction.response.send_message(
            "❌ Định dạng ngày không hợp lệ! Vui lòng dùng format: `DD/MM/YYYY` hoặc `DD/MM/YYYY HH:MM`",
            ephemeral=True,
        )
        return

    # Validate dates
    if start_dt > end_dt:
        await interaction.response.send_message(
            "❌ Ngày bắt đầu không thể sau ngày kết thúc!", ephemeral=True
        )
        return

    # Tạo task trong database
    task_id = await database.create_task(
        description=description,
        assignee_id=user.id,
        assignee_name=user.display_name,
        assigner_id=interaction.user.id,
        assigner_name=interaction.user.display_name,
        start_date=start_dt,
        end_date=end_dt,
    )

    # Lấy task vừa tạo
    task = await database.get_task_by_id(task_id)

    # Tạo embed và view
    embed = create_task_embed(task)
    view = TaskActionView(task_id, TaskStatus.TODO)

    # Gửi tin nhắn
    await interaction.response.send_message(
        content=f"🆕 **Task mới được giao!**\n👤 Người làm: {user.mention}\n📅 Deadline: {end_date}",
        embed=embed,
        view=view,
    )

    # Lưu message_id để cập nhật sau
    message = await interaction.original_response()
    await database.update_task_message(task_id, message.id, interaction.channel_id)


@bot.tree.command(name="mytasks", description="Xem danh sách task của bạn")
async def my_tasks(interaction: discord.Interaction):
    """Xem danh sách tasks của bản thân."""
    tasks = await database.get_tasks_by_user(interaction.user.id)

    embeds = create_task_list_embed(
        tasks, f"📋 Tasks của {interaction.user.display_name}", interaction.user
    )

    if len(tasks) > 5:
        view = TaskListView(tasks)
        await interaction.response.send_message(embeds=embeds[:2], view=view)
    else:
        await interaction.response.send_message(embeds=embeds)


@bot.tree.command(name="alltasks", description="Xem tất cả task của team")
async def all_tasks(interaction: discord.Interaction):
    """Xem tất cả tasks trong server."""
    tasks = await database.get_all_tasks()

    embeds = create_task_list_embed(tasks, "📋 Tất cả Tasks của Team")

    if len(tasks) > 5:
        view = TaskListView(tasks)
        await interaction.response.send_message(embeds=embeds[:2], view=view)
    else:
        await interaction.response.send_message(embeds=embeds)


@bot.tree.command(name="task", description="Xem chi tiết một task")
@app_commands.describe(task_id="ID của task cần xem")
async def view_task(interaction: discord.Interaction, task_id: int):
    """Xem chi tiết một task cụ thể."""
    task = await database.get_task_by_id(task_id)

    if not task:
        await interaction.response.send_message(
            f"❌ Không tìm thấy task với ID #{task_id}", ephemeral=True
        )
        return

    embed = create_task_embed(task)
    view = TaskActionView(task_id, task["status"])

    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="deletetask", description="Xóa một task")
@app_commands.describe(task_id="ID của task cần xóa")
async def delete_task(interaction: discord.Interaction, task_id: int):
    """Xóa một task (chỉ người giao mới có quyền)."""
    task = await database.get_task_by_id(task_id)

    if not task:
        await interaction.response.send_message(
            f"❌ Không tìm thấy task với ID #{task_id}", ephemeral=True
        )
        return

    # Kiểm tra quyền: chỉ người giao hoặc admin mới được xóa
    if (
        interaction.user.id != task["assigner_id"]
        and not interaction.user.guild_permissions.administrator
    ):
        await interaction.response.send_message(
            "❌ Bạn không có quyền xóa task này! Chỉ người giao việc hoặc Admin mới có thể xóa.",
            ephemeral=True,
        )
        return

    success = await database.delete_task(task_id)

    if success:
        await interaction.response.send_message(
            f"✅ Đã xóa task **#{task_id}: {task['description'][:50]}**"
        )
    else:
        await interaction.response.send_message(
            "❌ Có lỗi xảy ra khi xóa task!", ephemeral=True
        )


@bot.tree.command(name="taskhelp", description="Hướng dẫn sử dụng bot")
async def task_help(interaction: discord.Interaction):
    """Hiển thị hướng dẫn sử dụng bot."""
    embed = discord.Embed(
        title="📚 Hướng dẫn sử dụng Task Bot",
        description="Bot quản lý công việc cho team Discord",
        color=0x3498db,
    )

    embed.add_field(
        name="🆕 `/assign`",
        value="Giao việc cho một thành viên\n"
        "Cú pháp: `/assign @user mô_tả ngày_bắt_đầu deadline`\n"
        "VD: `/assign @John Làm báo cáo 15/10/2025 20/10/2025`",
        inline=False,
    )

    embed.add_field(
        name="📋 `/mytasks`",
        value="Xem danh sách task của bạn",
        inline=True,
    )

    embed.add_field(
        name="📋 `/alltasks`",
        value="Xem tất cả task của team",
        inline=True,
    )

    embed.add_field(
        name="🔍 `/task`",
        value="Xem chi tiết một task\n" "VD: `/task 5`",
        inline=True,
    )

    embed.add_field(
        name="🗑️ `/deletetask`",
        value="Xóa một task (chỉ người giao)",
        inline=True,
    )

    embed.add_field(
        name="📊 Trạng thái Task",
        value="📋 TODO - Chưa bắt đầu\n"
        "🔄 IN_PROGRESS - Đang thực hiện\n"
        "✅ DONE - Hoàn thành\n"
        "❌ CANCELLED - Đã hủy\n"
        "⚠️ LATE - Quá hạn",
        inline=False,
    )

    embed.add_field(
        name="💡 Mẹo",
        value="• Dùng các nút **Start**, **Complete**, **Cancel** hoặc dropdown để cập nhật trạng thái\n"
        "• Bot sẽ tự động nhắc nhở khi task sắp hết hạn\n"
        "• Task quá hạn sẽ tự động chuyển sang trạng thái LATE",
        inline=False,
    )

    embed.set_footer(text="Made with ❤️ for your team")

    await interaction.response.send_message(embed=embed)


# ==================== RUN BOT ====================

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file!")
        print("Please create a .env file with your bot token.")
    else:
        bot.run(DISCORD_TOKEN)
