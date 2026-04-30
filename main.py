import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user.name} v1.0")

async def get_target_channel():
    channel = bot.get_channel(1499443210471342242)
    if channel is None:
        try:
            channel = await bot.fetch_channel(1499443210471342242)
        except Exception as exc:
            print("Target channel not found or fetch failed:", exc)
            return None
    return channel

async def get_tsl_forum_channel():
    for guild in bot.guilds:
        for channel in guild.channels:
            if channel.name == "tsl-worthy-opinions":
                return channel
    return None

async def get_summary_message(target_channel):
    async for message in target_channel.history(limit=100):
        if message.author == bot.user and message.content.startswith("TSL:"):
            return message
    return None

def format_channel_label(channel):
    if isinstance(channel, discord.Thread):
        return f"<#{channel.id}>"
    return channel.mention

async def update_summary_line(channel):
    target_channel = await get_target_channel()
    if target_channel is None:
        return

    if channel.id == target_channel.id:
        return

    counts = {"RA": 0, "RR": 0, "FA": 0, "FR": 0}
    async for msg in channel.pins():
        content = (msg.content or "").lower()
        counts["RA"] += int("reliable accept" in content)
        counts["RR"] += int("reliable reject" in content)
        counts["FA"] += int("feedback accept" in content)
        counts["FR"] += int("feedback reject" in content)

    summary_header = "TSL:"
    channel_label = format_channel_label(channel)
    new_line = (
        f"{channel_label}: RA {counts['RA']} | RR {counts['RR']} | FA {counts['FA']} | FR {counts['FR']}"
    )

    summary_message = await get_summary_message(target_channel)
    if summary_message is None:
        await target_channel.send(f"{summary_header}\n{new_line}")
        return

    lines = summary_message.content.splitlines()
    channel_label = format_channel_label(channel)
    found = False
    for i in range(1, len(lines)):
        if lines[i].startswith(f"{channel_label}:"):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)

    await summary_message.edit(content="\n".join(lines))

async def remove_summary_line(channel):
    target_channel = await get_target_channel()
    if target_channel is None:
        return

    summary_message = await get_summary_message(target_channel)
    if summary_message is None:
        return

    lines = summary_message.content.splitlines()
    channel_label = format_channel_label(channel)
    new_lines = [lines[0]] + [line for line in lines[1:] if not line.startswith(f"{channel_label}:")]
    if len(new_lines) == len(lines):
        return

    await summary_message.edit(content="\n".join(new_lines) if len(new_lines) > 1 else new_lines[0])

@bot.event
async def on_guild_channel_pins_update(channel, last_pin):
    is_tsl_forum = False
    if isinstance(channel, discord.Thread):
        is_tsl_forum = channel.parent is not None and channel.parent.name == "tsl-worthy-opinions"
    else:
        is_tsl_forum = channel.name == "tsl-worthy-opinions"

    if not is_tsl_forum:
        return

    if channel.id == 1499443210471342242:
        return

    await update_summary_line(channel)

@bot.event
async def on_thread_create(thread):
    if thread.parent is None or thread.parent.name != "tsl-worthy-opinions":
        return
    await update_summary_line(thread)

@bot.event
async def on_thread_update(before, after):
    if after.parent is None or after.parent.name != "tsl-worthy-opinions":
        return

    was_closed = before.locked or before.archived
    is_closed = after.locked or after.archived
    if was_closed and not is_closed:
        await update_summary_line(after)
    elif is_closed and not was_closed:
        await remove_summary_line(after)

@bot.event
async def on_guild_channel_delete(channel):
    if isinstance(channel, discord.Thread) and channel.parent is not None and channel.parent.name == "tsl-worthy-opinions":
        await remove_summary_line(channel)

@bot.command(name="refresh")
async def refresh_summary(ctx):
    forum_channel = await get_tsl_forum_channel()
    if forum_channel is None:
        await ctx.send("Could not find the `tsl-worthy-opinions` forum channel.")
        return

    target_channel = await get_target_channel()
    if target_channel is None:
        await ctx.send("Could not find the summary target channel.")
        return

    summary_message = await get_summary_message(target_channel)
    summary_header = "TSL:"
    lines = [summary_header]

    threads = [thread for thread in ctx.guild.threads if thread.parent_id == forum_channel.id and not thread.locked and not thread.archived and thread.id != target_channel.id]
    for thread in sorted(threads, key=lambda t: t.name.lower()):
        counts = {"RA": 0, "RR": 0, "FA": 0, "FR": 0}
        async for msg in thread.pins():
            content = (msg.content or "").lower()
            counts["RA"] += int("reliable accept" in content)
            counts["RR"] += int("reliable reject" in content)
            counts["FA"] += int("feedback accept" in content)
            counts["FR"] += int("feedback reject" in content)

        channel_label = format_channel_label(thread)
        lines.append(
            f"{channel_label}: RA {counts['RA']} | RR {counts['RR']} | FA {counts['FA']} | FR {counts['FR']}"
        )

    content = "\n".join(lines)
    if summary_message is None:
        await target_channel.send(content)
    else:
        await summary_message.edit(content=content)

    msg = await ctx.send("Refreshed")
    await asyncio.sleep(3)
    await msg.delete()
    await ctx.message.delete()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)