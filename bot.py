import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select, Button, ChannelSelect
import aiohttp
import json
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

MONITOR_FILE = "monitors.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------- LOAD / SAVE ----------

def load_json(file):
    if not os.path.exists(file):
        return []
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

monitors = load_json(MONITOR_FILE)
seen_items = set()

# ---------- BUILD URL ----------

def build_url(keyword, price):

    keyword = keyword.replace(" ", "%20")

    return f"https://www.vinted.co.uk/api/v2/catalog/items?search_text={keyword}&price_to={price}&order=newest_first"

# ---------- FETCH ITEMS ----------

async def fetch_items(url):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:

            if resp.status != 200:
                return []

            data = await resp.json()

            return data.get("items", [])

# ---------- CALCULATE EXTRA COSTS ----------

def calculate_total(price):

    buyer_fee = price * 0.05 + 0.7
    shipping = 2.99

    total = price + buyer_fee + shipping

    return round(total, 2), round(buyer_fee, 2), shipping

# ---------- SEND ITEM ----------

async def send_item(channel, item):

    item_id = item["id"]

    if item_id in seen_items:
        return

    seen_items.add(item_id)

    title = item["title"]
    price = float(item["price"]["amount"])
    brand = item.get("brand_title", "Unknown")
    size = item.get("size_title", "Unknown")
    image = item["photo"]["url"]
    url = item["url"]

    seller = item["user"]["login"]
    rating = item["user"].get("feedback_reputation", 0)

    total, fee, shipping = calculate_total(price)

    embed = discord.Embed(
        title=title,
        url=url,
        color=0x00ff99
    )

    embed.set_thumbnail(url=image)

    embed.add_field(name="💰 Price", value=f"£{price}", inline=True)
    embed.add_field(name="🏷 Brand", value=brand, inline=True)
    embed.add_field(name="📏 Size", value=size, inline=True)

    embed.add_field(name="👤 Seller", value=seller, inline=True)
    embed.add_field(name="⭐ Rating", value=f"{rating}", inline=True)

    embed.add_field(name="💸 Buyer Fee", value=f"£{fee}", inline=True)
    embed.add_field(name="🚚 Shipping", value=f"£{shipping}", inline=True)
    embed.add_field(name="💵 Total Cost", value=f"£{total}", inline=True)

    await channel.send(embed=embed)

# ---------- MONITOR LOOP ----------

@tasks.loop(seconds=15)
async def monitor_loop():

    await bot.wait_until_ready()

    for monitor in monitors:

        channel = bot.get_channel(monitor["channel"])

        if not channel:
            continue

        items = await fetch_items(monitor["url"])

        for item in items[:5]:
            await send_item(channel, item)

# ---------- DASHBOARD ----------

sessions = {}

@tree.command(name="dashboard", description="Open Vinted dashboard", guild=discord.Object(id=GUILD_ID))
async def dashboard(interaction: discord.Interaction):

    sessions[interaction.user.id] = {
        "brand": "",
        "category": "",
        "size": "",
        "price": 100,
        "channel": interaction.channel.id
    }

    brand = discord.ui.TextInput(label="Brand", placeholder="Nike, Stussy, Zara, ANY brand")

    category = discord.ui.TextInput(label="Category", placeholder="Shoes, Hoodie, Jacket")

    size = discord.ui.TextInput(label="Size", placeholder="S, M, L, XL")

    price = discord.ui.TextInput(label="Max Price", placeholder="40")

    class Modal(discord.ui.Modal, title="Create Monitor"):

        brand_input = brand
        category_input = category
        size_input = size
        price_input = price

        async def on_submit(self, interaction2):

            keyword = f"{self.brand_input.value} {self.category_input.value} {self.size_input.value}"

            url = build_url(keyword, int(self.price_input.value))

            monitors.append({
                "keyword": keyword,
                "price": int(self.price_input.value),
                "channel": interaction.channel.id,
                "url": url
            })

            save_json(MONITOR_FILE, monitors)

            await interaction2.response.send_message(
                f"✅ Monitor created\n{keyword}\nMax price £{self.price_input.value}"
            )

    await interaction.response.send_modal(Modal())

# ---------- VIEW MONITORS ----------

@tree.command(name="monitors", description="View monitors", guild=discord.Object(id=GUILD_ID))
async def view_monitors(interaction: discord.Interaction):

    if not monitors:
        await interaction.response.send_message("No monitors active")
        return

    text = ""

    for m in monitors:
        text += f"{m['keyword']} - £{m['price']}\n"

    await interaction.response.send_message(text)

# ---------- READY ----------

@bot.event
async def on_ready():

    await tree.sync(guild=discord.Object(id=GUILD_ID))

    print(f"Logged in as {bot.user}")

    monitor_loop.start()

bot.run(TOKEN)
