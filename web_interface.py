from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import json
import os
from datetime import datetime
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL, EqualTo
from flask_caching import Cache
import matplotlib.pyplot as plt
import io
import base64
from flask_paginate import Pagination, get_page_args
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import plotly.express as px
import pandas as pd
from flask import abort
import threading
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///videos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
Bootstrap(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Asynchronous database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///videos.db')
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
Base = declarative_base()

class User(UserMixin, Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
async def load_user(user_id):
    async with async_session() as session:
        result = await session.execute(select(User).filter_by(id=int(user_id)))
        return result.scalars().first()

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

class Comment(Base):
    __tablename__ = 'comment'
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    video_id = Column(Integer, ForeignKey('video.id'), nullable=False)

    user = relationship('User', backref='comments')
    video = relationship('Video', backref='comments')

async def create_admin_user():
    async with async_session() as session:
        result = await session.execute(select(User).filter_by(username='admin'))
        admin = result.scalars().first()
        if not admin:
            admin = User(username='admin')
            admin.set_password('admin_password')  # Change this to a secure password
            session.add(admin)
            await session.commit()

class ConfigForm(FlaskForm):
    github_username = StringField('GitHub Username', validators=[DataRequired()])
    editor_channel_id = StringField('Editor Channel ID', validators=[DataRequired()])
    thumbnail_channel_id = StringField('Thumbnail Channel ID', validators=[DataRequired()])
    github_issues_channel_id = StringField('GitHub Issues Channel ID', validators=[DataRequired()])
    trusted_role_id = StringField('Trusted Role ID', validators=[DataRequired()])
    github_token = StringField('GitHub Token', validators=[DataRequired()])
    youtube_token_path = StringField('YouTube Token Path', validators=[DataRequired()])
    submit = SubmitField('Save Configuration')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Post Comment')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Register')

class VideoSubmissionForm(FlaskForm):
    title = StringField('Video Title', validators=[DataRequired()])
    description = TextAreaField('Video Description', validators=[DataRequired()])
    gdrive_link = StringField('Google Drive Link', validators=[DataRequired(), URL()])
    submit = SubmitField('Submit Video')

def load_config():
    config = {
        'github_username': os.getenv('GITHUB_USERNAME', ''),
        'editor_channel_id': os.getenv('EDITOR_CHANNEL_ID', ''),
        'thumbnail_channel_id': os.getenv('THUMBNAIL_CHANNEL_ID', ''),
        'github_issues_channel_id': os.getenv('GITHUB_ISSUES_CHANNEL_ID', ''),
        'trusted_role_id': os.getenv('TRUSTED_ROLE_ID', ''),
        'github_token': os.getenv('GITHUB_TOKEN', ''),
        'youtube_token_path': os.getenv('YOUTUBE_TOKEN_PATH', '')
    }
    return {k: v for k, v in config.items() if v}  # Remove empty values

def save_config(config):
    for key, value in config.items():
        os.environ[key.upper()] = value

@app.route('/')
async def index():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    async with async_session() as session:
        result = await session.execute(select(Video).order_by(Video.created_at.desc()).offset(offset).limit(per_page))
        videos = result.scalars().all()
        total = await session.execute(select(func.count(Video.id)))
        total = total.scalar()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4')
    config = load_config()
    return render_template('index.html', videos=videos, pagination=pagination, config=config, current_user=current_user)

@app.route('/config', methods=['GET', 'POST'])
async def config():
    form = ConfigForm()
    if form.validate_on_submit():
        config = {
            'github_username': form.github_username.data,
            'editor_channel_id': form.editor_channel_id.data,
            'thumbnail_channel_id': form.thumbnail_channel_id.data,
            'github_issues_channel_id': form.github_issues_channel_id.data,
            'trusted_role_id': form.trusted_role_id.data,
            'github_token': form.github_token.data,
            'youtube_token_path': form.youtube_token_path.data
        }
        save_config(config)
        flash('Configuration updated successfully!', 'success')
        return redirect(url_for('index'))
    
    config = load_config()
    form.github_username.data = config.get('github_username', '')
    form.editor_channel_id.data = config.get('editor_channel_id', '')
    form.thumbnail_channel_id.data = config.get('thumbnail_channel_id', '')
    form.github_issues_channel_id.data = config.get('github_issues_channel_id', '')
    form.trusted_role_id.data = config.get('trusted_role_id', '')
    form.github_token.data = config.get('github_token', '')
    form.youtube_token_path.data = config.get('youtube_token_path', '')
    return render_template('config.html', form=form)

@app.route('/video/<int:id>')
async def video_detail(id):
    async with async_session() as session:
        result = await session.execute(select(Video).filter_by(id=id))
        video = result.scalars().first()
    if not video:
        abort(404)
    form = CommentForm()
    if form.validate_on_submit():
        async with async_session() as session:
            comment = Comment(content=form.content.data, user_id=current_user.id, video_id=video.id)
            session.add(comment)
            await session.commit()
        flash('Your comment has been posted!', 'success')
        return redirect(url_for('video_detail', id=video.id))
    return render_template('video_detail.html', title=video.title, video=video, form=form)

@app.route('/api/videos')
async def api_videos():
    async with async_session() as session:
        result = await session.execute(select(Video).order_by(Video.created_at.desc()))
        videos = result.scalars().all()
    return jsonify([{
        'id': v.id,
        'title': v.title,
        'status': v.status,
        'created_at': v.created_at.isoformat()
    } for v in videos])

@app.route('/leaderboard')
@cache.cached(timeout=300)  # Cache for 5 minutes
async def leaderboard():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    async with async_session() as session:
        result = await session.execute(
            select(Video.maker, func.count(Video.id).label('video_count'))
            .group_by(Video.maker)
            .order_by(func.count(Video.id).desc())
        )
        results = result.all()
    total = len(results)
    pagination_results = results[offset: offset + per_page]
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4')
    return render_template('leaderboard.html', results=pagination_results, pagination=pagination, enumerate=enumerate)

@app.route('/analytics')
@login_required
@cache.cached(timeout=3600)  # Cache for 1 hour
async def analytics():
    async with async_session() as session:
        result = await session.execute(select(Video))
        videos = result.scalars().all()
    df = pd.DataFrame([(v.created_at, v.status) for v in videos], columns=['date', 'status'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.resample('D').count().reset_index()

    fig = px.line(df, x='date', y='status', title='Video Submissions Over Time')
    graph_json = fig.to_json()

    status_counts = [(v.status, df[df['status'] == v.status].shape[0]) for v in videos]
    status_fig = px.pie(values=[count for _, count in status_counts], names=[status for status, _ in status_counts], title='Video Status Distribution')
    status_graph_json = status_fig.to_json()

    return render_template('analytics.html', line_graph=graph_json, pie_graph=status_graph_json)

@app.route('/video/<int:id>/preview')
async def video_preview(id):
    async with async_session() as session:
        result = await session.execute(select(Video).filter_by(id=id))
        video = result.scalars().first()
    if not video:
        abort(404)
    return render_template('video_preview.html', video=video)

@app.route('/login', methods=['GET', 'POST'])
async def login():
    form = LoginForm()
    if form.validate_on_submit():
        async with async_session() as session:
            result = await session.execute(select(User).filter_by(username=form.username.data))
            user = result.scalars().first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
async def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
async def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        async with async_session() as session:
            result = await session.execute(select(User).filter_by(username=form.username.data))
            user = result.scalars().first()
        if user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        async with async_session() as session:
            session.add(new_user)
            await session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/video/<int:id>/delete', methods=['POST'])
@login_required
async def delete_video(id):
    async with async_session() as session:
        result = await session.execute(select(Video).filter_by(id=id))
        video = result.scalars().first()
    if not video:
        abort(404)
    if current_user.username != 'admin':
        abort(403)
    async with async_session() as session:
        await session.delete(video)
        await session.commit()
    flash('Video has been deleted.', 'success')
    return redirect(url_for('index'))

@app.route('/submit_video', methods=['GET', 'POST'])
@login_required
async def submit_video():
    form = VideoSubmissionForm()
    if form.validate_on_submit():
        new_video = Video(
            title=form.title.data,
            description=form.description.data,
            maker=current_user.username,
            gdrive_link=form.gdrive_link.data,
            status='submitted'
        )
        async with async_session() as session:
            session.add(new_video)
            await session.commit()
        flash('Your video has been submitted successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('submit_video.html', form=form, title='Submit Video')

with app.app_context():
    db.create_all()
    asyncio.run(create_admin_user())

def run_bot():
    # Import the bot code here to avoid circular imports
    from bot import run_discord_bot
    run_discord_bot()

if __name__ == '__main__':
    app.run(debug=True)
