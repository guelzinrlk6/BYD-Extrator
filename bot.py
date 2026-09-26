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

# Vamos trabalhar com margem de segurança.
# O arquivo precisa ficar BEM abaixo do limite.
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
        print(f"⚠️ AVISO AO APAGAR: {erro}")


def encontrar_ffmpeg():

    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        if ffmpeg:
            return ffmpeg

    except Exception as erro:

        print(
            f"⚠️ imageio_ffmpeg não disponível: {erro}"
        )

    return None


def tamanho_mb(arquivo):

    if not arquivo or not os.path.exists(arquivo):
        return 0

    return os.path.getsize(arquivo) / 1024 / 1024


# =========================================================
# PEGAR DURAÇÃO DO VÍDEO
# =========================================================

def descobrir_duracao(ffmpeg, arquivo):

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

        texto = resultado.stderr

        encontrado = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            texto
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

            if duracao > 0:
                return duracao

    except Exception as erro:

        print(
            f"⚠️ Não consegui descobrir duração: {erro}"
        )

    return 60


# =========================================================
# COMPRIMIR VÍDEO
# =========================================================

def comprimir_video(arquivo):

    ffmpeg = encontrar_ffmpeg()

    if not ffmpeg:

        raise RuntimeError(
            "FFmpeg não encontrado no Railway."
        )

    if not arquivo or not os.path.exists(arquivo):

        raise FileNotFoundError(
            "Arquivo de vídeo não encontrado para compressão."
        )

    tamanho_original = os.path.getsize(arquivo)

    if tamanho_original <= LIMITE_DISCORD:

        print(
            f"✅ Vídeo já está abaixo do limite: "
            f"{tamanho_mb(arquivo):.2f} MB"
        )

        return arquivo

    duracao = descobrir_duracao(
        ffmpeg,
        arquivo
    )

    print(
        f"⏱️ Duração: {duracao:.2f} segundos"
    )

    # Arquivo temporário exclusivo
    base_temp = os.path.join(
        PASTA_VIDEOS,
        "video_comprimido_temp.mp4"
    )

    apagar_arquivo(base_temp)

    # Vamos tentar várias configurações.
    # Cada tentativa fica progressivamente menor.
    configuracoes = [
        {
            "escala": 854,
            "bitrate": None
        },
        {
            "escala": 720,
            "bitrate": None
        },
        {
            "escala": 640,
            "bitrate": None
        },
        {
            "escala": 540,
            "bitrate": None
        },
        {
            "escala": 480,
            "bitrate": None
        }
    ]

    for tentativa, config in enumerate(
        configuracoes,
        start=1
    ):

        # Alvo de aproximadamente 20 MB.
        # Deixamos bastante margem para o Discord.
        tamanho_alvo_bytes = 20 * 1024 * 1024

        bits_alvo = tamanho_alvo_bytes * 8

        bitrate_total = int(
            bits_alvo / duracao
        )

        # Áudio 64 kbps.
        bitrate_audio = 64000

        bitrate_video = (
            bitrate_total
            - bitrate_audio
        )

        # Evita bitrate absurdo.
        bitrate_video = max(
            bitrate_video,
            120000
        )

        # A cada tentativa diminuímos ainda mais.
        fator = 1.0

        if tentativa == 2:
            fator = 0.80

        elif tentativa == 3:
            fator = 0.65

        elif tentativa == 4:
            fator = 0.50

        elif tentativa == 5:
            fator = 0.40

        bitrate_video = int(
            bitrate_video * fator
        )

        bitrate_video = max(
            bitrate_video,
            100000
        )

        escala = config["escala"]

        filtro = (
            f"scale='min({escala},iw)':-2"
        )

        print(
            f"🗜️ Compressão {tentativa}/5 | "
            f"escala {escala}p | "
            f"vídeo {bitrate_video} bps"
        )

        comando = [
            ffmpeg,
            "-y",
            "-i",
            arquivo,

            "-vf",
            filtro,

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

            base_temp
        ]

        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode != 0:

            print(
                "❌ ERRO FFmpeg:"
            )

            print(
                resultado.stderr[-4000:]
            )

            apagar_arquivo(base_temp)

            continue

        if not os.path.exists(base_temp):

            print(
                "⚠️ FFmpeg não criou o arquivo."
            )

            continue

        tamanho_novo = os.path.getsize(
            base_temp
        )

        print(
            f"📦 Resultado da compressão: "
            f"{tamanho_novo / 1024 / 1024:.2f} MB"
        )

        if tamanho_novo <= LIMITE_DISCORD:

            apagar_arquivo(arquivo)

            os.replace(
                base_temp,
                arquivo
            )

            print(
                f"✅ Compressão concluída: "
                f"{tamanho_mb(arquivo):.2f} MB"
            )

            return arquivo

        # Ainda ficou grande.
        apagar_arquivo(base_temp)

    raise RuntimeError(
        "Não foi possível reduzir o vídeo para menos de 23 MB."
    )


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

        return ydl.extract_info(
            link,
            download=True
        )


# =========================================================
# /EXTRAIR
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
            content="⏳ Extraindo áudio..."
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
                content="❌ O áudio ficou maior que o limite do Discord."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando áudio..."
        )

        await interaction.followup.send(
            content=(
                f"🎵 **Áudio extraído:** "
                f"{info.get('title', 'TikTok')}"
            ),
            file=discord.File(arquivo)
        )

        apagar_arquivo(arquivo)

        arquivo = None

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
                content=(
                    "❌ Não consegui extrair esse TikTok.\n"
                    f"Motivo: {erro}"
                )
            )

        except Exception:
            pass


# =========================================================
# BAIXAR MEDAL
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

            # Pega o maior arquivo relacionado ao ID.
            arquivos.sort(
                key=lambda x: os.path.getsize(x),
                reverse=True
            )

            arquivo_saida = arquivos[0]

    if arquivo_saida is None:

        raise FileNotFoundError(
            "Vídeo não encontrado."
        )

    return arquivo_saida, info


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

        # =================================================
        # BAIXAR
        # =================================================

        for qualidade in [1080, 720, 480]:

            await interaction.edit_original_response(
                content=(
                    f"🎬 Baixando vídeo em {qualidade}p..."
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

                if not os.path.exists(arquivo_teste):

                    continue

                tamanho = os.path.getsize(
                    arquivo_teste
                )

                print(
                    f"📦 {qualidade}p baixado: "
                    f"{tamanho / 1024 / 1024:.2f} MB"
                )

                # Se já cabe, usa imediatamente.
                if tamanho <= LIMITE_DISCORD:

                    arquivo = arquivo_teste
                    info = info_teste

                    break

                # Se ainda não cabe, guarda o arquivo
                # somente se for 480p.
                if qualidade == 480:

                    arquivo = arquivo_teste
                    info = info_teste

                    print(
                        "⚠️ 480p ainda está grande. "
                        "Vai para compressão."
                    )

                    break

                # 1080/720 ficaram grandes.
                # Apaga e tenta qualidade menor.
                apagar_arquivo(
                    arquivo_teste
                )

                arquivo = None

                info = None

            except Exception as erro:

                print(
                    f"⚠️ ERRO {qualidade}p: "
                    f"{type(erro).__name__}: {erro}"
                )

                continue

        if arquivo is None:

            raise RuntimeError(
                "Não foi possível baixar o vídeo do Medal."
            )

        # =================================================
        # VERIFICAR TAMANHO
        # =================================================

        tamanho = os.path.getsize(
            arquivo
        )

        print(
            f"📦 Antes da compressão: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        # =================================================
        # COMPRIMIR SE NECESSÁRIO
        # =================================================

        if tamanho > LIMITE_DISCORD:

            await interaction.edit_original_response(
                content=(
                    "🗜️ O vídeo ficou grande. "
                    "Comprimindo automaticamente..."
                )
            )

            arquivo = await asyncio.to_thread(
                comprimir_video,
                arquivo
            )

        # =================================================
        # VERIFICAÇÃO FINAL
        # =================================================

        if not arquivo:

            raise RuntimeError(
                "Arquivo final não existe."
            )

        if not os.path.exists(arquivo):

            raise RuntimeError(
                "Arquivo final não foi encontrado."
            )

        tamanho_final = os.path.getsize(
            arquivo
        )

        print(
            f"📦 TAMANHO FINAL: "
            f"{tamanho_final / 1024 / 1024:.2f} MB"
        )

        # NÃO tenta enviar se estiver acima do limite.
        if tamanho_final > LIMITE_DISCORD:

            raise RuntimeError(
                f"Vídeo ainda ficou com "
                f"{tamanho_final / 1024 / 1024:.2f} MB."
            )

        # =================================================
        # ENVIO
        # =================================================

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
                f"❌ ERRO DISCORD AO ENVIAR: {erro}"
            )

            if getattr(erro, "status", None) == 413:

                raise RuntimeError(
                    "O Discord recusou o arquivo mesmo "
                    "depois da compressão."
                )

            raise

        # =================================================
        # LIMPAR
        # =================================================

        apagar_arquivo(
            arquivo
        )

        arquivo = None

        await interaction.edit_original_response(
            content=(
                "✅ Clipe baixado e enviado com sucesso!"
            )
        )

        print(
            "✅ MEDAL FINALIZADO."
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
