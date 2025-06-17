import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from datetime import datetime, timedelta
import asyncio
import discord.errors

# Intents and bot setup
intents = discord.Intents.default()

class HuntBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(update_loop())

bot = HuntBot(command_prefix="!", intents=intents)

SERVER = "Halicarnassus"
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
CURRENT_MESSAGE = None
MESSAGE_PIN_KEY = "a_rank_tracker_pin"

A_RANKS = [
    "Queen Hawk", "Nechuciho", "The Raintriller", "Pkuucha",
    "Starcrier 1", "Rrax Yity'a 1", "Starcrier 2", "Rrax Yity'a 2",
    "Yehehetoaua'pyo", "Keheniheyamewi", "Heshuala",
    "Urna Variabilis", "Sally the Sweeper", "Cat's Eye"
]

STATUS = {rank: {"last_killed": datetime.utcnow()} for rank in A_RANKS}

# Displays time since kill and if it's 100% spawn chance
def get_spawn_status_display(last_killed):
    if last_killed is None:
        return "❓ Unknown"

    hours = (datetime.utcnow() - last_killed).total_seconds() / 3600
    hours_str = f"{hours:.1f}h"

    if hours >= 6:
        return f"🟢 {hours_str}"
    else:
        return f"🔴 {hours_str}"

def build_embed():
    embed = discord.Embed(title=f"🧭 {SERVER} – Dawntrail A-Ranks", color=0x00b0f4)
    for rank in A_RANKS:
        last_killed = STATUS[rank]["last_killed"]
        timer = get_spawn_status_display(last_killed)
        embed.add_field(name=rank, value=timer, inline=False)
    embed.set_footer(text="Tap a button to mark kill time.")
    return embed

class ToggleButton(Button):
    def __init__(self, rank):
        super().__init__(label=rank, style=discord.ButtonStyle.secondary)
        self.rank = rank

    async def callback(self, interaction: discord.Interaction):
        STATUS[self.rank]["last_killed"] = datetime.utcnow()
        await interaction.response.edit_message(embed=build_embed(), view=build_view())

def build_view():
    view = View()
    for rank in A_RANKS:
        view.add_item(ToggleButton(rank))
    return view

@bot.command()
async def sethours(ctx, hours: float):
    global CURRENT_MESSAGE
    now = datetime.utcnow()
    for rank in STATUS:
        STATUS[rank]["last_killed"] = now - timedelta(hours=hours)

    # Unpin and delete the current tracker message
    channel = bot.get_channel(CHANNEL_ID)
    if CURRENT_MESSAGE:
        try:
            await CURRENT_MESSAGE.unpin()
            await CURRENT_MESSAGE.delete()
        except Exception as e:
            print(f"⚠️ Failed to unpin or delete CURRENT_MESSAGE: {e}")

    # Send and pin a new updated message
    CURRENT_MESSAGE = await channel.send(embed=build_embed(), view=build_view())
    await CURRENT_MESSAGE.pin()

    # Clean up pin notification
    await asyncio.sleep(1)
    async for msg in channel.history(limit=5):
        if msg.type == discord.MessageType.pins_add and msg.author == bot.user:
            try:
                await msg.delete()
            except Exception as e:
                print(f"⚠️ Failed to delete pin message: {e}")
            break

    await ctx.send(f"🕒 All A-Rank timers set to {hours}h ago.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    global CURRENT_MESSAGE
    channel = bot.get_channel(CHANNEL_ID)

    if not channel:
        print("❌ Channel not found.")
        return

    # Unpin and delete all previously pinned messages
    pinned_messages = await channel.pins()
    for msg in pinned_messages:
        if msg.author == bot.user:
            try:
                await msg.unpin()
                await msg.delete()
                print(f"🗑️ Unpinned and deleted old message: {msg.id}")
            except Exception as e:
                print(f"⚠️ Failed to unpin or delete message {msg.id}: {e}")

    # Send and pin a fresh new message
    CURRENT_MESSAGE = await channel.send(embed=build_embed(), view=build_view())
    await CURRENT_MESSAGE.pin()
    print("📌 Sent and pinned new message.")

    # Try to delete the automatic pin system message
    await asyncio.sleep(1)  # Give Discord time to post it
    async for msg in channel.history(limit=5):
        if msg.type == discord.MessageType.pins_add and msg.author == bot.user:
            try:
                await msg.delete()
                print("🧹 Deleted system pin message.")
            except Exception as e:
                print(f"⚠️ Failed to delete pin message: {e}")
            break

@bot.event
async def update_loop():
    await bot.wait_until_ready()
    global CURRENT_MESSAGE

    while not bot.is_closed():
        if CURRENT_MESSAGE:
            try:
                await CURRENT_MESSAGE.edit(embed=build_embed(), view=build_view())
            except discord.errors.HTTPException as e:
                print(f"⏳ Rate limited or failed to edit message: {e}")
        await asyncio.sleep(60)  # update every 60 seconds

bot.run(os.environ["BOT_TOKEN"])
