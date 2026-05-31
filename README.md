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

## Stats Dashboard

**Live stats:** [https://acceleratetothesingularity.github.io/Optimist/](https://acceleratetothesingularity.github.io/Optimist/)

Updated weekly (Mondays at midnight UTC).

## Setup

### 1. Fork this repository

### 2. Register a Reddit App

Go to https://www.reddit.com/prefs/apps/ and create a **web app**:
- Name: `OptimistPrimeModBot`
- Redirect URI: `http://localhost:8080`

Note the **client ID** (under the app name) and **client secret**.

### 3. Get a Refresh Token

Run the auth script locally to authorize the bot account:

```bash
set REDDIT_CLIENT_ID=your_client_id
set REDDIT_CLIENT_SECRET=your_client_secret
py obtain_refresh_token.py
```

This opens a Reddit page. Log in as `u/OptimistPrime_AI_Bot` and click "Allow".
The script prints a refresh token — copy it.

### 4. Add GitHub Secrets

Go to Settings → Secrets and variables → Actions:

| Secret Name | Description |
|-------------|-------------|
| `REDDIT_CLIENT_ID` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret |
| `REDDIT_REFRESH_TOKEN` | Refresh token from step 3 |
| `REDDIT_APP_NAME` | App name for User-Agent (default: OptimistPrimeModBot) |
| `OPENAI_API_KEY` | LLM API key (MiniMax via OpenAI-compatible API) |
| `EMAIL_USERNAME` | Gmail for notifications (optional) |
| `EMAIL_PASSWORD` | Gmail app password (optional) |
| `NOTIFICATION_EMAIL` | Email to receive failure alerts (optional) |

### 5. Enable Actions

Go to the Actions tab and enable workflows.

## Configuration

Edit `config.py` to customize all settings.

## API Compliance (2026)

This bot complies with Reddit's 2026 automated account transparency requirements:

- **User-Agent Format**: Uses the required format: `<platform>:<app ID>:<version> (by /u/<reddit username>)`
- **Registered App**: Uses the "Optimist Prime Mod Bot" registered under u/stealthispost
- **[App] Label**: Bot posts show the [App] label to identify as automated content

To test the bot's API compliance, you can run:
```bash
python bot_runner.py --test-comment
```

This will post a test comment in the specified Reddit thread to verify:
1. Bot can authenticate as u/OptimistPrime_AI_Bot
2. User-Agent is properly formatted
3. Bot posts show the [App] label

## Costs

- **GitHub Actions**: Free for public repos
- **LLM API (MiniMax)**: billed per provider usage; see [MiniMax pricing](https://platform.minimax.io/)

## License

MIT
