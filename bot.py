```python
import discord
from discord import app_commands
import yt_dlp
import os
import asyncio

# =========================================================
# CONFIGURAÇÃO
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
PASTA_VIDEOS = "videos"

os.makedirs(PASTA_AUDIOS, exist_ok=True)
os.makedirs(PASTA_VIDEOS, exist_ok=True)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# =========================================================
# LIMITE DE SEGURANÇA
# =========================================================
# O Discord pode rejeitar arquivos muito próximos do limite.
# Por isso usamos 24 MB como limite de segurança.

LIMITE_DISCORD = 24 * 1024 * 1024


# =========================================================
# /extrair
# =========================================================

@tree.command(
    name="extrair",
    description="Extrai o áudio de um TikTok"
)
@app_commands.describe(link="Link do TikTok")
async def extrair(
    interaction: discord.Interaction,
    link: str
):

    if "tiktok.com" not in link:
        await interaction.response.send_message(
            "❌ Envie um link válido do TikTok.",
            ephemeral=True
        )
        return

    # Responde imediatamente ao Discord
    await interaction.response.defer()

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Extraindo o áudio.
```
