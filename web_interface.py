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

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///videos.db')
db = SQLAlchemy(app)
Bootstrap(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    maker = db.Column(db.String(100), nullable=False)
    editor = db.Column(db.String(100))
    thumbnail_maker = db.Column(db.String(100))
    edited_path = db.Column(db.String(200))
    thumbnail_path = db.Column(db.String(200))
    gdrive_link = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    video = db.relationship('Video', backref=db.backref('comments', lazy=True))

with app.app_context():
    db.create_all()

def create_admin_user():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin')
        admin.set_password('admin_password')  # Change this to a secure password
        db.session.add(admin)
        db.session.commit()

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
def index():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    videos = Video.query.order_by(Video.created_at.desc()).offset(offset).limit(per_page).all()
    total = Video.query.count()
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4')
    config = load_config()
    return render_template('index.html', videos=videos, pagination=pagination, config=config, current_user=current_user)

@app.route('/config', methods=['GET', 'POST'])
def config():
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
def video_detail(id):
    video = Video.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, user_id=current_user.id, video_id=video.id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been posted!', 'success')
        return redirect(url_for('video_detail', id=video.id))
    return render_template('video_detail.html', title=video.title, video=video, form=form)

@app.route('/api/videos')
def api_videos():
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return jsonify([{
        'id': v.id,
        'title': v.title,
        'status': v.status,
        'created_at': v.created_at.isoformat()
    } for v in videos])

@app.route('/leaderboard')
@cache.cached(timeout=300)  # Cache for 5 minutes
def leaderboard():
    page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
    results = db.session.query(Video.maker, db.func.count(Video.id).label('video_count')) \
        .group_by(Video.maker) \
        .order_by(db.desc('video_count')) \
        .all()
    total = len(results)
    pagination_results = results[offset: offset + per_page]
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4')
    return render_template('leaderboard.html', results=pagination_results, pagination=pagination, enumerate=enumerate)

@app.route('/analytics')
@login_required
@cache.cached(timeout=3600)  # Cache for 1 hour
def analytics():
    videos = Video.query.all()
    df = pd.DataFrame([(v.created_at, v.status) for v in videos], columns=['date', 'status'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.resample('D').count().reset_index()

    fig = px.line(df, x='date', y='status', title='Video Submissions Over Time')
    graph_json = fig.to_json()

    status_counts = Video.query.with_entities(Video.status, db.func.count(Video.id)).group_by(Video.status).all()
    status_fig = px.pie(values=[count for _, count in status_counts], names=[status for status, _ in status_counts], title='Video Status Distribution')
    status_graph_json = status_fig.to_json()

    return render_template('analytics.html', line_graph=graph_json, pie_graph=status_graph_json)

@app.route('/video/<int:id>/preview')
def video_preview(id):
    video = Video.query.get_or_404(id)
    return render_template('video_preview.html', video=video)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/video/<int:id>/delete', methods=['POST'])
@login_required
def delete_video(id):
    video = Video.query.get_or_404(id)
    if current_user.username != 'admin':
        abort(403)
    db.session.delete(video)
    db.session.commit()
    flash('Video has been deleted.', 'success')
    return redirect(url_for('index'))

@app.route('/submit_video', methods=['GET', 'POST'])
@login_required
def submit_video():
    form = VideoSubmissionForm()
    if form.validate_on_submit():
        new_video = Video(
            title=form.title.data,
            description=form.description.data,
            maker=current_user.username,
            gdrive_link=form.gdrive_link.data,
            status='submitted'
        )
        db.session.add(new_video)
        db.session.commit()
        flash('Your video has been submitted successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('submit_video.html', form=form, title='Submit Video')

with app.app_context():
    db.create_all()
    create_admin_user()

def run_bot():
    # Import the bot code here to avoid circular imports
    from bot import run_discord_bot
    run_discord_bot()

if __name__ == '__main__':
    app.run(debug=True)