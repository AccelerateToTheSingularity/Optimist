"""
Generate a comprehensive stats dashboard HTML page for GitHub Pages.
This page displays all bot statistics for r/accelerate moderators.
"""

import json
import os
from datetime import datetime, timezone
from collections import Counter


def load_json(filepath, default):
    """Load JSON file or return default."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            pass
    return default


def format_cost(cost):
    """Format cost nicely."""
    if cost < 0.01:
        return f"${cost:.6f}"
    elif cost < 1:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"


def format_number(n):
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 10_000:
        return f"{n/1_000:.1f}K"
    else:
        return f"{n:,}"


def format_datetime(dt_str):
    """Format datetime string nicely."""
    if not dt_str or dt_str == "Never":
        return "Never"
    try:
        # Handle both ISO formats
        dt_str = dt_str.replace('Z', '+00:00')
        if '+' not in dt_str and 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        return dt_str


def generate_html():
    """Generate the comprehensive stats dashboard HTML."""
    # Load both data sources
    stats = load_json("data/stats.json", {
        "total_tldrs": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "runs": 0,
        "last_run": None
    })
    
    state = load_json("data/bot_state.json", {
        "processed_posts": [],
        "processed_comments": [],
        "replied_to_comments": [],
        "summon_responses": [],
        "stats": {},
        "crosspost": {"history": []},
        "acceleration": {"opted_in_users": {}, "scanned_users": {}, "high_score": 0},
        "moderator_cache": {"moderators": []}
    })
    
    # Extract stats from state (more comprehensive)
    state_stats = state.get("stats", {})
    
    # Core metrics
    total_tldrs = stats.get("total_tldrs", 0) or state_stats.get("total_tldrs_generated", 0)
    total_runs = stats.get("runs", 0)
    total_tokens = stats.get("total_tokens", 0)
    total_cost = stats.get("total_cost", 0.0)
    
    # From state
    total_posts_processed = state_stats.get("total_posts_processed", len(state.get("processed_posts", [])))
    total_comments_processed = len(state.get("processed_comments", []))
    total_replies_sent = state_stats.get("total_replies_sent", len(state.get("replied_to_comments", [])))
    total_summons_handled = state_stats.get("total_summons_handled", len(state.get("summon_responses", [])))
    total_crossposts = state_stats.get("total_crossposts", len(state.get("crosspost", {}).get("history", [])))
    
    # Acceleration stats
    acceleration = state.get("acceleration", {})
    opted_in_users = acceleration.get("opted_in_users", {})
    scanned_users = acceleration.get("scanned_users", {})
    high_score = acceleration.get("high_score", 0)
    
    # Count users by tier
    tier_counts = Counter()
    for user_data in opted_in_users.values():
        if user_data.get("enabled"):
            tier = user_data.get("tier", "Unknown")
            tier_counts[tier] += 1
    
    total_flair_users = sum(1 for u in opted_in_users.values() if u.get("enabled"))
    total_users_scanned = len(scanned_users)
    
    # Moderator stats
    moderators = state.get("moderator_cache", {}).get("moderators", [])
    mod_count = len([m for m in moderators if not m.lower().endswith("bot") and m != "AutoModerator"])
    
    # Crosspost history
    crosspost_history = state.get("crosspost", {}).get("history", [])[-5:]  # Last 5
    crosspost_history.reverse()  # Most recent first
    
    # Last run
    last_run = stats.get("last_run", "Never")
    last_run_formatted = format_datetime(last_run)
    
    # Generate timestamp
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    # Build crosspost list HTML
    crosspost_html = ""
    if crosspost_history:
        crosspost_html = """
            <div class="section">
                <h2>🔗 Recent Crossposts to r/ProAI</h2>
                <div class="crosspost-list">
        """
        for cp in crosspost_history:
            title = cp.get("original_title", "Unknown")[:60]
            if len(cp.get("original_title", "")) > 60:
                title += "..."
            score = cp.get("score_at_crosspost", 0)
            timestamp = cp.get("timestamp", "")
            date_str = timestamp.split("T")[0] if "T" in timestamp else timestamp
            target_url = cp.get("target_url", "#")
            
            crosspost_html += f"""
                    <div class="crosspost-item">
                        <a href="{target_url}" target="_blank" class="crosspost-title">{title}</a>
                        <div class="crosspost-meta">
                            <span class="crosspost-score">⬆ {score}</span>
                            <span class="crosspost-date">{date_str}</span>
                        </div>
                    </div>
            """
        crosspost_html += """
                </div>
            </div>
        """
    
    # Build acceleration tier breakdown HTML
    tier_html = ""
    if tier_counts:
        tier_order = ["Light-speed", "Hypersonic", "Supersonic", "Speeding", "Cruising", "Crawling"]
        # Flame colors: cool (dark red) to hot (white-blue)
        tier_colors = {
            "Crawling": "#8b0000",      # Dark red (coolest flame)
            "Cruising": "#dc2626",      # Red
            "Speeding": "#f97316",      # Orange
            "Supersonic": "#facc15",    # Yellow-orange
            "Hypersonic": "#fef08a",    # Pale yellow (hot)
            "Light-speed": "#bfdbfe",   # White-blue (hottest flame core)
        }
        tier_html = """
            <div class="section">
                <h2>🚀 Acceleration Flair Breakdown</h2>
                <div class="tier-grid">
        """
        for tier in tier_order:
            count = tier_counts.get(tier, 0)
            if count > 0:
                color = tier_colors.get(tier, "#58a6ff")
                tier_html += f"""
                    <div class="tier-card" style="border-color: {color}">
                        <div class="tier-name" style="color: {color}">{tier}</div>
                        <div class="tier-count">{count}</div>
                        <div class="tier-label">users</div>
                    </div>
                """
        tier_html += """
                </div>
            </div>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimist Prime Bot - Stats Dashboard</title>
    <meta name="description" content="Live statistics dashboard for the Optimist Prime bot on r/accelerate">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0f0f14;
            --bg-card: #1a1a24;
            --bg-card-hover: #24242f;
            --border: #3a3a4a;
            --text-primary: #ffffff;
            --text-secondary: #a0a0b8;
            --text-muted: #70708a;
            --accent: #818cf8;
            --accent-bright: #a5b4fc;
            --accent-glow: rgba(129, 140, 248, 0.3);
            --success: #4ade80;
            --success-glow: rgba(74, 222, 128, 0.3);
            --warning: #fbbf24;
            --purple: #c084fc;
            --pink: #f472b6;
            --cyan: #22d3ee;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2.5rem;
            font-size: 16px;
            line-height: 1.6;
            background-image: 
                radial-gradient(ellipse at top, rgba(129, 140, 248, 0.12) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(192, 132, 252, 0.1) 0%, transparent 50%);
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem 0;
        }}
        
        .logo {{
            font-size: 4rem;
            margin-bottom: 0.5rem;
            animation: float 3s ease-in-out infinite;
        }}
        
        @keyframes float {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-10px); }}
        }}
        
        h1 {{
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            background: linear-gradient(135deg, var(--accent-bright), var(--purple), var(--pink));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.25rem;
            font-weight: 400;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.75rem 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), var(--purple));
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-4px);
            background: var(--bg-card-hover);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }}
        
        .stat-card:hover::before {{
            opacity: 1;
        }}
        
        .stat-icon {{
            font-size: 2rem;
            margin-bottom: 0.75rem;
        }}
        
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 500;
        }}
        
        .section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
        }}
        
        .section h2 {{
            font-size: 1.35rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: var(--text-primary);
        }}
        
        .tier-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1.25rem;
        }}
        
        .tier-card {{
            background: rgba(255, 255, 255, 0.04);
            border: 2px solid;
            border-radius: 14px;
            padding: 1.25rem 1rem;
            text-align: center;
            transition: transform 0.2s ease;
        }}
        
        .tier-card:hover {{
            transform: scale(1.05);
        }}
        
        .tier-name {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .tier-count {{
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .tier-label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-top: 0.25rem;
        }}
        
        .crosspost-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .crosspost-item {{
            background: rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 1.25rem;
            transition: background 0.2s ease;
        }}
        
        .crosspost-item:hover {{
            background: rgba(255, 255, 255, 0.07);
        }}
        
        .crosspost-title {{
            color: var(--accent-bright);
            text-decoration: none;
            font-weight: 500;
            font-size: 1.05rem;
            display: block;
            margin-bottom: 0.6rem;
            line-height: 1.4;
        }}
        
        .crosspost-title:hover {{
            text-decoration: underline;
        }}
        
        .crosspost-meta {{
            display: flex;
            gap: 1.25rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}
        
        .crosspost-score {{
            color: var(--success);
            font-weight: 500;
        }}
        
        .status-bar {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.25rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .status-indicator {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .status-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 12px var(--success-glow);
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; box-shadow: 0 0 12px var(--success-glow); }}
            50% {{ opacity: 0.6; box-shadow: 0 0 20px var(--success-glow); }}
        }}
        
        .status-text {{
            font-weight: 600;
            font-size: 1.1rem;
        }}
        
        .last-run {{
            color: var(--text-secondary);
            font-size: 1rem;
        }}
        
        footer {{
            text-align: center;
            margin-top: 3rem;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 1rem;
        }}
        
        footer a {{
            color: var(--accent-bright);
            text-decoration: none;
            transition: color 0.2s ease;
        }}
        
        footer a:hover {{
            color: var(--purple);
        }}
        
        .footer-links {{
            margin-bottom: 1rem;
        }}
        
        .footer-links span {{
            margin: 0 0.6rem;
            color: var(--text-muted);
        }}
        
        .generated-time {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}
        
        /* Responsive adjustments */
        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}
            
            h1 {{
                font-size: 1.75rem;
            }}
            
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 0.75rem;
            }}
            
            .stat-card {{
                padding: 1rem;
            }}
            
            .stat-value {{
                font-size: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">🤖</div>
            <h1>Optimist Prime</h1>
            <p class="subtitle">Bot Statistics for r/accelerate</p>
        </header>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span class="status-text">Bot Active</span>
            </div>
            <div class="last-run">
                Last run: {last_run_formatted}
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📝</div>
                <div class="stat-value">{format_number(total_tldrs)}</div>
                <div class="stat-label">TLDRs Generated</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-value">{format_number(total_posts_processed)}</div>
                <div class="stat-label">Posts Processed</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">💬</div>
                <div class="stat-value">{format_number(total_comments_processed)}</div>
                <div class="stat-label">Long Comments</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🗣️</div>
                <div class="stat-value">{total_replies_sent}</div>
                <div class="stat-label">Replies Sent</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">📢</div>
                <div class="stat-value">{total_summons_handled}</div>
                <div class="stat-label">Summons Handled</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-value">{total_crossposts}</div>
                <div class="stat-label">Crossposts Made</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🚀</div>
                <div class="stat-value">{total_flair_users}</div>
                <div class="stat-label">Flair Users</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-value">{format_number(total_users_scanned)}</div>
                <div class="stat-label">Users Scanned</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🔁</div>
                <div class="stat-value">{format_number(total_runs)}</div>
                <div class="stat-label">Bot Runs</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🪙</div>
                <div class="stat-value">{format_number(total_tokens)}</div>
                <div class="stat-label">Tokens Used</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">💰</div>
                <div class="stat-value">{format_cost(total_cost)}</div>
                <div class="stat-label">API Cost</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-value">{format_number(high_score)}</div>
                <div class="stat-label">Top Accelerator Score</div>
            </div>
        </div>
        
        {tier_html}
        
        {crosspost_html}
        
        <footer>
            <div class="footer-links">
                <a href="https://github.com/features/actions">GitHub Actions</a>
                <span>•</span>
                <a href="https://ai.google.dev/">Google Gemini</a>
                <span>•</span>
                <a href="https://reddit.com/r/accelerate">r/accelerate</a>
                <span>•</span>
                <a href="https://reddit.com/r/ProAI">r/ProAI</a>
            </div>
            <p class="generated-time">
                Page generated: {generated_at}
            </p>
        </footer>
    </div>
</body>
</html>"""
    
    return html


def main():
    """Generate and save the stats page."""
    os.makedirs("docs", exist_ok=True)
    
    html = generate_html()
    
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("[OK] Generated docs/index.html")


if __name__ == "__main__":
    main()
