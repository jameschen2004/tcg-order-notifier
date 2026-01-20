# TCGplayer Discord Order Notifier

An automated solution for TCGplayer sellers to receive real-time Discord notifications for new orders, including buyer information missing from standard email alerts.

## Overview
Standard TCGplayer email notifications omit the buyer's name. This project automates the process of watching for new order emails, scraping the buyer's name from the seller portal, and pushing a formatted alert to a Discord channel.

## Features
* Uses Gmail Push Notifications (Pub/Sub) for instant detection.
* Leverages Playwright to securely retrieve buyer names from the TCGplayer Seller Portal.
* Hosted on AWS Lambda for cost effective and 24/7 reliability.
* Sends Discord embeds with order IDs, items, and buyer names.

## Tech Stack
* **Language:** Python 3.x
* **Browser Automation:** Playwright (Chromium)
* **Cloud Infrastructure:** AWS Lambda, Amazon ECR (Docker)
* **APIs:** Gmail API, Google Cloud Pub/Sub, Discord Webhooks