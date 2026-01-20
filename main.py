import os
import re
import base64
import html
import asyncio
import discord
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from scraper import get_order_details # Ensure you renamed this in scraper.py

load_dotenv()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def get_gmail_service():
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

def clean_html_body(raw_data):
    raw_html = base64.urlsafe_b64decode(raw_data).decode()
    text = html.unescape(raw_html)
    text = re.sub(r'<[^>]+>', ' ', text)
    return " ".join(text.split())

async def process_gmail_orders():
    """Checks Gmail, scrapes order details, and marks emails as read."""
    service = get_gmail_service()
    # Search for unread TCGplayer emails
    query = 'from:sales@tcgplayer.com subject:"Your TCGplayer.com items" is:unread'
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print("📭 No new unread orders found.")
        return

    channel = client.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))

    for msg in messages:
        message_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        payload = message_data.get('payload', {})
        
        # Safe decoding of email body
        data = payload.get('body', {}).get('data') or payload.get('parts', [{}])[0].get('body', {}).get('data')
        if not data: continue

        clean_text = clean_html_body(data)
        # Regex to find the 8-6-5 ID pattern
        order_match = re.search(r"Order[:\s]*([A-F0-9]{8}-[A-F0-9]{6}-[A-F0-9]{5})", clean_text, re.IGNORECASE)
        
        if order_match:
            order_id = order_match.group(1)
            print(f"🎯 Processing Order: {order_id}")
            
            # Use the async scraper
            order_info = await get_order_details(order_id)
            
            if order_info:
                # Build the item string once per order to avoid duplicates
                items_str = "\n".join([f"📦 **{i['qty']}x** {i['name']} — {i['price']}" for i in order_info['items']])
                
                # Fetch the Role ID from your environment variables
                role_id = os.getenv("DISCORD_ROLE_ID")
                ping_content = f"<@&{role_id}>" if role_id else ""

                embed = discord.Embed(title="🚀 New TCGplayer Order!", color=0x03b2f8)
                embed.add_field(name="Buyer", value=order_info['buyer'], inline=True)
                embed.add_field(name="Order ID", value=f"`{order_id}`", inline=True)
                embed.add_field(name="Products", value=items_str or "No items parsed", inline=False)
                
                # Send and Add reactions for your workflow
                discord_msg = await channel.send(content=ping_content, embed=embed)
                await discord_msg.add_reaction("📦") # Packed
                await discord_msg.add_reaction("✅") # Delivered
                await discord_msg.add_reaction("⚠️") # Issue
                
                # This prevents the order from being processed again in 5 minutes
                service.users().messages().batchModify(
                    userId='me', 
                    body={'ids': [msg['id']], 'removeLabelIds': ['UNREAD']}
                ).execute()
                print(f"✅ Order {order_id} processed and marked as read.")
        else:
            print(f"❌ Failed to parse ID from email {msg['id']}")

async def main_loop():
    """Runs the Gmail check every 5 minutes."""
    while True:
        print("🔍 Checking Gmail for new orders...")
        try:
            await process_gmail_orders()
        except Exception as e:
            print(f"⚠️ Error in loop: {e}")
        
        print("Sleeping for 5 minutes...")
        await asyncio.sleep(300) # 300 seconds = 5 minutes

@client.event
async def on_ready():
    print(f"🤖 Bot logged in as {client.user}")
    # Start the background Gmail loop
    if not hasattr(client, 'gmail_task'):
        client.gmail_task = client.loop.create_task(main_loop())

if __name__ == "__main__":
    client.run(os.getenv("DISCORD_BOT_TOKEN"))

@client.event
async def on_raw_reaction_add(payload):
    # Ignore reactions from the bot itself
    if payload.user_id == client.user.id:
        return

    # Check if the reaction is in your specific channel
    if payload.channel_id == int(os.getenv("DISCORD_CHANNEL_ID")):
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = client.get_user(payload.user_id)
        
        # Determine the status update based on the emoji
        emoji_map = {
            "📦": "is now **Packed**",
            "✅": "has been **Delivered**",
            "⚠️": "has a **Partial/Issue** report"
        }
        
        status_update = emoji_map.get(str(payload.emoji))
        
        if status_update:
            # Send a confirmation thread or message
            await channel.send(f"🆔 Order update for `{message.embeds[0].fields[1].value}`: This order {status_update} by {user.display_name}.")