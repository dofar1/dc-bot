import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from keep_alive import keep_alive

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

COMMAND_ROLE = 951477680245731408

FORUM_ID = 1132608152660103199
SUMMARY_CHANNEL_ID = 1132608904522637322

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user.name}")

# helpers

async def get_target_channel():
    channel = bot.get_channel(SUMMARY_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(SUMMARY_CHANNEL_ID)
        except Exception as exc:
            print("Target channel not found:", exc)
            return None
    return channel

async def get_summary_message(channel):
    async for message in channel.history(limit=100):
        if message.author == bot.user and message.embeds:
            return message
    return None

def is_tsl_thread(channel):
    return (
        isinstance(channel, discord.Thread)
        and channel.parent
        and channel.parent.id == FORUM_ID
    )

async def count_pins(thread):
    counts = {"RA": 0, "RR": 0, "FA": 0, "FR": 0}

    async for msg in thread.pins():
        content = (msg.content or "").lower()
        counts["RA"] += content.count("reliable accept")
        counts["RR"] += content.count("reliable reject")
        counts["FA"] += content.count("feedback accept")
        counts["FR"] += content.count("feedback reject")

    return counts

def build_embed(data):
    embed = discord.Embed(
        title="TSL Opinions",
        color=discord.Color.blue()
    )

    if not data:
        embed.description = "No active threads."
        return embed

    sorted_data = sorted(
        data.items(),
        key=lambda x: (x[1]["RA"], x[1]["FA"]),
        reverse=True
    )

    for thread, counts in sorted_data:
        embed.add_field(
            name=f"{thread.mention}",
            value=(
                f"**Reliables:** ✅ {counts['RA']} | ❌ {counts['RR']}\n"
                f"**Feedbacks:** ✅ {counts['FA']} | ❌ {counts['FR']}"
            ),
            inline=False
        )

    return embed

# logic

async def update_summary():
    target_channel = await get_target_channel()
    if target_channel is None:
        return

    data = {}

    for guild in bot.guilds:
        for thread in guild.threads:
            if not is_tsl_thread(thread):
                continue
            if thread.id == SUMMARY_CHANNEL_ID:
                continue
            if thread.archived or thread.locked:
                continue

            counts = await count_pins(thread)
            data[thread] = counts

    embed = build_embed(data)

    summary_message = await get_summary_message(target_channel)

    if summary_message:
        await summary_message.edit(embed=embed)
    else:
        await target_channel.send(embed=embed)

# events

@bot.event
async def on_guild_channel_pins_update(channel, last_pin):
    if is_tsl_thread(channel):
        await update_summary()

@bot.event
async def on_thread_create(thread):
    if is_tsl_thread(thread):
        await update_summary()

@bot.event
async def on_thread_update(before, after):
    if is_tsl_thread(after):
        await update_summary()

@bot.event
async def on_guild_channel_delete(channel):
    if is_tsl_thread(channel):
        await update_summary()



# commands

@bot.tree.command(name="refresh", description="Refresh the TSL summary")
async def refresh(interaction: discord.Interaction):

    if not any(role.id == COMMAND_ROLE for role in interaction.user.roles):
        await interaction.response.send_message(
            "You don’t have permission to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    await update_summary()

    await interaction.followup.send("Refreshed ✅", ephemeral=True)

# flask server
keep_alive()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)