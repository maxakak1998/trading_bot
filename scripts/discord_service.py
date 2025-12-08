#!/usr/bin/env python3
"""
Discord Notification Service for Trading Bot.

Usage:
    python scripts/discord_service.py --message "Hello World"
    python scripts/discord_service.py --hyperopt-start --epochs 800 --timerange 20240101-20240701
    python scripts/discord_service.py --hyperopt-complete --result "75 trades, 53% win rate"
"""

import argparse
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Discord Webhook URL
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1447437726038233244/DvfA_bftWa_xUsGVqCOAPcWRUg-i08t7HooV2Q_c91U6Kb4l0j0SjKU20U0_Vl0fWY85"


def send_discord(message: str, webhook_url: str = DISCORD_WEBHOOK) -> bool:
    """Send a message to Discord webhook."""
    try:
        data = json.dumps({"content": message}).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status in [200, 204]
    
    except urllib.error.URLError as e:
        print(f"Error sending Discord message: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def send_hyperopt_start(epochs: int, timerange: str) -> bool:
    """Send hyperopt start notification."""
    message = f"🚀 **Hyperopt Started**\n" \
              f"📊 Epochs: {epochs}\n" \
              f"📅 Timerange: {timerange}\n" \
              f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return send_discord(message)


def send_hyperopt_complete(result: str = "") -> bool:
    """Send hyperopt complete notification."""
    message = f"✅ **Hyperopt Complete!**\n" \
              f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
              f"📊 Results backed up to Google Drive"
    
    if result:
        message += f"\n```\n{result}\n```"
    
    return send_discord(message)


def send_hyperopt_error(error: str) -> bool:
    """Send hyperopt error notification."""
    message = f"❌ **Hyperopt Failed!**\n" \
              f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
              f"```\n{error[:500]}\n```"
    return send_discord(message)


def main():
    parser = argparse.ArgumentParser(description="Discord Notification Service")
    parser.add_argument("--message", "-m", help="Custom message to send")
    parser.add_argument("--hyperopt-start", action="store_true", help="Send hyperopt start notification")
    parser.add_argument("--hyperopt-complete", action="store_true", help="Send hyperopt complete notification")
    parser.add_argument("--hyperopt-error", action="store_true", help="Send hyperopt error notification")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--timerange", default="", help="Timerange for hyperopt")
    parser.add_argument("--result", default="", help="Result summary")
    parser.add_argument("--error", default="Unknown error", help="Error message")
    
    args = parser.parse_args()
    
    success = False
    
    if args.message:
        success = send_discord(args.message)
    elif args.hyperopt_start:
        success = send_hyperopt_start(args.epochs, args.timerange)
    elif args.hyperopt_complete:
        success = send_hyperopt_complete(args.result)
    elif args.hyperopt_error:
        success = send_hyperopt_error(args.error)
    else:
        parser.print_help()
        return
    
    if success:
        print("✅ Discord notification sent!")
    else:
        print("❌ Failed to send Discord notification")


if __name__ == "__main__":
    main()
