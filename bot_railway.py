import os
import asyncio
from typing import Optional

import discord
from discord.ext import commands

# ==== ここを書き換える（ローカル用） =====================
TOKEN = os.getenv("TOKEN")
TOILET_CHANNEL_ID = int(os.getenv("TOILET_CHANNEL_ID"))
FOODWATER_CHANNEL_ID = int(os.getenv("FOODWATER_CHANNEL_ID"))
WATER_BOWL_ML = int(os.getenv("WATER_BOWL_ML", "300"))
# ======================================================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def send_log(
    *,
    client: discord.Client,
    channel_id: int,
    user: discord.abc.User,
    emoji: str,
    title: str,
    extra: str = "",
    attachment: Optional[discord.File] = None,
):
    """共通のログ送信関数"""
    channel = client.get_channel(channel_id)
    if channel is None:
        return

    timestamp = discord.utils.format_dt(discord.utils.utcnow(), style="F")
    content = f"{emoji} **{title}** {extra}｜{user.mention}｜{timestamp}"

    if attachment:
        await channel.send(content, file=attachment)
    else:
        await channel.send(content)


# ---------- Food 用の Select ----------

class FoodSelect(discord.ui.Select):
    def __init__(self):
        options = []

        # 10〜100g Dry
        for g in range(10, 110, 10):
            options.append(
                discord.SelectOption(
                    label=f"{g}g Dry",
                    value=f"{g}:dry",
                )
            )

        # Wet food / Treat は量指定なし
        options.append(
            discord.SelectOption(
                label="Wet food (1 pack)",
                value="wetpack",
            )
        )
        options.append(
            discord.SelectOption(
                label="Treat (1 pack)",
                value="treatpack",
            )
        )

        super().__init__(
            placeholder="ご飯の量・種類を選んでください",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        # Wet / Treat のときは量なし
        if value == "wetpack":
            extra = "(Wet food, 1 pack)"
            log_msg = "🥣 ウェットフード（1パック）を記録しました。"
        elif value == "treatpack":
            extra = "(Treat, 1 pack)"
            log_msg = "🥣 おやつ（1パック）を記録しました。"
        else:
            grams_str, kind = value.split(":")  # "40:dry" → ("40", "dry")
            extra = f"({grams_str}g Dry)"
            log_msg = f"🥣 ドライフード {grams_str}g を記録しました。"

        await send_log(
            client=interaction.client,
            channel_id=FOODWATER_CHANNEL_ID,
            user=interaction.user,
            emoji="🥣",
            title="Food",
            extra=extra,
        )
        await interaction.response.edit_message(
            content=log_msg, view=None
        )


class FoodView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(FoodSelect())


# ---------- Water 用の Select ----------

class WaterSelect(discord.ui.Select):
    def __init__(self):
        # 110〜250ml を10ml刻み
        options = []
        for remain in range(110, 251, 10):  # 110,120,...,250
            options.append(
                discord.SelectOption(
                    label=f"残り {remain}ml",
                    value=str(remain),
                )
            )
        super().__init__(
            placeholder="補充前にどれくらい残っていましたか？（110〜250ml）",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        remain = int(self.values[0])
        drank = max(WATER_BOWL_ML - remain, 0)

        extra = f"(bowl {WATER_BOWL_ML}ml: drank {drank}ml, left {remain}ml)"

        await send_log(
            client=interaction.client,
            channel_id=FOODWATER_CHANNEL_ID,
            user=interaction.user,
            emoji="🚰",
            title="Water refill",
            extra=extra,
        )
        await interaction.response.edit_message(
            content=f"🚰 水を補充しました：{drank}ml 飲んで、残り {remain}ml でした。",
            view=None,
        )


class WaterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(WaterSelect())


# ---------- メインのボタン View ----------

class CareView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # 永続ボタン

    # 💩 Poop：押したら即ログだけ
    @discord.ui.button(
        label="💩 Poop",
        style=discord.ButtonStyle.primary,
        custom_id="yanagi_poop",
    )
    async def poop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_log(
            client=interaction.client,
            channel_id=TOILET_CHANNEL_ID,
            user=interaction.user,
            emoji="💩",
            title="Poop",
        )
        await interaction.response.send_message(
            "💩 うんちを記録しました。", ephemeral=True
        )

    # 💧 Pee
    @discord.ui.button(
        label="💧 Pee",
        style=discord.ButtonStyle.secondary,
        custom_id="yanagi_pee",
    )
    async def pee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_log(
            client=interaction.client,
            channel_id=TOILET_CHANNEL_ID,
            user=interaction.user,
            emoji="💧",
            title="Pee",
        )
        await interaction.response.send_message(
            "💧 おしっこを記録しました。", ephemeral=True
        )

    # 🥣 Food
    @discord.ui.button(
        label="🥣 Food",
        style=discord.ButtonStyle.success,
        custom_id="yanagi_food",
    )
    async def food(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = FoodView()
        await interaction.response.send_message(
            "🥣 ご飯ログ：量と種類を選んでください。", view=view, ephemeral=True
        )

    # 🚰 Water
    @discord.ui.button(
        label="🚰 Water",
        style=discord.ButtonStyle.danger,
        custom_id="yanagi_water",
    )
    async def water(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = WaterView()
        await interaction.response.send_message(
            f"🚰 水ログ：補充前の残量（{WATER_BOWL_ML}mlボウル・110〜250ml）を選んでください。",
            view=view,
            ephemeral=True,
        )


# ---------- スラッシュコマンド & 起動 ----------

@bot.event
async def on_ready():
    print("Bot logged in!")
    bot.add_view(CareView())  # 永続ビュー登録
    await bot.tree.sync()


@bot.tree.command(name="carepanel", description="Show Yanagi care buttons")
async def carepanel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Yanagi care log buttons:", view=CareView()
    )


bot.run(TOKEN)
