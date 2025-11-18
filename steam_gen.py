# Added simple web server for UptimeRobot ping
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "OK", 200

# ============================
# DISCORD BOT + FULL ORIGINAL SCRIPT
# ============================

import discord
from discord import app_commands
from discord.ext import commands
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

# ============================
# ENV
# ============================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("ERREUR : DISCORD_TOKEN manquant dans le fichier .env")

# ============================
# CONFIG
# ============================
ZIP_DIR = Path("zip_downloads")
ZIP_DIR.mkdir(exist_ok=True)

# Source principale (GitHub)
GITHUB_BASE = "https://raw.githubusercontent.com/MOLDY12457/TanBot20000.games/master/{appid}.zip"

# Source secondaire (fallback)
R2_BASE = "https://pub-5b6d3b7c03fd4ac1afb5bd3017850e20.r2.dev/{appid}.zip"

# ============================
# DISCORD BOT
# ============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# ============================
# Upload Catbox
# ============================
def upload_catbox(filepath):
    with open(filepath, "rb") as f:
        r = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": f},
            timeout=300
        )

    if r.status_code != 200:
        raise Exception(f"Erreur HTTP {r.status_code}")

    url = r.text.strip()
    if not url.startswith("https://"):
        raise Exception(f"Réponse Catbox invalide : {url}")

    return url


# ============================
# READY
# ============================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"[OK] {bot.user} en ligne ! Slash commands prêtes")


# ============================
# /search
# ============================
@tree.command(name="search", description="Recherche un jeu Steam")
@app_commands.describe(query="Nom du jeu à rechercher")
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.send_message(f"Recherche de **{query}**... 🔍", ephemeral=False)
    message = await interaction.original_response()

    r = requests.get(f"https://steamcommunity.com/actions/SearchApps/{query}")
    results = r.json()[:25]

    if not results:
        await message.edit(content=f"Aucun résultat pour **{query}** ❌")
        return

    options = []
    for i, game in enumerate(results):
        name = game["name"][:97] + "..." if len(game["name"]) > 100 else game["name"]
        options.append(discord.SelectOption(label=f"{i+1}. {name}", value=str(game["appid"])))

    select = discord.ui.Select(placeholder="Sélectionnez un jeu", options=options)

    async def callback(select_interaction: discord.Interaction):
        appid = select.values[0]
        await select_interaction.response.defer()

        info_req = requests.get(f"http://store.steampowered.com/api/appdetails?appids={appid}")
        info = info_req.json()
        data = info.get(appid, {}).get("data", {})

        embed = discord.Embed(title=data["name"], color=0x1b2838)
        embed.add_field(name="Nom", value=data["name"], inline=False)
        embed.add_field(name="AppID", value=f"`{appid}`", inline=True)
        embed.add_field(name="Développeur", value=", ".join(data.get("developers", ["N/A"])), inline=True)
        embed.add_field(name="Sortie", value=data.get("release_date", {}).get("date", "N/A"), inline=True)
        embed.add_field(name="Prix", value=data.get("price_overview", {}).get("final_formatted", "Gratuit"), inline=True)
        embed.set_image(url=f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/header.jpg")
        embed.set_footer(text="Utilise /get <appid> pour télécharger")

        await select_interaction.message.edit(embed=embed, view=None)

    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)

    embed_search = discord.Embed(
        title=f"Résultats pour : {query}",
        description="Sélectionnez un jeu dans le menu ci-dessous 👇",
        color=0x1b2838
    )

    await message.edit(content="", embed=embed_search, view=view)


# ============================
# /get
# ============================
@tree.command(name="get", description="Télécharge un ZIP Lua du jeu Steam")
@app_commands.describe(appid="ID du jeu Steam")
async def get(interaction: discord.Interaction, appid: str):
    if not appid.isdigit():
        await interaction.response.send_message("Usage : `/get <appid>`", ephemeral=True)
        return

    await interaction.response.send_message(f"Téléchargement `{appid}`... ⏳", ephemeral=False)
    msg = await interaction.original_response()

    primary_url = GITHUB_BASE.format(appid=appid)
    secondary_url = R2_BASE.format(appid=appid)
    path = ZIP_DIR / f"{appid}.zip"

    source_used = None

    try:
        req = requests.get(primary_url, stream=True, timeout=100, headers={"User-Agent": "Mozilla/5.0"})
        if req.status_code == 200:
            source_used = "Steam Unlock DB"
        else:
            req = requests.get(secondary_url, stream=True, timeout=100, headers={"User-Agent": "Mozilla/5.0"})
            if req.status_code == 200:
                source_used = "Unofficial: SteamML"
            else:
                await msg.edit(content="Introuvable sur **GitHub DB** et **SteamML R2** ❌")
                return

        with open(path, "wb") as f:
            for chunk in req.iter_content(1024 * 1024):
                f.write(chunk)

        size = path.stat().st_size / (1024 * 1024)

        info_req = requests.get(f"http://store.steampowered.com/api/appdetails?appids={appid}").json()
        name = info_req.get(appid, {}).get("data", {}).get("name", f"Jeu {appid}")

        embed = discord.Embed(title=name, color=0x1b2838)
        embed.add_field(name="AppID", value=f"`{appid}`", inline=True)
        embed.add_field(name="Taille ZIP", value=f"`{size:.2f} MB`", inline=True)
        embed.add_field(name="Source", value=source_used, inline=False)
        embed.set_thumbnail(url=f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/header.jpg")

        if size <= 8:
            file = discord.File(path, filename=f"{appid}.zip")
            await msg.delete()
            await interaction.followup.send(embed=embed, file=file)
            path.unlink()
            return

        await msg.edit(content=f"Upload Catbox ({size:.2f} MB)... ⏳")
        link = upload_catbox(str(path))
        embed.add_field(name="Lien Catbox", value=link, inline=False)
        embed.set_footer(text=f"DB: {source_used} • Catbox utilisé (>8MB)")
        await msg.edit(content="", embed=embed)

        path.unlink()

    except Exception as e:
        await msg.edit(content=f"Erreur : {e}")


# ============================
# RUN BOT
# ============================
bot.run(TOKEN)
# (Paste full updated bot code integrating the Flask server and ensuring both run)

# To run both Flask and Discord bot, use threading
import threading

def run_web():
    import os
PORT = int(os.getenv("PORT", 10000))
app.run(host='0.0.0.0', port=PORT)

web_thread = threading.Thread(target=run_web)
web_thread.start()

# --- Your original code continues here ---
