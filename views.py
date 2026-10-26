import os, time, secrets
import discord
import db, crawler, character

ARTICLE_ID  = os.getenv("ARTICLE_ID")
CATEGORY_ID = os.getenv("CATEGORY_ID", "")
ROLE_ID     = int(os.getenv("VERIFIED_ROLE_ID"))
LOG_ID      = int(os.getenv("LOG_CHANNEL_ID"))
SERVER_ID   = os.getenv("SERVER_ID", "").strip()   # 비워두면 서버 체크 안 함
MIN_LEVEL   = int(os.getenv("MIN_LEVEL", 50))
MIN_POWER   = int(os.getenv("MIN_POWER", 700000))
AUTO_CLASS_ROLE = os.getenv("AUTO_CLASS_ROLE", "1") == "1"

# 디스코드에 이 이름들과 똑같은 이름의 역할을 만들어 두면 자동 부여된다.
# API 가 돌려주는 className 과 글자가 정확히 같아야 한다.
CLASS_NAMES = ("검성", "수호성", "살성", "궁성",
               "마도성", "정령성", "치유성", "호법성")

BOARD_URL = (f"https://aion2.plaync.com/ko-kr/board/server/view"
             f"?articleId={ARTICLE_ID}&categoryId={CATEGORY_ID}")

_cooldown: dict[int, float] = {}


def _cool_ok(uid: int, sec: int = 30) -> bool:
    now = time.time()
    if now - _cooldown.get(uid, 0) < sec:
        return False
    _cooldown[uid] = now
    return True


class VerifyPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _log(self, guild, msg):
        ch = guild.get_channel(LOG_ID)
        if ch:
            await ch.send(msg)

    @discord.ui.button(label="인증코드 발급", emoji="🔑",
                       style=discord.ButtonStyle.primary,
                       custom_id="aion2:issue")
    async def issue(self, itr: discord.Interaction, _):
        code = "CODE" + secrets.token_hex(5).upper()
        await db.issue_code(itr.user.id, code)
        await itr.response.send_message(
            f"**인증코드**\n```{code}```\n"
            f"[게시글로 이동]({BOARD_URL}) → 댓글에 위 코드를 작성한 뒤 "
            f"**[인증 확인]** 을 눌러주세요.\n"
            f"-# 유효시간 10분 · 이 메시지는 본인만 보입니다.",
            ephemeral=True)

    @discord.ui.button(label="인증 확인", emoji="✅",
                       style=discord.ButtonStyle.success,
                       custom_id="aion2:check")
    async def check(self, itr: discord.Interaction, _):
        await itr.response.defer(ephemeral=True)
        uid = itr.user.id

        # ① 쿨다운
        if not _cool_ok(uid):
            return await itr.followup.send("30초 후 다시 시도해주세요.", ephemeral=True)

        # ② 코드 존재 / 만료 확인
        row = await db.get_pending(uid)
        if not row:
            return await itr.followup.send("먼저 인증코드를 발급해주세요.", ephemeral=True)
        code, issued_at, expires_at = row
        if time.time() > expires_at:
            return await itr.followup.send("코드가 만료됐습니다. 재발급해주세요.",
                                           ephemeral=True)

        # ③ 댓글 검색
        try:
            hit = await crawler.find_code(ARTICLE_ID, code, issued_at)
        except Exception as e:
            await self._log(itr.guild, f"⚠️ API 오류: `{e}`")
            return await itr.followup.send("홈페이지 연결 실패. 잠시 후 재시도해주세요.",
                                           ephemeral=True)
        if not hit:
            return await itr.followup.send(
                "댓글을 찾지 못했습니다. 작성 후 1분쯤 기다렸다 다시 눌러주세요.",
                ephemeral=True)

        # ④ 중복 인증 차단
        owner = await db.find_owner(hit["origin_id"])
        if owner and owner != uid:
            await self._log(itr.guild,
                            f"⚠️ 중복 시도 {itr.user.mention} → `{hit['name']}` "
                            f"(소유자 <@{owner}>)")
            return await itr.followup.send("이미 다른 계정에 등록된 캐릭터입니다.",
                                           ephemeral=True)

        # ⑤ 서버 제한 (.env 의 SERVER_ID 가 비어있으면 건너뜀)
        if SERVER_ID and str(hit["server_id"]) != SERVER_ID:
            return await itr.followup.send(
                f"페르노스 서버 캐릭터만 인증 가능합니다.\n"
                f"-# 감지된 서버 ID: `{hit['server_id']}`",
                ephemeral=True)

        # ⑥ 레벨 · 전투력 확인
        try:
            info = await character.get_info(hit["char_id"], hit["server_id"])
        except Exception as e:
            await self._log(itr.guild, f"⚠️ 캐릭터 조회 오류: `{e}`")
            return await itr.followup.send(
                "캐릭터 정보 조회에 실패했습니다. 잠시 후 재시도해주세요.", ephemeral=True)

        if info is None:
            await self._log(itr.guild,
                            f"❓ 조회 실패 {itr.user.mention} `{hit['name']}`")
            return await itr.followup.send(
                "캐릭터 정보를 불러오지 못했습니다. 관리자에게 문의해주세요.",
                ephemeral=True)

        if info["level"] < MIN_LEVEL:
            return await itr.followup.send(
                f"{MIN_LEVEL}레벨부터 인증 가능합니다. (현재 Lv.{info['level']})",
                ephemeral=True)

        if info["power"] < MIN_POWER:
            return await itr.followup.send(
                f"전투력 {MIN_POWER:,} 이상부터 인증 가능합니다. "
                f"(현재 {info['power']:,})",
                ephemeral=True)

        # ⑦ 역할 부여 + 닉네임 변경
        try:
            to_add = [itr.guild.get_role(ROLE_ID)]

            if AUTO_CLASS_ROLE:
                # 전에 받은 다른 직업 역할은 회수 (캐릭터 변경 대비)
                old = [r for r in itr.user.roles
                       if r.name in CLASS_NAMES and r.name != info["class"]]
                if old:
                    await itr.user.remove_roles(*old)

                cls_role = discord.utils.get(itr.guild.roles, name=info["class"])
                if cls_role:
                    to_add.append(cls_role)
                else:
                    await self._log(
                        itr.guild,
                        f"⚠️ `{info['class']}` 역할이 서버에 없어 건너뛰었습니다.")

            await itr.user.add_roles(*[r for r in to_add if r])
            await itr.user.edit(nick=hit["name"][:32])
        except discord.Forbidden:
            await self._log(itr.guild, f"❌ 권한 부족 {itr.user.mention}")
            return await itr.followup.send("봇 권한 문제입니다. 관리자에게 문의해주세요.",
                                           ephemeral=True)

        # ⑧ 저장
        await db.save_verified(hit["origin_id"], uid, hit["name"], hit["server_id"])
        await self._log(itr.guild,
                        f"✅ {itr.user.mention} → `{hit['name']}` "
                        f"({info['class']} Lv.{info['level']} / "
                        f"전투력 {info['power']:,})")
        await itr.followup.send(
            f"인증 완료!\n"
            f"**{hit['name']}** · {info['class']} · Lv.{info['level']}\n"
            f"전투력 {info['power']:,}",
            ephemeral=True)