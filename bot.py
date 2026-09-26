import discord
from discord import app_commands
import yt_dlp
import os

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

# Limite usado pelo bot para envio
LIMITE_DISCORD = 25 * 1024 * 1024


# =========================================================
# /extrair
# =========================================================

@tree.command(
    name="extrair",
    description="Extrai o áudio de um TikTok"
)
@app_commands.describe(link="Link do TikTok")
async def extrair(interaction: discord.Interaction, link: str):

    if "tiktok.com" not in link:
        await interaction.response.send_message(
            "❌ Envie um link válido do TikTok.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "⏳ Extraindo o áudio..."
    )

    try:
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
        }

        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(
                link,
                download=True
            )

        arquivo = os.path.join(
            PASTA_AUDIOS,
            f"{info['id']}.mp3"
        )

        if not os.path.exists(arquivo):
            raise FileNotFoundError(
                "MP3 não foi encontrado."
            )

        tamanho = os.path.getsize(arquivo)

        if tamanho > LIMITE_DISCORD:
            os.remove(arquivo)

            await interaction.edit_original_response(
                content="❌ O áudio ficou maior que 25 MB."
            )
            return

        await interaction.channel.send(
            content=(
                f"🎵 **Áudio extraído:** "
                f"{info.get('title', 'TikTok')}"
            ),
            file=discord.File(arquivo)
        )

        os.remove(arquivo)

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as erro:
        print(f"ERRO EXTRAIR: {erro}")

        await interaction.edit_original_response(
            content=(
                "❌ Não consegui extrair o áudio desse TikTok."
            )
        )


# =========================================================
# FUNÇÃO PARA BAIXAR MEDAL
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
            ".mp4",
            ".webm",
            ".mkv",
            ".mov"
        ]:

            possivel = arquivo_base + extensao

            if os.path.exists(possivel):
                arquivo_saida = possivel
                break

    if arquivo_saida is None:
        raise FileNotFoundError(
            "Vídeo não foi encontrado depois do download."
        )

    return arquivo_saida, info


# =========================================================
# /medal
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

    if "medal.tv" not in link:
        await interaction.response.send_message(
            "❌ Envie um link válido do Medal.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "⏳ Baixando o clipe em 1080p..."
    )

    arquivo = None

    try:

        # =================================================
        # 1ª TENTATIVA — 1080p
        # =================================================

        print("🎬 Tentando baixar em 1080p...")

        arquivo, info = baixar_medal(
            link,
            1080
        )

        tamanho = os.path.getsize(arquivo)

        print(
            f"📦 Tamanho do vídeo: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        # =================================================
        # SE PASSAR DE 25 MB
        # =================================================

        if tamanho > LIMITE_DISCORD:

            print(
                "⚠️ Vídeo maior que 25 MB."
            )

            os.remove(arquivo)
            arquivo = None

            # =============================================
            # 2ª TENTATIVA — 720p
            # =============================================

            await interaction.edit_original_response(
                content=(
                    "⚠️ O vídeo em 1080p ficou grande. "
                    "Tentando 720p..."
                )
            )

            print("🎬 Tentando baixar em 720p...")

            arquivo, info = baixar_medal(
                link,
                720
            )

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 Tamanho em 720p: "
                f"{tamanho / 1024 / 1024:.2f} MB"
            )

        # =================================================
        # SE AINDA PASSAR DE 25 MB
        # =================================================

        if tamanho > LIMITE_DISCORD:

            os.remove(arquivo)
            arquivo = None

            # =============================================
            # 3ª TENTATIVA — 480p
            # =============================================

            await interaction.edit_original_response(
                content=(
                    "⚠️ Ainda ficou grande. "
                    "Tentando 480p..."
                )
            )

            print("🎬 Tentando baixar em 480p...")

            arquivo, info = baixar_medal(
                link,
                480
            )

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 Tamanho em 480p: "
                f"{tamanho / 1024 / 1024:.2f} MB"
            )

        # =================================================
        # VERIFICAÇÃO FINAL
        # =================================================

        if tamanho > LIMITE_DISCORD:

            os.remove(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content=(
                    "❌ Mesmo em 480p o vídeo ficou "
                    "maior que 25 MB."
                )
            )

            return

        # =================================================
        # ENVIA PARA O DISCORD
        # =================================================

        await interaction.edit_original_response(
            content="📤 Enviando o vídeo para o Discord..."
        )

        await interaction.channel.send(
            content=(
                f"🎬 **Clipe do Medal:** "
                f"{info.get('title', 'Vídeo')}"
            ),
            file=discord.File(arquivo)
        )

        # =================================================
        # APAGA O ARQUIVO DO PC
        # =================================================

        os.remove(arquivo)
        arquivo = None

        await interaction.edit_original_response(
            content="✅ Clipe baixado com sucesso!"
        )

    except Exception as erro:

        print(f"ERRO MEDAL: {erro}")

        # Remove arquivo caso tenha ficado para trás
        if arquivo and os.path.exists(arquivo):
            try:
                os.remove(arquivo)
            except:
                pass

        await interaction.edit_original_response(
            content=(
                "❌ Não consegui baixar esse clipe do Medal. "
                "Veja o erro no CMD."
            )
        )


# =========================================================
# BOT ONLINE
# =========================================================

@bot.event
async def on_ready():

    await tree.sync()

    print(
        f"✅ BYD Extrator conectado como {bot.user}"
    )


# =========================================================
# INICIAR BOT
# =========================================================

bot.run(TOKEN)
