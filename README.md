# Discord RSVP Bot

A comprehensive Discord bot that helps manage weekly event schedules with RSVP tracking, automatic reminders, and mobile support for gaming communities and organized groups.

## 🎯 Features

- **Weekly Schedule Setup**: Configure events for each day of the week with event names, outfits/gear, and vehicles
- **Interactive Setup**: Easy-to-use modal forms for configuring weekly schedules
- **RSVP System**: Four response options (Yes, No, Maybe, Mobile) with persistent buttons
- **Automatic Daily Posting**: Events posted automatically at 9 AM UTC daily
- **Smart Reminder System**: Configurable reminders (1 hour, 15 minutes, 5 minutes before events)
- **Timezone Support**: Events stored in Eastern time, displayed in multiple timezones
- **Database Integration**: Persistent storage using Supabase with duplicate prevention
- **Admin Controls**: Restricted to users with "Manage Server" permissions
- **Mobile Support**: Dedicated RSVP option for mobile users

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Supabase account and project
- Discord Bot Token
- Server with "Manage Server" permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/discord-rsvp-bot.git
   cd discord-rsvp-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your_supabase_anon_key_here
   ```
   
   **Getting your Supabase credentials:**
   - Go to your [Supabase Dashboard](https://supabase.com/dashboard)
   - Select your project (or create a new one)
   - Go to Settings → API
   - Copy the **Project URL** (for `SUPABASE_URL`)
   - Copy the **anon public** key (for `SUPABASE_KEY`)

4. **Set up the database**
   
   In your Supabase dashboard:
   - Go to the SQL Editor
   - Run the contents of `supabase_schema.sql` to create the required tables
   - Run `migration_add_mobile_rsvp.sql` to add mobile RSVP support
   - Run `migration_add_reminder_system.sql` to add reminder system support
   - Run `migration_add_4pm_reminder.sql` to add 4:00 PM reminder support
   - Copy your project URL and anon key to the `.env` file

5. **Run the bot**
   ```bash
   python main.py
   ```

## 🎮 How to Use

### Initial Setup

1. **Invite the bot** to your Discord server with the following permissions:
   - Send Messages
   - Use Slash Commands
   - Manage Messages
   - View Members (for RSVP tracking)

2. **Set up your weekly schedule**:
   ```
   /setup_weekly_schedule
   ```
   *Note: Only users with "Manage Server" permission can use this command*

3. **Configure your event channel**:
   ```
   /set_event_channel #your-events-channel
   ```

4. **Set event time** (Eastern Time):
   ```
   /set_event_time hour:20 minute:0
   ```
   This sets events to start at 8:00 PM Eastern Time

5. **Configure reminders**:
   ```
   /configure_reminders enabled:true four_pm:true one_hour:true fifteen_minutes:true
   ```

### Weekly Schedule Setup

The bot will present a modal for each day of the week (Monday through Sunday). For each day, provide:

- **Event Name**: The name of the event/activity
- **Outfit**: Required gear, clothing, or loadout
- **Vehicle**: Transportation or vehicle type needed

**Example Setup:**
- **Monday**: Raid Night | Combat Gear | Tank
- **Tuesday**: PvP Tournament | Light Armor | Fast Car
- **Wednesday**: Training Session | Practice Gear | Motorcycle

### RSVP System

Once daily events are posted, users can RSVP using four options:

- **✅ Yes**: Attending (desktop/regular)
- **❌ No**: Not attending
- **❓ Maybe**: Maybe attending
- **📱 Mobile**: Attending on mobile device

Users can change their RSVP at any time by clicking a different button.

### Automatic Features

- **Daily Posting**: Events automatically post at 9:00 AM Eastern Time
- **Reminders**: Automatic reminders sent based on your settings:
  - 4:00 PM Eastern (default: enabled)
  - 1 hour before event (default: enabled)
  - 15 minutes before event (default: enabled)

## 🛠️ Commands

| Command | Description | Permissions Required |
|---------|-------------|---------------------|
| `/setup_weekly_schedule` | Set up or modify the weekly event schedule | Manage Server |
| `/set_event_channel` | Set the channel for daily event posts | Manage Server |
| `/set_event_time` | Set event start time (Eastern Time) | Manage Server |
| `/configure_reminders` | Configure reminder settings | Manage Server |
| `/test_daily_event` | Test daily event posting | Manage Server |
| `/test_reminder` | Test reminder system (10/20 second test) | Manage Server |
| `/view_rsvps` | View RSVP responses for today's event | Manage Server |
| `/view_yesterday_rsvps` | View RSVP responses for yesterday's event | Manage Server |
| `/list_commands` | List all available commands | Manage Server |
| `/force_sync` | Force sync commands to Discord | Manage Server |
| `/test_command` | Test if slash commands are working | Manage Server |

## 🧪 Testing Guide

### Quick Test Sequence

1. **Set Up Your Server** (One-time setup)
   ```
   /setup_weekly_schedule
   /set_event_channel #your-events-channel
   /set_event_time hour:20 minute:0
   /configure_reminders enabled:true four_pm:true one_hour:true fifteen_minutes:true
   ```

2. **Test Daily Event Posting**
   ```
   /test_daily_event
   ```
   - Should post event in designated channel
   - Shows today's event with RSVP buttons
   - Displays event name, outfit, and vehicle

3. **Test RSVP Functionality**
   - Click each RSVP button (✅ Yes, ❌ No, ❓ Maybe, 📱 Mobile)
   - Bot should respond with confirmation
   - Test changing responses multiple times

4. **View RSVP Results**
   ```
   /view_rsvps
   ```
   - Shows summary of all RSVPs
   - Lists users under each category
   - Shows total response count

5. **Test Reminder System**
   ```
   /test_reminder
   ```
   - First reminder after 10 seconds
   - Second reminder after 20 seconds
   - Both tag @everyone with event details

### Production Testing Checklist

- [ ] Events post automatically at 9 AM UTC
- [ ] RSVP buttons work and persist through restarts
- [ ] Users can change their RSVP responses
- [ ] Admin can view RSVP summary with user names
- [ ] Reminders sent at configured times
- [ ] Timezone display shows Eastern and UTC times
- [ ] Mobile RSVP option works correctly

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | `MTM4ODI4MzI5OTU2MjI2MjU1OQ...` |
| `SUPABASE_URL` | Your Supabase project URL | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon key | `eyJhbGciOiJIUzI1NiIsInR...` |

### Database Schema

The bot uses several tables:
- `weekly_schedules`: Stores the weekly event data for each Discord server
- `daily_posts`: Tracks daily event posts for RSVP management
- `rsvp_responses`: Stores user RSVP responses (yes/no/maybe/mobile)
- `guild_settings`: Stores server configuration (channels, times, reminders)
- `reminder_sends`: Prevents duplicate reminder sends

### Dependencies

- `disnake`: Discord API library for Python
- `supabase`: Official Supabase Python client
- `python-dotenv`: Environment variable management
- `pytz`: Timezone handling
- `aiofiles`: Async file operations

## 🚀 Deployment

### Option 1: Railway (Recommended)
1. Connect your GitHub repository to [Railway](https://railway.app)
2. Add environment variables in the Railway dashboard
3. Deploy automatically

### Option 2: Heroku
1. Create a new app on [Heroku](https://heroku.com)
2. Connect to GitHub or use Heroku CLI
3. Set config vars for environment variables
4. Deploy

### Option 3: VPS/Self-Hosted
1. Clone repository on your server
2. Set up environment variables
3. Install dependencies: `pip install -r requirements.txt`
4. Run with process manager like PM2 or systemd

## 🔍 Troubleshooting

### Common Issues

**"Environment variable not set" error:**
- Ensure your `.env` file is in the root directory
- Check that environment variables are properly set on your hosting platform

**Database connection errors:**
- Verify your Supabase URL and API key are correct
- Ensure your Supabase project is active and accessible
- Check that all migration files have been applied in the SQL Editor
- Make sure Row Level Security (RLS) policies are configured correctly

**Bot not responding to commands:**
- Verify the bot has proper permissions in your Discord server
- Check that the bot is online and connected
- Use `/force_sync` to resync slash commands
- Ensure slash commands are synced (may take up to 1 hour)

**"Unknown User" in RSVP lists:**
- Bot needs "View Members" permission
- Users may have left the server or blocked the bot
- Bot will try to fetch user info from Discord API as fallback

**Reminders not sending:**
- Check reminder settings with `/configure_reminders`
- Verify event time is set with `/set_event_time`
- Ensure event channel is configured
- Check bot has permissions to send messages in event channel

**Setup already in progress:**
- If you get this error, wait for the current setup to complete or restart the bot

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 📋 Future Features

- User attendance statistics and analytics
- Custom time zones per server
- Event modification commands
- Bulk RSVP management
- Integration with calendar systems
- Advanced reminder customization

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you need help or have questions:
1. Check the troubleshooting section above
2. Review the testing guide for common issues
3. Create an issue on GitHub
4. Make sure to include error messages and relevant logs

## 🎉 What's New

### Latest Updates
- ✅ **Mobile RSVP Support**: Dedicated button for mobile users
- ✅ **Full Reminder System**: Configurable automatic reminders
- ✅ **Timezone Support**: Eastern time storage with multi-timezone display
- ✅ **Enhanced RSVP Tracking**: Better user name resolution
- ✅ **Duplicate Prevention**: No more duplicate reminders
- ✅ **Improved Testing**: Comprehensive testing guide included