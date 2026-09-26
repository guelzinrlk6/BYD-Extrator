import discord
from discord import app_commands
import yt_dlp
import os
import asyncio
import glob

# =========================================================
# CONFIGURAÇÃO
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

PASTA_AUDIOS = "audios"
PASTA_VIDEOS = "videos"

os.makedirs(PASTA_AUDIOS, exist_ok=True)
os.makedirs(PASTA_VIDEOS, exist_ok=True)

# Limite de segurança abaixo dos 25 MB
LIMITE_DISCORD = 24 * 1024 * 1024

intents = discord.Intents.default()

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def apagar_arquivo(arquivo):
    """Apaga um arquivo sem deixar o bot quebrar se ele não existir."""
    try:
        if arquivo and os.path.exists(arquivo):
            os.remove(arquivo)
    except Exception as erro:
        print(f"AVISO: não consegui apagar arquivo: {erro}")


def limpar_arquivos_pasta(pasta):
    """Limpa arquivos temporários antigos."""
    try:
        for arquivo in glob.glob(os.path.join(pasta, "*")):
            if os.path.isfile(arquivo):
                apagar_arquivo(arquivo)
    except Exception as erro:
        print(f"AVISO AO LIMPAR PASTA: {erro}")


# =========================================================
# DOWNLOAD DE ÁUDIO DO TIKTOK
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
                "preferredquality": "192",
            }
        ],

        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        # Evita alguns problemas de rede
        "retries": 3,
        "fragment_retries": 3,
    }

    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(
            link,
            download=True
        )

    return info


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

    # Verifica o link
    if "tiktok.com" not in link.lower():

        await interaction.response.send_message(
            "❌ Envie um link válido do TikTok.",
            ephemeral=True
        )

        return

    # IMPORTANTE:
    # defer evita o erro Unknown interaction
    await interaction.response.defer()

    arquivo = None

    try:

        await interaction.edit_original_response(
            content="⏳ Extraindo o áudio do TikTok..."
        )

        print("🎵 Iniciando download do TikTok...")

        # yt-dlp roda fora da thread principal
        info = await asyncio.to_thread(
            baixar_audio_tiktok,
            link
        )

        arquivo = os.path.join(
            PASTA_AUDIOS,
            f"{info['id']}.mp3"
        )

        # Confirma se o MP3 existe
        if not os.path.exists(arquivo):

            raise FileNotFoundError(
                "O MP3 não foi encontrado após o download."
            )

        tamanho = os.path.getsize(arquivo)

        tamanho_mb = tamanho / 1024 / 1024

        print(
            f"📦 Tamanho do áudio: {tamanho_mb:.2f} MB"
        )

        # Segurança
        if tamanho > LIMITE_DISCORD:

            apagar_arquivo(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content=(
                    "❌ O áudio ficou maior que 24 MB "
                    "e não pode ser enviado pelo Discord."
                )
            )

            return

        await interaction.edit_original_response(
            content="📤 Enviando o áudio para o Discord..."
        )

        try:

            await interaction.followup.send(
                content=(
                    f"🎵 **Áudio extraído:** "
                    f"{info.get('title', 'TikTok')}"
                ),
                file=discord.File(arquivo)
            )

        except discord.HTTPException as erro:

            print(f"❌ ERRO AO ENVIAR ÁUDIO: {erro}")

            if getattr(erro, "status", None) == 413:

                await interaction.edit_original_response(
                    content=(
                        "❌ O Discord recusou o arquivo "
                        "porque ele ficou grande demais."
                    )
                )

                return

            raise

        # Apaga depois do envio
        apagar_arquivo(arquivo)
        arquivo = None

        await interaction.edit_original_response(
            content="✅ Áudio extraído com sucesso!"
        )

        print("✅ TikTok concluído.")

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
                    "Verifique o link e tente novamente."
                )
            )

        except Exception:
            pass


# =========================================================
# DOWNLOAD DO MEDAL
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

        # Tentativas automáticas
        "retries": 3,
        "fragment_retries": 3,

        # Continua mesmo se algum formato específico falhar
        "ignoreerrors": False,
    }

    print(
        f"🎬 Iniciando download Medal em {qualidade}p..."
    )

    with yt_dlp.YoutubeDL(opcoes) as ydl:

        info = ydl.extract_info(
            link,
            download=True
        )

        if not info:
            raise RuntimeError(
                "O Medal não retornou informações do vídeo."
            )

        arquivo_base = os.path.join(
            PASTA_VIDEOS,
            str(info["id"])
        )

        # Procura o arquivo final
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

        # Segunda tentativa procurando qualquer arquivo
        arquivos = glob.glob(
            os.path.join(
                PASTA_VIDEOS,
                f"{info['id']}.*"
            )
        )

        arquivos = [
            arquivo
            for arquivo in arquivos
            if os.path.isfile(arquivo)
        ]

        if arquivos:

            arquivo_saida = arquivos[0]

    if arquivo_saida is None:

        raise FileNotFoundError(
            "O vídeo não foi encontrado depois do download."
        )

    print(
        f"✅ Vídeo encontrado: {arquivo_saida}"
    )

    return arquivo_saida, info


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

    # Verifica o link
    if "medal.tv" not in link.lower():

        await interaction.response.send_message(
            "❌ Envie um link válido do Medal.",
            ephemeral=True
        )

        return

    # IMPORTANTE:
    # evita Unknown interaction
    await interaction.response.defer()

    arquivo = None
    info = None

    try:

        await interaction.edit_original_response(
            content="⏳ Baixando o clipe do Medal..."
        )

        # =================================================
        # 1080P
        # =================================================

        print("🎬 Tentando 1080p...")

        try:

            arquivo, info = await asyncio.to_thread(
                baixar_medal,
                link,
                1080
            )

        except Exception as erro:

            print(
                f"⚠️ Falha no 1080p: "
                f"{type(erro).__name__}: {erro}"
            )

            arquivo = None

        # Verifica tamanho
        if arquivo and os.path.exists(arquivo):

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 1080p: "
                f"{tamanho / 1024 / 1024:.2f} MB"
            )

            if tamanho > LIMITE_DISCORD:

                print(
                    "⚠️ 1080p ficou grande demais."
                )

                apagar_arquivo(arquivo)
                arquivo = None

        # =================================================
        # 720P
        # =================================================

        if arquivo is None:

            await interaction.edit_original_response(
                content=(
                    "⚠️ 1080p ficou indisponível ou grande. "
                    "Tentando 720p..."
                )
            )

            print("🎬 Tentando 720p...")

            try:

                arquivo, info = await asyncio.to_thread(
                    baixar_medal,
                    link,
                    720
                )

            except Exception as erro:

                print(
                    f"⚠️ Falha no 720p: "
                    f"{type(erro).__name__}: {erro}"
                )

                arquivo = None

        # Verifica tamanho
        if arquivo and os.path.exists(arquivo):

            tamanho = os.path.getsize(arquivo)

            print(
                f"📦 720p: "
                f"{tamanho / 1024 / 1024:.2f} MB"
            )

            if tamanho > LIMITE_DISCORD:

                print(
                    "⚠️ 720p ficou grande demais."
                )

                apagar_arquivo(arquivo)
                arquivo = None

        # =================================================
        # 480P
        # =================================================

        if arquivo is None:

            await interaction.edit_original_response(
                content=(
                    "⚠️ 720p também ficou indisponível ou grande. "
                    "Tentando 480p..."
                )
            )

            print("🎬 Tentando 480p...")

            try:

                arquivo, info = await asyncio.to_thread(
                    baixar_medal,
                    link,
                    480
                )

            except Exception as erro:

                print(
                    f"⚠️ Falha no 480p: "
                    f"{type(erro).__name__}: {erro}"
                )

                arquivo = None

        # =================================================
        # NENHUM ARQUIVO
        # =================================================

        if arquivo is None:

            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui baixar esse clipe "
                    "em 1080p, 720p ou 480p."
                )
            )

            return

        # =================================================
        # VERIFICA TAMANHO FINAL
        # =================================================

        tamanho = os.path.getsize(arquivo)

        print(
            f"📦 Tamanho final: "
            f"{tamanho / 1024 / 1024:.2f} MB"
        )

        if tamanho > LIMITE_DISCORD:

            apagar_arquivo(arquivo)
            arquivo = None

            await interaction.edit_original_response(
                content=(
                    "❌ O vídeo continua maior que 24 MB "
                    "mesmo em 480p."
                )
            )

            return

        # =================================================
        # ENVIO
        # =================================================

        await interaction.edit_original_response(
            content="📤 Enviando o vídeo para o Discord..."
        )

        print("📤 Enviando vídeo para o Discord...")

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

            apagar_arquivo(arquivo)
            arquivo = None

            if getattr(erro, "status", None) == 413:

                await interaction.edit_original_response(
                    content=(
                        "❌ O Discord recusou o vídeo "
                        "porque o arquivo ficou grande demais."
                    )
                )

                return

            raise

        # =================================================
        # FINALIZAÇÃO
        # =================================================

        apagar_arquivo(arquivo)
        arquivo = None

        await interaction.edit_original_response(
            content="✅ Clipe baixado com sucesso!"
        )

        print("✅ Medal concluído com sucesso.")

    except Exception as erro:

        print(
            f"❌ ERRO MEDAL: "
            f"{type(erro).__name__}: {erro}"
        )

        apagar_arquivo(arquivo)

        try:

            await interaction.edit_original_response(
                content=(
                    "❌ Não consegui baixar esse clipe do Medal.\n"
                    "Veja os detalhes no log do Railway."
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

        print("✅ Comandos sincronizados.")

    except Exception as erro:

        print(
            f"❌ Erro ao sincronizar comandos: "
            f"{type(erro).__name__}: {erro}"
        )


# =========================================================
# INICIAR BOT
# =========================================================

if not TOKEN:

    print(
        "❌ ERRO: DISCORD_TOKEN não foi encontrado."
    )

else:

    print("🚀 Iniciando BYD Extrator...")

    bot.run(TOKEN)
