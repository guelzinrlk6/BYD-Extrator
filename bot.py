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

# Margem de segurança para o Discord
LIMITE_DISCORD = 23 * 1024 * 1024

intents = discord.Intents.default()

bot = discord.Client(intents=intents)

tree = app_commands.CommandTree(bot)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def apagar_arquivo(arquivo):

    try:

        if arquivo and os.path.exists(arquivo):
            os.remove(arquivo)

    except Exception as erro:

        print(
            f"⚠️ AVISO AO APAGAR: {erro}"
        )


def tamanho_mb(arquivo):

    if not arquivo:
        return 0

    if not os.path.exists(arquivo):
        return 0

    return (
        os.path.getsize(arquivo)
        / 1024
        / 1024
    )


def encontrar_ffmpeg():

    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    try:

        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()

    except Exception as erro:

        print(
            f"⚠️ FFmpeg não encontrado: {erro}"
        )

        return None


# =========================================================
# COMPRESSÃO DE VÍDEO
# =========================================================

def descobrir_duracao(
    ffmpeg,
    arquivo
):

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

            horas = int(
                encontrado.group(1)
            )

            minutos = int(
                encontrado.group(2)
            )

            segundos = float(
                encontrado.group(3)
            )

            duracao = (
                horas * 3600
                + minutos * 60
                + segundos
            )

            if duracao > 0:
                return duracao

    except Exception as erro:

        print(
            f"⚠️ Erro ao descobrir duração: {erro}"
        )

    return 60


def comprimir_video(arquivo):

    ffmpeg = encontrar_ffmpeg()

    if not ffmpeg:

        raise RuntimeError(
            "FFmpeg não encontrado."
        )

    if not arquivo or not os.path.exists(arquivo):

        raise FileNotFoundError(
            "Vídeo não encontrado."
        )

    tamanho_original = os.path.getsize(
        arquivo
    )

    if tamanho_original <= LIMITE_DISCORD:

        return arquivo

    duracao = descobrir_duracao(
        ffmpeg,
        arquivo
    )

    print(
        f"🗜️ Comprimindo vídeo de "
        f"{tamanho_mb(arquivo):.2f} MB"
    )

    arquivo_temp = os.path.join(
        PASTA_VIDEOS,
        "temp_comprimido.mp4"
    )

    apagar_arquivo(
        arquivo_temp
    )

    configuracoes = [
        (854, 1.00),
        (720, 0.80),
        (640, 0.65),
        (540, 0.50),
        (480, 0.40)
    ]

    for tentativa, (
        escala,
        fator
    ) in enumerate(
        configuracoes,
        start=1
    ):

        alvo_bytes = (
            18 * 1024 * 1024
        )

        bitrate_total = int(
            (alvo_bytes * 8)
            / duracao
        )

        bitrate_audio = 64000

        bitrate_video = (
            bitrate_total
            - bitrate_audio
        )

        bitrate_video = int(
            bitrate_video * fator
        )

        bitrate_video = max(
            bitrate_video,
            100000
        )

        print(
            f"🗜️ Tentativa {tentativa}/5 | "
            f"{escala}p | "
            f"{bitrate_video} bps"
        )

        comando = [

            ffmpeg,

            "-y",

            "-i",
            arquivo,

            "-vf",
            f"scale='min({escala},iw)':-2",

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
            "64000",

            "-movflags",
            "+faststart",

            arquivo_temp
        ]

        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode != 0:

            print(
                resultado.stderr[-3000:]
            )

            apagar_arquivo(
                arquivo_temp
            )

            continue

        if not os.path.exists(
            arquivo_temp
        ):

            continue

        tamanho_novo = os.path.getsize(
            arquivo_temp
        )

        print(
            f"📦 Resultado: "
            f"{tamanho_novo / 1024 / 1024:.2f} MB"
        )

        if tamanho_novo <= LIMITE_DISCORD:

            apagar_arquivo(
                arquivo
            )

            os.replace(
                arquivo_temp,
                arquivo
            )

            print(
                f"✅ Vídeo final: "
                f"{tamanho_mb(arquivo):.2f} MB"
            )

            return arquivo

        apagar_arquivo(
            arquivo_temp
        )

    raise RuntimeError(
        "Não foi possível comprimir o vídeo."
    )


# =========================================================
# ÁUDIO DO TIKTOK
# =========================================================

def baixar_audio_tiktok(
    link
):

    opcoes = {

        "format":
            "bestaudio/best",

        "outtmpl":
            os.path.join(
                PASTA_AUDIOS,
                "%(id)s.%(ext)s"
            ),

        "postprocessors": [

            {
                "key":
                    "FFmpegExtractAudio",

                "preferredcodec":
                    "mp3",

                "preferredquality":
                    "192"
            }
        ],

        "noplaylist":
            True,

        "quiet":
            True,

        "no_warnings":
            True,

        "retries":
            3,

        "fragment_retries":
            3
    }

    with yt_dlp.YoutubeDL(
        opcoes
    ) as ydl:

        return ydl.extract_info(
            link,
            download=True
        )


# =========================================================
# ÁUDIO DO SOUNDCLOUD
# =========================================================

def baixar_audio_soundcloud(
    link
):

    opcoes = {

        "format":
            "bestaudio/best",

        "outtmpl":
            os.path.join(
                PASTA_AUDIOS,
                "soundcloud_%(id)s.%(ext)s"
            ),

        "postprocessors": [

            {
                "key":
                    "FFmpegExtractAudio",

                "preferredcodec":
                    "mp3",

                "preferredquality":
                    "192"
            }
        ],

        "noplaylist":
            False,

        "quiet":
            True,

        "no_warnings":
            True,

        "retries":
            3,

        "fragment_retries":
            3
    }

    with yt_dlp.YoutubeDL(
        opcoes
    ) as ydl:

        return ydl.extract_info(
            link,
            download=True
        )


# =========================================================
# /EXTRAIR - TIKTOK
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

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Extraindo áudio do TikTok..."
        )

        info = await asyncio.to_thread(
            baixar_audio_tiktok,
            link
        )

        arquivo = os.path.join(
            PASTA_AUDIOS,
            f"{info['id']}.mp3"
        )

        if not os.path.exists(
            arquivo
        ):

            raise FileNotFoundError(
                "MP3 não encontrado."
            )

        if os.path.getsize(
            arquivo
        ) > LIMITE_DISCORD:

            apagar_arquivo(
                arquivo
            )

            arquivo = None

            raise RuntimeError(
                "O áudio ficou maior que 23 MB."
            )

        await interaction.edit_original_response(
            content="📤 Enviando áudio..."
        )

        await interaction.followup.send(
            content=(
                f"🎵 **Áudio extraído:** "
                f"{info.get('title', 'TikTok')}"
            ),
            file=discord.File(
                arquivo
            )
        )

        apagar_arquivo(
            arquivo
        )

        arquivo = None

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as erro:

        print(
            f"❌ ERRO TIKTOK: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(
            arquivo
        )

        try:

            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui extrair o áudio.\n"
                    f"Motivo: {erro}"
                )
            )

        except Exception:
            pass


# =========================================================
# /SOUNDCLOUD
# =========================================================

@tree.command(
    name="soundcloud",
    description="Extrai o áudio de um link do SoundCloud"
)
@app_commands.describe(
    link="Link da música ou áudio do SoundCloud"
)
async def soundcloud(
    interaction: discord.Interaction,
    link: str
):

    if (
        "soundcloud.com" not in
        link.lower()
    ):

        await interaction.response.send_message(
            "❌ Link inválido do SoundCloud.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    arquivos_antes = set(
        glob.glob(
            os.path.join(
                PASTA_AUDIOS,
                "*"
            )
        )
    )

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Baixando áudio do SoundCloud..."
        )

        info = await asyncio.to_thread(
            baixar_audio_soundcloud,
            link
        )

        # Primeiro procura pelo ID.
        arquivo_id = os.path.join(
            PASTA_AUDIOS,
            f"soundcloud_{info['id']}.mp3"
        )

        if os.path.exists(
            arquivo_id
        ):

            arquivo = arquivo_id

        else:

            # Procura novos MP3 criados pelo download.
            arquivos_depois = set(
                glob.glob(
                    os.path.join(
                        PASTA_AUDIOS,
                        "*"
                    )
                )
            )

            novos = (
                arquivos_depois
                - arquivos_antes
            )

            mp3s = [
                x for x in novos
                if x.lower().endswith(
                    ".mp3"
                )
            ]

            if mp3s:

                mp3s.sort(
                    key=os.path.getmtime,
                    reverse=True
                )

                arquivo = mp3s[0]

        if not arquivo:

            # Última tentativa:
            # procura MP3 mais recente.
            mp3s = glob.glob(
                os.path.join(
                    PASTA_AUDIOS,
                    "*.mp3"
                )
            )

            if mp3s:

                mp3s.sort(
                    key=os.path.getmtime,
                    reverse=True
                )

                arquivo = mp3s[0]

        if not arquivo or not os.path.exists(
            arquivo
        ):

            raise FileNotFoundError(
                "Áudio do SoundCloud não foi encontrado."
            )

        tamanho = os.path.getsize(
            arquivo
        )

        print(
            f"🎵 SoundCloud: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            apagar_arquivo(
                arquivo
            )

            arquivo = None

            raise RuntimeError(
                "O áudio ficou maior que 23 MB."
            )

        await interaction.edit_original_response(
            content="📤 Enviando áudio..."
        )

        titulo = info.get(
            "title",
            "SoundCloud"
        )

        await interaction.followup.send(
            content=(
                f"🎵 **SoundCloud:** {titulo}"
            ),
            file=discord.File(
                arquivo,
                filename="soundcloud.mp3"
            )
        )

        apagar_arquivo(
            arquivo
        )

        arquivo = None

        await interaction.edit_original_response(
            content=(
                "✅ Áudio do SoundCloud "
                "extraído com sucesso!"
            )
        )

    except Exception as erro:

        print(
            f"❌ ERRO SOUNDCLOUD: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(
            arquivo
        )

        try:

            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui extrair o SoundCloud.\n"
                    f"Motivo: {erro}"
                )
            )

        except Exception:
            pass


# =========================================================
# BAIXAR MEDAL
# =========================================================

def baixar_medal(
    link,
    qualidade
):

    arquivo_saida = None

    opcoes = {

        "format": (
            f"bestvideo[height<={qualidade}]"
            "+bestaudio/"
            f"best[height<={qualidade}]/best"
        ),

        "outtmpl":
            os.path.join(
                PASTA_VIDEOS,
                "%(id)s.%(ext)s"
            ),

        "merge_output_format":
            "mp4",

        "noplaylist":
            True,

        "quiet":
            True,

        "no_warnings":
            True,

        "retries":
            3,

        "fragment_retries":
            3
    }

    with yt_dlp.YoutubeDL(
        opcoes
    ) as ydl:

        info = ydl.extract_info(
            link,
            download=True
        )

        if not info:

            raise RuntimeError(
                "Medal não retornou informações."
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
                arquivo_base
                + extensao
            )

            if os.path.exists(
                possivel
            ):

                arquivo_saida = (
                    possivel
                )

                break

    if arquivo_saida is None:

        arquivos = glob.glob(
            os.path.join(
                PASTA_VIDEOS,
                f"{info['id']}.*"
            )
        )

        if arquivos:

            arquivos.sort(
                key=os.path.getsize,
                reverse=True
            )

            arquivo_saida = (
                arquivos[0]
            )

    if arquivo_saida is None:

        raise FileNotFoundError(
            "Vídeo não encontrado."
        )

    return (
        arquivo_saida,
        info
    )


# =========================================================
# /MEDAL
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
    info = None

    try:

        for qualidade in [
            1080,
            720,
            480
        ]:

            await interaction.edit_original_response(
                content=(
                    f"🎬 Baixando em {qualidade}p..."
                )
            )

            try:

                arquivo_teste, info_teste = (
                    await asyncio.to_thread(
                        baixar_medal,
                        link,
                        qualidade
                    )
                )

                if not arquivo_teste:

                    continue

                if not os.path.exists(
                    arquivo_teste
                ):

                    continue

                tamanho = os.path.getsize(
                    arquivo_teste
                )

                print(
                    f"📦 {qualidade}p: "
                    f"{tamanho / 1024 / 1024:.2f} MB"
                )

                if tamanho <= LIMITE_DISCORD:

                    arquivo = (
                        arquivo_teste
                    )

                    info = (
                        info_teste
                    )

                    break

                # Se chegou em 480p,
                # mantém para compressão.
                if qualidade == 480:

                    arquivo = (
                        arquivo_teste
                    )

                    info = (
                        info_teste
                    )

                    break

                apagar_arquivo(
                    arquivo_teste
                )

            except Exception as erro:

                print(
                    f"⚠️ ERRO {qualidade}p: "
                    f"{type(erro).__name__}: {erro}"
                )

                continue

        if not arquivo:

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

        tamanho_final = os.path.getsize(
            arquivo
        )

        print(
            f"📦 TAMANHO FINAL: "
            f"{tamanho_final / 1024 / 1024:.2f} MB"
        )

        if tamanho_final > LIMITE_DISCORD:

            raise RuntimeError(
                "Vídeo ainda está acima do limite."
            )

        await interaction.edit_original_response(
            content=(
                f"📤 Enviando vídeo "
                f"({tamanho_final / 1024 / 1024:.2f} MB)..."
            )
        )

        try:

            await interaction.followup.send(
                content=(
                    f"🎬 **Clipe do Medal:** "
                    f"{info.get('title', 'Vídeo')}"
                ),
                file=discord.File(
                    arquivo,
                    filename="medal.mp4"
                )
            )

        except discord.HTTPException as erro:

            print(
                f"❌ ERRO DISCORD AO ENVIAR: "
                f"{erro}"
            )

            raise RuntimeError(
                "O Discord recusou o arquivo."
            )

        apagar_arquivo(
            arquivo
        )

        arquivo = None

        await interaction.edit_original_response(
            content=(
                "✅ Clipe baixado e enviado com sucesso!"
            )
        )

    except Exception as erro:

        print(
            f"❌ ERRO MEDAL: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(
            arquivo
        )

        try:

            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui enviar o vídeo.\n"
                    f"Motivo: {erro}"
                )
            )

        except Exception:
            pass


# =========================================================
# BOT ONLINE
# =========================================================

@bot.event
async def on_ready():

    try:

        await tree.sync()

        print(
            f"✅ BYD Extrator conectado como "
            f"{bot.user}"
        )

        print(
            "✅ Comandos sincronizados."
        )

    except Exception as erro:

        print(
            f"❌ ERRO AO SINCRONIZAR: "
            f"{type(erro).__name__}: {erro}"
        )


# =========================================================
# INICIAR
# =========================================================

if not TOKEN:

    print(
        "❌ DISCORD_TOKEN não encontrado."
    )

else:

    print(
        "🚀 Iniciando BYD Extrator..."
    )

    bot.run(TOKEN)
