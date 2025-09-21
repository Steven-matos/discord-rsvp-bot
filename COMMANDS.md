# Discord RSVP Bot - Commands Documentation

This bot helps manage weekly event schedules and RSVP tracking for Discord servers.

> **📢 Recent Update**: Command interface has been streamlined! We've removed technical/debugging commands that were cluttering the interface, keeping only the essential commands you need for daily RSVP management.

## 🚀 Getting Started

### Initial Setup Commands

#### `/setup_weekly_schedule`
Plan your week! Tell the bot what events you want (like Monday raids, Tuesday training, etc.) and it will post them automatically every day.
- **Usage**: Follow the interactive setup process
- **Example**: Monday = "Raid Night", Tuesday = "PvP Practice"

#### `/set_event_channel <channel>`
Pick which channel the bot should post events in. This is where your team will see daily announcements and click buttons to say if they're coming.
- **Parameters**: `channel` - The text channel for event posts
- **Example**: `/set_event_channel #events`

#### `/set_event_time <hour> <minute>`
What time do your events usually start? This helps the bot send reminders at the right times.
- **Parameters**: 
  - `hour` - Hour in 24-hour format (0-23)
  - `minute` - Minute (0-59)
- **Example**: `/set_event_time 20 00` (8:00 PM Eastern)

#### `/set_posting_time <hour> <minute>`
What time should the bot create the daily RSVP posts? (Default: 9:00 AM Eastern). This is when the post appears each day.
- **Parameters**: 
  - `hour` - Hour in 24-hour format (0-23) 
  - `minute` - Minute (0-59)
- **Example**: `/set_posting_time 09 00` (9:00 AM Eastern)

---

## 📋 Managing Your Events

#### `/view_schedule`
Show this week's event plan. See what's happening each day at a glance.
- **Usage**: No parameters needed
- **Shows**: All 7 days with event names, outfits, and vehicles

#### `/edit_event <day>`
Change or add events for any day. Maybe Monday changed from 'Raids' to 'PvP Night'? This command has you covered!
- **Parameters**: `day` - monday, tuesday, wednesday, thursday, friday, saturday, sunday
- **Example**: `/edit_event monday`

#### `/configure_reminders [enabled] [four_pm] [one_hour] [fifteen_minutes]`
Want reminders? The bot can ping everyone about tonight's event, or remind them an hour before it starts.
- **Parameters** (all optional):
  - `enabled` - Enable/disable all reminders (default: true)
  - `four_pm` - Send reminder at 4:00 PM Eastern (default: true)
  - `one_hour` - Send reminder 1 hour before event (default: true)
  - `fifteen_minutes` - Send reminder 15 minutes before event (default: true)

---

## 👥 See Who's Coming

#### `/view_rsvps`
Who's joining today's event? See the list of people coming, maybe coming, or can't make it.
- **Usage**: No parameters needed
- **Shows**: Lists of Yes/No/Maybe/Mobile responses plus non-responders

#### `/view_yesterday_rsvps`  
Check who showed up yesterday. Great for seeing attendance trends!
- **Usage**: No parameters needed
- **Shows**: Previous day's RSVP summary

#### `/midweek_rsvp_report`
Get a comprehensive RSVP report for Monday through Wednesday of the current week. Shows actual member names who RSVPed and participation stats.
- **Usage**: No parameters needed
- **Admin Only**: Yes
- **Shows**: Day-by-day breakdown with member names for each response type (Yes/No/Maybe/Mobile/No Response), participation rates, consistent attendees, and summary statistics for Mon-Wed
- **Features**: Smart name truncation (shows up to 10 names per category), visual day separation, detailed attendance tracking

#### `/weekly_rsvp_report`
Get a complete RSVP report for the entire week (Monday through Sunday). Perfect for analyzing weekly attendance patterns with member identification.
- **Usage**: No parameters needed  
- **Admin Only**: Yes
- **Shows**: Full week breakdown with compact daily summaries, most active attendees list, members who never responded, attendance analysis, participation trends, and comprehensive statistics
- **Features**: Deduplicated member lists, perfect attendance tracking, good attendance analysis (70%+ participation), week totals

---

## 🔧 Help & Support

#### `/list_commands`
Show the main commands menu with everyday bot features.
- **Usage**: No parameters needed
- **Shows**: Setup, management, and RSVP viewing commands

#### `/list_help`
Show troubleshooting, maintenance, and diagnostic commands.
- **Usage**: No parameters needed  
- **Shows**: Advanced commands for fixing issues and debugging the bot

---

## 🛠️ Advanced Commands (Available via `/list_help`)

*The following commands are accessed through `/list_help` and are used for troubleshooting, maintenance, and advanced diagnostics.*

### 🛠️ Troubleshooting & Fixes

#### `/force_post_rsvp`
Didn't get today's event post? Use this to make the bot post it right now.
- **Usage**: No parameters needed
- **Note**: Checks all requirements before posting

#### `/reset_setup`
Stuck on 'setup already in progress'? This clears the setup state so you can start fresh.
- **Usage**: No parameters needed
- **When to use**: If weekly setup gets stuck

#### `/force_sync`
Commands not showing up when you type '/'? This refreshes everything.
- **Usage**: No parameters needed
- **Note**: Forces re-registration of all slash commands

### 🧹 Maintenance & Cleanup

#### `/delete_message <message_id> [channel]`
Remove any unwanted message by copying its ID. Useful for cleaning up mistakes.
- **Parameters**: 
  - `message_id` - The Discord message ID to delete
  - `channel` - Optional channel (defaults to current channel)

#### `/cleanup_old_posts`
Remove old event posts to keep your channel tidy (but keeps all the RSVP records).
- **Usage**: No parameters needed
- **Note**: Only deletes Discord messages, preserves database records

#### `/set_admin_channel <channel>`
Choose where the bot sends important alerts (like 'Hey, you forgot to set up this week's schedule!').
- **Parameters**: `channel` - Text channel for admin notifications
- **Example**: `/set_admin_channel #bot-admin`

### 🔧 Advanced Diagnostics

#### `/debug_auto_posting`
Diagnose why automatic daily posts aren't working. Shows timing, settings, and schedule status.
- **Usage**: No parameters needed
- **Shows**: Current time, posting configuration, schedule status, task status


#### `/debug_view_rsvps`
Debug why view_rsvps isn't finding posts when they exist.
- **Usage**: No parameters needed
- **Shows**: Database query details and troubleshooting info

#### `/debug_reminders`
Debug why reminders are not being sent out. Shows complete reminder system diagnosis.
- **Usage**: No parameters needed
- **Shows**: Task status, reminder settings, timing, database queries, duplicate prevention
- **When to use**: When reminders stop working or aren't being sent


### 🔧 System Information

#### `/bot_status`
Is the bot working properly? Check here if things seem slow.
- **Usage**: No parameters needed  
- **Shows**: Basic bot health information

#### `/clear_cache`
Clear all cache entries to force fresh data.
- **Usage**: No parameters needed
- **Shows**: Cache statistics after clearing
- **Access**: Admin permissions required
- **Use Case**: When RSVP data appears stale or outdated

---

## 🔄 Automatic Features

The bot automatically:

- **Daily Posting**: Posts RSVP messages at your configured time (default 9:00 AM Eastern)
- **Reminders**: Sends event reminders based on your settings:
  - 4:00 PM Eastern (if enabled)
  - 1 hour before event (if enabled) 
  - 15 minutes before event (if enabled)
- **Cleanup**: Removes old event posts daily to keep channels tidy
- **Rate Limiting**: Protects against Discord API limits with built-in delays

---

## 🆘 Common Issues & Solutions

### Automatic Posting Not Working
1. Use `/list_help` then `/debug_auto_posting` to diagnose
2. Check if current week's schedule is set up
3. Verify event channel is configured
4. Restart the bot if the task appears stuck

### Commands Not Showing
1. Use `/list_help` then `/force_sync` to re-register commands
2. Check bot permissions in server
3. Restart bot if necessary

### Rate Limiting (459 Errors)
1. Avoid running `/view_rsvps` during peak times if server is large (500+ members)
2. Bot includes automatic rate limiting protection
3. Restart bot if rate limiting persists

### RSVP Posts Missing
1. Use `/list_help` then `/force_post_rsvp` to post immediately
2. Check if today's event is configured with `/view_schedule`
3. Verify bot permissions in event channel

---

## ⚙️ Permissions Required

The bot requires these Discord permissions:
- **Send Messages** - To post events and responses
- **Embed Links** - To create rich event posts
- **Manage Messages** - To delete old posts during cleanup
- **Use Slash Commands** - To register and respond to commands
- **View Channel** - To read channels and member lists

---

## 🎯 Best Practices

1. **Weekly Setup**: Run `/setup_weekly_schedule` at the start of each week
2. **Monitor Logs**: Watch console for `[AUTO-POST]`, `[RATE-LIMIT]`, and `[TASK]` messages
3. **Test Changes**: Use debug commands after configuration changes
4. **Regular Maintenance**: Occasionally run `/cleanup_old_posts` and `/server_settings`
5. **Rate Limiting**: Be mindful of API usage in large servers (500+ members)

---

*For technical support or feature requests, check the bot console logs or contact your server administrator.* 