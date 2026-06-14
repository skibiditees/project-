import os
import random
import sqlite3
import asyncio
import discord
from discord.ext import commands
from fastapi import FastAPI
import uvicorn

# ==============================================================================
# 1. LOCAL DATA LEDGER SETUP (SQLite)
# ==============================================================================
DB_FILE = "taiga_state.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS citizens (
            discord_id TEXT UNIQUE,
            mojang_uuid TEXT UNIQUE,
            username TEXT,
            national_id TEXT UNIQUE,
            district_digit INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()
active_tokens = {}

# ==============================================================================
# 2. DISCORD BOT ENGINE (NATIVE COMMANDS FRAMEWORK)
# ==============================================================================
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f"🏛️ Taiga Republic Bot Online as {bot.user}!")
    except Exception as e:
        print(f"Sync Error: {e}")

# ==============================================================================
# 3. CORE WEB GATEWAY (FASTAPI)
# ==============================================================================
app = FastAPI()

@app.get("/")
async def homepage():
    return {
        "status": "online",
        "government": "Taiga Republic State Ledger",
        "bot_connected": bot.is_ready()
    }

@app.get("/api/verify_link")
async def verify_link_from_minecraft(username: str, uuid: str, token: str, district: int):
    if token not in active_tokens:
        return "INVALID_TOKEN"
        
    discord_id = active_tokens[token]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    secure_rand = f"{random.randint(0, 99999):05d}"
    compiled_id = f"T-{district}-{secure_rand}"
    
    try:
        cursor.execute("INSERT INTO citizens VALUES (?, ?, ?, ?, ?)", (discord_id, uuid, username, compiled_id, district))
        conn.commit()
        del active_tokens[token]
        return f"SUCCESS:{compiled_id}"
    except:
        return "ALREADY_LINKED"
    finally:
        conn.close()

# ==============================================================================
# 4. UNIFIED CONCURRENT TASK LOOP RUNNER
# ==============================================================================
async def main():
    # Railway automatically injects the PORT parameter based on its routing layer
    port = int(os.environ.get("PORT", 8080))
    
    # Pulls the token dynamically from your Railway Service Variables tab
    token = os.environ.get("DISCORD_BOT_TOKEN")
    
    if not token:
        print("❌ CRITICAL ERROR: The 'DISCORD_BOT_TOKEN' environment variable is missing on Railway!")
        # We still serve FastAPI so the project doesn't completely crash/loop error out
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        return

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    
    # Run the Web Gateway and the Discord WebSocket Client concurrently on the same loop
    await asyncio.gather(
        server.serve(),
        bot.start(token.strip())
    )

if __name__ == "__main__":
    asyncio.run(main())
