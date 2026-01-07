# Reddit Bot (r/accelerate)

Multi-function Reddit bot for r/accelerate community moderation.

## Features

- **TLDR Generation**: Summarizes long posts (270+ words) automatically
- **Discussion Summaries**: Tracks comment milestones (20/50/100) and generates conversation summaries
- **Reply Monitoring**: Responds to users who reply to the bot's comments
- **Summon Detection**: Responds when directly addressed ("Hey bot", "Optimist Prime")
- **Auto-Ban**: Bans users with excessive negative karma (< -80) when detected by AutoMod

## How It Works

Runs on GitHub Actions every 3 minutes, 24/7.

## Setup

### 1. Fork this repository

### 2. Add GitHub Secrets

Go to Settings → Secrets and variables → Actions:

| Secret Name | Description |
|-------------|-------------|
| `REDDIT_CLIENT_ID` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret |
| `REDDIT_USERNAME` | Bot Reddit username |
| `REDDIT_PASSWORD` | Bot Reddit password |
| `GEMINI_API_KEY` | Google Gemini API key |
| `EMAIL_USERNAME` | Gmail for notifications (optional) |
| `EMAIL_PASSWORD` | Gmail app password (optional) |
| `NOTIFICATION_EMAIL` | Email to receive failure alerts (optional) |

### 3. Enable Actions

Go to the Actions tab and enable workflows.

## Configuration

Edit `config.py` to customize all settings.

## Costs

- **GitHub Actions**: Free for public repos
- **Gemini API**: ~$0.0001 per generation

## License

MIT
