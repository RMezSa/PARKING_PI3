# 🔐 Telegram Bot Authentication System

## Overview

The parking bot now implements a comprehensive phone number-based authentication system with two user roles: **Admins** and **Users**.

## 📋 Features

### ✅ Implemented Features

1. **Phone Number Authentication**
   - Users must register with their Mexican phone number (10 digits)
   - Phone numbers are hashed using SHA256 for security
   - Persistent storage in `/app/data/users.json`
   - Survives container restarts

2. **Two User Roles**
   - **Admin**: Full access to all commands including LED control, counter modification, logs, and user promotion
   - **User**: Access to parking status, schedules, and reporting

3. **Duplicate Phone Number Protection**
   - When a phone number is already registered, the system sends a verification code to the original device
   - The new device must enter the code to transfer the account
   - Protects against account takeover
   - 5-minute timeout for verification codes

4. **Registration Codes**
   - **Admin Code**: `ADMIN2024PARK` (hardcoded)
   - **User Code**: `USER2024PARK` (hardcoded)
   - Can be overridden via environment variables

5. **Wrong Parking Report System**
   - Users can report incorrect parking counts
   - 5-minute cooldown between reports
   - Reports notify admins who have enabled notifications
   - Includes difference calculation

6. **Admin Notification Toggle**
   - Admins can opt-in/out of receiving user reports
   - Command: `/notifications on|off`

---

## 🚀 User Registration Flow

### For New Users

1. **Start the bot**: `/start`
2. **Register with code**: `/register USER2024PARK`
3. **Share phone number**: Click the "📱 Compartir mi número" button
4. **Confirmation**: Receive confirmation and access to commands

### For New Admins

1. **Start the bot**: `/start`
2. **Register with admin code**: `/register ADMIN2024PARK`
3. **Share phone number**: Click the "📱 Compartir mi número" button
4. **Confirmation**: Receive full admin access

### First Admin (Hardcoded)

The first admin is automatically initialized with phone number: **5611930911**

When this user registers:
1. Use `/register ADMIN2024PARK`
2. Share the phone number `5611930911`
3. The account will be activated with full admin privileges

---

## 📱 Phone Number Requirements

### Validation Rules

- **Must be exactly 10 digits**
- **No country code (+52)**
- **No special characters** (spaces, dashes, parentheses)

### Valid Examples
- ✅ `5611930911`
- ✅ `5512345678`
- ✅ `8181234567`

### Invalid Examples
- ❌ `+525611930911` (contains +52)
- ❌ `561-193-0911` (contains dashes)
- ❌ `561 193 0911` (contains spaces)
- ❌ `56119309` (too short)

---

## 🔐 Security Features

### 1. Phone Number Hashing
Phone numbers are hashed using SHA256 before storage:
```python
phone_hash = hashlib.sha256(phone.encode()).hexdigest()
```

### 2. Duplicate Detection
When a duplicate phone is detected:
1. A 6-digit verification code is generated
2. Code is sent to the original device
3. New device must enter the code within 5 minutes
4. Account transfers to new device if code is correct

### 3. Account Transfer Notifications
Both devices receive notifications:
- **Original device**: "Your account has been transferred"
- **New device**: "Verification successful"

---

## 👥 User Roles & Permissions

### Admin Permissions

| Command | Description |
|---------|-------------|
| `/parking` | View parking status |
| `/status` | View system status |
| `/schedule` | Set up notifications |
| `/listschedules` | View schedules |
| `/removeschedule` | Remove schedules |
| `/report <número>` | Report wrong count |
| **`/set <número>`** | **Modify parking counter** |
| **`/leds <on\|off>`** | **Control traffic light LEDs** |
| **`/logs <container> <lines>`** | **View Docker logs** |
| **`/addadmin <phone>`** | **Promote user to admin** |
| **`/notifications <on\|off>`** | **Toggle report notifications** |

### User Permissions

| Command | Description |
|---------|-------------|
| `/parking` | View parking status |
| `/status` | View system status |
| `/schedule` | Set up notifications |
| `/listschedules` | View schedules |
| `/removeschedule` | Remove schedules |
| `/report <número>` | Report wrong count (5-min cooldown) |

---

## 🚨 Report System

### How It Works

1. **User submits report**:
   ```
   /report 20
   ```
   Reports that there are 20 occupied spaces

2. **System checks cooldown**: Must wait 5 minutes between reports

3. **Confirmation sent to user**:
   - Shows reported count
   - Shows system count
   - Confirms report was sent

4. **Admins notified** (if opted in):
   - User name
   - Phone number (last 4 digits)
   - Reported count vs. system count
   - Difference calculation

### Report Cooldown

- **Cooldown period**: 5 minutes
- **Purpose**: Prevent spam
- **Enforcement**: Per user, tracked in `users.json`

---

## 🛠️ Admin Management

### Promoting Users to Admin

Only existing admins can promote users:

```
/addadmin 5512345678
```

**Requirements**:
- User must be registered first
- Phone number must be valid (10 digits)
- Executor must be an admin

**What happens**:
1. User role is upgraded to `admin`
2. Notifications are enabled by default
3. Both admin and promoted user receive notifications

### Managing Notifications

Admins can control whether they receive user reports:

```
/notifications on   # Enable report notifications
/notifications off  # Disable report notifications
```

Check current status:
```
/notifications
```

---

## 💾 Data Persistence

### Users Database (`/app/data/users.json`)

```json
{
  "phone_hash_here": {
    "chat_id": "123456789",
    "phone": "5611930911",
    "role": "admin",
    "registered_at": "23/10/2025 14:30:00",
    "notifications_enabled": true,
    "last_report_time": null,
    "pending_activation": false
  }
}
```

### Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `chat_id` | string | Telegram chat ID (null if not activated) |
| `phone` | string | Plain phone number (for reference) |
| `role` | string | `admin` or `user` |
| `registered_at` | string | Registration timestamp (Mexico City time) |
| `notifications_enabled` | boolean | Receive reports (admins only) |
| `last_report_time` | string\|null | Last time user submitted a report |
| `pending_activation` | boolean | True for initial admin before first registration |

### Data Survival

- Data persists in Docker volume: `/app/data/`
- Survives container restarts
- Survives container updates
- Backed up with volume backups

---

## 🔧 Configuration

### Environment Variables

Add to your `.env` file or Docker Compose:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional (defaults shown)
ADMIN_REG_CODE=ADMIN2024PARK
USER_REG_CODE=USER2024PARK
```

### Hardcoded Configuration

In `telegram_bot.py`:

```python
INITIAL_ADMIN_PHONE = "5611930911"  # First admin phone
REPORT_COOLDOWN_MINUTES = 5         # Report cooldown
VERIFICATION_CODE_TIMEOUT = 300     # 5 minutes in seconds
```

---

## 🧪 Testing Guide

### Test 1: New User Registration

1. Start bot: `/start`
2. Register: `/register USER2024PARK`
3. Share phone number (10 digits)
4. Verify you can use `/parking` but NOT `/set`

### Test 2: Admin Registration

1. Use phone `5611930911`
2. Register: `/register ADMIN2024PARK`
3. Share phone number
4. Verify you can use `/set`, `/leds`, `/logs`

### Test 3: Duplicate Phone Detection

1. Register with phone X on Device A
2. Try to register with same phone X on Device B
3. Verify Device A receives verification code
4. Enter code on Device B
5. Verify account transfers successfully

### Test 4: Report System

1. As regular user: `/report 20`
2. Verify confirmation message
3. Try to report again immediately
4. Verify cooldown message (5 minutes)
5. As admin: Verify you receive the report

### Test 5: Data Persistence

1. Register users and admins
2. Restart Docker container:
   ```bash
   docker-compose restart telegram-bot
   ```
3. Verify users can still use commands
4. Verify roles are preserved

---

## 📝 Example Usage

### Complete Registration Flow

```
User: /start
Bot: 👋 ¡Hola! ... 🔒 No estás registrado

User: /register USER2024PARK
Bot: ✅ Código válido (USER)
     📱 Paso 2: Compartir tu número de teléfono
     [Button: 📱 Compartir mi número]

User: [Shares phone: 5512345678]
Bot: ✅ ¡Registro Exitoso!
     👤 Nombre: User
     📱 Teléfono: 5512345678
     🎫 Rol: Usuario
     
User: /help
Bot: [Shows user commands]

User: /report 25
Bot: ✅ Reporte Enviado
     📊 Conteo reportado: 25/35
     📊 Conteo actual del sistema: 20/35
     
User: /report 25
Bot: ⏱️ Espera un momento
     Puedes reportar nuevamente en 5 minuto(s)
```

---

## 🔍 Troubleshooting

### Problem: "Código de registro inválido"

**Solution**: Verify you're using the correct registration code:
- Users: `USER2024PARK`
- Admins: `ADMIN2024PARK`

### Problem: "Número de teléfono inválido"

**Solution**: Ensure phone number:
- Is exactly 10 digits
- Contains no spaces, dashes, or special characters
- Does not include +52 country code

### Problem: "Este comando solo está disponible para administradores"

**Solution**: Your account is registered as a regular user. Ask an admin to promote you:
```
/addadmin YOUR_PHONE_NUMBER
```

### Problem: "Duplicate phone" verification not working

**Possible causes**:
1. Original device didn't receive code → Check if chat_id is valid
2. Code expired → Wait 5 minutes and try registering again
3. Wrong code entered → Verify the 6-digit code carefully

### Problem: Reports not reaching admins

**Check**:
1. Admins have notifications enabled: `/notifications on`
2. Admins are properly registered
3. Check bot logs for errors

---

## 🚀 Deployment

### Docker Compose Volume

Ensure your `docker-compose.yml` has the data volume:

```yaml
services:
  telegram-bot:
    volumes:
      - ./telegram_bot/data:/app/data
```

### First-Time Setup

1. Deploy the updated bot
2. Register the first admin with phone `5611930911`
3. First admin can then:
   - Promote other admins: `/addadmin <phone>`
   - Configure notifications: `/notifications on`

### Migration from Old Version

If you have an existing bot without authentication:

1. All users will need to register
2. Create initial admin first
3. Have admin promote trusted users to admin
4. Distribute registration codes to legitimate users

---

## 📊 Monitoring

### Check Logs

```bash
docker logs telegram-bot | grep -i "register\|auth\|admin"
```

### View Users Database

```bash
docker exec telegram-bot cat /app/data/users.json | jq .
```

### Count Users

```bash
docker exec telegram-bot cat /app/data/users.json | jq 'length'
```

---

## 🔐 Security Best Practices

1. **Change registration codes** in production:
   ```bash
   export ADMIN_REG_CODE="YourSecureAdminCode123"
   export USER_REG_CODE="YourSecureUserCode456"
   ```

2. **Backup users database** regularly:
   ```bash
   docker cp telegram-bot:/app/data/users.json ./backup/users_$(date +%Y%m%d).json
   ```

3. **Monitor admin promotions** via logs

4. **Rotate initial admin** if compromised:
   - Edit `INITIAL_ADMIN_PHONE` in code
   - Redeploy container
   - Remove old users.json

5. **Limit admin promotion** to trusted personnel only

---

## 📞 Support

For issues or questions:
1. Check logs: `docker logs telegram-bot`
2. Review this guide
3. Check `users.json` for data issues
4. Verify environment variables

---

## 🎉 Summary

✅ Phone number authentication with SHA256 hashing
✅ Two roles: Admin and User with different permissions
✅ Duplicate phone protection with verification codes
✅ Report system with 5-minute cooldown
✅ Admin notification toggle
✅ Persistent storage surviving restarts
✅ Mexican phone number validation
✅ Admin promotion system
✅ Comprehensive help system

**Initial Admin Phone**: `5611930911`
**Admin Code**: `ADMIN2024PARK`
**User Code**: `USER2024PARK`
