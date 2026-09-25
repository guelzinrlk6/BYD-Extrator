import discord
from discord import app_commands
import yt_dlp
import os
import re

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

PASTA = r"C:\BYD Extrator\audios"
os.makedirs(PASTA, exist_ok=True)


@tree.command(name="extrair", description="Extrai o áudio de um TikTok")
@app_commands.describe(link="Link do TikTok")
async def extrair(interaction: discord.Interaction, link: str):

    if "tiktok.com" not in link:
        await interaction.response.send_message(
            "❌ Envie um link válido do TikTok.",
            ephemeral=True
        )
        return

    await interaction.response.send_message("⏳ Extraindo o áudio...")

    try:
        opcoes = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(PASTA, "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(link, download=True)

        arquivo = os.path.join(PASTA, f"{info['id']}.mp3")

        if not os.path.exists(arquivo):
            raise FileNotFoundError("MP3 não foi encontrado.")

        await interaction.channel.send(
            content=f"🎵 **Áudio extraído:** {info.get('title', 'TikTok')}",
            file=discord.File(arquivo)
        )

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as erro:
        print(erro)
        await interaction.edit_original_response(
            content="❌ Não consegui extrair o áudio desse TikTok."
        )


@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ BYD Extrator conectado como {bot.user}")


bot.run(TOKEN)