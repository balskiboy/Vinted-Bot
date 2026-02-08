import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os
from datetime import datetime, timezone

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SEARCH_FILE = "searches.json"
SEEN_FILE = "seen.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

tree = bot.tree

# Load searches
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

searches = load_json(SEARCH_FILE, [])
seen = load_json(SEEN_FILE, {})

# Vinted headers (fixes 401)
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.vinted.co.uk/",
}

# Fee calculator
def calculate_total(price):
    fee = 0.7 + price * 0.05
    shipping = 2.99
    return round(price + fee + shipping, 2)

# Time ago
def time_ago(timestamp):
    now = datetime.now(timezone.utc)
    diff = now - datetime.fromisoformat(timestamp.replace("Z","+00:00"))
    mins = int(diff.total_seconds() / 60)
    return f"{mins} mins ago"

# Fetch items
async def fetch_items(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as resp:

            if resp.status != 200:
                print("Vinted error:", resp.status)
                return []

            data = await resp.json()

            if "items" not in data:
                return []

            return data["items"]

# Create embed
def create_embed(item):

    price = float(item["price"]["amount"])
    total = calculate_total(price)

    embed = discord.Embed(
        title=item["title"],
        url=item["url"],
        color=0x09ff00
    )

    embed.add_field(name="💷 Price", value=f"£{price}", inline=True)
    embed.add_field(name="💰 Total", value=f"£{total}", inline=True)

    embed.add_field(
        name="📦 Size",
        value=item.get("size_title","N/A"),
        inline=True
    )

    embed.add_field(
        name="🏷 Brand",
        value=item.get("brand_title","N/A"),
        inline=True
    )

    embed.add_field(
        name="👤 Seller rating",
        value=str(item["user"].get("feedback_reputation", "0")),
        inline=True
    )

    embed.add_field(
        name="⏱ Listed",
        value=time_ago(item["created_at_ts"]),
        inline=True
    )

    if item.get("photo"):
        embed.set_thumbnail(url=item["photo"]["url"])

    return embed

# Background tracker
@tasks.loop(seconds=20)
async def tracker():

    for search in searches:

        channel = bot.get_channel(search["channel"])
        if not channel:
            continue

        items = await fetch_items(search["url"])

        if search["name"] not in seen:
            seen[search["name"]] = []

        for item in items[:5]:

            if item["id"] in seen[search["name"]]:
                continue

            seen[search["name"]].append(item["id"])

            embed = create_embed(item)
            await channel.send(embed=embed)

    save_json(SEEN_FILE, seen)

# Dashboard command
@tree.command(name="dashboard", description="Create tracker")
@app_commands.describe(
    channel="Channel to send items",
    keywords="Search words",
    max_price="Maximum price"
)
async def dashboard(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    keywords: str,
    max_price: int
):

    await interaction.response.defer(ephemeral=True)

    url = f"https://www.vinted.co.uk/api/v2/catalog/items?search_text={keywords}&price_to={max_price}&order=newest_first"

    searches.append({
        "name": keywords,
        "url": url,
        "channel": channel.id
    })

    save_json(SEARCH_FILE, searches)

    await interaction.followup.send(
        f"✅ Tracker created\n"
        f"Keywords: {keywords}\n"
        f"Max price: £{max_price}\n"
        f"Channel: {channel.mention}",
        ephemeral=True
    )

# List searches
@tree.command(name="list", description="List trackers")
async def list_trackers(interaction: discord.Interaction):

    if not searches:
        await interaction.response.send_message("No trackers", ephemeral=True)
        return

    msg = ""

    for s in searches:
        msg += f"{s['name']}\n"

    await interaction.response.send_message(msg, ephemeral=True)

# Sync commands and start
@bot.event
async def on_ready():

    guild = discord.Object(id=GUILD_ID)

    await tree.sync(guild=guild)

    print("Bot ready")
    tracker.start()

bot.run(TOKEN)
