import discord
from discord.ext import commands, tasks
import os
import requests

# =========================
# LOAD VARIABLES FROM RAILWAY
# =========================

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# TEST COMMAND
# =========================

@bot.tree.command(
    name="test",
    description="Test if bot is working",
    guild=discord.Object(id=GUILD_ID)
)
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot is working!")

# =========================
# DASHBOARD COMMAND
# =========================

@bot.tree.command(
    name="dashboard",
    description="Open the dashboard",
    guild=discord.Object(id=GUILD_ID)
)
async def dashboard(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📊 Vinted Tracker Dashboard",
        description="Bot is online and ready.",
        color=0x00ff00
    )

    embed.add_field(name="Status", value="🟢 Online", inline=True)
    embed.add_field(name="Tracking", value="Active", inline=True)

    await interaction.response.send_message(embed=embed)

# =========================
# READY EVENT
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands to guild")
    except Exception as e:
        print(f"Sync error: {e}")

    print("Bot ready")

# =========================
# START BOT
# =========================

bot.run(TOKEN)
