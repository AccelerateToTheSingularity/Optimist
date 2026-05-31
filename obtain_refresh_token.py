#!/usr/bin/env python3
"""
One-time script to obtain a Reddit refresh token for PRAW authentication.

Opens a Reddit authorization page in your browser. Log in as the bot account
and click "Allow". The script captures the refresh token and prints it.
"""

import os
import sys
import random
import socket
import webbrowser
import time

import praw


def main():
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.")
        return 1

    scopes = [
        "identity", "edit", "submit", "read", "save",
        "history", "mysubreddits", "subscribe", "vote",
        "privatemessages", "modconfig", "modflair", "modlog",
        "modposts", "modwiki", "wikiedit", "wikiread",
    ]

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8080",
        user_agent="OptimistPrimeModBot obtain_refresh_token by u/stealthispost",
    )

    state = str(random.randint(0, 65000))
    url = reddit.auth.url(duration="permanent", scopes=scopes, state=state)

    print("=" * 60)
    print("OPEN THIS URL IN YOUR BROWSER:")
    print()
    print(url)
    print()
    print("Log in as u/OptimistPrime_AI_Bot and click Allow.")
    print("Waiting for authorization on http://localhost:8080 ...")
    print("=" * 60)

    # Open browser automatically
    webbrowser.open(url)

    # Wait for the redirect
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("localhost", 8080))
    server.listen(1)
    server.settimeout(120)  # 2 minute timeout
    try:
        client = server.accept()[0]
    except socket.timeout:
        print("Timed out waiting for authorization.")
        server.close()
        return 1

    data = client.recv(1024).decode("utf-8")

    # Parse the redirect URL
    try:
        param_tokens = data.split(" ", 2)[1].split("?", 1)[1].split("&")
        params = {key: value for key, value in [token.split("=") for token in param_tokens]}
    except (IndexError, ValueError):
        client.send(b"HTTP/1.1 400 Bad Request\r\n\r\nFailed to parse request")
        client.close()
        server.close()
        print("Failed to parse the redirect URL.")
        return 1

    if state != params.get("state"):
        client.send(b"HTTP/1.1 400 Bad Request\r\n\r\nState mismatch")
        client.close()
        server.close()
        print(f"Error: State mismatch. Expected: {state}, Got: {params.get('state')}")
        return 1

    if "error" in params:
        client.send(f"HTTP/1.1 400 Bad Request\r\n\r\nError: {params['error']}".encode())
        client.close()
        server.close()
        print(f"Error: {params['error']}")
        return 1

    # Exchange code for refresh token
    refresh_token = reddit.auth.authorize(params["code"])

    # Send success response to browser
    client.send(b"HTTP/1.1 200 OK\r\n\r\nAuthorization complete! You can close this tab.")
    client.close()
    server.close()

    print()
    print("=" * 60)
    print("SUCCESS! Your refresh token is:")
    print()
    print(f"  {refresh_token}")
    print()
    print("=" * 60)
    print()
    print("Next: Add this as GitHub secret REDDIT_REFRESH_TOKEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
