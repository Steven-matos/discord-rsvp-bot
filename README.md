# Discord RSVP Bot

A Discord bot that helps manage weekly event schedules with RSVP tracking for gaming communities and organized groups.

## 🎯 Features

- **Weekly Schedule Setup**: Configure events for each day of the week with event names, outfits/gear, and vehicles
- **Interactive Setup**: Easy-to-use modal forms for configuring weekly schedules
- **Database Integration**: Persistent storage of schedules using Supabase
- **Admin Controls**: Restricted to users with "Manage Server" permissions
- **Future-Ready**: Built with extensibility for RSVP tracking and daily event posting

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
   - Copy your project URL and anon key to the `.env` file

5. **Run the bot**
   ```bash
   python main.py
   ```

## 🎮 How to Use

### Setting Up Your Weekly Schedule

1. **Invite the bot** to your Discord server with the following permissions:
   - Send Messages
   - Use Slash Commands
   - Manage Messages

2. **Run the setup command**:
   ```
   /setup_weekly_schedule
   ```
   *Note: Only users with "Manage Server" permission can use this command*

3. **Fill out the weekly schedule**:
   - The bot will present a modal for each day of the week (Monday through Sunday)
   - For each day, provide:
     - **Event Name**: The name of the event/activity
     - **Outfit**: Required gear, clothing, or loadout
     - **Vehicle**: Transportation or vehicle type needed

4. **Complete the setup**:
   - Fill out all 7 days to complete your weekly schedule
   - The bot will confirm when setup is complete
   - Your schedule is automatically saved to the database

### Example Usage

**Monday Setup:**
- Event Name: `Raid Night`
- Outfit: `Combat Gear`
- Vehicle: `Tank`

**Tuesday Setup:**
- Event Name: `PvP Tournament`
- Outfit: `Light Armor`
- Vehicle: `Fast Car`

...and so on for each day of the week.

## 🛠️ Commands

| Command | Description | Permissions Required |
|---------|-------------|---------------------|
| `/setup_weekly_schedule` | Set up or modify the weekly event schedule | Manage Server |

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | `MTM4ODI4MzI5OTU2MjI2MjU1OQ...` |
| `SUPABASE_URL` | Your Supabase project URL | `https://your-project-id.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon key | `eyJhbGciOiJIUzI1NiIsInR...` |

### Database Schema

The bot uses the following main table:
- `weekly_schedules`: Stores the weekly event data for each Discord server
- Each day's data is stored as JSON in columns like `monday_data`, `tuesday_data`, etc.

### Dependencies

The bot uses the following main dependencies:
- `disnake`: Discord API library for Python
- `supabase`: Official Supabase Python client for database operations
- `python-dotenv`: Environment variable management

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
- Check that the database schema has been applied in the SQL Editor
- Make sure Row Level Security (RLS) is disabled for the `weekly_schedules` table if you encounter permission errors

**Bot not responding to commands:**
- Verify the bot has proper permissions in your Discord server
- Check that the bot is online and connected
- Ensure slash commands are synced (may take up to 1 hour)

**Setup already in progress:**
- If you get this error, wait for the current setup to complete or restart the bot

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 📋 Future Features

- Automatic daily event posting
- RSVP tracking with reactions
- User attendance statistics
- Custom time zones per server
- Event reminders

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you need help or have questions:
1. Check the troubleshooting section above
2. Create an issue on GitHub
3. Make sure to include error messages and relevant logs