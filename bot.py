import discord
from discord.ext import commands
import sqlite3
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

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
conn = sqlite3.connect('videos.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS video
             (id INTEGER PRIMARY KEY, title TEXT, description TEXT, maker TEXT, 
              editor TEXT, thumbnail_maker TEXT, edited_path TEXT, thumbnail_path TEXT,
              gdrive_link TEXT, status TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS editor_ratings
             (editor_id TEXT, rater_id TEXT, rating INTEGER)''')
conn.commit()

# Configuration
config = {}

# Thread pool for background tasks
thread_pool = ThreadPoolExecutor(max_workers=5)

def load_config():
    global config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {
            'github_username': None,
            'editor_channel_id': None,
            'thumbnail_channel_id': None,
            'github_issues_channel_id': None,
            'trusted_role_id': None,
            'github_token': None,
            'youtube_token_path': None
        }
        save_config()

def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()
    load_config()
    if all(config.values()):
        bot.loop.create_task(monitor_github_issues())
    else:
        print("Please configure all settings using /config command")

@bot.tree.command()
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Video Manager Bot Help", color=discord.Color.blue())
    embed.add_field(name="/config", value="Configure bot settings (Admin only)", inline=False)
    embed.add_field(name="/submit_video", value="Submit a new video for editing", inline=False)
    embed.add_field(name="/show_config", value="Display current configuration (Admin only)", inline=False)
    embed.add_field(name="/video_status", value="Check the status of your submitted videos", inline=False)
    embed.add_field(name="/leaderboard", value="Show the top 10 content creators", inline=False)
    embed.add_field(name="/rate_editor", value="Rate an editor (1-5 stars)", inline=False)
    embed.add_field(name="/video_analytics", value="View video submission analytics", inline=False)
    embed.add_field(name="/help", value="Show this help message", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command()
@commands.has_permissions(administrator=True)
async def config(interaction: discord.Interaction, setting: str, value: str):
    if setting in config:
        config[setting] = value
        save_config()
        embed = discord.Embed(title="Configuration Updated", color=discord.Color.green())
        embed.add_field(name="Setting", value=setting, inline=True)
        embed.add_field(name="New Value", value=value, inline=True)
        await interaction.response.send_message(embed=embed)
        if all(config.values()):
            bot.loop.create_task(monitor_github_issues())
    else:
        embed = discord.Embed(title="Invalid Setting", color=discord.Color.red())
        embed.description = f"The setting '{setting}' is not valid."
        await interaction.response.send_message(embed=embed)

@bot.tree.command()
@commands.has_permissions(administrator=True)
async def show_config(interaction: discord.Interaction):
    embed = discord.Embed(title="Current Configuration", color=discord.Color.blue())
    for key, value in config.items():
        if key in ['github_token', 'youtube_token_path']:
            value = '[REDACTED]' if value else 'Not set'
        embed.add_field(name=key.replace('_', ' ').title(), value=value, inline=False)
    await interaction.response.send_message(embed=embed)

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
            c.execute('''INSERT INTO video (title, description, maker, gdrive_link, status)
                         VALUES (?, ?, ?, ?, ?)''',
                      (self.title.value, self.description.value, str(interaction.user.id),
                       self.gdrive_link.value, 'submitted'))
            conn.commit()

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
    c.execute('''SELECT title, status FROM video WHERE maker = ? ORDER BY created_at DESC LIMIT 5''', (str(interaction.user.id),))
    videos = c.fetchall()

    if not videos:
        await interaction.response.send_message("You haven't submitted any videos yet.")
        return

    embed = discord.Embed(title="Your Recent Video Submissions", color=discord.Color.blue())
    for title, status in videos:
        embed.add_field(name=title, value=f"Status: {status.capitalize()}", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command()
async def leaderboard(interaction: discord.Interaction):
    c.execute('''
        SELECT maker, COUNT(*) as video_count
        FROM video
        GROUP BY maker
        ORDER BY video_count DESC
        LIMIT 10
    ''')
    results = c.fetchall()

    embed = discord.Embed(title="Top 10 Content Creators", color=discord.Color.gold())
    for i, (maker_id, count) in enumerate(results, 1):
        user = await bot.fetch_user(int(maker_id))
        embed.add_field(name=f"{i}. {user.name}", value=f"{count} videos", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command()
async def rate_editor(interaction: discord.Interaction, editor: discord.Member, rating: int):
    if rating < 1 or rating > 5:
        await interaction.response.send_message("Rating must be between 1 and 5.", ephemeral=True)
        return

    c.execute('''
        INSERT OR REPLACE INTO editor_ratings (editor_id, rater_id, rating)
        VALUES (?, ?, ?)
    ''', (str(editor.id), str(interaction.user.id), rating))
    conn.commit()

    await interaction.response.send_message(f"You've rated {editor.name} with {rating} stars!", ephemeral=True)

@bot.tree.command()
async def video_analytics(interaction: discord.Interaction):
    c.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM video
        GROUP BY month
        ORDER BY month
    ''')
    results = c.fetchall()

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
    if not all(config.values()):
        return

    if message.channel.id == int(config['editor_channel_id']):
        if message.attachments:
            video_file = message.attachments[0]
            thread_pool.submit(download_file, video_file.url, f"edited_{video_file.filename}")
            c.execute('''UPDATE video SET editor = ?, edited_path = ?, status = 'edited'
                         WHERE id = (SELECT id FROM video WHERE status = 'submitted' LIMIT 1)''',
                      (str(message.author.id), f"edited_{video_file.filename}"))
            conn.commit()
            embed = discord.Embed(title="Edited Video Received", color=discord.Color.green())
            embed.description = "The edited video has been received and is now downloading."
            embed.set_footer(text=f"Edited by {message.author.name}")
            await message.channel.send(embed=embed)

    elif message.channel.id == int(config['thumbnail_channel_id']):
        if message.attachments:
            thumbnail_file = message.attachments[0]
            thread_pool.submit(download_file, thumbnail_file.url, f"thumbnail_{thumbnail_file.filename}")
            c.execute('''UPDATE video SET thumbnail_maker = ?, thumbnail_path = ?, status = 'thumbnail_added'
                         WHERE id = (SELECT id FROM video WHERE status = 'edited' LIMIT 1)''',
                      (str(message.author.id), f"thumbnail_{thumbnail_file.filename}"))
            conn.commit()
            embed = discord.Embed(title="Thumbnail Received", color=discord.Color.green())
            embed.description = "The thumbnail has been received and is now downloading."
            embed.set_footer(text=f"Created by {message.author.name}")
            await message.channel.send(embed=embed)

    await bot.process_commands(message)

def download_file(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

async def upload_to_youtube(video_id):
    # Retrieve video info from database
    c.execute("SELECT * FROM video WHERE id = ?", (video_id,))
    video_data = c.fetchone()

    # Set up YouTube API client
    credentials = Credentials.from_authorized_user_file(config['youtube_token_path'], ['https://www.googleapis.com/auth/youtube.upload'])
    youtube = build('youtube', 'v3', credentials=credentials)

    # Prepare video upload
    request_body = {
        'snippet': {
            'title': video_data[1],
            'description': video_data[2] + f"\n\nCredits:\nMaker: {bot.get_user(int(video_data[3])).name}\nEditor: {bot.get_user(int(video_data[4])).name}\nThumbnail: {bot.get_user(int(video_data[5])).name}",
            'tags': ['YourChannelTag']
        },
        'status': {
            'privacyStatus': 'private'  # or 'public', 'unlisted'
        }
    }

    # Upload video
    media_file = MediaFileUpload(video_data[6])
    response_upload = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()

    # Set thumbnail
    youtube.thumbnails().set(
        videoId=response_upload.get('id'),
        media_body=MediaFileUpload(video_data[7])
    ).execute()

    print(f"Video uploaded successfully! Video ID: {response_upload.get('id')}")

bot.run(os.getenv('DISCORD_BOT_TOKEN'))