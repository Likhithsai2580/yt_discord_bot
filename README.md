<<<<<<< HEAD
# Discord Bot Video Manager

This project consists of a Discord bot for managing video submissions and a web interface for monitoring and configuration.

## Features

- Discord bot for video submission and management
- Web interface for configuration and video status overview
- GitHub issue monitoring
- YouTube video upload functionality
- Enhanced UI with Bootstrap
- Improved Discord interaction system using modals and buttons
- Leaderboard for top content creators
- Editor rating system
- Video analytics with graphs
- Video preview functionality

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/discord-bot-video-manager.git
   cd discord-bot-video-manager
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root and add the following:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   GITHUB_TOKEN=your_github_personal_access_token
   ```

4. Configure the bot using the `/config` command in Discord or through the web interface.

5. Run the Discord bot:
   ```
   python bot.py
   ```

6. Run the web interface:
   ```
   python web_interface.py
   ```

## Usage

- Use Discord slash commands to interact with the bot:
  - `/help`: Show available commands
  - `/submit_video`: Submit a new video for editing
  - `/video_status`: Check the status of your submitted videos
  - `/config`: Configure bot settings (admin only)
  - `/show_config`: Display current configuration (admin only)
  - `/leaderboard`: View top 10 content creators
  - `/rate_editor`: Rate an editor's work
  - `/video_analytics`: View video submission analytics

- Access the web interface at `http://localhost:5000` to:
  - View video status
  - Manage configuration
  - See leaderboard
  - View analytics
  - Preview videos

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)

## Additional Features

- **Video Commenting System**: Users can comment on videos through the web interface, fostering engagement and feedback.
- **Editor Assignment**: The bot can automatically assign editors to submitted videos based on their availability and expertise.
- **Video Status Notifications**: The bot sends notifications to users when the status of their submitted videos changes.
- **Customizable Video Categories**: Admins can create and manage custom categories for videos, making it easier to organize and filter content.
- **Enhanced Video Analytics**: The web interface provides detailed analytics on video performance, including views, engagement, and ratings.
- **User Profile Management**: Users can view their submission history, ratings, and other profile information through the web interface.
- **Role-Based Access Control**: The bot and web interface implement role-based access control, ensuring that only authorized users can perform certain actions.
- **Integration with Other Services**: The project can be extended to integrate with other services, such as social media platforms or content management systems, to further streamline video management.

