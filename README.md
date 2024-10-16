# Discord Bot Video Manager
This project provides a complete solution for managing video submissions and editor interactions through a Discord bot, paired with a web interface for monitoring and configuration. It enhances video content workflows for content creators, editors, and admins alike.

## Key Features

- **Discord Bot** for seamless video submission, status tracking, and editor management.
- **Web Interface** for easy configuration, real-time monitoring, and status overview.
- **GitHub Integration** for issue tracking related to video submissions and project management.
- **YouTube Video Uploading** functionality directly from the bot interface.
- **Interactive Discord Elements** such as modals, buttons, and slash commands for better user interaction.
- **Content Creator Leaderboard** showcasing top contributors based on submission performance.
- **Editor Rating System** enabling users to rate editors' work post-editing.
- **Video Analytics Dashboard** with interactive graphs and performance metrics.
- **Video Preview Functionality** allowing quick previews of edited content.
- **Role-Based Access Control** for managing permissions across bot and web interface features.
- **Notification System** to inform users about important events like video status updates, new comments, and assigned tasks.
- **Enhanced Analytics** with more detailed insights, such as video performance metrics, user engagement, and editor efficiency.
- **Responsive Design** ensuring the web interface works well on mobile devices.
- **User-Friendly Forms** with better validation, error handling, and user feedback.
- **Interactive Elements** like drag-and-drop file uploads, real-time updates, and progress indicators.

## Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/discord-bot-video-manager.git
   cd discord-bot-video-manager
   ```

2. **Install Required Packages**:
   Ensure you have Python 3.9+ installed. Then run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**:
   Create a `.env` file in the project root and configure your credentials:
   ```plaintext
   DISCORD_BOT_TOKEN=your_discord_bot_token
   GITHUB_TOKEN=your_github_personal_access_token
   YOUTUBE_API_KEY=your_youtube_api_key
   ```

4. **Bot Configuration**:
   Configure the bot through Discord commands (`/config`) or via the web interface.

5. **Run the Discord Bot**:
   ```bash
   python bot.py
   ```

6. **Launch the Web Interface**:
   ```bash
   python web_interface.py
   ```
   Access the web interface at `http://localhost:5000`.

## Usage

- **Discord Commands**:
  - `/help`: Display available commands and their descriptions.
  - `/submit_video`: Submit a video for editing.
  - `/video_status`: Check the current status of your submitted videos.
  - `/config`: Modify bot settings (admin only).
  - `/show_config`: View current bot configurations (admin only).
  - `/leaderboard`: See the top 10 content creators by video performance.
  - `/rate_editor`: Rate an editor’s work after reviewing the edited video.
  - `/video_analytics`: Get detailed video submission analytics.
  - `/video_info`: Get detailed information about a specific video.
  - `/support`: Create a support request.

- **Web Interface**:
  - **Dashboard**: View video submission statuses, see editor ratings, and analyze video performance through graphs.
  - **Configuration Management**: Update bot settings, GitHub issue tracking, YouTube API keys, etc.
  - **Leaderboard**: Track top creators and editors based on ratings and submissions.
  - **Video Preview**: Review submitted and edited videos before final approval.
  - **Submit Video**: Submit new videos for editing.
  - **Analytics**: View detailed video performance metrics and user engagement.

## Additional Features

- **Commenting System**: Users can leave feedback and comments on videos through the web interface, fostering engagement.
- **Automatic Editor Assignment**: Editors are auto-assigned based on availability and skill level.
- **Status Notifications**: The bot notifies users when the status of their submitted videos is updated (e.g., In Review, Approved).
- **Custom Video Categories**: Admins can define custom categories for better content organization.
- **Detailed Analytics**: View submission trends, editor performance, video views, and user engagement with detailed graphs.
- **User Profiles**: Users can manage their submission history, ratings, and track performance.
- **Role-Based Access**: Ensures only authorized users (e.g., admins, editors) can perform specific actions within the bot or web interface.
- **Service Integrations**: Extend functionality by integrating with social media platforms or CMS tools for streamlined video publishing.

## Contribution Guidelines

We welcome contributions! If you're interested in improving this project, please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m 'Add feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request for review.

For major changes, it’s recommended to discuss the feature first via a GitHub issue.

## License

This project is licensed under the [MIT License](LICENSE).

## Future Enhancements

- **Live Collaboration**: Enable real-time collaboration between editors and creators on video projects.
- **Expanded Analytics**: Incorporate advanced insights into user engagement, video completion rates, and viewer demographics.
- **Mobile-Friendly Web Interface**: Optimize the web dashboard for mobile devices.
- **Cloud Deployment Support**: Provide out-of-the-box integration with cloud services like AWS or Heroku for easy deployment.
