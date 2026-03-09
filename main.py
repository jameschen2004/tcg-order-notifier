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

# --- Database Initialization ---
def init_db():
    try:
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS orders 
                     (order_id TEXT PRIMARY KEY, buyer TEXT, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully.", flush=True)
    except Exception as e:
        print(f"❌ Database Error: {e}", flush=True)

def get_gmail_service():
    if not os.path.exists('token.json'):
        raise FileNotFoundError("token.json missing!")
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

# --- Database Helpers ---
def save_order_to_db(order_id, buyer):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
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

# --- Core Logic: Processing Orders ---
async def process_new_orders():
    """Central function to check Gmail and process any found orders."""
    try:
        service = get_gmail_service()
        query = 'from:sales@tcgplayer.com subject:"Your TCGplayer.com items" is:unread'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages: 
            return 0

        order_ids = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            snippet = msg_data.get('snippet', '')
            match = re.search(r'([A-F0-9]{8}-[A-F0-9]{6}-[A-F0-9]{5})', snippet)
            if match:
                oid = match.group(1)
                order_ids.append(oid)
                # Mark as read immediately
                service.users().messages().batchModify(
                    userId='me', 
                    body={'removeLabelIds': ['UNREAD'], 'ids': [msg['id']]}
                ).execute()

        if order_ids:
            channel = bot.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
            role_id = os.getenv("DISCORD_ROLE_ID")
            ping = f"<@&{role_id}>" if role_id else "@everyone"

            for oid in order_ids:
                data = await get_order_details(oid)
                if data:
                    save_order_to_db(oid, data['buyer'])
                    # Updated Embed: Buyer Name is the Title
                    embed = discord.Embed(title=f"Order for {data['buyer']}", color=0x3498db)
                    embed.add_field(name="Order ID", value=f"`{oid}`", inline=False)
                    items_str = "".join([f"• {i['qty']}x {i['name']} ({i['price']})\n" for i in data['items']])
                    embed.add_field(name="Items", value=items_str or "No items found", inline=False)
                    
                    msg = await channel.send(content=ping, embed=embed)
                    await msg.add_reaction("📦")
                    await msg.add_reaction("✅")
                    await msg.add_reaction("⚠️")
                    print(f"✅ Processed and posted: {oid}", flush=True)
        
        return len(order_ids)
    except Exception as e:
        print(f"⚠️ Processing Error: {e}", flush=True)
        return -1

# --- Discord Commands ---
@bot.command(name="sync")
async def manual_sync(ctx):
    await ctx.send("Manually checking Gmail for new orders...")
    count = await process_new_orders()
    if count > 0:
        await ctx.send(f"Processed {count} new orders.")
    elif count == 0:
        await ctx.send("No new unread orders found.")
    else:
        await ctx.send("An error occurred during the sync.")

@bot.command(name="remove")
async def remove_order(ctx, order_id: str):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT buyer FROM orders WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        conn.commit()
        await ctx.send(f"✅ Removed order `{order_id}` (Buyer: {row[0]}) from the database.")
    else:
        await ctx.send(f"❌ Order ID `{order_id}` not found.")
    conn.close()

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
    res = f"**Last {x} Orders:**\n" + "\n".join([f"• `{r[0]}` - **{r[1]}** [{r[2]}]" for r in rows])
    await ctx.send(res)

@bot.command(name="pending")
async def pending_orders(ctx):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT order_id, buyer FROM orders WHERE status = 'Pending' ORDER BY timestamp ASC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await ctx.send("✅ No pending orders!")
        return
    res = "**Pending Orders:**\n" + "\n".join([f"• `{r[0]}` - **{r[1]}**" for r in rows])
    await ctx.send(res)

# --- Event Listeners ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return
    emoji_map = {"📦": "Packed", "✅": "Delivered", "⚠️": "Issue"}
    status = emoji_map.get(str(payload.emoji))
    if status:
        try:
            channel = bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            if not message.embeds: return
            
            # Find the Order ID from the embed field
            order_id = None
            for field in message.embeds[0].fields:
                if field.name == "Order ID":
                    order_id = field.value.replace("`", "")
                    break
            
            if order_id:
                buyer = get_buyer_from_db(order_id)
                update_order_status(order_id, status)
                await channel.send(f"👤 **{buyer}** ({order_id}) is now **{status}** by <@{payload.user_id}>")
        except Exception as e:
            print(f"Reaction Error: {e}", flush=True)

async def main_loop():
    await bot.wait_until_ready()
    init_db() 
    while not bot.is_closed():
        print("🔍 Periodic sync starting...", flush=True)
        await process_new_orders()
        await asyncio.sleep(600)

@bot.event
async def on_ready():
    print(f"🤖 Bot logged in as {bot.user}", flush=True)
    if not hasattr(bot, 'gmail_task'):
        bot.gmail_task = bot.loop.create_task(main_loop())

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))