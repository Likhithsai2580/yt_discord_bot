import discord
from discord.ext import commands
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import aiohttp
import asyncio
import os
from github import Github, GithubException
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from concurrent.futures import ThreadPoolExecutor
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import io
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bcrypt import Bcrypt

load_dotenv()

# Use environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
EDITOR_CHANNEL_ID = os.getenv('EDITOR_CHANNEL_ID')
THUMBNAIL_CHANNEL_ID = os.getenv('THUMBNAIL_CHANNEL_ID')
GITHUB_ISSUES_CHANNEL_ID = os.getenv('GITHUB_ISSUES_CHANNEL_ID')
TRUSTED_ROLE_ID = os.getenv('TRUSTED_ROLE_ID')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
YOUTUBE_TOKEN_PATH = os.getenv('YOUTUBE_TOKEN_PATH')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///videos.db')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

class Video(Base):
    __tablename__ = 'video'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    maker = Column(String(100), nullable=False)
    editor = Column(String(100))
    thumbnail_maker = Column(String(100))
    edited_path = Column(String(200))
    thumbnail_path = Column(String(200))
    gdrive_link = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class EditorRating(Base):
    __tablename__ = 'editor_ratings'
    editor_id = Column(String(100), primary_key=True)
    rater_id = Column(String(100), primary_key=True)
    rating = Column(Integer, nullable=False)

Base.metadata.create_all(engine)

# Configuration
config = {}

# Thread pool for background tasks
thread_pool = ThreadPoolExecutor(max_workers=5)

# Load configuration
def load_config():
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {}

# Save configuration
def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

# Initialize config
config = load_config()

# Define allowed configuration keys
ALLOWED_CONFIG_KEYS = [
    'support_channel_id',
    'editor_channel_id',
    'thumbnail_channel_id',
    'github_issues_channel_id',
    'trusted_role_id',
    'github_token',
    'youtube_token_path'
]

# Update configuration
def update_config(key, value):
    if key in ALLOWED_CONFIG_KEYS:
        config[key] = value
        save_config(config)
        return True
    return False

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()
    config = load_config()
    if all(config.values()):
        bot.loop.create_task(monitor_github_issues())
    else:
        print("Please configure all settings using /config command")

@bot.tree.command()
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Video Manager Bot Help", color=discord.Color.blue())
    embed.set_thumbnail(url=bot.user.avatar.url)
    
    commands = [
        ("🎥 Video Management", [
            ("/submit_video", "Submit a new video for editing"),
            ("/video_status", "Check the status of your submitted videos"),
            ("/video_analytics", "View video submission analytics"),
        ]),
        ("📊 Leaderboards & Ratings", [
            ("/leaderboard", "Show the top 10 content creators"),
            ("/rate_editor", "Rate an editor (1-5 stars)"),
            ("/editor_leaderboard", "View top-rated editors"),
        ]),
        ("⚙️ Configuration", [
            ("/config", "Configure bot settings (Admin only)"),
            ("/show_config", "Display current configuration (Admin only)"),
        ]),
    ]
    
    for category, cmds in commands:
        embed.add_field(name=category, value="\n".join([f"`{cmd}`: {desc}" for cmd, desc in cmds]), inline=False)
    
    embed.set_footer(text="Use /help <command> for more details on a specific command.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command()
@commands.has_permissions(administrator=True)
async def config(interaction: discord.Interaction, setting: str, value: str):
    if interaction.user.guild_permissions.administrator:
        if setting in ALLOWED_CONFIG_KEYS:
            config[setting] = value
            save_config(config)
            embed = discord.Embed(title="Configuration Updated", color=discord.Color.green())
            embed.add_field(name="Setting", value=setting, inline=True)
            embed.add_field(name="New Value", value=value if setting not in ['github_token', 'youtube_token_path'] else '[REDACTED]', inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Invalid Setting", color=discord.Color.red())
            embed.description = f"The setting '{setting}' is not valid."
            await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

@bot.tree.command()
@commands.has_permissions(administrator=True)
async def show_config(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        embed = discord.Embed(title="Current Configuration", color=discord.Color.blue())
        for key, value in config.items():
            if key in ['github_token', 'youtube_token_path']:
                value = '[REDACTED]' if value else 'Not set'
            embed.add_field(name=key.replace('_', ' ').title(), value=value, inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

@bot.tree.command()
async def submit_video(interaction: discord.Interaction):
    if not all(config.values()):
        embed = discord.Embed(title="Bot Not Configured", color=discord.Color.red())
        embed.description = "Bot is not fully configured. Please ask an admin to set all configuration values."
        await interaction.response.send_message(embed=embed)
        return

    class VideoSubmission(discord.ui.Modal, title='Submit a New Video'):
        title = discord.ui.TextInput(label='Video Title', placeholder='Enter the title of your video')
        description = discord.ui.TextInput(label='Video Description', style=discord.TextStyle.paragraph, placeholder='Describe your video')
        gdrive_link = discord.ui.TextInput(label='Google Drive Link', placeholder='Paste the Google Drive link to your video')

        async def on_submit(self, interaction: discord.Interaction):
            new_video = Video(
                title=self.title.value,
                description=self.description.value,
                maker=str(interaction.user.id),
                gdrive_link=self.gdrive_link.value,
                status='submitted'
            )
            session.add(new_video)
            session.commit()

            editor_channel = bot.get_channel(int(config['editor_channel_id']))
            embed = discord.Embed(title="New Video Submitted", color=discord.Color.green())
            embed.add_field(name="Title", value=self.title.value, inline=False)
            embed.add_field(name="Description", value=self.description.value, inline=False)
            embed.add_field(name="Drive Link", value=self.gdrive_link.value, inline=False)
            embed.set_footer(text=f"Submitted by {interaction.user.name}")
            await editor_channel.send(embed=embed)

            success_embed = discord.Embed(title="Video Submitted Successfully", color=discord.Color.green())
            success_embed.description = "Your video has been submitted for editing."
            await interaction.response.send_message(embed=success_embed)

    modal = VideoSubmission()
    await interaction.response.send_modal(modal)

@bot.tree.command()
async def video_status(interaction: discord.Interaction):
    videos = session.query(Video).filter_by(maker=str(interaction.user.id)).order_by(Video.created_at.desc()).limit(5).all()

    if not videos:
        await interaction.response.send_message("You haven't submitted any videos yet.")
        return

    embed = discord.Embed(title="Your Recent Video Submissions", color=discord.Color.blue())
    for video in videos:
        embed.add_field(name=video.title, value=f"Status: {video.status.capitalize()}", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command()
async def leaderboard(interaction: discord.Interaction):
    results = session.query(Video.maker, func.count(Video.id).label('video_count')) \
        .group_by(Video.maker) \
        .order_by(func.count(Video.id).desc()) \
        .limit(10) \
        .all()

    embed = discord.Embed(title="Top 10 Content Creators", color=discord.Color.gold())
    for i, (maker_id, count) in enumerate(results, 1):
        user = await bot.fetch_user(int(maker_id))
        embed.add_field(name=f"{i}. {user.name}", value=f"{count} videos", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command()
async def rate_editor(interaction: discord.Interaction, editor: discord.Member):
    current_rating = session.query(EditorRating).filter_by(editor_id=str(editor.id), rater_id=str(interaction.user.id)).first()

    embed = discord.Embed(title=f"Rate Editor: {editor.name}", color=discord.Color.blue())
    embed.description = f"Current rating: {'Not rated' if current_rating is None else f'{current_rating.rating} ⭐'}"

    class RatingDropdown(discord.ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=f"{i} Stars", value=str(i), emoji="⭐") for i in range(1, 6)]
            super().__init__(placeholder="Select a rating", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            rating = int(self.values[0])
            editor_rating = session.query(EditorRating).filter_by(editor_id=str(editor.id), rater_id=str(interaction.user.id)).first()
            if editor_rating:
                editor_rating.rating = rating
            else:
                editor_rating = EditorRating(editor_id=str(editor.id), rater_id=str(interaction.user.id), rating=rating)
                session.add(editor_rating)
            session.commit()

            embed = discord.Embed(title="Rating Submitted", color=discord.Color.green())
            embed.description = f"You've rated {editor.name} with {rating} ⭐"
            await interaction.response.edit_message(embed=embed, view=None)

    view = discord.ui.View()
    view.add_item(RatingDropdown())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command()
async def video_analytics(interaction: discord.Interaction):
    results = session.query(func.strftime('%Y-%m', Video.created_at).label('month'), func.count(Video.id).label('count')) \
        .group_by('month') \
        .order_by('month') \
        .all()

    months, counts = zip(*results)
    plt.figure(figsize=(10, 5))
    plt.bar(months, counts)
    plt.title("Video Submissions Over Time")
    plt.xlabel("Month")
    plt.ylabel("Number of Videos")
    plt.xticks(rotation=45)

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    file = discord.File(buf, filename="video_analytics.png")
    await interaction.response.send_message(file=file)

@bot.tree.command()
async def editor_leaderboard(interaction: discord.Interaction):
    results = session.query(EditorRating.editor_id, func.avg(EditorRating.rating).label('avg_rating'), func.count(EditorRating.rating).label('total_ratings')) \
        .group_by(EditorRating.editor_id) \
        .order_by(func.avg(EditorRating.rating).desc(), func.count(EditorRating.rating).desc()) \
        .limit(10) \
        .all()

    embed = discord.Embed(title="Top 10 Editors", color=discord.Color.gold())
    for i, (editor_id, avg_rating, total_ratings) in enumerate(results, 1):
        user = await bot.fetch_user(int(editor_id))
        embed.add_field(name=f"{i}. {user.name}", value=f"Rating: {avg_rating:.2f} ⭐ ({total_ratings} ratings)", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command()
async def video_info(interaction: discord.Interaction, video_id: int):
    video = session.query(Video).get(video_id)

    if not video:
        await interaction.response.send_message(f"No video found with ID {video_id}", ephemeral=True)
        return

    embed = discord.Embed(title=f"Video Information: {video.title}", color=discord.Color.blue())
    embed.add_field(name="Description", value=video.description, inline=False)
    embed.add_field(name="Status", value=video.status, inline=True)
    embed.add_field(name="Submitted by", value=f"<@{video.maker}>", inline=True)
    
    if video.editor:
        embed.add_field(name="Editor", value=f"<@{video.editor}>", inline=True)
    if video.thumbnail_maker:
        embed.add_field(name="Thumbnail Creator", value=f"<@{video.thumbnail_maker}>", inline=True)
    
    embed.add_field(name="Google Drive Link", value=video.gdrive_link, inline=False)
    embed.add_field(name="Submitted at", value=video.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)

    await interaction.response.send_message(embed=embed)

async def monitor_github_issues():
    github_client = Github(config['github_token'])
    user = github_client.get_user(config['github_username'])
    
    while True:
        for repo in user.get_repos():
            try:
                for issue in repo.get_issues(state='open'):
                    channel = bot.get_channel(int(config['github_issues_channel_id']))
                    embed = discord.Embed(title=f"New Issue in {repo.name}", color=discord.Color.orange())
                    embed.add_field(name="Title", value=issue.title, inline=False)
                    embed.add_field(name="Link", value=issue.html_url, inline=False)
                    embed.set_footer(text=f"Created at {issue.created_at}")
                    await channel.send(embed=embed)
            except GithubException as e:
                if e.status == 403 and "Repository access blocked" in str(e):
                    print("Error: Repository access is blocked. Please check your GitHub account status.")
                    # You might want to disable this feature or retry after some time
                else:
                    print(f"An unexpected error occurred: {e}")
        
        await asyncio.sleep(300)  # Check every 5 minutes

@bot.event
async def on_message(message):
    if message.guild is None and message.author.guild_permissions.administrator:  # Check if it's a DM and from an admin
        if message.content.startswith('!config'):
            parts = message.content.split(maxsplit=2)
            if len(parts) == 3:
                setting, value = parts[1], parts[2]
                if setting in ALLOWED_CONFIG_KEYS:
                    config[setting] = value
                    save_config(config)
                    await message.channel.send(f"Configuration updated: {setting} = {value if setting not in ['github_token', 'youtube_token_path'] else '[REDACTED]'}")
                else:
                    await message.channel.send(f"Invalid setting: {setting}")
            else:
                await message.channel.send("Usage: !config <setting> <value>")
        elif message.content == '!show_config':
            config_str = "\n".join([f"{k}: {'[REDACTED]' if k in ['github_token', 'youtube_token_path'] else v}" 
                                    for k, v in config.items()])
            await message.channel.send(f"Current configuration:\n```\n{config_str}\n```")
    await bot.process_commands(message)

def download_file(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

async def upload_to_youtube(video_id):
    # Retrieve video info from database
    video_data = session.query(Video).get(video_id)

    # Set up YouTube API client
    credentials = Credentials.from_authorized_user_file(config['youtube_token_path'], ['https://www.googleapis.com/auth/youtube.upload'])
    youtube = build('youtube', 'v3', credentials=credentials)

    # Prepare video upload
    request_body = {
        'snippet': {
            'title': video_data.title,
            'description': video_data.description + f"\n\nCredits:\nMaker: {bot.get_user(int(video_data.maker)).name}\nEditor: {bot.get_user(int(video_data.editor)).name}\nThumbnail: {bot.get_user(int(video_data.thumbnail_maker)).name}",
            'tags': ['YourChannelTag']
        },
        'status': {
            'privacyStatus': 'private'  # or 'public', 'unlisted'
        }
    }

    # Upload video
    media_file = MediaFileUpload(video_data.edited_path)
    response_upload = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()

    # Set thumbnail
    youtube.thumbnails().set(
        videoId=response_upload.get('id'),
        media_body=MediaFileUpload(video_data.thumbnail_path)
    ).execute()

    print(f"Video uploaded successfully! Video ID: {response_upload.get('id')}")

@bot.command()
async def support(ctx, *, title):
    config = load_config()
    support_channel_id = config.get('support_channel_id')
    
    if not support_channel_id:
        await ctx.send("Support channel not configured. Please ask an admin to set it up.")
        return

    support_channel = bot.get_channel(int(support_channel_id))
    if not support_channel:
        await ctx.send("Support channel not found. Please ask an admin to check the configuration.")
        return

    thread_name = f"{ctx.author.display_name} | {title}"[:100]
    thread = await support_channel.create_thread(name=thread_name, auto_archive_duration=1440)
    await thread.add_user(ctx.author)
    await thread.send(f"Support request from {ctx.author.mention}: {title}")

@bot.command()
@commands.has_permissions(administrator=True)
async def support_channel(ctx, channel: discord.TextChannel):
    config = load_config()
    config['support_channel_id'] = str(channel.id)
    save_config(config)
    await ctx.send(f"Support channel set to {channel.mention}")

def run_discord_bot():
    if not DISCORD_TOKEN:
        print("Discord token not found. Please set the DISCORD_TOKEN environment variable.")
        return
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    run_discord_bot()

# Define admin_ids (you should populate this with actual admin user IDs)
admin_ids = [123456789, 987654321]  # Replace with actual admin user IDs
