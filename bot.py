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

        print("🎵 Iniciando extração do TikTok...")

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

        # yt-dlp roda em outra thread para não bloquear o bot
        info = await asyncio.to_thread(
            baixar_audio_tiktok,
            link,
            opcoes
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

        print(
            f"📦 Tamanho do áudio: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            os.remove(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content="❌ O áudio ficou maior que 25 MB."
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando o áudio para o Discord..."
        )

        await interaction.followup.send(
            content=(
                f"🎵 **Áudio extraído:** "
                f"{info.get('title', 'TikTok')}"
            ),
            file=discord.File(arquivo)
        )

        os.remove(arquivo)
        arquivo = None

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

    except Exception as erro:

        print(f"ERRO EXTRAIR: {erro}")

        if arquivo and os.path.exists(arquivo):
            try:
                os.remove(arquivo)
            except Exception:
                pass

        await interaction.edit_original_response(
            content=(
                "❌ Não consegui extrair o áudio desse TikTok. "
                "Veja o erro no CMD."
            )
        )


def baixar_audio_tiktok(link, opcoes):

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        return ydl.extract_info(
            link,
            download=True
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

    # =====================================================
    # IMPORTANTE:
    # Responde imediatamente ao Discord.
    # =====================================================

    await interaction.response.defer()

    arquivo = None

    try:

        # =================================================
        # 1ª TENTATIVA — 1080p
        # =================================================

        await interaction.edit_original_response(
            content="⏳ Baixando o clipe em 1080p..."
        )

        print("🎬 Tentando baixar em 1080p...")

        arquivo, info = await asyncio.to_thread(
            baixar_medal,
            link,
            1080
        )

        tamanho = os.path.getsize(arquivo)

        print(
            f"📦 Tamanho do vídeo em 1080p: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        # =================================================
        # SE PASSAR DE 25 MB
        # =================================================

        if tamanho > LIMITE_DISCORD:

            print("⚠️ Vídeo maior que 25 MB.")

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

            arquivo, info = await asyncio.to_thread(
                baixar_medal,
                link,
                720
            )

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 Tamanho do vídeo em 720p: "
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

            arquivo, info = await asyncio.to_thread(
                baixar_medal,
                link,
                480
            )

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 Tamanho do vídeo em 480p: "
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

        await interaction.followup.send(
            content=(
                f"🎬 **Clipe do Medal:** "
                f"{info.get('title', 'Vídeo')}"
            ),
            file=discord.File(arquivo)
        )

        # =================================================
        # APAGA O ARQUIVO
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
            except Exception:
                pass

        try:
            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui baixar esse clipe do Medal. "
                    "Veja o erro no CMD."
                )
            )
        except Exception:
            pass


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

if not TOKEN:
    raise RuntimeError(
        "A variável DISCORD_TOKEN não foi encontrada."
    )

bot.run(TOKEN)
```
