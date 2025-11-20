# 🔐 Authentication System - Quick Reference

## 📋 Registration Codes

| Role | Code | Access Level |
|------|------|-------------|
| **Admin** | `ADMIN2024PARK` | Full control |
| **User** | `USER2024PARK` | View & Report only |

**First Admin Phone**: `5611930911`

---

## 🚀 Quick Start

### Register as User
```
1. /start
2. /register USER2024PARK
3. [Share phone via button]
4. Done! ✅
```

### Register as Admin
```
1. /start
2. /register ADMIN2024PARK
3. [Share phone via button]
4. Done! ✅ Full access
```

### ⚠️ Registration Stuck? Use /cancel
```
If registration fails or app bugs out:
1. /cancel
2. /register <CODE>
3. [Share phone again]
```

---

## 📱 Phone Number Format

✅ **Valid**: `5611930911` (exactly 10 digits)
❌ **Invalid**: 
- `+525611930911` (has +52)
- `561-193-0911` (has dashes)
- `561 193 0911` (has spaces)

---

## 👥 Commands by Role

### 🟢 User Commands
- `/parking` - Check availability
- `/schedule <día> <hora>` - Set notification
- `/listschedules` - View schedules
- `/removeschedule <#>` - Remove schedule
- `/report <número>` - Report wrong count (5min cooldown)

### 🔴 Admin Commands (All User Commands +)
- `/set <número>` - Modify counter
- `/leds <on|off>` - Control LEDs
- `/logs <container> <lines>` - View logs
- `/addadmin <phone>` - Promote user
- `/notifications <on|off>` - Toggle reports

---

## 🚨 Report System

**Users can report wrong counts**:
```
/report 25    # Report 25 occupied spaces
```

**Cooldown**: 5 minutes between reports

**Admins receive**:
- User info
- Reported count vs system count
- Time of report

**Admin toggle**:
```
/notifications on   # Receive reports
/notifications off  # Stop receiving reports
```

---

## 🔐 Duplicate Phone Protection

**What happens if phone is already registered?**

1. Original device gets verification code (6 digits)
2. New device must enter code within 5 minutes
3. If correct → Account transfers to new device
4. If incorrect → Registration fails

**Security Features**:
- Prevents account takeover
- Both devices get notified
- Automatic timeout (5 min)

---

## 💾 Data Files

| File | Location | Contents |
|------|----------|----------|
| `users.json` | `/app/data/` | User accounts (hashed phones) |
| `schedules.json` | `/app/data/` | Notification schedules |

**Persistence**: Survives container restarts ✅

---

## 🛠️ Admin Management

### Promote User to Admin
```bash
/addadmin 5512345678
```
**Requirements**: User must be registered first

### Check User Status
Only authenticated users can use commands. Unauthenticated users see:
> 🔒 Acceso no autorizado
> Usa /register para comenzar

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| Invalid registration code | Use `ADMIN2024PARK` or `USER2024PARK` |
| Invalid phone | Use exactly 10 digits, no +52 |
| Registration stuck/app bugged | Use `/cancel` then restart with `/register <code>` |
| Verification stuck | Use `/cancel` then restart registration |
| Command not available | Ask admin to promote you: `/addadmin <phone>` |
| Reports not received | Admin: use `/notifications on` |
| Duplicate phone | Check original device for verification code |
| Registration expired (10min+) | Automatically cleaned up, just use `/register` again |

---

## 🎯 Testing Checklist

- [ ] Register as user (USER2024PARK)
- [ ] Verify user can't use `/set` or `/leds`
- [ ] Register as admin (5611930911 + ADMIN2024PARK)
- [ ] Verify admin can use all commands
- [ ] Test report system with 5-min cooldown
- [ ] Test `/addadmin` to promote user
- [ ] Restart container, verify data persists
- [ ] Test duplicate phone detection
- [ ] Test verification code transfer
- [ ] Test `/cancel` during registration
- [ ] Test registration restart after app bug
- [ ] Test 10-minute registration timeout

---

## 📊 Database Structure

```json
{
  "hashed_phone": {
    "chat_id": "123456789",
    "phone": "5611930911",
    "role": "admin",
    "registered_at": "23/10/2025 14:30:00",
    "notifications_enabled": true,
    "last_report_time": null
  }
}
```

---

## 🚀 Deployment Steps

1. Update bot code
2. Restart container
3. Register first admin (5611930911)
4. Admin promotes other admins
5. Distribute codes to users

---

## 🔐 Security Notes

✅ Phone numbers hashed with SHA256
✅ Duplicate detection with verification
✅ Role-based access control
✅ 5-minute report cooldown
✅ Admin-only promotion
✅ Persistent storage

---

## � Edge Case: Registration App Bug

**Problem**: User's app crashes/bugs out after entering code but before sharing phone.

**Symptoms**:
- User entered `/register <CODE>`
- Bot asked for phone
- App crashed or network failed
- User is stuck - can't complete registration or start over

**Solutions** (in order of preference):

### 1. Use /cancel Command (Immediate)
```
/cancel
/register USER2024PARK
[Share phone]
```

### 2. Restart with Same Code (Auto-cleanup old state)
```
/register USER2024PARK
[Share phone]
```
Bot automatically detects and cleans up old pending state.

### 3. Wait 10 Minutes (Auto-expiry)
```
[Wait 10 minutes]
/register USER2024PARK
[Share phone]
```
Old registration automatically expires.

**Prevention**:
- ✅ Automatic expiry after 10 minutes
- ✅ Manual cancel with `/cancel`
- ✅ Auto-restart detection when providing code again
- ✅ Clear error messages when stuck

---

## �📞 Support Commands

```bash
# View logs
docker logs telegram-bot

# Check users database
docker exec telegram-bot cat /app/data/users.json

# Backup users
docker cp telegram-bot:/app/data/users.json ./backup/

# Check pending registrations (in logs)
docker logs telegram-bot | grep "pending"
```

---

**Full Documentation**: See `AUTHENTICATION_GUIDE.md`
