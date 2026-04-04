# TCGplayer Discord Order Notifier

An automated solution for TCGplayer sellers to receive real-time Discord notifications for new orders, including buyer information and automated order tracking.

## Overview
Standard TCGplayer email notifications omit the buyer's name. This project automates the process of watching for new order emails via the Gmail API, scraping the buyer's name from the seller portal using Playwright, and pushing a formatted alert to a Discord channel with built-in status tracking.

## Features
* Uses the Gmail API to poll for unread TCGplayer order confirmations every 10 minutes.
* Leverages Playwright (Chromium) to securely retrieve buyer names and item details from the TCGplayer Seller Portal.
* Stores order history, buyer names, and fulfillment status in a local SQLite database.
* Sends embeds to Discord, with the buyer's name featured in the header for quick identification.
* Supports Discord reactions to update order status in real-time.
* Architected to run on a zero-cost Google Cloud Platform (GCP) e2-micro instance using a Linux Swap file for memory management.

## Tech Stack
* **Language**: Python 3.x
* **Database**: SQLite3 (Persistent Relational Storage)
* **Browser Automation**: Playwright (Chromium)
* **Cloud Infrastructure**: Google Cloud Platform (Compute Engine), Docker
* **APIs**: Gmail API (OAuth 2.0), Discord API (discord.py)

## Discord Commands
* `!sync`: Manually triggers a Gmail check and processes new orders immediately.
* `!pending`: Displays a list of all orders currently marked as "Pending" in the database.
* `!recent [x]`: Shows the last `x` orders processed by the bot.
* `!remove [OrderID]`: Manually deletes a specific order entry from the database.

## Setup & Deployment

### 1. GCP Configuration
* Enable the **Gmail API** in the Google Cloud Console.
* Configure the **OAuth Consent Screen** and add your email as a Test User.
* Create **OAuth 2.0 Desktop Credentials** and save them as `credentials.json`.
* Run `get_token.py` locally to generate `token.json`.

### 2. VM Preparation
To run on a free-tier `e2-micro` instance, a swap file is required to handle Playwright's memory usage:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
