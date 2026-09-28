import os
import asyncio
import glob
import shutil

import discord
from discord import app_commands
import yt_dlp


# =========================================================
# CONFIGURAÇÃO
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
LIMITE_DISCORD = 23 * 1024 * 1024

os.makedirs(PASTA_AUDIOS, exist_ok=True)

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# FUNÇÕES
# =========================================================

def apagar_arquivo(arquivo):
    try:
        if arquivo and os.path.exists(arquivo):
            os.remove(arquivo)
    except Exception as e:
        print(f"AVISO AO APAGAR: {e}")


def encontrar_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def baixar_audio(link):
    """
    Baixa TikTok ou SoundCloud e converte para MP3.
    """

    link_lower = link.lower()

    if "tiktok.com" in link_lower:
        prefixo = "tiktok"
    elif "soundcloud.com" in link_lower:
        prefixo = "soundcloud"
    else:
        raise ValueError(
            "O link precisa ser do TikTok ou SoundCloud."
        )

    opcoes = {
        "format": "bestaudio/best",

        "outtmpl": os.path.join(
            PASTA_AUDIOS,
            f"{prefixo}_%(id)s.%(ext)s"
        ),

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ],

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "retries": 3,
        "fragment_retries": 3,

        "ignoreerrors": False
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(
            link,
            download=True
        )

    return info, prefixo


# =========================================================
# /EXTRAIR
# =========================================================

@tree.command(
    name="extrair",
    description="Extrai áudio do TikTok ou SoundCloud"
)
@app_commands.describe(
    link="Link do TikTok ou SoundCloud"
)
async def extrair(
    interaction: discord.Interaction,
    link: str
):

    link_lower = link.lower()

    if (
        "tiktok.com" not in link_lower
        and "soundcloud.com" not in link_lower
    ):

        await interaction.response.send_message(
            "❌ Link inválido. Use um link do TikTok ou SoundCloud.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    arquivo = None

    try:

        if "tiktok.com" in link_lower:
            plataforma = "TikTok"

        else:
            plataforma = "SoundCloud"

        await interaction.edit_original_response(
            content=f"⏳ Extraindo áudio do {plataforma}..."
        )

        info, prefixo = await asyncio.to_thread(
            baixar_audio,
            link
        )

        audio_id = info.get("id")

        # -------------------------------------------------
        # Procura o arquivo pelo ID
        # -------------------------------------------------

        if audio_id:

            possivel = os.path.join(
                PASTA_AUDIOS,
                f"{prefixo}_{audio_id}.mp3"
            )

            if os.path.exists(possivel):
                arquivo = possivel

        # -------------------------------------------------
        # Fallback: procura o MP3 mais recente
        # -------------------------------------------------

        if not arquivo:

            arquivos = glob.glob(
                os.path.join(
                    PASTA_AUDIOS,
                    "*.mp3"
                )
            )

            arquivos = [
                x for x in arquivos
                if os.path.isfile(x)
            ]

            if arquivos:

                arquivos.sort(
                    key=os.path.getmtime,
                    reverse=True
                )

                arquivo = arquivos[0]

        # -------------------------------------------------
        # Verifica se encontrou
        # -------------------------------------------------

        if not arquivo or not os.path.exists(arquivo):

            raise RuntimeError(
                "O arquivo MP3 não foi encontrado."
            )

        tamanho = os.path.getsize(arquivo)

        print(
            f"📦 ÁUDIO: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        # -------------------------------------------------
        # Verifica limite do Discord
        # -------------------------------------------------

        if tamanho > LIMITE_DISCORD:

            apagar_arquivo(arquivo)

            await interaction.edit_original_response(
                content=(
                    "❌ O áudio ficou maior que o limite "
                    "permitido pelo Discord."
                )
            )

            return

        # -------------------------------------------------
        # Envia
        # -------------------------------------------------

        await interaction.edit_original_response(
            content=f"📤 Enviando áudio do {plataforma}..."
        )

        try:

            await interaction.followup.send(
                file=discord.File(
                    arquivo,
                    filename="audio.mp3"
                )
            )

        except discord.HTTPException as e:

            print(
                f"ERRO DISCORD: "
                f"{type(e).__name__}: {e}"
            )

            if getattr(e, "status", None) == 413:

                await interaction.edit_original_response(
                    content=(
                        "❌ O Discord recusou o áudio "
                        "por tamanho."
                    )
                )

                return

            raise

        apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content=(
                f"✅ Áudio do {plataforma} "
                "extraído com sucesso!"
            )
        )

    except Exception as e:

        print(
            f"❌ ERRO {type(e).__name__}: {e}"
        )

        if arquivo:
            apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content=(
                f"❌ ERRO AO EXTRAIR: "
                f"{type(e).__name__}: {e}"
            )
        )


# =========================================================
# SINCRONIZAÇÃO
# =========================================================

@bot.event
async def on_ready():

    try:

        comandos = await tree.sync()

        print(
            f"✅ Bot conectado como {bot.user}"
        )

        print(
            f"✅ {len(comandos)} comando(s) sincronizado(s):"
        )

        for comando in comandos:
            print(
                f"   /{comando.name}"
            )

    except Exception as e:

        print(
            f"❌ ERRO AO SINCRONIZAR: "
            f"{type(e).__name__}: {e}"
        )


# =========================================================
# INICIAR
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN não foi encontrado no Railway."
    )

bot.run(TOKEN)
