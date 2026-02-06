import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os
import time
from datetime import datetime, timezone

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

MONITORS_FILE = "monitors.json"
SEEN_FILE = "seen.json"

# Load files
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

# WORKING Vinted fetch
async def fetch_items(session):
    url = "https://www.vinted.co.uk/api/v2/catalog/items?page=1&per_page=20&order=newest_first"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.vinted.co.uk/"
    }

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print("Bad response:", resp.status)
                return []
            data = await resp.json()
            return data.get("items", [])
    except Exception as e:
        print("Fetch error:", e)
        return []

# Dashboard command
@bot.tree.command(name="dashboard", description="Create a new Vinted monitor")
@app_commands.describe(
    brand="Brand name (optional)",
    category="Category (optional)",
    size="Size (optional)",
    max_price="Maximum price",
    channel="Channel to send alerts"
)
async def dashboard(interaction: discord.Interaction,
                    brand: str,
                    category: str,
                    size: str,
                    max_price: int,
                    channel: discord.TextChannel):

    monitor = {
        "brand": brand.lower() if brand else "",
        "category": category.lower() if category else "",
        "size": size.lower() if size else "",
        "max_price": max_price,
        "channel": channel.id
    }

    monitors.append(monitor)
    save_json(MONITORS_FILE, monitors)

    await interaction.response.send_message(
        f"✅ Monitor created in {channel.mention}",
        ephemeral=True
    )

# List monitors
@bot.tree.command(name="monitors", description="View active monitors")
async def monitors_cmd(interaction: discord.Interaction):

    if not monitors:
        await interaction.response.send_message("No monitors active.")
        return

    msg = ""

    for m in monitors:
        channel = bot.get_channel(m["channel"])
        msg += f"Brand: {m['brand']} Price ≤ £{m['max_price']} → {channel.mention}\n"

    await interaction.response.send_message(msg)

# Test command
@bot.tree.command(name="test", description="Test bot")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot working and monitoring")

# Monitor loop
@tasks.loop(seconds=15)
async def monitor_task():

    await bot.wait_until_ready()

    async with aiohttp.ClientSession() as session:

        items = await fetch_items(session)

        print(f"Fetched {len(items)} items")

        for monitor in monitors:

            channel = bot.get_channel(monitor["channel"])
            if not channel:
                continue

            if str(monitor["channel"]) not in seen:
                seen[str(monitor["channel"])] = []

            for item in items:

                item_id = str(item["id"])

                if item_id in seen[str(monitor["channel"])]:
                    continue

                title = item.get("title", "").lower()
                price = float(item.get("price", {}).get("amount", 0))

                # Filter checks
                if monitor["brand"] and monitor["brand"] not in title:
                    continue

                if price > monitor["max_price"]:
                    continue

                seen[str(monitor["channel"])].append(item_id)
                save_json(SEEN_FILE, seen)

                image = item.get("photo", {}).get("url", "")
                url = item.get("url", "")
                brand = item.get("brand_title", "Unknown")
                size = item.get("size_title", "Unknown")
                user = item.get("user", {})
                seller = user.get("login", "Unknown")
                rating = user.get("feedback_reputation", 0)

                embed = discord.Embed(
                    title=item.get("title"),
                    url=url,
                    description=f"£{price}",
                    color=discord.Color.green()
                )

                embed.add_field(name="Brand", value=brand)
                embed.add_field(name="Size", value=size)
                embed.add_field(name="Seller", value=seller)
                embed.add_field(name="Rating", value=f"{rating}⭐")

                if image:
                    embed.set_thumbnail(url=image)

                await channel.send(embed=embed)

# Ready event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

    monitor_task.start()

bot.run(TOKEN)
