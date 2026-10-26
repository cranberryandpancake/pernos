import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
import db
from views import VerifyPanel

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    await db.init()
    bot.add_view(VerifyPanel())
    await bot.tree.sync()


@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user}")


@bot.tree.command(name="패널설치", description="인증 패널을 설치합니다")
@discord.app_commands.checks.has_permissions(administrator=True)
async def setup_panel(itr: discord.Interaction):
    embed = discord.Embed(
        title="아이온2 캐릭터 인증",
        description=(
            "**1.** `인증코드 발급` 을 눌러 코드를 받습니다\n"
            "**2.** 공식 홈페이지에서 인증받을 캐릭터로 **캐릭터 변경** 후\n"
            "　　안내 게시글 댓글에 코드를 작성합니다\n"
            "**3.** `인증 확인` 을 누르면 완료됩니다"
        ),
        color=0x3BA7FF)
    await itr.channel.send(embed=embed, view=VerifyPanel())
    await itr.response.send_message("설치했습니다.", ephemeral=True)


bot.run(TOKEN)