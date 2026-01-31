import os
import re
import asyncio
import discord
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from scraper import get_order_details

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def get_gmail_service():
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

async def check_gmail_for_orders():
    try:
        service = get_gmail_service()
        query = 'from:sales@tcgplayer.com subject:"Your TCGplayer.com items" is:unread'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages: return []

        order_ids = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            snippet = msg_data.get('snippet', '')
            match = re.search(r'([A-F0-9]{8}-[A-F0-9]{6}-[A-F0-9]{5})', snippet)
            if match:
                order_ids.append(match.group(1))
                service.users().messages().batchModify(
                    userId='me', 
                    body={'removeLabelIds': ['UNREAD'], 'ids': [msg['id']]}
                ).execute()
        return order_ids
    except Exception as e:
        print(f"Gmail Error: {e}", flush=True)
        return []

async def main_loop():
    await client.wait_until_ready()
    print("Bot started. More logs will appear when an order is found.", flush=True)
    while not client.is_closed():
        try:
            order_ids = await check_gmail_for_orders()
            if order_ids:
                print(f"Found {len(order_ids)} new orders!", flush=True)
                channel = client.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
                role_id = os.getenv("DISCORD_ROLE_ID")
                ping_content = f"<@&{role_id}>" if role_id else "@everyone"

                for oid in order_ids:
                    data = await get_order_details(oid)
                    if data:
                        embed = discord.Embed(title=f"New Order: {oid}", color=0x3498db)
                        embed.add_field(name="Buyer", value=data['buyer'], inline=False)
                        items_str = "".join([f"• {i['qty']}x {i['name']} ({i['price']})\n" for i in data['items']])
                        embed.add_field(name="Items", value=items_str or "No items found", inline=False)
                        
                        msg = await channel.send(content=ping_content, embed=embed)
                        await msg.add_reaction("📦")
                        await msg.add_reaction("✅")
                        await msg.add_reaction("⚠️")
                        print(f"Posted order {oid} to Discord.", flush=True)
                    else:
                        print(f"Scraper returned no data for {oid}", flush=True)
            
            await asyncio.sleep(600)
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
            await asyncio.sleep(60)

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id: return
    emoji_map = {"📦": "is now **Packed**", "✅": "has been **Delivered**", "⚠️": "has an **Issue**"}
    status_update = emoji_map.get(str(payload.emoji))
    if status_update:
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        order_id = message.embeds[0].title.split(": ")[1]
        await channel.send(f"🆔 Order `{order_id}` {status_update} by <@{payload.user_id}>")

@client.event
async def on_ready():
    print(f"Bot logged in as {client.user}", flush=True)
    if not hasattr(client, 'gmail_task'):
        client.gmail_task = client.loop.create_task(main_loop())

if __name__ == "__main__":
    client.run(os.getenv("DISCORD_BOT_TOKEN"))