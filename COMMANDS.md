# Discord RSVP Bot - Commands Reference

This document contains all available commands for the Discord RSVP Bot, organized by user type and functionality.

## 🔧 Admin Commands

*These commands require "Manage Guild" permissions OR the specific user ID (300157754012860425)*

### Setup Commands

#### `/setup_weekly_schedule`
**What it does:** Creates your weekly event schedule by walking you through each day of the week.

**How to use:**
1. Type `/setup_weekly_schedule`
2. The bot will present a form for each day (Monday through Sunday)
3. For each day, fill in:
   - **Event Name:** What the event is called (e.g., "Raid Night", "Training Session")
   - **Outfit:** What gear/clothing people need (e.g., "Combat Gear", "Practice Clothes")
   - **Vehicle:** What vehicle they should bring (e.g., "Tank", "Fast Car")
4. Click "Continue to Next Day" to move to the next day
5. Repeat until all days are set up

**Example:**
```
Event Name: Monday Raid Night
Outfit: Combat Gear
Vehicle: Tank
```

**Error Handling:**
- If the modal fails to appear due to timing issues, you'll get a clear error message
- Simply try the command again - no need to restart or wait
- Failed setups automatically clean up their state so you can retry immediately
- The "Continue to Next Day" button also has improved error handling for timing issues

#### `/set_event_channel`
**What it does:** Chooses which Discord channel the bot will post daily events to.

**How to use:**
1. Type `/set_event_channel`
2. Select the channel where you want events posted
3. The bot will confirm the channel is set

**Example:**
```
/set_event_channel #events
```

#### `/set_event_time`
**What it does:** Sets what time your events start each day (in Eastern Time).

**How to use:**
1. Type `/set_event_time`
2. Enter the hour (0-23)
3. Enter the minute (0-59)
4. The bot will confirm the time is set

**Example:**
```
/set_event_time hour:20 minute:0
```
*This sets events to start at 8:00 PM Eastern Time*

#### `/configure_reminders`
**What it does:** Controls when reminder messages are sent for events.

**How to use:**
1. Type `/configure_reminders`
2. Set each option to true/false:
   - **enabled:** Turn all reminders on/off
   - **four_pm:** Send reminder at 4:00 PM Eastern
   - **one_hour:** Send reminder 1 hour before event
   - **fifteen_minutes:** Send reminder 15 minutes before event

**Example:**
```
/configure_reminders enabled:true four_pm:true one_hour:true fifteen_minutes:true
```

#### `/set_admin_channel`
**What it does:** Sets the channel where admin notifications are sent (like "schedule not set up" alerts).

**How to use:**
1. Type `/set_admin_channel`
2. Select the channel where you want admin notifications sent
3. The bot will confirm the channel is set

**Example:**
```
/set_admin_channel #admin-notifications
```

**When it's used:**
- Admin notifications are sent when the current week's schedule hasn't been set up
- Helps prevent the bot from posting outdated schedules
- Only one notification per day to avoid spam

### Management Commands

#### `/view_schedule`
**What it does:** Shows your complete weekly schedule with all events for each day.

**How to use:**
1. Type `/view_schedule`
2. The bot will display an embed showing:
   - Each day of the week
   - Event name for each day
   - Outfit requirements
   - Vehicle requirements
   - "No event scheduled" for empty days

**What you'll see:**
```
📅 Weekly Schedule
Monday: Raid Night | Combat Gear | Tank
Tuesday: PvP Tournament | Light Armor | Fast Car
Wednesday: No event scheduled
...
```

#### `/edit_event`
**What it does:** Modifies an existing event for any day of the week.

**How to use:**
1. Type `/edit_event`
2. Select the day you want to edit
3. The bot will show a form with current event data
4. Modify the event name, outfit, or vehicle
5. Submit the form to save changes

**Example:**
```
/edit_event day:monday
```
*Then modify the form that appears*

**Error Handling:**
- If the modal fails to appear due to timing issues, you'll get a clear error message
- Simply try the command again - no need to restart or wait
- The bot now handles Discord's interaction timing automatically

#### `/force_post_rsvp`
**What it does:** Manually posts today's RSVP if the automatic daily posting failed or didn't happen.

**How to use:**
1. Type `/force_post_rsvp`
2. The bot will show progress updates:
   - 🔄 **Checking current setup...** (validates configuration)
   - 🔄 **Validating configuration...** (checks permissions and settings)
   - 🔄 **Removing existing post and creating new one...** (if post already exists)
   - 🔄 **Creating today's RSVP post...** (for new posts)
3. The bot will check:
   - If today's RSVP was already posted (will delete and recreate if needed)
   - If the event channel is configured
   - If the bot has proper permissions in the channel
   - If the weekly schedule is set up
4. If all checks pass, it will post today's RSVP to the configured event channel

**When to use it:**
- The automatic daily posting at 9:00 AM Eastern didn't work
- You want to post today's RSVP manually
- You're testing the bot's posting functionality

**Error messages you might see:**
- "No event channel has been configured" - Use `/set_event_channel` first
- "Bot doesn't have permission to send messages" - Ask admin to grant Send Messages + Embed Links permissions
- "The current week's schedule has not been set up" - Use `/setup_weekly_schedule` first

**Note:** If today's RSVP has already been posted, the bot will automatically delete the existing post and create a new one instead of showing an error.

**Example:**
```
/force_post_rsvp
```
*The bot will then post today's event with RSVP buttons*

#### `/delete_message`
**What it does:** Deletes a specific message by its message ID.

**How to use:**
1. Right-click on any message and select "Copy Message ID" (requires Developer Mode enabled)
2. Type `/delete_message message_id:[paste the ID here]`
3. Optionally specify a channel with `channel:#channel-name`
4. The bot will delete the message and show you a confirmation

**Parameters:**
- `message_id` (required): The numeric ID of the message to delete
- `channel` (optional): The channel where the message is located (defaults to current channel)

**Examples:**
```
/delete_message message_id:1234567890123456789
```
```
/delete_message message_id:1234567890123456789 channel:#general
```

**Error messages you might see:**
- "Invalid Message ID" - The ID you provided isn't a valid number
- "Message Not Found" - The message doesn't exist or has already been deleted
- "Bot doesn't have permission" - The bot needs "Manage Messages" permission
- "Permission Denied" - The message is from someone with higher permissions

**How to get a message ID:**
1. Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
2. Right-click any message and select "Copy Message ID"
3. Use that ID with this command

#### `/list_commands`
**What it does:** Shows all available commands with descriptions.

**How to use:**
1. Type `/list_commands`
2. The bot will display an embed with all commands and their purposes

#### `/force_sync`
**What it does:** Refreshes the bot's commands in Discord (fixes command display issues).

**How to use:**
1. Type `/force_sync`
2. Wait for the confirmation message
3. Try typing `/` again - commands should now appear

## 👥 Member Commands

*These commands can be used by anyone in the server*

### RSVP Commands

#### `/view_rsvps`
**What it does:** Shows who has RSVP'd for today's event.

**How to use:**
1. Type `/view_rsvps`
2. The bot will display:
   - ✅ **Attending:** People who clicked "Yes"
   - ❓ **Maybe:** People who clicked "Maybe"
   - 📱 **Mobile:** People who clicked "Mobile"
   - ❌ **Not Attending:** People who clicked "No"
   - ⏰ **No Response:** People who haven't RSVP'd yet

**What you'll see:**
```
📋 RSVP Summary - Today's Event
Raid Night

✅ Attending (5)
- John (john#1234)
- Sarah (sarah#5678)
...

❓ Maybe (2)
- Mike (mike#9012)
...
```

#### `/view_yesterday_rsvps`
**What it does:** Shows who RSVP'd for yesterday's event (useful for tracking attendance).

**How to use:**
1. Type `/view_yesterday_rsvps`
2. The bot will display the same format as `/view_rsvps` but for yesterday's event

## 🎮 RSVP Buttons

*These appear automatically on daily event posts*

### Button Options

- **✅ Yes** - "I'm coming to the event!"
- **❌ No** - "I can't make it to the event"
- **❓ Maybe** - "I might come to the event"
- **📱 Mobile** - "I'm coming, but I'll be on mobile"

### How to Use RSVP Buttons

1. **Find the daily event post** in your designated events channel
2. **Click one of the RSVP buttons** to respond
3. **Change your mind anytime** by clicking a different button
4. **Your response is private** - only you see the confirmation message

## 📅 Automatic Features

*These happen automatically once set up*

### Daily Posts
- **When:** 9:00 AM Eastern Time daily
- **What:** Posts today's event with RSVP buttons
- **Where:** Your designated events channel

### Smart Reminders
- **4:00 PM Eastern:** Daily reminder about tonight's event
- **1 hour before:** Reminder 1 hour before event starts
- **15 minutes before:** Final reminder 15 minutes before event

## 🔍 Troubleshooting Commands

### If Commands Don't Appear
1. Use `/force_sync` to refresh commands
2. Wait up to 1 hour for Discord to update
3. Make sure the bot has "Use Slash Commands" permission

### If Commands Seem Slow or Timeout
1. Look for progress updates (🔄 messages) - the bot is working
2. Commands now show real-time status instead of "thinking"
3. Most commands complete in 1-2 seconds with parallel processing
4. If a command times out, it may still complete successfully

### If Setup Gets Stuck
1. Wait for the current setup to finish
2. Or restart the bot and try again
3. Use `/list_commands` to see available options

### If Setup Commands Fail with "Interaction Already Acknowledged"
1. **This error has been fixed** - the bot now handles Discord's interaction timing automatically
2. If you still see this error, simply **try the command again**
3. Failed setups now **automatically clean up** their state so you can retry immediately
4. The bot will show clear error messages if timing issues occur
5. You can safely retry `/setup_weekly_schedule` or `/edit_event` without restarting the bot

### If Modals Don't Appear
1. The bot now checks for interaction timing issues before sending modals
2. If a modal fails to appear, you'll get a clear error message
3. Simply **try the command again** - no need to restart or wait
4. Common modal commands that are now more reliable:
   - `/setup_weekly_schedule`
   - `/edit_event`
   - Clicking "Continue to Next Day" during setup

### If Reminders Aren't Working
1. Check your reminder settings with `/configure_reminders`
2. Make sure you set an event time with `/set_event_time`
3. Verify the bot can send messages in your event channel

### If Duplicate Posts Appear
1. The bot now automatically deletes previous posts before creating new ones
2. Make sure the bot has "Manage Messages" permission in the event channel
3. Use `/delete_message` to manually remove specific unwanted messages

### If Database Errors Occur
The bot now provides detailed error messages instead of cryptic errors like "[Errno -2] Name or service not known". Here's what each error type means:

**🚨 DNS Resolution Failed:**
- Your Supabase project may have expired or been deleted
- Check your project status at https://supabase.com
- Verify your SUPABASE_URL in .env file is correct
- Try creating a new Supabase project if the current one no longer exists

**🚨 Connection Timeout:**
- Check your internet connection
- Verify firewall settings aren't blocking the connection
- Check Supabase service status at https://status.supabase.com

**🚨 Authentication Error:**
- Your SUPABASE_KEY may be invalid or expired
- Check your Supabase project settings
- Regenerate your API key if needed
- Update your .env file with the correct SUPABASE_KEY

**🚨 Generic Database Error:**
- Double-check your Supabase URL and key in the `.env` file
- Make sure you ran all the SQL files in Supabase
- Check that your Supabase project is active
- Try restarting the bot

## 📋 Command Summary Table

| Command | Purpose | Who Can Use | Required Setup |
|---------|---------|-------------|----------------|
| `/setup_weekly_schedule` | Create weekly events | Admins | None |
| `/view_schedule` | View all events | Admins | Schedule must exist |
| `/edit_event` | Modify events | Admins | Schedule must exist |
| `/set_event_channel` | Choose posting channel | Admins | None |
| `/set_event_time` | Set event start time | Admins | None |
| `/configure_reminders` | Control reminders | Admins | None |
| `/set_admin_channel` | Set admin notification channel | Admins | None |
| `/view_rsvps` | See today's responses | Everyone | Event must be posted |
| `/view_yesterday_rsvps` | See yesterday's responses | Everyone | Event must have been posted |
| `/delete_message` | Delete a specific message by ID | Admins | None |
| `/list_commands` | Show all commands | Admins | None |
| `/force_sync` | Fix command issues | Admins | None |

## 🎯 Quick Start Guide

1. **Set up your schedule:** `/setup_weekly_schedule`
2. **Choose where to post:** `/set_event_channel #your-channel`
3. **Set event time:** `/set_event_time hour:20 minute:0`
4. **Turn on reminders:** `/configure_reminders enabled:true`
5. **Test it:** Wait for the next daily post or use `/view_schedule`

---

*Need help? Check the main README.md for detailed setup instructions and troubleshooting tips.* 

## 🩺 Monitoring & Diagnostics Commands

### `/bot_status`
**What it does:** Shows the bot's current status, uptime, number of servers, latency, and reconnection attempts.

**How to use:**
1. Type `/bot_status`
2. The bot will display an embed with status and uptime info

### `/monitor_status`
**What it does:** Shows detailed monitoring information including memory usage, CPU usage, latency, and warnings if any issues are detected.

**How to use:**
1. Type `/monitor_status`
2. The bot will display an embed with detailed monitoring and performance info

### `/test_connection`
**What it does:** Tests the bot's connection to Discord and the database, and reports latency.

**How to use:**
1. Type `/test_connection`
2. The bot will display an embed with the results of the connection tests

---

Mention these commands in the troubleshooting section as ways to check bot health and diagnose issues. 