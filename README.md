# Discord RSVP Bot

A friendly Discord bot that helps your community organize weekly events with easy RSVP tracking, automatic reminders, and support for mobile users. Perfect for gaming groups, clubs, or any community that meets regularly!

## ✨ What This Bot Does

- **📅 Weekly Planning**: Set up your events for each day of the week (like "Monday Raid Night" or "Wednesday Training")
- **🎯 Easy RSVPs**: Members can quickly respond with Yes, No, Maybe, or Mobile with just one click
- **⏰ Smart Reminders**: Automatically reminds people about upcoming events
- **📱 Mobile Friendly**: Special RSVP option for members on mobile devices
- **👥 Attendance Tracking**: See who's coming to each event
- **🔄 Automatic Posts**: Posts daily events automatically so you don't have to remember

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

2. **Start the bot**
   ```bash
   python main.py
   ```

## 🎮 Setting Up Your Events

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

### Example Weekly Schedule

Here's what a typical setup might look like:

- **Monday**: "Raid Night" | Combat Gear | Tank
- **Tuesday**: "PvP Tournament" | Light Armor | Fast Car  
- **Wednesday**: "Training Session" | Practice Gear | Motorcycle
- **Thursday**: "Casual Night" | Comfortable Clothes | Any Vehicle
- **Friday**: "Weekend Prep" | Weekend Gear | SUV

## 📋 How Members Use the Bot

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
| `/setup_weekly_schedule` | Create or change your weekly events | Server Admins |
| `/set_event_channel` | Choose where events are posted | Server Admins |
| `/set_event_time` | Set what time events start | Server Admins |
| `/configure_reminders` | Control when reminders are sent | Server Admins |
| `/view_rsvps` | See who's coming today | Everyone |
| `/view_yesterday_rsvps` | Check yesterday's attendance | Everyone |
| `/list_commands` | See all available commands | Server Admins |
| `/force_sync` | Fix command display issues | Server Admins |

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

### "Setup Already in Progress" Error?
- Wait for the current setup to finish, or restart the bot

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

- ✅ **Mobile Support**: Special RSVP option for mobile users
- ✅ **Smart Reminders**: Automatic reminders at multiple times
- ✅ **Easy Setup**: Step-by-step weekly schedule creation
- ✅ **Attendance Tracking**: See exactly who's coming to events
- ✅ **User-Friendly**: Clear, simple commands and explanations

---

**Happy organizing! 🎮✨**