"""
Generate a beautiful stats dashboard HTML page for GitHub Pages.
"""

import json
import os
from datetime import datetime

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


def generate_html():
    """Generate the stats dashboard HTML."""
    stats = load_json("data/stats.json", {
        "total_tldrs": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "runs": 0,
        "last_run": None
    })
    
    state = load_json("data/tldr_state.json", {
        "processed_posts": [],
        "stats": {}
    })
    
    last_run = stats.get("last_run", "Never")
    if last_run and last_run != "Never":
        try:
            dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            last_run = dt.strftime("%Y-%m-%d %H:%M UTC")
        except:
            pass
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit TLDR Bot - Stats Dashboard</title>
    <style>
        :root {{
            --bg-dark: #0d1117;
            --bg-card: #161b22;
            --border: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --success: #3fb950;
            --warning: #d29922;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--accent), var(--success));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }}
        
        .stat-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--accent);
            margin-bottom: 0.5rem;
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .status-bar {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .status-indicator {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .status-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .last-run {{
            color: var(--text-secondary);
        }}
        
        footer {{
            text-align: center;
            margin-top: 3rem;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        
        footer a {{
            color: var(--accent);
            text-decoration: none;
        }}
        
        footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Reddit TLDR Bot</h1>
            <p class="subtitle">Automatic summaries for r/accelerate</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_tldrs', 0)}</div>
                <div class="stat-label">TLDRs Generated</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{stats.get('runs', 0):,}</div>
                <div class="stat-label">Bot Runs</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{stats.get('total_tokens', 0):,}</div>
                <div class="stat-label">Tokens Used</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{format_cost(stats.get('total_cost', 0))}</div>
                <div class="stat-label">Total API Cost</div>
            </div>
        </div>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span>Bot Active</span>
            </div>
            <div class="last-run">
                Last run: {last_run}
            </div>
        </div>
        
        <footer>
            <p>
                Running on <a href="https://github.com/features/actions">GitHub Actions</a> • 
                Powered by <a href="https://ai.google.dev/">Google Gemini</a> • 
                <a href="https://reddit.com/r/accelerate">r/accelerate</a>
            </p>
            <p style="margin-top: 0.5rem;">
                Page generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
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
    
    print("✅ Generated docs/index.html")


if __name__ == "__main__":
    main()
