import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import os

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

tree = bot.tree

# Store seen items
seen_items = set()

# Your channel ID where alerts will be sent
CHANNEL_ID = None


# ---------------- BOT READY ---------------- #

@bot.event
async def on_ready():

    guild = discord.Object(id=GUILD_ID)

    tree.copy_global_to(guild=guild)

    synced = await tree.sync(guild=guild)

    print(f"Logged in as {bot.user}")
    print(f"Commands synced: {len(synced)}")

    tracker.start()


# ---------------- DASHBOARD COMMAND ---------------- #

@tree.command(name="dashboard", description="Open tracker dashboard")
async def dashboard(interaction: discord.Interaction):

    global CHANNEL_ID

    CHANNEL_ID = interaction.channel.id

    embed = discord.Embed(
        title="📊 Vinted Tracker Dashboard",
        description="Tracker is now active in this channel",
        color=0x00ff00
    )

    embed.add_field(name="Status", value="🟢 Running", inline=False)
    embed.add_field(name="Channel", value=f"<#{CHANNEL_ID}>", inline=False)

    await interaction.response.send_message(embed=embed)


# ---------------- FETCH ITEMS ---------------- #

async def fetch_items():

    url = "https://www.vinted.co.uk/api/v2/catalog/items?per_page=10&order=newest_first"

    async with aiohttp.ClientSession() as session:

        async with session.get(url, headers=HEADERS) as resp:

            print("Vinted response:", resp.status)

            if resp.status != 200:
                return []

            data = await resp.json()

            return data.get("items", [])


# ---------------- SEND ITEM ---------------- #

async def send_item(item):

    if CHANNEL_ID is None:
        return

    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        return

    title = item.get("title", "No title")
    price = item.get("price", {}).get("amount", "0")
    brand = item.get("brand_title", "Unknown")
    size = item.get("size_title", "Unknown")
    url = item.get("url", "")
    image = item.get("photo", {}).get("url", "")

    embed = discord.Embed(
        title=title,
        url=url,
        color=0x00ffcc
    )

    embed.add_field(name="💰 Price", value=f"£{price}")
    embed.add_field(name="🏷 Brand", value=brand)
    embed.add_field(name="📏 Size", value=size)

    embed.set_image(url=image)

    await channel.send(embed=embed)


# ---------------- TRACKER LOOP ---------------- #

@tasks.loop(seconds=30)
async def tracker():

    items = await fetch_items()

    for item in items:

        item_id = item.get("id")

        if item_id not in seen_items:

            seen_items.add(item_id)

            await send_item(item)


# ---------------- RUN ---------------- #

bot.run(TOKEN)
