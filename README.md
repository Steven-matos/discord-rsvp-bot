# Discord RSVP Bot

A friendly Discord bot that helps your community organize weekly events with easy RSVP tracking, automatic reminders, and support for mobile users. Perfect for gaming groups, clubs, or any community that meets regularly!

## ✨ What This Bot Does

- **📅 Weekly Planning**: Set up your events for each day of the week (like "Monday Raid Night" or "Wednesday Training")
- **🎯 Easy RSVPs**: Members can quickly respond with Yes, No, Maybe, or Mobile with just one click
- **⏰ Smart Reminders**: Automatically reminds people about upcoming events
- **📱 Mobile Friendly**: Special RSVP option for members on mobile devices
- **👥 Attendance Tracking**: See who's coming to each event
- **🔄 Automatic Posts**: Posts daily events automatically so you don't have to remember
- **🔧 Manual Override**: Force post RSVPs if automatic posting fails
- **👑 Admin Access**: Specific user ID can access all admin commands regardless of role

## 🚀 Getting Started

### What You'll Need

- A Discord server where you have admin permissions
- A free Supabase account (for storing your data)
- About 10 minutes to set everything up

### Step 1: Set Up Your Bot

1. **Download the bot files**
   ```bash
   git clone https://github.com/yourusername/discord-rsvp-bot.git
   cd discord-rsvp-bot
   ```

2. **Install the required software**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create your configuration file**
   
   Create a file called `.env` in the bot folder and add:
   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your_supabase_anon_key_here
   ```

### Step 2: Set Up Your Database (Supabase)

1. **Create a free Supabase account**
   - Go to [supabase.com](https://supabase.com) and sign up
   - Create a new project

2. **Set up your database tables**
   - In your Supabase dashboard, go to "SQL Editor"
   - Copy and paste the contents of `database_schemas/supabase_schema.sql`
   - Click "Run" to create the tables
   - Do the same for the other migration files in the `database_schemas` folder

3. **Get your connection details**
   - Go to Settings → API in your Supabase dashboard
   - Copy the "Project URL" and "anon public" key
   - Put these in your `.env` file

### Step 3: Add the Bot to Your Server

1. **Invite the bot** to your Discord server with these permissions:
   - Send Messages
   - Use Slash Commands
   - Manage Messages
   - View Members
   - Embed Links

2. **Start the bot**
   ```bash
   python main.py
   ```

## 🎮 Setting Up Your Events

### Invite to Server

URL: https://discord.com/oauth2/authorize?client_id=1388283299562262559&permissions=1144344644123728&integration_type=0&scope=bot

### First Time Setup (5 minutes)

1. **Create your weekly schedule**
   ```
   /setup_weekly_schedule
   ```
   The bot will ask you about each day of the week. For each day, tell it:
   - What the event is called (like "Raid Night" or "Training")
   - What gear/outfit people need
   - What vehicle they should bring

2. **Choose where events will be posted**
   ```
   /set_event_channel #your-events-channel
   ```
   Pick the channel where you want daily event announcements to appear.

3. **Set your event time**
   ```
   /set_event_time hour:20 minute:0
   ```
   This example sets events to start at 8:00 PM Eastern Time.

4. **Turn on reminders**
   ```
   /configure_reminders enabled:true four_pm:true one_hour:true fifteen_minutes:true
   ```
   This sends reminders at 4 PM, 1 hour before, and 15 minutes before events.

5. **View and edit your schedule** (optional)
   ```
   /view_schedule
   ```
   See your complete weekly schedule. Use `/edit_event [day]` to modify any event.

### Example Weekly Schedule

Here's what a typical setup might look like:

- **Monday**: "Raid Night" | Combat Gear | Tank
- **Tuesday**: "PvP Tournament" | Light Armor | Fast Car  
- **Wednesday**: "Training Session" | Practice Gear | Motorcycle
- **Thursday**: "Casual Night" | Comfortable Clothes | Any Vehicle
- **Friday**: "Weekend Prep" | Weekend Gear | SUV

## 📋 How Members Use the Bot

## 🛠️ Managing Your Events

### Viewing Your Schedule
- **`/view_schedule`** - See your complete weekly schedule with all events
- Shows each day with event name, outfit, and vehicle requirements

### Editing Events
- **`/edit_event [day]`** - Modify any day's event
- Change the event name, outfit, or vehicle
- Updates take effect immediately for future posts
- Only admins can edit events

### RSVP Options

Once you set up your schedule, the bot will automatically post daily events. Members can then RSVP using these buttons:

- **✅ Yes** - "I'm coming!"
- **❌ No** - "I can't make it"
- **❓ Maybe** - "I might come"
- **📱 Mobile** - "I'm coming, but on mobile"

Members can change their mind anytime by clicking a different button.

### Viewing Attendance

Anyone can see who's coming to events:
- **`/view_rsvps`** - See today's RSVPs
- **`/view_yesterday_rsvps`** - Check yesterday's attendance

## 🛠️ Admin Commands

| Command | What It Does | Who Can Use |
|---------|-------------|-------------|
| `/setup_weekly_schedule` | Create or change your weekly events | Server Admins + Specific User |
| `/view_schedule` | View the current weekly schedule | Server Admins + Specific User |
| `/edit_event` | Edit an existing event for any day | Server Admins + Specific User |
| `/set_event_channel` | Choose where events are posted | Server Admins + Specific User |
| `/set_event_time` | Set what time events start | Server Admins + Specific User |
| `/configure_reminders` | Control when reminders are sent | Server Admins + Specific User |
| `/set_admin_channel` | Set admin notification channel | Server Admins + Specific User |
| `/force_post_rsvp` | Manually post today's RSVP if automatic posting fails | Server Admins + Specific User |
| `/view_rsvps` | See who's coming today | Everyone |
| `/view_yesterday_rsvps` | Check yesterday's attendance | Everyone |
| `/list_commands` | See all available commands | Server Admins + Specific User |
| `/force_sync` | Fix command display issues | Server Admins + Specific User |

## 🩺 Monitoring & Diagnostics

| Command | What It Does |
|---------|--------------|
| `/bot_status` | Check the bot's current status, uptime, and connection health |
| `/monitor_status` | Get detailed monitoring information including memory, CPU, and performance metrics |
| `/test_connection` | Test the bot's connection to Discord and database |

Mention these commands in troubleshooting and tips sections as ways to check bot health and diagnose issues.

## 🔧 Special Access

The bot includes a special access system for a specific user ID (300157754012860425) who can use all admin commands regardless of their role in the server. This provides backup access in case of permission issues.

## ⚙️ Automatic Features

The bot works automatically once you set it up:

- **Daily Posts**: Events appear automatically at 9:00 AM Eastern Time
- **Smart Reminders**: Sends reminders based on your settings:
  - 4:00 PM Eastern (daily reminder)
  - 1 hour before the event
  - 15 minutes before the event

## 🔧 Troubleshooting

### Bot Won't Start?
- Check your `.env` file has the right information
- Make sure you installed the requirements: `pip install -r requirements.txt`

### Commands Not Showing Up?
- Use `/force_sync` to refresh the commands
- Make sure the bot has "Use Slash Commands" permission
- Wait up to 1 hour for Discord to update

### Database Errors?
- Double-check your Supabase URL and key in the `.env` file
- Make sure you ran all the SQL files in Supabase
- Check that your Supabase project is active

### Reminders Not Working?
- Check your reminder settings with `/configure_reminders`
- Make sure you set an event time with `/set_event_time`
- Verify the bot can send messages in your event channel

### RSVP Posts Not Appearing?
- Use `/force_post_rsvp` to manually post today's RSVP
- Check bot permissions in the event channel (Send Messages, Embed Links)
- Verify the event channel is configured with `/set_event_channel`
- Ensure the weekly schedule is set up with `/setup_weekly_schedule`

### Permission Issues?
- The bot needs these permissions in the event channel:
  - Send Messages
  - Embed Links
- Ask a server admin to grant these permissions to the bot
- The specific user ID (300157754012860425) has access to all admin commands regardless of role

## 🎯 Tips for Success

1. **Start Simple**: Set up just a few days first, then add more
2. **Use Clear Names**: Make event names easy to understand
3. **Test Your Setup**: Try the RSVP buttons yourself first
4. **Check Permissions**: Make sure the bot has all the permissions it needs
5. **Keep It Updated**: The bot will automatically handle time changes and daylight saving

## 🆘 Need Help?

If something isn't working:
1. Check the troubleshooting section above
2. Make sure you followed all the setup steps
3. Try restarting the bot
4. Check that your Supabase project is still active

## 🎉 What's New

### Latest Update: Weekly Schedule Bug Fix ✅
**Fixed a critical bug where the bot would post outdated schedules when a new week wasn't set up.**

#### What Changed:
- **No More Outdated Posts**: Bot now checks if current week's schedule is set up before posting
- **Admin Notifications**: Sends admin alerts instead of posting old schedules when new week isn't configured
- **Smart Validation**: Compares schedule's last updated timestamp with current week
- **Anti-Spam**: Notifications limited to once per day per server
- **New Command**: `/set_admin_channel` to specify where admin notifications are sent

#### How It Works:
1. **Daily Check**: At 9 AM Eastern, bot validates current week's schedule
2. **Smart Response**: Posts normally if schedule is current, sends admin notification if outdated
3. **Admin Awareness**: Admins get notified when they need to set up the weekly schedule
4. **Flexible Configuration**: Choose where admin notifications are sent

#### Database Updates Required:
Run the safe migration file `database_schemas/complete_schema_update_safe.sql` in your Supabase SQL Editor to enable these features.

---

### Previous Features:
- ✅ **Event Editing**: Admins can now edit existing events with `/edit_event`
- ✅ **Schedule Viewing**: View your complete weekly schedule with `/view_schedule`
- ✅ **Mobile Support**: Special RSVP option for mobile users
- ✅ **Smart Reminders**: Automatic reminders at multiple times
- ✅ **Easy Setup**: Step-by-step weekly schedule creation
- ✅ **Attendance Tracking**: See exactly who's coming to events
- ✅ **User-Friendly**: Clear, simple commands and explanations

---

**Happy organizing! 🎮✨**