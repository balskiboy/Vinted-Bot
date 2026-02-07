import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os

# ========================
# VARIABLES (FROM RAILWAY)
# ========================

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# ========================
# DISCORD SETUP
# ========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

MONITORS_FILE = "monitors.json"
SEEN_FILE = "seen.json"

# ========================
# FILE FUNCTIONS
# ========================

def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

monitors = load_json(MONITORS_FILE, [])
seen = load_json(SEEN_FILE, {})

# ========================
# FETCH VINTED ITEMS
# ========================

async def fetch_items(session):

    url = "https://www.vinted.co.uk/api/v2/catalog/items"

    params = {
        "page": 1,
        "per_page": 20,
        "order": "newest_first"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.vinted.co.uk/",
        "Origin": "https://www.vinted.co.uk",
        "Connection": "keep-alive"
    }

    try:

        async with session.get(url, headers=headers, params=params) as resp:

            print("Vinted response:", resp.status)

            if resp.status != 200:
                text = await resp.text()
                print("Error body:", text)
                return []

            data = await resp.json()

            items = data.get("items", [])

            print("Items fetched:", len(items))

            return items

    except Exception as e:

        print("Fetch error:", e)
        return []


# ========================
# DASHBOARD COMMAND
# ========================

@bot.tree.command(name="dashboard", description="Create a monitor", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    brand="Brand name",
    max_price="Maximum price",
    channel="Channel for alerts"
)
async def dashboard(interaction: discord.Interaction, brand: str, max_price: int, channel: discord.TextChannel):

    monitor = {
        "brand": brand.lower(),
        "max_price": max_price,
        "channel": channel.id
    }

    monitors.append(monitor)
    save_json(MONITORS_FILE, monitors)

    await interaction.response.send_message(
        f"✅ Monitor created in {channel.mention}",
        ephemeral=True
    )

# ========================
# LIST MONITORS
# ========================

@bot.tree.command(name="monitors", description="View monitors", guild=discord.Object(id=GUILD_ID))
async def monitors_cmd(interaction: discord.Interaction):

    if not monitors:
        await interaction.response.send_message("No monitors active.")
        return

    msg = ""

    for m in monitors:

        channel = bot.get_channel(m["channel"])

        msg += f"Brand: {m['brand']} | Price ≤ £{m['max_price']} | Channel: {channel.mention}\n"

    await interaction.response.send_message(msg)

# ========================
# TEST COMMAND
# ========================

@bot.tree.command(name="test", description="Test bot", guild=discord.Object(id=GUILD_ID))
async def test(interaction: discord.Interaction):

    await interaction.response.send_message("✅ Bot working")

# ========================
# MONITOR LOOP
# ========================

@tasks.loop(seconds=20)
async def monitor_task():

    await bot.wait_until_ready()

    async with aiohttp.ClientSession() as session:

        items = await fetch_items(session)

        for monitor in monitors:

            channel = bot.get_channel(monitor["channel"])

            if not channel:
                continue

            if str(channel.id) not in seen:
                seen[str(channel.id)] = []

            for item in items:

                item_id = str(item["id"])

                if item_id in seen[str(channel.id)]:
                    continue

                title = item.get("title", "").lower()
                price = float(item.get("price", {}).get("amount", 0))

                if monitor["brand"] not in title:
                    continue

                if price > monitor["max_price"]:
                    continue

                seen[str(channel.id)].append(item_id)
                save_json(SEEN_FILE, seen)

                embed = discord.Embed(
                    title=item.get("title"),
                    url=item.get("url"),
                    description=f"£{price}",
                    color=discord.Color.green()
                )

                embed.add_field(
                    name="Seller",
                    value=item.get("user", {}).get("login", "Unknown")
                )

                image = item.get("photo", {}).get("url")

                if image:
                    embed.set_thumbnail(url=image)

                await channel.send(embed=embed)

# ========================
# READY EVENT
# ========================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)

    synced = await bot.tree.sync(guild=guild)

    print(f"Commands synced: {len(synced)}")

    monitor_task.start()

# ========================
# START BOT
# ========================

bot.run(TOKEN)
