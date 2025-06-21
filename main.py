import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from datetime import datetime, timedelta, timezone
import asyncio
import discord.errors
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Intents and bot setup
intents = discord.Intents.default()
intents.message_content = True

class HuntBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(self.update_loop())

    async def update_loop(self):
        await self.wait_until_ready()
        global CURRENT_MESSAGE
        while not self.is_closed():
            if CURRENT_MESSAGE:
                try:
                    now = datetime.now(timezone.utc)
                    await CURRENT_MESSAGE.edit(embed=build_embed(now), view=build_view())
                except discord.errors.HTTPException as e:
                    print(f"⏳ Rate limited or failed to edit message: {e}")
            await asyncio.sleep(60)

bot = HuntBot(command_prefix="!", intents=intents)

SERVER = "Halicarnassus"
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CURRENT_MESSAGE = None
MESSAGE_PIN_KEY = "a_rank_tracker_pin"

A_RANKS = [
    "Queen Hawk", "Nechuciho", "The Raintriller", "Pkuucha",
    "Starcrier 1", "Rrax Yity'a 1", "Starcrier 2", "Rrax Yity'a 2",
    "Yehehetoaua'pyo", "Keheniheyamewi", "Heshuala",
    "Urna Variabilis", "Sally the Sweeper", "Cat's Eye"
]

ZONED_A_RANKS = {
    "Urqopacha": ["Queen Hawk", "Nechuciho"],
    "Kozama'uka": ["The Raintriller", "Pkuucha"],
    "Yak T'el (i1)": ["Starcrier 1", "Rrax Yity'a 1"],
    "Yak T'el (i2)": ["Starcrier 2", "Rrax Yity'a 2"],
    "Shaaloani": ["Yehehetoaua'pyo", "Keheniheyamewi"],
    "Heritage Found": ["Heshuala", "Urna Variabilis"],
    "Living Memory": ["Sally the Sweeper", "Cat's Eye"]
}

WORLDS = [
    "Halicarnassus",
    "Cuchulainn",
    "Golem",
    "Kraken",
    "Seraph",
    "Maduin",
    "Marilith",
    "Rafflesia"
]

STATUS = {world: {rank: {"last_killed": datetime.now(timezone.utc) + timedelta(hours=2, minutes=24)} for rank in A_RANKS} for world in WORLDS}
CURRENT_MESSAGE = {world: None for world in WORLDS}

# Displays time since kill and if it's 100% spawn chance
def get_spawn_status_display(last_killed, now):
    def parse_hhmm(hhmm):
        h, m = map(int, hhmm.split(":"))
        return round(h + m / 60, 4)  # <-- ROUNDING for safety

    green_ranges = [
    ("02:00", "24:00"), ("32:00", "52:00"), ("62:00", "80:00"),
    ("92:00", "108:00"), ("122:00", "136:00"), ("152:00", "164:00"),
    ("182:00", "192:00"), ("212:00", "220:00"), ("242:00", "248:00"),
    ("272:00", "276:00"), ("302:00", "304:00")
    ]
    yellow_ranges = [
    ("00:00", "02:00"), ("24:01", "31:59"), ("52:01", "61:59"),
    ("80:01", "91:59"), ("108:01", "121:59"), ("136:01", "151:59"),
    ("164:01", "181:59"), ("192:01", "211:59"), ("220:01", "241:59"),
    ("248:01", "271:59"), ("276:01", "301:59"), ("304:01", "9999:00")
]

    green_ranges = [(parse_hhmm(start), parse_hhmm(end)) for start, end in green_ranges]
    yellow_ranges = [(parse_hhmm(start), parse_hhmm(end)) for start, end in yellow_ranges]

    if last_killed is None:
        return "❓ Unknown"

    remaining = now - last_killed
    total_seconds = remaining.total_seconds()
    total_hours = round(total_seconds / 3600, 4)  # <-- Also rounded here

    # Format as HH:MM with +/- sign
    hours = int(total_hours)
    minutes = int((abs(total_seconds) % 3600) // 60)
    sign = '-' if total_hours < 0 else ''
    time_str = f"{sign}{abs(hours):02}:{minutes:02}"

    if total_hours < 0:
        return f"🔴 {time_str}"

    for start, end in green_ranges:
        if start <= total_hours <= end:
            return f"🟢 {time_str}"

    for start, end in yellow_ranges:
        if start <= total_hours <= end:
            return f"🟡 {time_str}"

    return f"⚪ {time_str}"  # fallback


# Update build_embed to take world as argument
def build_embed(world, now=None):
    if not now:
        now = datetime.now(timezone.utc)
    embed = discord.Embed(title=f"🧭 {world} – Dawntrail A-Ranks", color=0x00b0f4)
    all_ranks = [rank for ranks in ZONED_A_RANKS.values() for rank in ranks]
    lines = []
    def shorten(name, length=18):
        return name if len(name) <= length else name[:length - 1] + "…"
    for i in range(0, len(all_ranks), 2):
        rank1 = all_ranks[i]
        rank2 = all_ranks[i + 1]
        r1_timer = get_spawn_status_display(STATUS[world][rank1]["last_killed"], now)
        r2_timer = get_spawn_status_display(STATUS[world][rank2]["last_killed"], now)
        r1_name = f"`{shorten(rank1, 18):<18}`"
        r2_name = f"`{shorten(rank2, 18):<18}`"
        line = f"{r1_name} {r1_timer}     {r2_name} {r2_timer}"
        lines.append(line)
    embed.add_field(name="\u200b", value="\n".join(lines), inline=True)
    embed.set_footer(text="Tap a button to mark kill time. Use the correct world!")
    return embed

# Update ToggleButton to take world
class ToggleButton(Button):
    def __init__(self, world, rank):
        super().__init__(label=rank, style=discord.ButtonStyle.secondary)
        self.rank = rank
        self.world = world
    async def callback(self, interaction: discord.Interaction):
        now = datetime.now(timezone.utc)
        STATUS[self.world][self.rank]["last_killed"] = now + timedelta(hours=4)
        await interaction.response.edit_message(embed=build_embed(self.world, now), view=build_view(self.world))

def build_view(world):
    view = View()
    for rank in A_RANKS:
        view.add_item(ToggleButton(world, rank))
    return view

# Update commands to require world as first argument
@bot.command(name="setall", usage="<world> <time>")
async def setall(ctx, world: str = None, time_input: str = None):
    if not world or world not in WORLDS or not time_input:
        await ctx.send(f"❌ Usage: !setall <world> <time>\nWorlds: {', '.join(WORLDS)}", delete_after=6)
        await ctx.message.delete()
        return
    try:
        sign = -1 if time_input.strip().startswith("-") else 1
        time_input = time_input.strip().lstrip("-")
        if ":" in time_input:
            hours, minutes = map(int, time_input.split(":"))
        else:
            decimal_hours = float(time_input)
            hours = int(decimal_hours)
            minutes = int((decimal_hours - hours) * 60)
        offset = timedelta(hours=hours * sign, minutes=minutes * sign)
    except Exception:
        await ctx.send(f"❌ Invalid time format: `{time_input}`. Use `HH:MM` or decimal hours.", delete_after=6)
        await ctx.message.delete()
        return
    now = datetime.now(timezone.utc)
    for rank in A_RANKS:
        STATUS[world][rank]["last_killed"] = datetime.now(timezone.utc) - offset
    if CURRENT_MESSAGE[world]:
        try:
            await CURRENT_MESSAGE[world].edit(embed=build_embed(world), view=build_view(world))
        except Exception as e:
            print(f"⚠️ Failed to update tracker message: {e}")
    try:
        await ctx.message.delete()
    except Exception as e:
        print(f"⚠️ Could not delete user command: {e}")

@bot.command(name="set", usage="<world> <A-Rank Name> <time>")
async def set_timer(ctx, *, args: str = None):
    if not args or len(args.strip().split()) < 3:
        await ctx.send(f"❌ Usage: !set <world> <A-Rank Name> <time>\nWorlds: {', '.join(WORLDS)}", delete_after=6)
        await ctx.message.delete()
        return
    parts = args.strip().split()
    world = parts[0]
    if world not in WORLDS:
        await ctx.send(f"❌ Unknown world: `{world}`\nWorlds: {', '.join(WORLDS)}", delete_after=6)
        await ctx.message.delete()
        return
    *rank_parts, time_input = parts[1:]
    rank_name = " ".join(rank_parts[:-1]) if len(rank_parts) > 1 else rank_parts[0]
    time_input = rank_parts[-1] if len(rank_parts) > 1 else time_input
    matched_rank = next((r for r in A_RANKS if r.lower() == rank_name.lower()), None)
    if not matched_rank:
        await ctx.send(f"❌ Unknown A-Rank: `{rank_name}`", delete_after=6)
        await ctx.message.delete()
        return
    try:
        sign = -1 if time_input.strip().startswith("-") else 1
        time_input = time_input.strip().lstrip("-")
        if ":" in time_input:
            hours, minutes = map(int, time_input.split(":"))
        else:
            decimal_hours = float(time_input)
            hours = int(decimal_hours)
            minutes = int((decimal_hours - hours) * 60)
        offset = timedelta(hours=hours * sign, minutes=minutes * sign)
    except Exception:
        await ctx.send(f"❌ Invalid format. Example: `!set {world} 'Rrax Yity'a 1' -2:00`", delete_after=6)
        await ctx.message.delete()
        return
    STATUS[world][matched_rank]["last_killed"] = datetime.now(timezone.utc) - offset
    if CURRENT_MESSAGE[world]:
        try:
            await CURRENT_MESSAGE[world].edit(embed=build_embed(world), view=build_view(world))
        except Exception as e:
            print(f"⚠️ Failed to update message: {e}")
    try:
        await ctx.message.delete()
    except Exception as e:
        print(f"⚠️ Could not delete command message: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    global CURRENT_MESSAGE
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Channel not found.")
        return
    # Delete all messages in the channel before creating new ones
    try:
        async for msg in channel.history(limit=None):
            try:
                await msg.delete()
            except Exception as e:
                print(f"⚠️ Could not delete message {msg.id}: {e}")
    except Exception as e:
        print(f"⚠️ Failed to fetch or delete messages: {e}")
    now = datetime.now(timezone.utc)
    for world in WORLDS:
        CURRENT_MESSAGE[world] = await channel.send(embed=build_embed(world), view=build_view(world))
        await CURRENT_MESSAGE[world].pin()
        print(f"📌 Sent and pinned new message for {world}.")
    await asyncio.sleep(1)
    async for msg in channel.history(limit=5):
        if msg.type == discord.MessageType.pins_add and msg.author == bot.user:
            try:
                await msg.delete()
                print("🧹 Deleted system pin message.")
            except Exception as e:
                print(f"⚠️ Failed to delete pin message: {e}")
            break

# Replace Flask app with FastAPI
app = FastAPI()

@app.post("/sonar")
async def sonar_webhook(data: dict):
    world = data.get("world")
    rank = data.get("rank")
    if not world or not rank:
        raise HTTPException(status_code=400, detail="Missing world or rank")
    if world not in WORLDS:
        raise HTTPException(status_code=400, detail=f"Unknown world: {world}")
    matched_rank = next((r for r in A_RANKS if r.lower() == rank.lower()), None)
    if not matched_rank:
        raise HTTPException(status_code=400, detail=f"Unknown rank: {rank}")
    # Update timer for this world/rank
    STATUS[world][matched_rank]["last_killed"] = datetime.now(timezone.utc)
    # Update the embed in Discord
    if CURRENT_MESSAGE[world]:
        coro = CURRENT_MESSAGE[world].edit(embed=build_embed(world), view=build_view(world))
        asyncio.run_coroutine_threadsafe(coro, bot.loop)
    return JSONResponse(content={"status": "ok"})

async def start_bot():
    try:
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            print("❌ BOT_TOKEN environment variable is missing.")
            return
        await bot.start(bot_token)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")

# Update the entry point to use uvicorn
if __name__ == "__main__":
    import uvicorn
    import asyncio

    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    uvicorn.run(app, host="0.0.0.0", port=5000)
