import discord
import os
import aiohttp
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="+", intents=intents)

OWNER_ID = 1471476071290634305

config = {
    "tokens": [],
    "message": None,
    "embed_title": None,
    "embed_description": None,
    "embed_color": 0x5865f2,
    "user_ids": [],
    "ignored_ids": [],
    "status_filter": ["online", "idle", "dnd", "offline"],
    "panel_message_id": None,
    "panel_channel_id": None,
}

ACTIVITY_TYPES = {
    "joue": discord.ActivityType.playing,
    "regarde": discord.ActivityType.watching,
    "ecoute": discord.ActivityType.listening,
    "stream": discord.ActivityType.streaming,
}

STATUS_LABELS = {
    "online": "🟢 En ligne",
    "idle": "🌙 Inactif",
    "dnd": "🔴 DND",
    "offline": "⚫ Hors ligne",
}


def build_panel_components():
    token_text = f"**{len(config['tokens'])}** token(s) ajouté(s)" if config["tokens"] else "Aucun token ajouté"
    raw_msg = (config["message"][:80] + "...") if config["message"] and len(config["message"]) > 80 else (config["message"] or "Aucun message défini")
    raw_embed = config["embed_title"] or "Aucun embed défini"
    statuses = " • ".join([STATUS_LABELS[s] for s in config["status_filter"]]) if config["status_filter"] else "Aucun"

    return [
        {
            "type": 17,
            "accent_color": 0x5865f2,
            "components": [
                {
                    "type": 10,
                    "content": "💎 〃 **Configuration du UhqZkDmall**"
                },
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": f"🤖 **Tokens** — {token_text}"
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": "🤖 Ajouter Token", "style": 2, "custom_id": "add_token_btn"},
                        {"type": 2, "label": "🗑️ Retirer Token", "style": 4, "custom_id": "remove_token_btn"},
                    ]
                },
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": f"📩 **Message**\n```{raw_msg}```\n✏️ **Embed**\n```{raw_embed}```"
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": "📩 Message", "style": 1, "custom_id": "set_message_btn"},
                        {"type": 2, "label": "✏️ Embed", "style": 1, "custom_id": "set_embed_btn"},
                    ]
                },
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": f"👥 **User IDs — Total : {len(config['user_ids'])} ID**　　👥 **User IDs à Ignorer — Total : {len(config['ignored_ids'])} ID**"
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": "⚙️ Options DM", "style": 2, "custom_id": "dm_options_btn"},
                    ]
                },
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": f"⚙️ **Statuts ciblés** — {statuses}"
                },
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": "⭐ Statut", "style": 2, "custom_id": "set_status_btn"},
                        {"type": 2, "label": "📨 DM All", "style": 4, "custom_id": "dmall_execute_btn"},
                    ]
                },
                {"type": 14, "divider": True, "spacing": 1},
                {
                    "type": 10,
                    "content": "-# UhqZkDmall • Réservé au propriétaire"
                },
            ]
        }
    ]


async def send_panel_v2(channel_id: int) -> dict:
    bot_token = os.environ.get("TOKEN", "")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            json={"flags": 32768, "components": build_panel_components()},
            headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
        ) as r:
            return await r.json()


async def refresh_panel():
    if not config["panel_message_id"] or not config["panel_channel_id"]:
        return
    bot_token = os.environ.get("TOKEN", "")
    async with aiohttp.ClientSession() as session:
        try:
            await session.patch(
                f"https://discord.com/api/v10/channels/{config['panel_channel_id']}/messages/{config['panel_message_id']}",
                json={"flags": 32768, "components": build_panel_components()},
                headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
            )
        except Exception:
            pass


async def send_dm_via_token(token: str, user_id: int, embed_dict: dict) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/v10/users/@me/channels",
            json={"recipient_id": str(user_id)},
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        ) as r:
            if r.status != 200:
                return False
            channel_id = (await r.json())["id"]
        async with session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            json={"embeds": [embed_dict]},
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        ) as r:
            return r.status in (200, 201)


class TokenModal(discord.ui.Modal, title="🤖 Ajouter un Token"):
    token_input = discord.ui.TextInput(
        label="Token du bot",
        placeholder="Colle ton token bot ici...",
        style=discord.TextStyle.short,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        config["tokens"].append(self.token_input.value.strip())
        await interaction.response.send_message(
            f"✅ Token ajouté ! Total : **{len(config['tokens'])}** token(s)", ephemeral=True
        )
        await refresh_panel()


class RemoveTokenModal(discord.ui.Modal, title="🗑️ Retirer un Token"):
    index_input = discord.ui.TextInput(
        label="Numéro du token à retirer",
        placeholder="ex: 1 pour le premier token",
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            idx = int(self.index_input.value.strip()) - 1
            if 0 <= idx < len(config["tokens"]):
                config["tokens"].pop(idx)
                await interaction.response.send_message(
                    f"✅ Token retiré. Total : **{len(config['tokens'])}** token(s)", ephemeral=True
                )
                await refresh_panel()
            else:
                await interaction.response.send_message("❌ Numéro invalide.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Entre un numéro valide.", ephemeral=True)


class RemoveTokenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🗑️ Retirer", style=discord.ButtonStyle.danger)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(RemoveTokenModal())


class MessageModal(discord.ui.Modal, title="📩 Définir le Message"):
    message_input = discord.ui.TextInput(
        label="Message",
        placeholder="Écris ton message ici...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        config["message"] = self.message_input.value.strip() or None
        await interaction.response.send_message("✅ Message défini !", ephemeral=True)
        await refresh_panel()


class EmbedModal(discord.ui.Modal, title="✏️ Définir l'Embed"):
    title_input = discord.ui.TextInput(
        label="Titre",
        placeholder="ex: 📩 Message important",
        max_length=256,
        required=False
    )
    desc_input = discord.ui.TextInput(
        label="Description",
        placeholder="Contenu de l'embed...",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=False
    )
    color_input = discord.ui.TextInput(
        label="Couleur hex (ex: ff0000)",
        placeholder="5865f2",
        max_length=6,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        config["embed_title"] = self.title_input.value.strip() or None
        config["embed_description"] = self.desc_input.value.strip() or None
        if self.color_input.value.strip():
            try:
                config["embed_color"] = int(self.color_input.value.strip("#"), 16)
            except ValueError:
                pass
        await interaction.response.send_message("✅ Embed défini !", ephemeral=True)
        await refresh_panel()


class DmOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        options = [
            discord.SelectOption(label="🟢 En ligne", value="online", default="online" in config["status_filter"]),
            discord.SelectOption(label="🌙 Inactif", value="idle", default="idle" in config["status_filter"]),
            discord.SelectOption(label="🔴 DND", value="dnd", default="dnd" in config["status_filter"]),
            discord.SelectOption(label="⚫ Hors ligne", value="offline", default="offline" in config["status_filter"]),
        ]
        select = discord.ui.Select(
            placeholder="Sélectionne les statuts ciblés...",
            min_values=1,
            max_values=4,
            options=options,
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        select = self.children[0]
        config["status_filter"] = list(select.values)
        selected = " • ".join([STATUS_LABELS[s] for s in config["status_filter"]])
        await interaction.response.send_message(f"✅ Statuts mis à jour : {selected}", ephemeral=True)
        await refresh_panel()


class StatusModal(discord.ui.Modal, title="🎮 Statut du Bot"):
    type_input = discord.ui.TextInput(label="Type", placeholder="joue / regarde / ecoute / stream", max_length=10)
    text_input = discord.ui.TextInput(label="Texte", placeholder="ex: avec vos DMs 💀", max_length=128)

    async def on_submit(self, interaction: discord.Interaction):
        type_str = self.type_input.value.strip().lower()
        text = self.text_input.value.strip()
        activity_type = ACTIVITY_TYPES.get(type_str)
        if not activity_type:
            return await interaction.response.send_message(
                "❌ Utilise : `joue`, `regarde`, `ecoute` ou `stream`", ephemeral=True
            )
        await bot.change_presence(activity=discord.Activity(type=activity_type, name=text))
        await interaction.response.send_message(f"✅ Statut : **{type_str} {text}**", ephemeral=True)


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID

    @discord.ui.button(label="🤖 Ajouter Token", style=discord.ButtonStyle.secondary, custom_id="add_token_btn", row=0)
    async def add_token_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(TokenModal())

    @discord.ui.button(label="🗑️ Retirer Token", style=discord.ButtonStyle.danger, custom_id="remove_token_btn", row=0)
    async def remove_token_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        if not config["tokens"]:
            return await interaction.response.send_message("❌ Aucun token à retirer.", ephemeral=True)
        list_text = "\n".join([f"**{i+1}.** `{t[:25]}...`" for i, t in enumerate(config["tokens"])])
        await interaction.response.send_message(
            f"**Tokens actuels :**\n{list_text}", ephemeral=True, view=RemoveTokenView()
        )

    @discord.ui.button(label="📩 Message", style=discord.ButtonStyle.primary, custom_id="set_message_btn", row=1)
    async def set_message_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        modal = MessageModal()
        if config["message"]:
            modal.message_input.default = config["message"]
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✏️ Embed", style=discord.ButtonStyle.primary, custom_id="set_embed_btn", row=1)
    async def set_embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        modal = EmbedModal()
        if config["embed_title"]:
            modal.title_input.default = config["embed_title"]
        if config["embed_description"]:
            modal.desc_input.default = config["embed_description"]
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⚙️ Options DM", style=discord.ButtonStyle.secondary, custom_id="dm_options_btn", row=2)
    async def dm_options_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_message(
            "**⚙️ Options DM** — Sélectionne les statuts à cibler :",
            view=DmOptionsView(),
            ephemeral=True
        )

    @discord.ui.button(label="⭐ Statut", style=discord.ButtonStyle.secondary, custom_id="set_status_btn", row=3)
    async def set_status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(StatusModal())

    @discord.ui.button(label="📨 DM All", style=discord.ButtonStyle.danger, custom_id="dmall_execute_btn", row=3)
    async def dmall_execute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        if not config["message"] and not config["embed_title"]:
            return await interaction.response.send_message(
                "❌ Définis d'abord un **Message** ou un **Embed**.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild or (bot.guilds[0] if bot.guilds else None)
        if not guild:
            return await interaction.followup.send("❌ Aucun serveur trouvé.", ephemeral=True)
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "offline": discord.Status.offline,
        }
        target_statuses = [status_map[s] for s in config["status_filter"] if s in status_map]
        members = []
        for m in guild.members:
            if m.bot:
                continue
            if config["user_ids"] and m.id not in config["user_ids"]:
                continue
            if m.id in config["ignored_ids"]:
                continue
            if target_statuses and m.status not in target_statuses:
                continue
            members.append(m)
        total = len(members)
        main_token = os.environ.get("TOKEN", "")
        all_tokens = [t for t in [main_token] + config["tokens"] if t]
        progress_msg = await interaction.followup.send(
            embed=discord.Embed(
                title="📨 Envoi en cours...",
                description=f"Envoi à **{total}** membre(s) avec **{len(all_tokens)}** token(s)...",
                color=0xfee75c
            ),
            ephemeral=True
        )
        sent = 0
        failed = 0
        dm_embed_dict = {"color": config["embed_color"], "footer": {"text": "UhqZkDmall"}}
        if config["embed_title"]:
            dm_embed_dict["title"] = config["embed_title"]
        if config["embed_description"]:
            dm_embed_dict["description"] = config["embed_description"]
        elif config["message"]:
            dm_embed_dict["description"] = config["message"]
        if guild.icon:
            dm_embed_dict["thumbnail"] = {"url": str(guild.icon.url)}

        def build_progress_embed(current_member=None, done=False):
            processed = sent + failed
            filled = int((processed / total) * 10) if total > 0 else 0
            bar = "🟩" * filled + "⬛" * (10 - filled)
            e = discord.Embed(
                title="✅ Dmall terminé" if done else "📨 Envoi en cours...",
                color=0x57f287 if done else 0xfee75c
            )
            e.add_field(name="✅ Envoyés", value=str(sent), inline=True)
            e.add_field(name="❌ Échoués", value=str(failed), inline=True)
            e.add_field(name="📊 Progression", value=f"{bar} `{processed}/{total}`", inline=False)
            if current_member and not done:
                e.add_field(name="📤 En cours", value=str(current_member), inline=False)
            preview = config["message"] or config["embed_title"] or ""
            e.add_field(name="📝 Message", value=preview[:200], inline=False)
            e.set_footer(text="UhqZkDmall")
            return e

        for i, member in enumerate(members):
            token = all_tokens[i % len(all_tokens)]
            if token == main_token:
                try:
                    dm = discord.Embed(color=config["embed_color"])
                    if config["embed_title"]:
                        dm.title = config["embed_title"]
                    dm.description = config["embed_description"] or config["message"]
                    if guild.icon:
                        dm.set_thumbnail(url=guild.icon.url)
                    dm.set_footer(text="UhqZkDmall")
                    await member.send(embed=dm)
                    sent += 1
                except (discord.Forbidden, discord.HTTPException):
                    failed += 1
            else:
                if await send_dm_via_token(token, member.id, dm_embed_dict):
                    sent += 1
                else:
                    failed += 1
            if i % 3 == 0:
                await progress_msg.edit(embed=build_progress_embed(current_member=member))
        await progress_msg.edit(embed=build_progress_embed(done=True))


@bot.event
async def on_ready():
    bot.add_view(PanelView())
    print(f"[BOT] Connecté : {bot.user}")


@bot.command(name="dmall")
async def dmall_panel_cmd(ctx):
    if ctx.author.id != OWNER_ID:
        return
    try:
        await ctx.message.delete()
    except Exception:
        pass
    msg_data = await send_panel_v2(ctx.channel.id)
    config["panel_message_id"] = int(msg_data["id"])
    config["panel_channel_id"] = ctx.channel.id


bot.run(os.environ.get("TOKEN", "TON_TOKEN_ICI"))
