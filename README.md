# Discord Task Manager Bot

Bot Discord quản lý công việc cho team với đầy đủ tính năng: giao việc, theo dõi tiến độ, cập nhật trạng thái bằng buttons/dropdown, và hệ thống nhắc nhở tự động.

## Tính năng

- **Giao việc (`/assign`)**: Giao task cho thành viên với deadline
- **Theo dõi (`/mytasks`, `/alltasks`)**: Xem danh sách task theo cá nhân hoặc team
- **Cập nhật trạng thái**: Buttons và Dropdown để thay đổi status nhanh chóng
- **Nhắc nhở tự động**: Bot tự động nhắc khi task sắp hết hạn
- **Cảnh báo quá hạn**: Task quá deadline tự động chuyển sang LATE
- **Hệ thống phạt trễ hạn**: Tự động tính tiền phạt theo số ngày trễ, xem bảng xếp hạng phạt team
- **GitHub Integration**: Thông báo tự động khi có Issue/PR mới, assign, labels...

## Cài đặt

### 1. Tạo Discord Bot

1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** và đặt tên cho bot
3. Vào tab **"Bot"**:
   - Click **"Reset Token"** và copy token
   - Bật **"Message Content Intent"**
   - Bật **"Server Members Intent"**
4. Vào tab **"OAuth2" > "URL Generator"**:
   - Chọn scopes: `bot`, `applications.commands`
   - Chọn permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Mention Everyone`
   - Copy URL và mở trong browser để invite bot vào server

### 2. Cấu hình môi trường

```bash
# Clone/copy project
cd bot-task

# Tạo virtual environment (khuyến khích)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env từ template
cp .env.example .env
```

### 3. Cập nhật file .env

```env
# Bot token từ Discord Developer Portal
DISCORD_TOKEN=your_bot_token_here

# Channel ID để gửi thông báo (Right-click channel > Copy ID)
NOTIFICATION_CHANNEL_ID=1234567890

# Thời gian nhắc nhở trước deadline (phút)
REMINDER_MINUTES_BEFORE=60
```

> **Lưu ý**: Để lấy Channel ID, bật **Developer Mode** trong Discord Settings > Advanced

### 4. Chạy bot

```bash
python bot.py
```

## Sử dụng

### Các lệnh Slash

| Lệnh | Mô tả |
|------|-------|
| `/assign @user mô_tả ngày_bắt_đầu deadline` | Giao việc cho thành viên |
| `/mytasks` | Xem task của bạn |
| `/alltasks` | Xem tất cả task của team |
| `/task task_id` | Xem chi tiết một task |
| `/deletetask task_id` | Xóa task (chỉ người giao) |
| `/penalty @user` | Xem chi tiết tiền phạt của một thành viên |
| `/penalties` | Bảng xếp hạng phạt team |
| `/excuse task_id` | Miễn phạt cho task (chỉ người giao/Admin) |
| `/taskhelp` | Xem hướng dẫn |

### Ví dụ

```
/assign @John Hoàn thành báo cáo Q4 15/01/2026 20/01/2026
/assign @Mary Review code feature login 16/01/2026 09:00 17/01/2026 18:00
```

### Trạng thái Task

| Status | Emoji | Màu | Mô tả |
|--------|-------|-----|-------|
| TODO | 📋 | Xanh dương | Chưa bắt đầu |
| IN_PROGRESS | 🔄 | Vàng cam | Đang thực hiện |
| DONE | ✅ | Xanh lá | Hoàn thành |
| CANCELLED | ❌ | Xám | Đã hủy |
| LATE | ⚠️ | Đỏ | Quá hạn |

### Cập nhật trạng thái

Mỗi task hiển thị kèm:
- **Buttons**: `[Start]` `[Complete]` `[Cancel]`
- **Dropdown menu**: Chọn bất kỳ trạng thái nào

Chỉ **người được giao** hoặc **người giao việc** mới có quyền cập nhật.

## Cấu trúc Project

```
bot-task/
├── bot.py              # File chính chạy bot
├── config.py           # Cấu hình (token, constants)
├── database.py         # Xử lý SQLite database
├── views.py            # Discord UI components (Embeds, Buttons, Dropdowns)
├── github_webhook.py   # GitHub webhook handler
├── requirements.txt
├── .env.example
└── README.md
```

## Hệ thống nhắc nhở

Bot chạy background task mỗi 5 phút để:

1. **Kiểm tra task sắp hết hạn**: Gửi nhắc nhở nếu còn dưới 60 phút (có thể config)
2. **Kiểm tra task quá hạn**: Tự động đổi status sang LATE và gửi cảnh báo

## Hệ thống phạt trễ hạn

Bot tự động tính tiền phạt cho các task quá deadline:

### Công thức tính phạt

| Ngày trễ | Phạt ngày đó | Tổng phạt |
|----------|-------------|-----------|
| Ngày 1 | 20k | 20k |
| Ngày 2 | 30k | 50k |
| Ngày 3 | 40k | 90k |
| Ngày N | (10 + 10N)k | (5N² + 15N)k |

- **BASE_PENALTY**: 20k (ngày đầu tiên)
- **PENALTY_INCREMENT**: +10k mỗi ngày sau

### Cách hoạt động

- Task quá hạn (status LATE): phạt **đang tính** (tăng mỗi ngày)
- Task hoàn thành trễ (DONE nhưng `completed_at > end_date`): phạt **đã khóa** (cố định)
- Miễn phạt: dùng `/excuse task_id` (chỉ người giao hoặc Admin)

### Các lệnh phạt

```
/penalty @John          # Xem chi tiết phạt của John
/penalties              # Bảng xếp hạng phạt cả team
/excuse 5               # Miễn phạt cho task #5
```

## GitHub Webhook Integration

Bot có thể nhận thông báo từ GitHub khi:
- **Issue**: Tạo mới, assign, đóng, thêm label
- **Pull Request**: Tạo mới, merge, request review
- **Push**: Commit mới lên branch

### Cách setup GitHub Webhook

#### 1. Expose webhook server (cho development)

Bot chạy webhook server trên port 8080. Để GitHub gửi được webhook, bạn cần expose port này ra internet:

**Dùng ngrok (miễn phí):**
```bash
# Cài đặt ngrok: https://ngrok.com/download
ngrok http 8080

# Sẽ nhận được URL như: https://abc123.ngrok.io
```

**Dùng Cloudflare Tunnel:**
```bash
cloudflared tunnel --url http://localhost:8080
```

#### 2. Cấu hình trên GitHub

1. Vào repo GitHub → **Settings** → **Webhooks** → **Add webhook**

2. Điền thông tin:
   - **Payload URL**: `https://your-ngrok-url.ngrok.io/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Tạo một chuỗi random (phải giống với `GITHUB_WEBHOOK_SECRET` trong .env)

3. Chọn events cần nhận:
   - **Issues** (để nhận thông báo issue)
   - **Pull requests** (để nhận thông báo PR)
   - **Pushes** (để nhận thông báo commit)

4. Click **Add webhook**

#### 3. Cập nhật .env

```env
# Secret phải giống với GitHub webhook settings
GITHUB_WEBHOOK_SECRET=your_random_secret_string

# Channel để gửi thông báo GitHub (có thể khác với task channel)
GITHUB_CHANNEL_ID=1234567890

# Port cho webhook server
WEBHOOK_PORT=8080
```

### Các thông báo GitHub

| Event | Hiển thị |
|-------|----------|
| Issue opened | 🆕 Embed màu xanh lá với title, assignees, labels |
| Issue assigned | 👤 Embed màu xanh dương, thông báo ai được assign |
| Issue closed | ✅ Embed màu đỏ |
| PR opened | 🆕 Embed với branch info |
| PR merged | 🔀 Embed màu tím |
| Push | 🚀 Danh sách commits |

## Phát triển thêm

Một số ý tưởng mở rộng:
- Thêm priority levels (High, Medium, Low)
- Thống kê hiệu suất làm việc
- Export báo cáo ra file (bao gồm bảng phạt)
- Tích hợp calendar/Google Calendar
- Recurring tasks (task lặp lại)

## Troubleshooting

**Q: Bot không phản hồi lệnh slash?**
- Đảm bảo đã invite bot với scope `applications.commands`
- Chờ vài phút để Discord sync commands

**Q: Bot không gửi nhắc nhở?**
- Kiểm tra `NOTIFICATION_CHANNEL_ID` trong .env
- Đảm bảo bot có quyền gửi tin nhắn trong channel đó

**Q: Lỗi "Token invalid"?**
- Reset token trong Discord Developer Portal và cập nhật .env
