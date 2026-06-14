import os
import random
import sqlite3
import asyncio
from contextlib import asynccontextmanager
import discord
from discord.ext import commands
from fastapi import FastAPI
import uvicorn

# ==============================================================================
# 1. LOCAL DATA LEDGER SETUP
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
# 2. DISCORD BOT LAYER
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
# 3. FASTAPI LIFESPAN MANAGER (THE ANTI-CRASH KEY)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs IMMEDIATELY after Uvicorn binds to the port, satisfying Railway
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ CRITICAL ERROR: 'DISCORD_BOT_TOKEN' variable missing on Railway!")
        yield
        return

    # Fire off the bot connection as a non-blocking background task
    bot_task = asyncio.create_task(bot.start(token.strip()))
    
    yield  # Hand over total execution control to the web framework
    
    # Clean up tasks cleanly if the container stops
    await bot.close()
    await bot_task

# Pass the lifespan handler directly into FastAPI
app = FastAPI(lifespan=lifespan)

# ==============================================================================
# 4. WEB ENDPOINTS
# ==============================================================================
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
# 5. MONOLITHIC ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    # Pull port assigned by Railway
    port = int(os.environ.get("PORT", 8080))
    # Run Uvicorn synchronously on the main thread so it opens the port instantly
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
