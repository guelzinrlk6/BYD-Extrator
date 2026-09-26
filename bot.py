```python
import discord
from discord import app_commands
import yt_dlp
import os
import asyncio

# =========================================================
# CONFIGURACAO
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
PASTA_VIDEOS = "videos"

os.makedirs(PASTA_AUDIOS, exist_ok=True)
os.makedirs(PASTA_VIDEOS, exist_ok=True)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Limite de seguranca: 24 MB
LIMITE_DISCORD = 24 * 1024 * 1024


# =========================================================
# FUNCAO PARA BAIXAR AUDIO DO TIKTOK
# =========================================================

def baixar_audio_tiktok(link):

    opcoes = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(
            PASTA_AUDIOS,
            "%(id)s.%(ext)s"
        ),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        return ydl.extract_info(
            link,
            download=True
        )


# =========================================================
# /extrair
# =========================================================

@tree.command(
    name="extrair",
    description="Extrai o audio de um TikTok"
)
@app_commands.describe(
    link="Link do TikTok"
)
async def extrair(
    interaction: discord.Interaction,
    link: str
):

    if "tiktok.com" not in link:
        await interaction.response.send_message(
            "Link invalido do TikTok.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="Extraindo o audio..."
        )

        print("Iniciando extracao do TikTok...")

        info = await asyncio.to_thread(
            baixar_audio_tiktok,
            link
        )

        arquivo = os.path.join(
            PASTA_AUDIOS,
            f"{info['id']}.mp3"
        )

        if not os.path.exists(arquivo):
            raise FileNotFoundError(
                "MP3 nao foi encontrado."
            )

        tamanho = os.path.getsize(arquivo)

        print(
            f"Tamanho do audio: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            os.remove(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content="O audio ficou maior que 24 MB."
            )

            return

        await interaction.edit_original_response(
            content="Enviando o audio para o Discord..."
        )

        try:

            await interaction.followup.send(
                content=(
                    f"Audio extraido: "
                    f"{info.get('title', 'TikTok')}"
                ),
                file=discord.File(arquivo)
            )

        except discord.HTTPException as erro:

            print(f"ERRO NO ENVIO DO AUDIO: {erro}")

            if getattr(erro, "status", None) == 413:

                await interaction.edit_original_response(
                    content="O Discord recusou o audio porque o arquivo ficou grande demais."
                )

                return

            raise

        if os.path.exists(arquivo):
            os.remove(arquivo)

        arquivo = None

        await interaction.edit_original_response(
            content="Audio extraido com sucesso!"
        )

    except Exception as erro:

        print(f"ERRO EXTRAIR: {erro}")

        if arquivo and os.path.exists(arquivo):

            try:
                os.remove(arquivo)
            except Exception:
                pass

        try:

            await interaction.edit_original_response(
                content="Nao consegui extrair esse TikTok. Veja o erro no CMD."
            )

        except Exception:
            pass


# =========================================================
# FUNCAO PARA BAIXAR MEDAL
# =========================================================

def baixar_medal(link, qualidade):

    arquivo_saida = None

    opcoes = {
        "format": (
            f"bestvideo[height<={qualidade}]"
            "+bestaudio/"
            f"best[height<={qualidade}]/best"
        ),
        "outtmpl": os.path.join(
            PASTA_VIDEOS,
            "%(id)s.%(ext)s"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:

        info = ydl.extract_info(
            link,
            download=True
        )

        arquivo_base = os.path.join(
            PASTA_VIDEOS,
            str(info["id"])
        )

        for extensao in [
