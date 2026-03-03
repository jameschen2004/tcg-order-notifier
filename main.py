import os
import re
import asyncio
import discord
import sqlite3
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from scraper import get_order_details
from discord.ext import commands

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (order_id TEXT PRIMARY KEY, buyer TEXT, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_gmail_service():
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

# Database Helper Functions
def save_order_to_db(order_id, buyer):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    # "INSERT OR IGNORE" prevents crashes if an order is found twice
    c.execute("INSERT OR IGNORE INTO orders (order_id, buyer, status) VALUES (?, ?, ?)", (order_id, buyer, "Pending"))
    conn.commit()
    conn.close()

def update_order_status(order_id, new_status):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

def get_buyer_from_db(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT buyer FROM orders WHERE order_id = ?", (order_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "Unknown Buyer"

# Commands
@bot.command(name="recent")
async def recent_orders(ctx, x: int = 10):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT order_id, buyer, status FROM orders ORDER BY timestamp DESC LIMIT ?", (x,))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await ctx.send("No orders found in history.")
        return

    response = f"**Last {x} Orders:**\n"
    for r in rows:
        response += f"• `{r[0]}` - **{r[1]}** [{r[2]}]\n"
    await ctx.send(response)

@bot.command(name="pending")
async def pending_orders(ctx):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT order_id, buyer FROM orders WHERE status = 'Pending' ORDER BY timestamp ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await ctx.send("No pending orders! Everything is packed.")
        return

    response = "**Pending Orders:**\n"
    for r in rows:
        response += f"• `{r[0]}` - **{r[1]}**\n"
    await ctx.send(response)

# Gmail Logic
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
    await bot.wait_until_ready()
    init_db() # Ensure DB is ready
    print("Bot loop started.", flush=True)
    while not bot.is_closed():
        try:
            order_ids = await check_gmail_for_orders()
            if order_ids:
                channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
                role_id = os.getenv("DISCORD_ROLE_ID")
                ping_content = f"<@&{role_id}>" if role_id else "@everyone"

                for oid in order_ids:
                    data = await get_order_details(oid)
                    if data:
                        # NEW: Save to Database
                        save_order_to_db(oid, data['buyer'])

                        embed = discord.Embed(title=f"New Order: {oid}", color=0x3498db)
                        embed.add_field(name="Buyer", value=data['buyer'], inline=False)
                        items_str = "".join([f"• {i['qty']}x {i['name']} ({i['price']})\n" for i in data['items']])
                        embed.add_field(name="Items", value=items_str or "No items found", inline=False)
                        
                        msg = await channel.send(content=ping_content, embed=embed)
                        await msg.add_reaction("📦")
                        await msg.add_reaction("✅")
                        await msg.add_reaction("⚠️")
                        print(f"Posted order {oid} and saved to DB.", flush=True)
                    else:
                        print(f"Scraper returned no data for {oid}", flush=True)
            
            await asyncio.sleep(600)
        except Exception as e:
            print(f"Loop Error: {e}", flush=True)
            await asyncio.sleep(60)

# Reactions Logic
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return
    
    emoji_map = {"📦": "Packed", "✅": "Delivered", "⚠️": "Issue"}
    status_key = emoji_map.get(str(payload.emoji))

    if status_key:
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        # Extract ID from Embed Title
        order_id = message.embeds[0].title.split(": ")[1]
        
        # NEW: Fetch Buyer Name from DB
        buyer_name = get_buyer_from_db(order_id)
        update_order_status(order_id, status_key)

        status_text = f"is now **{status_key}**"
        await channel.send(f"👤 **{buyer_name}** ({order_id}) {status_text} by <@{payload.user_id}>")

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}", flush=True)
    if not hasattr(bot, 'gmail_task'):
        bot.gmail_task = bot.loop.create_task(main_loop())

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))