import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
import json
import dotenv

# Load environment variables from .env if present (for local development)
dotenv.load_dotenv()

# Load tokens from environment variables (set in .env or Render.com dashboard)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # Discord bot token from environment
FACEIT_API_KEY = os.getenv('FACEIT_API_KEY')  # FACEIT API key from environment

# Set up Discord bot with required intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for command processing
bot = commands.Bot(command_prefix=commands.when_mentioned_or('/'), intents=intents)
tree = bot.tree  # Use the built-in tree attribute

# Path to the file storing Discord user to FACEIT username links
LINKS_FILE = os.path.join(os.path.dirname(__file__), 'faceit_links.json')

def load_links():
    """Load Discord user to FACEIT username links from file."""
    try:
        with open(LINKS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_links(links):
    """Save Discord user to FACEIT username links to file."""
    with open(LINKS_FILE, 'w') as f:
        json.dump(links, f)

@bot.event
async def on_ready():
    """Event handler for when the bot is ready."""
    print(f'Logged in as {bot.user}')
    print('Bot is ready and commands should be synced to the guild.')

@bot.event
async def setup_hook():
    # Sync commands globally instead of just to a guild
    await tree.sync()
    print("Slash commands synced globally. It may take up to 1 hour to appear in Discord UI.")

# Slash command: /faceitsearch
@tree.command(name="faceitsearch", description="Search FACEIT stats for a given username and display them in an embed.")
@app_commands.describe(username="FACEIT username to search for")
async def faceitsearch(interaction: discord.Interaction, username: str):
    """Search FACEIT stats for a given username and display them in an embed."""
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    user_url = f"https://open.faceit.com/data/v4/players?nickname={username}"
    user_resp = requests.get(user_url, headers=headers)
    if user_resp.status_code != 200:
        await interaction.response.send_message(f"Could not find FACEIT user: {username}", ephemeral=True)
        return
    user_data = user_resp.json()
    player_id = user_data.get('player_id')
    elo = 'N/A'
    try:
        elo = user_data['games']['cs2']['faceit_elo']
    except (KeyError, TypeError):
        pass
    avatar_url = user_data.get('avatar', None)
    faceit_level = None
    try:
        faceit_level = user_data['games']['cs2']['skill_level']
    except (KeyError, TypeError):
        pass
    level_img_url = None
    if faceit_level:
        level_img_url = f"https://cdn.faceit.com/images/levels/csgo/level_{faceit_level}_svg.svg"
    stats_url = f"https://open.faceit.com/data/v4/players/{player_id}/stats/cs2"
    stats_resp = requests.get(stats_url, headers=headers)
    if stats_resp.status_code != 200:
        await interaction.response.send_message(f"Could not fetch stats for: {username}", ephemeral=True)
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
    await interaction.response.send_message(embed=embed)

# Slash command: /linkfaceit
@tree.command(name="linkfaceit", description="Link your Discord account to your FACEIT username.")
@app_commands.describe(username="FACEIT username to link")
async def linkfaceit(interaction: discord.Interaction, username: str):
    """Link your Discord account to your FACEIT username."""
    links = load_links()
    links[str(interaction.user.id)] = username
    save_links(links)
    await interaction.response.send_message(f"Linked your Discord account to FACEIT username: {username}", ephemeral=True)

# Slash command: /faceitupdate
@tree.command(name="faceitupdate", description="Update your Discord role based on your FACEIT level.")
async def faceitupdate(interaction: discord.Interaction):
    """Update your Discord role based on your FACEIT level."""
    links = load_links()
    user_id = str(interaction.user.id)
    if user_id not in links:
        await interaction.response.send_message("You need to link your FACEIT account first using /linkfaceit <username>.", ephemeral=True)
        return
    username = links[user_id]
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    user_url = f"https://open.faceit.com/data/v4/players?nickname={username}"
    user_resp = requests.get(user_url, headers=headers)
    if user_resp.status_code != 200:
        await interaction.response.send_message(f"Could not find FACEIT user: {username}", ephemeral=True)
        return
    user_data = user_resp.json()
    faceit_level = None
    try:
        faceit_level = user_data['games']['cs2']['skill_level']
    except (KeyError, TypeError):
        pass
    if not faceit_level:
        await interaction.response.send_message("Could not determine your FACEIT level.", ephemeral=True)
        return
    role_name = f"FACEIT Level {faceit_level}"
    guild = interaction.guild
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        role = await guild.create_role(name=role_name, colour=discord.Colour.green())
    member = interaction.user
    for r in member.roles:
        if r.name.startswith("FACEIT Level ") and r != role:
            await member.remove_roles(r)
    await member.add_roles(role)
    await interaction.response.send_message(f"Your role has been updated to {role_name}!", ephemeral=True)

# Slash command: /faceitupdateall
@tree.command(name="faceitupdateall", description="(Admin) Update FACEIT roles for all linked users in the server.")
async def faceitupdateall(interaction: discord.Interaction):
    """(Admin) Update FACEIT roles for all linked users in the server."""
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    links = load_links()
    headers = {"Authorization": f"Bearer {FACEIT_API_KEY}"}
    updated = 0
    for user_id, username in links.items():
        member = interaction.guild.get_member(int(user_id))
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
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            role = await interaction.guild.create_role(name=role_name, colour=discord.Colour.green())
        for r in member.roles:
            if r.name.startswith("FACEIT Level ") and r != role:
                await member.remove_roles(r)
        await member.add_roles(role)
        updated += 1
    await interaction.response.send_message(f"Updated FACEIT roles for {updated} members.", ephemeral=True)

# Slash command: /help
@tree.command(name="help", description="Show all available commands and their descriptions.")
async def help_command(interaction: discord.Interaction):
    """Show all available commands and their descriptions."""
    help_text = (
        "**Available Commands:**\n"
        "/faceitsearch <username> - Search FACEIT stats for a given username.\n"
        "/linkfaceit <username> - Link your Discord account to your FACEIT username.\n"
        "/faceitupdate - Update your Discord role based on your FACEIT level.\n"
        "/faceitupdateall - (Admin) Update FACEIT roles for all linked users in the server.\n"
        "/help - Show this help message."
    )
    await interaction.response.send_message(help_text, ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
