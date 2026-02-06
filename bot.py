import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
import os
from datetime import datetime, timezone

# ✅ Token is now read from environment variables
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1379141195388813393  # Replace with your server ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

MONITOR_FILE = "monitors.json"
SEEN_FILE = "seen.json"

# -------- HELPER FUNCTIONS --------
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

monitors = load_json(MONITOR_FILE, [])
seen = load_json(SEEN_FILE, {})

def build_url(keyword, max_price):
    """Builds a Vinted API URL for the monitor"""
    return (
        "https://www.vinted.co.uk/api/v2/catalog/items?"
        f"search_text={keyword}"
        f"&price_to={max_price}"
        "&order=newest_first"
        "&per_page=20"
    )

def estimate_total(price):
    """Estimate total cost including buyer fee and shipping"""
    buyer_fee = price * 0.05 + 0.7
    shipping = 2.99
    total = price + buyer_fee + shipping
    return buyer_fee, shipping, total

def time_ago(timestamp):
    """Convert Vinted ISO time to minutes ago"""
    now = datetime.now(timezone.utc)
    item_time = datetime.fromisoformat(timestamp.replace("Z","+00:00"))
    diff = now - item_time
    minutes = int(diff.total_seconds() / 60)
    return f"{minutes} min ago"

# -------- DISCORD EVENTS --------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Commands synced")
    fast_monitor.start()

# -------- SLASH COMMANDS --------
@tree.command(name="monitor", description="Create a Vinted monitor", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(keyword="Keyword (example: nike)", max_price="Maximum price", channel="Channel for alerts")
async def monitor(interaction: discord.Interaction, keyword: str, max_price: int, channel: discord.TextChannel):
    url = build_url(keyword, max_price)
    monitors.append({
        "keyword": keyword,
        "price": max_price,
        "channel": channel.id,
        "url": url
    })
    save_json(MONITOR_FILE, monitors)
    await interaction.response.send_message(
        f"✅ Monitoring '{keyword}' under £{max_price} in {channel.mention}"
    )

@tree.command(name="monitors", description="List active monitors", guild=discord.Object(id=GUILD_ID))
async def monitors_list(interaction: discord.Interaction):
    if not monitors:
        await interaction.response.send_message("No active monitors")
        return
    msg = ""
    for m in monitors:
        ch = bot.get_channel(m["channel"])
        msg += f"{m['keyword']} → {ch.mention}\n"
    await interaction.response.send_message(msg)

@tree.command(name="test", description="Test the bot", guild=discord.Object(id=GUILD_ID))
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot is online and working!")

# -------- MONITOR LOOP --------
@tasks.loop(seconds=5)
async def fast_monitor():
    async with aiohttp.ClientSession() as session:
        headers = {"User-Agent":"Mozilla/5.0"}
        for m in monitors:
            try:
                async with session.get(m["url"], headers=headers) as resp:
                    data = await resp.json()
                items = data.get("items", [])
                channel = bot.get_channel(m["channel"])
                for item in items:
                    item_id = str(item["id"])
                    if item_id in seen:
                        continue
                    seen[item_id] = True
                    save_json(SEEN_FILE, seen)
                    # Extract info
                    title = item["title"]
                    price = float(item["price"]["amount"])
                    brand = item.get("brand_title", "Unknown")
                    size = item.get("size_title", "Unknown")
                    image = item["photo"]["url"]
                    url = item["url"]
                    user = item["user"]["login"]
                    rating = item["user"].get("feedback_reputation", 0)
                    created = item["created_at"]
                    ago = time_ago(created)
                    fee, shipping, total = estimate_total(price)
                    # Build embed
                    embed = discord.Embed(title=title, url=url, color=0x00ff00)
                    embed.set_image(url=image)
                    embed.add_field(name="Price", value=f"£{price}", inline=True)
                    embed.add_field(name="Brand", value=brand, inline=True)
                    embed.add_field(name="Size", value=size, inline=True)
                    embed.add_field(name="Seller", value=f"{user} ⭐{rating}", inline=True)
                    embed.add_field(name="Posted", value=ago, inline=True)
                    embed.add_field(
                        name="Total Cost",
                        value=f"Item: £{price}\nBuyer fee: £{fee:.2f}\nShipping: £{shipping}\nTotal: £{total:.2f}",
                        inline=False
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                print("Monitor error:", e)

# -------- RUN BOT --------
bot.run(TOKEN)
