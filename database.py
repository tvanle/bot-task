import aiosqlite
from datetime import datetime
from typing import Optional, List, Tuple
from config import DATABASE_PATH, TaskStatus, BASE_PENALTY, PENALTY_INCREMENT


async def init_db():
    """Khởi tạo database và tạo bảng tasks nếu chưa tồn tại."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                assignee_id INTEGER NOT NULL,
                assignee_name TEXT NOT NULL,
                assigner_id INTEGER NOT NULL,
                assigner_name TEXT NOT NULL,
                status TEXT DEFAULT 'TODO',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_id INTEGER,
                channel_id INTEGER,
                reminder_sent INTEGER DEFAULT 0
            )
        """)

        # Migration: thêm cột mới cho hệ thống phạt
        for col, col_def in [
            ("completed_at", "TEXT"),
            ("excused", "INTEGER DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Cột đã tồn tại

        await db.commit()


async def create_task(
    description: str,
    assignee_id: int,
    assignee_name: str,
    assigner_id: int,
    assigner_name: str,
    start_date: datetime,
    end_date: datetime,
) -> int:
    """Tạo task mới và trả về task ID."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO tasks (
                description, assignee_id, assignee_name,
                assigner_id, assigner_name, status,
                start_date, end_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                description,
                assignee_id,
                assignee_name,
                assigner_id,
                assigner_name,
                TaskStatus.TODO,
                start_date.isoformat(),
                end_date.isoformat(),
                now,
                now,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def update_task_message(task_id: int, message_id: int, channel_id: int):
    """Cập nhật message_id và channel_id cho task."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE tasks SET message_id = ?, channel_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (message_id, channel_id, datetime.now().isoformat(), task_id),
        )
        await db.commit()


async def update_task_status(task_id: int, status: str) -> bool:
    """Cập nhật trạng thái task. Trả về True nếu thành công."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE tasks SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, datetime.now().isoformat(), task_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_task_by_id(task_id: int) -> Optional[dict]:
    """Lấy thông tin task theo ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_tasks_by_user(user_id: int) -> List[dict]:
    """Lấy danh sách tasks của một user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE assignee_id = ?
            ORDER BY
                CASE status
                    WHEN 'LATE' THEN 1
                    WHEN 'IN_PROGRESS' THEN 2
                    WHEN 'TODO' THEN 3
                    WHEN 'DONE' THEN 4
                    WHEN 'CANCELLED' THEN 5
                END,
                end_date ASC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_tasks() -> List[dict]:
    """Lấy tất cả tasks."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            ORDER BY
                CASE status
                    WHEN 'LATE' THEN 1
                    WHEN 'IN_PROGRESS' THEN 2
                    WHEN 'TODO' THEN 3
                    WHEN 'DONE' THEN 4
                    WHEN 'CANCELLED' THEN 5
                END,
                end_date ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_pending_tasks_near_deadline(minutes_before: int) -> List[dict]:
    """Lấy các task sắp hết hạn trong khoảng thời gian cho trước."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE status IN (?, ?)
            AND reminder_sent = 0
            """,
            (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_overdue_tasks() -> List[dict]:
    """Lấy các task đã quá hạn nhưng chưa hoàn thành."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE status IN (?, ?)
            AND end_date < ?
            """,
            (TaskStatus.TODO, TaskStatus.IN_PROGRESS, now),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_reminder_sent(task_id: int):
    """Đánh dấu đã gửi nhắc nhở cho task."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE tasks SET reminder_sent = 1, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), task_id),
        )
        await db.commit()


async def delete_task(task_id: int) -> bool:
    """Xóa task theo ID. Trả về True nếu thành công."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return cursor.rowcount > 0


async def mark_task_completed(task_id: int):
    """Ghi nhận thời điểm hoàn thành task (để khóa phạt)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE tasks SET completed_at = ?, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), datetime.now().isoformat(), task_id),
        )
        await db.commit()


async def excuse_task(task_id: int) -> bool:
    """Miễn phạt cho task. Trả về True nếu thành công."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET excused = 1, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), task_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_late_tasks_by_user(user_id: int) -> List[dict]:
    """Lấy task trễ hạn của user (LATE hoặc DONE trễ), chưa excused."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE assignee_id = ?
            AND excused = 0
            AND (
                status = ?
                OR (status = ? AND completed_at > end_date)
            )
            ORDER BY end_date ASC
            """,
            (user_id, TaskStatus.LATE, TaskStatus.DONE),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_late_tasks() -> List[dict]:
    """Lấy tất cả task trễ hạn chưa excused."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE excused = 0
            AND (
                status = ?
                OR (status = ? AND completed_at > end_date)
            )
            ORDER BY assignee_id, end_date ASC
            """,
            (TaskStatus.LATE, TaskStatus.DONE),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


def calculate_penalty(end_date_str: str, completed_at_str: str = None) -> Tuple[int, int]:
    """Tính tiền phạt dựa trên số ngày trễ.

    - Nếu đã hoàn thành (completed_at): tính từ end_date → completed_at
    - Nếu chưa: tính từ end_date → now
    Returns: (days_late, penalty) — penalty đơn vị nghìn đồng
    """
    end_date = datetime.fromisoformat(end_date_str)
    if completed_at_str:
        reference = datetime.fromisoformat(completed_at_str)
    else:
        reference = datetime.now()

    delta = reference - end_date
    days_late = max(0, delta.days + (1 if delta.seconds > 0 and delta.days >= 0 else 0))

    if days_late <= 0:
        return (0, 0)

    # Công thức: tổng N ngày = 5N² + 15N (nghìn đồng)
    # Ngày 1: 20k, ngày 2: 30k, ngày 3: 40k ...
    # Tổng = sum(BASE_PENALTY + (i-1)*PENALTY_INCREMENT for i in 1..N)
    #       = N*BASE_PENALTY + PENALTY_INCREMENT * N*(N-1)/2
    penalty = days_late * BASE_PENALTY + PENALTY_INCREMENT * days_late * (days_late - 1) // 2

    return (days_late, penalty)
