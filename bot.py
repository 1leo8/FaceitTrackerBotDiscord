import discord
from discord.ext import commands
import requests
import os
import json

# Replace 'YOUR_DISCORD_BOT_TOKEN' with your actual bot token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'YOUR_DISCORD_BOT_TOKEN')
# Replace 'YOUR_FACEIT_API_KEY' with your actual FACEIT API key
FACEIT_API_KEY = os.getenv('FACEIT_API_KEY', 'YOUR_FACEIT_API_KEY')
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for command processing
bot = commands.Bot(command_prefix='#', intents=intents)

LINKS_FILE = os.path.join(os.path.dirname(__file__), 'faceit_links.json')

def load_links():
    try:
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_links(links):
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def faceitsearch(ctx, *, username: str):
    """Search FACEIT stats for a given username."""
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    user_url = f"https://open.faceit.com/data/v4/players?nickname={username}"
    user_resp = requests.get(user_url, headers=headers)
    if user_resp.status_code != 200:
        await ctx.send(f"Could not find FACEIT user: {username}")
        return
    user_data = user_resp.json()
    player_id = user_data.get('player_id')
    # Get ELO from user profile data
    elo = 'N/A'
    try:
        elo = user_data['games']['cs2']['faceit_elo']
    except (KeyError, TypeError):
        pass
    # Get avatar URL from user profile data
    avatar_url = user_data.get('avatar', None)
    # Get FACEIT level from user profile data
    faceit_level = None
    try:
        faceit_level = user_data['games']['cs2']['skill_level']
    except (KeyError, TypeError):
        pass
    # FACEIT level image URL pattern (official CDN)
    level_img_url = None
    if faceit_level:
        level_img_url = f"https://cdn.faceit.com/images/levels/csgo/level_{faceit_level}_svg.svg"
    stats_url = f"https://open.faceit.com/data/v4/players/{player_id}/stats/cs2"
    stats_resp = requests.get(stats_url, headers=headers)
    if stats_resp.status_code != 200:
        await ctx.send(f"Could not fetch stats for: {username}")
        return
    stats = stats_resp.json()
    lifetime = stats.get('lifetime', {})
    matches = lifetime.get('Matches', 'N/A')
    winrate = lifetime.get('Win Rate %', 'N/A')
    kd = lifetime.get('Average K/D Ratio', 'N/A')
    embed = discord.Embed(title=f"FACEIT Stats for {username}", color=0x00ff00)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    if level_img_url:
        embed.set_image(url=level_img_url)
    embed.add_field(name="ELO", value=elo, inline=True)
    embed.add_field(name="Matches", value=matches, inline=True)
    embed.add_field(name="Win Rate %", value=winrate, inline=True)
    embed.add_field(name="K/D Ratio", value=kd, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def linkfaceit(ctx, *, username: str):
    """Link your Discord account to your FACEIT username."""
    links = load_links()
    links[str(ctx.author.id)] = username
    save_links(links)
    await ctx.send(f"Linked your Discord account to FACEIT username: {username}")

@bot.command()
async def faceitupdate(ctx):
    """Update your Discord role based on your FACEIT level."""
    links = load_links()
    user_id = str(ctx.author.id)
    if user_id not in links:
        await ctx.send("You need to link your FACEIT account first using #linkfaceit <username>.")
        return
    username = links[user_id]
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    user_url = f"https://open.faceit.com/data/v4/players?nickname={username}"
    user_resp = requests.get(user_url, headers=headers)
    if user_resp.status_code != 200:
        await ctx.send(f"Could not find FACEIT user: {username}")
        return
    user_data = user_resp.json()
    faceit_level = None
    try:
        faceit_level = user_data['games']['cs2']['skill_level']
    except (KeyError, TypeError):
        pass
    if not faceit_level:
        await ctx.send("Could not determine your FACEIT level.")
        return
    # Role name pattern: "FACEIT Level X"
    role_name = f"FACEIT Level {faceit_level}"
    guild = ctx.guild
    # Find or create the role
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        role = await guild.create_role(name=role_name, colour=discord.Colour.green())
    # Remove old FACEIT Level roles
    member = ctx.author
    for r in member.roles:
        if r.name.startswith("FACEIT Level ") and r != role:
            await member.remove_roles(r)
    # Add the new role
    await member.add_roles(role)
    await ctx.send(f"Your role has been updated to {role_name}!")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def faceitupdateall(ctx):
    """Update FACEIT roles for all linked users in the server (admin only)."""
    links = load_links()
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    updated = 0
    for user_id, username in links.items():
        member = ctx.guild.get_member(int(user_id))
        if not member:
            continue
        user_url = f"https://open.faceit.com/data/v4/players?nickname={username}"
        user_resp = requests.get(user_url, headers=headers)
        if user_resp.status_code != 200:
            continue
        user_data = user_resp.json()
        faceit_level = None
        try:
            faceit_level = user_data['games']['cs2']['skill_level']
        except (KeyError, TypeError):
            continue
        if not faceit_level:
            continue
        role_name = f"FACEIT Level {faceit_level}"
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            role = await ctx.guild.create_role(name=role_name, colour=discord.Colour.green())
        # Remove old FACEIT Level roles
        for r in member.roles:
            if r.name.startswith("FACEIT Level ") and r != role:
                await member.remove_roles(r)
        await member.add_roles(role)
        updated += 1
    await ctx.send(f"Updated FACEIT roles for {updated} members.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
