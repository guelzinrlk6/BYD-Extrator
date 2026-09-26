import discord
from discord import app_commands
import yt_dlp
import os
import asyncio
import glob
import shutil
import subprocess
import re

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
PASTA_VIDEOS = "videos"

os.makedirs(PASTA_AUDIOS, exist_ok=True)
os.makedirs(PASTA_VIDEOS, exist_ok=True)

LIMITE_DISCORD = 24 * 1024 * 1024

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def apagar_arquivo(arquivo):
    try:
        if arquivo and os.path.exists(arquivo):
            os.remove(arquivo)
    except Exception as erro:
        print(f"AVISO AO APAGAR ARQUIVO: {erro}")


def encontrar_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def comprimir_video(arquivo):

    ffmpeg = encontrar_ffmpeg()

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg não encontrado."
        )

    tamanho_original = os.path.getsize(arquivo)

    if tamanho_original <= LIMITE_DISCORD:
        return arquivo

    arquivo_temp = os.path.join(
        PASTA_VIDEOS,
        "temp_" + os.path.basename(arquivo)
    )

    duracao = 60

    try:
        resultado = subprocess.run(
            [
                ffmpeg,
                "-i",
                arquivo
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        encontrado = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            resultado.stderr
        )

        if encontrado:
            horas = int(encontrado.group(1))
            minutos = int(encontrado.group(2))
            segundos = float(encontrado.group(3))

            duracao = (
                horas * 3600
                + minutos * 60
                + segundos
            )

    except Exception:
        duracao = 60

    if duracao <= 0:
        duracao = 60

    bitrate_total = int(
        (22 * 1024 * 1024 * 8) / duracao
    )

    bitrate_video = int(
        bitrate_total * 0.88
    )

    bitrate_video = max(
        bitrate_video,
        250000
    )

    comando = [
        ffmpeg,
        "-y",
        "-i",
        arquivo,
        "-vf",
        "scale='min(854,iw)':-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        str(bitrate_video),
        "-maxrate",
        str(bitrate_video),
        "-bufsize",
        str(bitrate_video * 2),
        "-c:a",
        "aac",
        "-b:a",
        "96000",
        "-movflags",
        "+faststart",
        arquivo_temp
    ]

    print(
        f"🗜️ Comprimindo "
        f"{tamanho_original / 1024 / 1024:.2f} MB..."
    )

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if resultado.returncode != 0:

        print(resultado.stderr[-3000:])

        apagar_arquivo(arquivo_temp)

        raise RuntimeError(
            "Erro ao comprimir o vídeo."
        )

    if not os.path.exists(arquivo_temp):

        raise RuntimeError(
            "FFmpeg não criou o vídeo."
        )

    tamanho_novo = os.path.getsize(
        arquivo_temp
    )

    print(
        f"📦 Após compressão: "
        f"{tamanho_novo / 1024 / 1024:.2f} MB"
    )

    if tamanho_novo > LIMITE_DISCORD:

        apagar_arquivo(arquivo_temp)

        bitrate_video = int(
            bitrate_video * 0.55
        )

        comando[10] = str(bitrate_video)
        comando[12] = str(bitrate_video)
        comando[-1] = arquivo_temp

        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode != 0:
            apagar_arquivo(arquivo_temp)

            raise RuntimeError(
                "Segunda compressão falhou."
            )

        tamanho_novo = os.path.getsize(
            arquivo_temp
        )

        print(
            f"📦 Segunda compressão: "
            f"{tamanho_novo / 1024 / 1024:.2f} MB"
        )

    if tamanho_novo > LIMITE_DISCORD:

        apagar_arquivo(arquivo_temp)

        raise RuntimeError(
            "O vídeo continua maior que 24 MB."
        )

    apagar_arquivo(arquivo)

    os.rename(
        arquivo_temp,
        arquivo
    )

    return arquivo


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
        return ydl.extract_info(
            link,
            download=True
        )


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
            "❌ Envie um link válido do TikTok.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Extraindo o áudio..."
        )

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
                "MP3 não encontrado."
            )

        tamanho = os.path.getsize(
            arquivo
        )

        if tamanho > LIMITE_DISCORD:

            apagar_arquivo(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content="❌ O áudio ficou maior que 24 MB."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando o áudio..."
        )

        await interaction.followup.send(
            content=(
                f"🎵 **Áudio extraído:** "
                f"{info.get('title', 'TikTok')}"
            ),
            file=discord.File(arquivo)
        )

        apagar_arquivo(arquivo)

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as erro:

        print(
            f"❌ ERRO EXTRAIR: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(arquivo)

        try:
            await interaction.edit_original_response(
                content="❌ Não consegui extrair esse TikTok."
            )
        except Exception:
            pass


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
        "retries": 3,
        "fragment_retries": 3
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:

        info = ydl.extract_info(
            link,
            download=True
        )

        if not info:
            raise RuntimeError(
                "O Medal não retornou informações."
            )

        arquivo_base = os.path.join(
            PASTA_VIDEOS,
            str(info["id"])
        )

        for extensao in [
            ".mp4",
            ".webm",
            ".mkv",
            ".mov"
        ]:

            possivel = (
                arquivo_base + extensao
            )

            if os.path.exists(possivel):

                arquivo_saida = possivel

                break

    if arquivo_saida is None:

        arquivos = glob.glob(
            os.path.join(
                PASTA_VIDEOS,
                f"{info['id']}.*"
            )
        )

        if arquivos:
            arquivo_saida = arquivos[0]

    if arquivo_saida is None:

        raise FileNotFoundError(
            "Vídeo não encontrado."
        )

    return arquivo_saida, info


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
            "❌ Envie um link válido do Medal.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    arquivo = None
    info = None

    try:

        for qualidade in [1080, 720, 480]:

            await interaction.edit_original_response(
                content=(
                    f"🎬 Baixando o vídeo em "
                    f"{qualidade}p..."
                )
            )

            try:

                arquivo, info = await asyncio.to_thread(
                    baixar_medal,
                    link,
                    qualidade
                )

                if arquivo and os.path.exists(arquivo):

                    tamanho = os.path.getsize(
                        arquivo
                    )

                    print(
                        f"📦 {qualidade}p: "
                        f"{tamanho / 1024 / 1024:.2f} MB"
                    )

                    if tamanho <= LIMITE_DISCORD:
                        break

                    apagar_arquivo(arquivo)
                    arquivo = None

            except Exception as erro:

                print(
                    f"⚠️ Erro em {qualidade}p: "
                    f"{type(erro).__name__}: {erro}"
                )

                apagar_arquivo(arquivo)
                arquivo = None

        if arquivo is None:

            raise RuntimeError(
                "Não foi possível baixar o vídeo."
            )

        tamanho = os.path.getsize(
            arquivo
        )

        if tamanho > LIMITE_DISCORD:

            await interaction.edit_original_response(
                content=(
                    "🗜️ Vídeo grande. "
                    "Comprimindo automaticamente..."
                )
            )

            arquivo = await asyncio.to_thread(
                comprimir_video,
                arquivo
            )

        tamanho = os.path.getsize(
            arquivo
        )

        print(
            f"📦 Tamanho final: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            raise RuntimeError(
                "O vídeo continua maior que 24 MB."
            )

        await interaction.edit_original_response(
            content="📤 Enviando o vídeo para o Discord..."
        )

        try:

            await interaction.followup.send(
                content=(
                    f"🎬 **Clipe do Medal:** "
                    f"{info.get('title', 'Vídeo')}"
                ),
                file=discord.File(arquivo)
            )

        except discord.HTTPException as erro:

            print(
                f"❌ ERRO DISCORD AO ENVIAR: {erro}"
            )

            if getattr(erro, "status", None) == 413:

                raise RuntimeError(
                    "O Discord recusou o arquivo por tamanho."
                )

            raise

        apagar_arquivo(arquivo)
        arquivo = None

        await interaction.edit_original_response(
            content="✅ Clipe baixado e enviado com sucesso!"
        )

        print("✅ MEDAL CONCLUÍDO.")

    except Exception as erro:

        print(
            f"❌ ERRO MEDAL: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(arquivo)

        try:

            await interaction.edit_original_response(
                content=(
                    f"❌ Não consegui enviar o vídeo.\n"
                    f"Motivo: {erro}"
                )
            )

        except Exception:
            pass


@bot.event
async def on_ready():

    try:

        await tree.sync()

        print(
            f"✅ BYD Extrator conectado como "
            f"{bot.user}"
        )

        print("✅ Comandos sincronizados.")

    except Exception as erro:

        print(
            f"❌ ERRO AO SINCRONIZAR: "
            f"{type(erro).__name__}: {erro}"
        )


if not TOKEN:

    print(
        "❌ ERRO: DISCORD_TOKEN não encontrado."
    )

else:

    print("🚀 Iniciando BYD Extrator...")

    bot.run(TOKEN)
