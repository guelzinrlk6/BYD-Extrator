import os
import asyncio
import glob
import shutil
import subprocess
import re

import discord
from discord import app_commands
import yt_dlp


# =========================================================
# CONFIGURAÇÃO
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
PASTA_VIDEOS = "videos"

LIMITE_DISCORD = 23 * 1024 * 1024  # 23 MB

os.makedirs(PASTA_AUDIOS, exist_ok=True)
os.makedirs(PASTA_VIDEOS, exist_ok=True)

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# FUNÇÕES GERAIS
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


def tamanho_arquivo(arquivo):
    try:
        return os.path.getsize(arquivo)
    except Exception:
        return 0


# =========================================================
# TIKTOK
# =========================================================

def baixar_audio_tiktok(link):
    opcoes = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(
            PASTA_AUDIOS,
            "%(id)s.%(ext)s"
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
        "fragment_retries": 3
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        return ydl.extract_info(link, download=True)


# =========================================================
# SOUNDCLOUD
# =========================================================

def baixar_audio_soundcloud(link):
    opcoes = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(
            PASTA_AUDIOS,
            "soundcloud_%(id)s.%(ext)s"
        ),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ],
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        return ydl.extract_info(link, download=True)


# =========================================================
# FFPROBE / DURAÇÃO
# =========================================================

def descobrir_duracao(ffmpeg, arquivo):
    try:
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")

        if not os.path.exists(ffprobe):
            ffprobe = shutil.which("ffprobe")

        if not ffprobe:
            return None

        resultado = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                arquivo
            ],
            capture_output=True,
            text=True
        )

        valor = resultado.stdout.strip()

        if valor:
            return float(valor)

    except Exception as e:
        print(f"AVISO DURAÇÃO: {e}")

    return None


# =========================================================
# COMPRESSÃO DE VÍDEO
# =========================================================

def comprimir_video(arquivo):
    if not os.path.exists(arquivo):
        return None

    tamanho = tamanho_arquivo(arquivo)

    if tamanho <= LIMITE_DISCORD:
        return arquivo

    ffmpeg = encontrar_ffmpeg()

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg não encontrado para comprimir o vídeo."
        )

    duracao = descobrir_duracao(ffmpeg, arquivo)

    if not duracao or duracao <= 0:
        duracao = 60

    arquivo_temp = os.path.join(
        PASTA_VIDEOS,
        "temp_comprimido.mp4"
    )

    # Tentativas progressivamente mais agressivas
    configuracoes = [
        (854, 18_000_000),
        (720, 17_000_000),
        (640, 16_000_000),
        (540, 15_000_000),
        (480, 14_000_000),
    ]

    for largura, tamanho_alvo in configuracoes:

        try:
            if os.path.exists(arquivo_temp):
                os.remove(arquivo_temp)

            # Reserva para áudio
            audio_kbps = 64

            audio_bits = audio_kbps * 1000

            video_bits_total = (
                tamanho_alvo * 8
            )

            video_bits = (
                video_bits_total
                - (audio_bits * duracao)
            )

            video_kbps = int(
                video_bits / duracao / 1000
            )

            if video_kbps < 150:
                video_kbps = 150

            comando = [
                ffmpeg,
                "-y",
                "-i",
                arquivo,

                "-vf",
                f"scale='min({largura},iw)':-2",

                "-c:v",
                "libx264",

                "-preset",
                "veryfast",

                "-b:v",
                f"{video_kbps}k",

                "-maxrate",
                f"{int(video_kbps * 1.15)}k",

                "-bufsize",
                f"{int(video_kbps * 2)}k",

                "-pix_fmt",
                "yuv420p",

                "-c:a",
                "aac",

                "-b:a",
                "64k",

                "-movflags",
                "+faststart",

                arquivo_temp
            ]

            print(
                f"🗜️ Compressão: {largura}p "
                f"| {video_kbps} kbps"
            )

            resultado = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if resultado.returncode != 0:
                print(
                    "ERRO FFMPEG:",
                    resultado.stderr[-2000:]
                )
                continue

            if not os.path.exists(arquivo_temp):
                continue

            novo_tamanho = tamanho_arquivo(
                arquivo_temp
            )

            print(
                f"📦 Tamanho comprimido: "
                f"{novo_tamanho / 1024 / 1024:.2f} MB"
            )

            if novo_tamanho <= LIMITE_DISCORD:

                apagar_arquivo(arquivo)

                os.replace(
                    arquivo_temp,
                    arquivo
                )

                return arquivo

        except Exception as e:
            print(
                f"ERRO NA COMPRESSÃO: {type(e).__name__}: {e}"
            )

    apagar_arquivo(arquivo_temp)

    raise RuntimeError(
        "Vídeo não conseguiu ficar abaixo de 23 MB."
    )


# =========================================================
# MEDAL
# =========================================================

def baixar_medal(link):
    opcoes_base = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(
            PASTA_VIDEOS,
            "medal_%(id)s.%(ext)s"
        )
    }

    formatos = [
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "bestvideo[height<=480]+bestaudio/best[height<=480]"
    ]

    ultimo_erro = None

    for formato in formatos:

        try:
            opcoes = opcoes_base.copy()
            opcoes["format"] = formato

            print(
                f"🎬 Tentando Medal: {formato}"
            )

            with yt_dlp.YoutubeDL(opcoes) as ydl:
                info = ydl.extract_info(
                    link,
                    download=True
                )

            if not info:
                continue

            video_id = info.get("id")

            if video_id:
                candidatos = glob.glob(
                    os.path.join(
                        PASTA_VIDEOS,
                        f"medal_{video_id}.*"
                    )
                )

                candidatos = [
                    x for x in candidatos
                    if os.path.isfile(x)
                    and not x.endswith(".part")
                ]

                if candidatos:
                    candidatos.sort(
                        key=os.path.getmtime,
                        reverse=True
                    )

                    return candidatos[0]

            arquivos = glob.glob(
                os.path.join(
                    PASTA_VIDEOS,
                    "*"
                )
            )

            arquivos = [
                x for x in arquivos
                if os.path.isfile(x)
                and not x.endswith(".part")
                and not x.endswith(".ytdl")
            ]

            if arquivos:
                arquivos.sort(
                    key=os.path.getmtime,
                    reverse=True
                )

                return arquivos[0]

        except Exception as e:
            ultimo_erro = e

            print(
                f"ERRO MEDAL FORMATO: "
                f"{type(e).__name__}: {e}"
            )

    if ultimo_erro:
        raise ultimo_erro

    raise RuntimeError(
        "Não foi possível baixar o clipe do Medal."
    )


# =========================================================
# COMANDO /EXTRAIR
# =========================================================

@tree.command(
    name="extrair",
    description="Extrai o áudio de um TikTok"
)
@app_commands.describe(
    link="Link do TikTok"
)
async def extrair(
    interaction: discord.Interaction,
    link: str
):

    if "tiktok.com" not in link.lower():

        await interaction.response.send_message(
            "❌ Link inválido do TikTok.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    try:

        await interaction.edit_original_response(
            content="⏳ Extraindo áudio do TikTok..."
        )

        info = await asyncio.to_thread(
            baixar_audio_tiktok,
            link
        )

        video_id = info.get("id")

        arquivo = os.path.join(
            PASTA_AUDIOS,
            f"{video_id}.mp3"
        )

        if not os.path.exists(arquivo):

            arquivos = glob.glob(
                os.path.join(
                    PASTA_AUDIOS,
                    "*.mp3"
                )
            )

            if arquivos:
                arquivos.sort(
                    key=os.path.getmtime,
                    reverse=True
                )

                arquivo = arquivos[0]

        if not os.path.exists(arquivo):
            raise RuntimeError(
                "O MP3 não foi encontrado."
            )

        if tamanho_arquivo(arquivo) > LIMITE_DISCORD:
            apagar_arquivo(arquivo)

            await interaction.edit_original_response(
                content="❌ O áudio ficou maior que o limite do Discord."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando áudio..."
        )

        await interaction.followup.send(
            file=discord.File(
                arquivo,
                filename="audio.mp3"
            )
        )

        apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as e:

        print(
            f"ERRO TIKTOK: "
            f"{type(e).__name__}: {e}"
        )

        await interaction.edit_original_response(
            content=f"❌ ERRO TIKTOK: {type(e).__name__}: {e}"
        )


# =========================================================
# COMANDO /SOUNDCLOUD
# =========================================================

@tree.command(
    name="soundcloud",
    description="Extrai áudio do SoundCloud"
)
@app_commands.describe(
    link="Link da música do SoundCloud"
)
async def soundcloud(
    interaction: discord.Interaction,
    link: str
):

    if "soundcloud.com" not in link.lower():

        await interaction.response.send_message(
            "❌ Link inválido do SoundCloud.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    try:

        await interaction.edit_original_response(
            content="⏳ Baixando áudio do SoundCloud..."
        )

        info = await asyncio.to_thread(
            baixar_audio_soundcloud,
            link
        )

        # Playlist pode retornar entries
        if info.get("entries"):
            entradas = [
                entrada
                for entrada in info["entries"]
                if entrada
            ]

            if entradas:
                info = entradas[0]

        audio_id = info.get("id")

        arquivo = None

        if audio_id:
            possivel = os.path.join(
                PASTA_AUDIOS,
                f"soundcloud_{audio_id}.mp3"
            )

            if os.path.exists(possivel):
                arquivo = possivel

        # Procura o MP3 mais recente como fallback
        if not arquivo:

            arquivos = glob.glob(
                os.path.join(
                    PASTA_AUDIOS,
                    "soundcloud_*.mp3"
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

        if not arquivo or not os.path.exists(arquivo):

            raise RuntimeError(
                "O MP3 do SoundCloud não foi encontrado."
            )

        if tamanho_arquivo(arquivo) > LIMITE_DISCORD:

            apagar_arquivo(arquivo)

            await interaction.edit_original_response(
                content="❌ O áudio do SoundCloud ficou maior que o limite do Discord."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando áudio do SoundCloud..."
        )

        try:

            await interaction.followup.send(
                file=discord.File(
                    arquivo,
                    filename="soundcloud.mp3"
                )
            )

        except discord.HTTPException as e:

            if getattr(e, "status", None) == 413:

                await interaction.edit_original_response(
                    content="❌ O Discord recusou o arquivo por tamanho."
                )

                return

            raise

        apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content="✅ Áudio do SoundCloud extraído com sucesso!"
        )

    except Exception as e:

        print(
            f"ERRO SOUNDCLOUD: "
            f"{type(e).__name__}: {e}"
        )

        await interaction.edit_original_response(
            content=f"❌ ERRO SOUNDCLOUD: {type(e).__name__}: {e}"
        )


# =========================================================
# COMANDO /MEDAL
# =========================================================

@tree.command(
    name="medal",
    description="Baixa um clipe do Medal"
)
@app_commands.describe(
    link="Link do clipe do Medal"
)
async def medal(
    interaction: discord.Interaction,
    link: str
):

    if "medal.tv" not in link.lower():

        await interaction.response.send_message(
            "❌ Link inválido do Medal.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Baixando o clipe do Medal..."
        )

        arquivo = await asyncio.to_thread(
            baixar_medal,
            link
        )

        if not arquivo or not os.path.exists(arquivo):
            raise RuntimeError(
                "O vídeo não foi encontrado."
            )

        tamanho = tamanho_arquivo(arquivo)

        print(
            f"📦 TAMANHO INICIAL: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            await interaction.edit_original_response(
                content="🗜️ O vídeo ficou grande. Comprimindo automaticamente..."
            )

            arquivo = await asyncio.to_thread(
                comprimir_video,
                arquivo
            )

        tamanho_final = tamanho_arquivo(arquivo)

        print(
            f"📦 TAMANHO FINAL: "
            f"{tamanho_final / 1024 / 1024:.2f} MB"
        )

        if tamanho_final > LIMITE_DISCORD:

            apagar_arquivo(arquivo)

            await interaction.edit_original_response(
                content="❌ Não consegui deixar o vídeo abaixo de 23 MB."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando vídeo..."
        )

        try:

            await interaction.followup.send(
                file=discord.File(
                    arquivo,
                    filename="medal.mp4"
                )
            )

        except discord.HTTPException as e:

            print(
                f"ERRO DISCORD AO ENVIAR: "
                f"{type(e).__name__}: {e}"
            )

            if getattr(e, "status", None) == 413:

                await interaction.edit_original_response(
                    content="❌ ERRO DISCORD: O arquivo foi recusado por tamanho."
                )

                return

            raise

        apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content="✅ Vídeo enviado com sucesso!"
        )

    except Exception as e:

        print(
            f"ERRO MEDAL: "
            f"{type(e).__name__}: {e}"
        )

        if arquivo:
            apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content=f"❌ ERRO MEDAL: {type(e).__name__}: {e}"
        )


# =========================================================
# BOT ONLINE / SINCRONIZAÇÃO DOS COMANDOS
# =========================================================

@bot.event
async def on_ready():

    try:

        comandos = await tree.sync()

        print(
            f"✅ Bot conectado como {bot.user}"
        )

        print(
            f"✅ {len(comandos)} comandos sincronizados:"
        )

        for comando in comandos:
            print(
                f"   /{comando.name}"
            )

    except Exception as e:

        print(
            f"❌ ERRO AO SINCRONIZAR COMANDOS: "
            f"{type(e).__name__}: {e}"
        )


# =========================================================
# INICIAR BOT
# =========================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN não foi encontrado nas variáveis do Railway."
    )

bot.run(TOKEN)
