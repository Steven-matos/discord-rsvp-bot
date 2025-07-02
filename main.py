import os
import disnake
from disnake.ext import commands
import database

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Set up bot intents
intents = disnake.Intents.default()
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.message_content = False

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has successfully logged in and is now online!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} guilds')
    
    # Initialize database connection pool
    try:
        await database.init_db_pool()
        print("Database connection pool initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database pool: {e}")

# Load extensions
async def load_cogs():
    try:
        bot.load_extension('cogs.schedule')
        print("Successfully loaded cogs.schedule")
    except Exception as e:
        print(f"Failed to load cogs.schedule: {e}")

@bot.event
async def on_connect():
    await load_cogs()

# Cleanup when bot shuts down
@bot.event
async def on_disconnect():
    print("Bot is disconnecting, closing database pool...")
    await database.close_db_pool()

if __name__ == "__main__":
    # Load Discord bot token from environment variable
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not discord_token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set")
    
    try:
        bot.run(discord_token)
    finally:
        # Ensure database pool is closed on exit
        import asyncio
        asyncio.run(database.close_db_pool()) 