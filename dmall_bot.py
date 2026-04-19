import asyncio
import json
import os
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="+", intents=intents)

OWNER_ID = 1471476071290634305
DISCORD_API = "https://discord.com/api/v10"
BLUE = 1
GRAY = 2
RED = 4
COMPONENTS_V2 = 32768
EPHEMERAL = 64
VIEWS_READY = False

config = {
    "tokens": [],
    "token_infos": [],
    "message": None,
    "embed": None,
    "button_label": None,
    "button_url": None,
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
    "idle": "🟡 Inactif",
    "dnd": "🔴 DND",
    "offline": "⚫ Hors ligne",
}


def text_component(content: str) -> dict:
    return {"type": 10, "content": content}


def separator() -> dict:
    return {"type": 14, "divider": True, "spacing": 1}


def button(label: str, style: int, custom_id: str) -> dict:
    return {"type": 2, "label": label, "style": style, "custom_id": custom_id}


def link_button(label: str, url: str) -> dict:
    return {"type": 2, "label": label, "style": 5, "url": url}


def action_row(*items: dict) -> dict:
    return {"type": 1, "components": list(items)}


def short_text(value: str | None, empty: str, limit: int = 90) -> str:
    if not value:
        return empty
    return value[:limit] + "..." if len(value) > limit else value


def build_token_text() -> str:
    if not config["tokens"]:
        return "Aucun token ajouté"

    lines = []
    for index, info in enumerate(config["token_infos"], start=1):
        name = info.get("name", f"Bot {index}")
        bot_id = info.get("id")
        if bot_id:
            invite = f"https://discord.com/oauth2/authorize?client_id={bot_id}&scope=bot&permissions=8"
            lines.append(f"`{index}.` **{name}** • [Inviter]({invite})")
        else:
            lines.append(f"`{index}.` **{name}**")

    for index in range(len(config["token_infos"]) + 1, len(config["tokens"]) + 1):
        lines.append(f"`{index}.` **Bot inconnu**")

    return "\n".join(lines)


def build_panel_components() -> list[dict]:
    token_text = build_token_text()
    message_text = short_text(config["message"], "Aucun message texte défini")
    embed_text = "Embed configuré" if config["embed"] else "Aucun embed défini"

    return [
        {
            "type": 17,
            "accent_color": 0x5865F2,
            "components": [
                text_component("## `💎` 〃 Configuration du MultiDmall\n*__Utilisez les boutons ci-dessous pour configurer votre Dmall.__**"),
                separator(),
                text_component(f"🤖 **Tokens** — {token_text}"),
                action_row(button("🤖 Ajouter Token", BLUE, "add_token_btn")),
                separator(),
                text_component(f"📝 **Message à envoyer**\n```{message_text}```\n✏️ **Embed**\n```{embed_text}```"),
                action_row(button("📝 Définir le message", BLUE, "open_message_config_btn")),
                separator(),
                text_component(f"👥 **User IDs à ignorer — Total : {len(config['ignored_ids'])} ID**"),
                action_row(button("⚙️ Options DM", GRAY, "dm_options_btn")),
                separator(),
                action_row(
                    button("⭐ Statut", GRAY, "set_status_btn"),
                    button("📨 DM All", RED, "dmall_execute_btn"),
                ),
                separator(),
                text_component("-# MultiDmall • Réservé au propriétaire"),
            ],
        }
    ]


def build_message_config_components() -> list[dict]:
    return [
        {
            "type": 17,
            "accent_color": 0x5865F2,
            "components": [
                text_component("## :pencil: 〃 Définir le Message à Envoyer\nChoisissez une méthode pour configurer le message qui sera envoyé aux membres :"),
                separator(),
                text_component(":one: **Message texte simple**\nRédigez un message classique."),
                action_row(button("Saisir un message", BLUE, "simple_message_btn")),
                separator(),
                text_component(":two: **Embed personnalisé**\nCréez un embed avec titre, description, bouton, etc."),
                action_row(
                    button("Embed JSON", BLUE, "embed_json_btn"),
                    button("Embed Builder", BLUE, "embed_builder_btn"),
                ),
                separator(),
                text_component(":bulb: **Astuce : Utilisez ces variables dans vos messages**\n```{user}``` → mention du membre\n```{user.id}``` → id du membre\n```{timestamp}``` → date/heure exact"),
                separator(),
                action_row(
                    button("Aperçu", GRAY, "preview_message_btn"),
                    button("Reset", RED, "reset_message_btn"),
                ),
            ],
        }
    ]


def bot_headers(token: str | None = None) -> dict:
    return {"Authorization": f"Bot {token or os.environ.get('TOKEN', '')}", "Content-Type": "application/json"}


async def send_panel_v2(channel_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            json={"flags": COMPONENTS_V2, "components": build_panel_components()},
            headers=bot_headers(),
        ) as response:
            data = await response.json()
            if response.status >= 400:
                raise RuntimeError(f"Erreur panneau Discord {response.status}: {data}")
            return data


async def refresh_panel() -> None:
    if not config["panel_message_id"] or not config["panel_channel_id"]:
        return

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{DISCORD_API}/channels/{config['panel_channel_id']}/messages/{config['panel_message_id']}",
            json={"flags": COMPONENTS_V2, "components": build_panel_components()},
            headers=bot_headers(),
        ):
            pass


async def get_token_bot_info(token: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API}/users/@me", headers=bot_headers(token)) as response:
            if response.status != 200:
                return None
            data = await response.json()
            bot_id = data.get("id")
            username = data.get("global_name") or data.get("username") or "Bot inconnu"
            discriminator = data.get("discriminator")
            if discriminator and discriminator != "0":
                username = f"{username}#{discriminator}"
            return {"id": bot_id, "name": username}


async def send_ephemeral_components(interaction: discord.Interaction, components: list[dict]) -> None:
    payload = {"type": 4, "data": {"flags": EPHEMERAL | COMPONENTS_V2, "components": components}}
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{DISCORD_API}/interactions/{interaction.id}/{interaction.token}/callback", json=payload) as response:
            if response.status >= 400:
                error_text = await response.text()
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Impossible d'afficher le panneau : {error_text}", ephemeral=True)


def apply_variables(value: str | None, member: discord.Member) -> str | None:
    if value is None:
        return None
    return (
        value.replace("{user}", member.mention)
        .replace("{user.id}", str(member.id))
        .replace("{timestamp}", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    )


def build_embed_for_member(member: discord.Member) -> dict | None:
    if not config["embed"]:
        return None

    embed_data = json.loads(json.dumps(config["embed"]))
    for key in ("title", "description", "url"):
        if key in embed_data and isinstance(embed_data[key], str):
            embed_data[key] = apply_variables(embed_data[key], member)

    if "fields" in embed_data and isinstance(embed_data["fields"], list):
        for field in embed_data["fields"]:
            if isinstance(field, dict):
                for key in ("name", "value"):
                    if key in field and isinstance(field[key], str):
                        field[key] = apply_variables(field[key], member)

    return embed_data


def build_dm_payload(member: discord.Member) -> dict:
    payload = {}
    content = apply_variables(config["message"], member)
    embed_data = build_embed_for_member(member)

    if content:
        payload["content"] = content
    if embed_data:
        payload["embeds"] = [embed_data]
    if config["button_label"] and config["button_url"]:
        payload["components"] = [action_row(link_button(config["button_label"], config["button_url"]))]

    return payload


async def send_dm_via_token(token: str, user_id: int, payload: dict) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DISCORD_API}/users/@me/channels",
            json={"recipient_id": str(user_id)},
            headers=bot_headers(token),
        ) as response:
            if response.status != 200:
                return False
            channel_id = (await response.json()).get("id")
            if not channel_id:
                return False

        async with session.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            json=payload,
            headers=bot_headers(token),
        ) as response:
            return response.status in (200, 201)


def is_member_targeted(member: discord.Member) -> bool:
    if member.bot or member.id in config["ignored_ids"]:
        return False
    status = str(member.status)
    return status in config["status_filter"]


class TokenModal(discord.ui.Modal, title="🤖 Ajouter un Token"):
    token_input = discord.ui.TextInput(label="Token du bot", placeholder="Colle ton token bot ici...", style=discord.TextStyle.short, max_length=120)

    async def on_submit(self, interaction: discord.Interaction):
        token = self.token_input.value.strip()
        if not token:
            return await interaction.response.send_message("❌ Token vide.", ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)

        bot_info = await get_token_bot_info(token)
        if not bot_info:
            return await interaction.followup.send("❌ Token invalide ou impossible de récupérer le bot.", ephemeral=True)

        config["tokens"].append(token)
        config["token_infos"].append(bot_info)

        invite = f"https://discord.com/oauth2/authorize?client_id={bot_info['id']}&scope=bot&permissions=8"
        await interaction.followup.send(f"✅ Token ajouté : **{bot_info['name']}**\n[Inviter le bot]({invite})", ephemeral=True)
        await refresh_panel()


class SimpleMessageModal(discord.ui.Modal, title="📝 Message texte simple"):
    message_input = discord.ui.TextInput(label="Message", placeholder="Écris ton message ici...", style=discord.TextStyle.paragraph, max_length=2000, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        config["message"] = self.message_input.value.strip() or None
        await interaction.response.send_message("✅ Message texte défini !", ephemeral=True)
        await refresh_panel()


class EmbedJsonModal(discord.ui.Modal, title="Embed JSON"):
    json_input = discord.ui.TextInput(label="JSON de l'embed", placeholder='{"title":"Titre","description":"Description","color":5793266}', style=discord.TextStyle.paragraph, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            embed_data = json.loads(self.json_input.value.strip())
            if not isinstance(embed_data, dict):
                raise ValueError
            discord.Embed.from_dict(embed_data)
        except Exception:
            return await interaction.response.send_message("❌ JSON embed invalide.", ephemeral=True)

        config["embed"] = embed_data
        await interaction.response.send_message("✅ Embed JSON défini !", ephemeral=True)
        await refresh_panel()


class EmbedBuilderModal(discord.ui.Modal, title="Embed Builder"):
    title_input = discord.ui.TextInput(label="Titre", placeholder="ex: 📩 Message important", max_length=256, required=False)
    desc_input = discord.ui.TextInput(label="Description", placeholder="Contenu de l'embed...", style=discord.TextStyle.paragraph, max_length=4000, required=False)
    color_input = discord.ui.TextInput(label="Couleur hex", placeholder="5865f2", max_length=7, required=False)
    button_label_input = discord.ui.TextInput(label="Texte du bouton", placeholder="ex: Ouvrir", max_length=80, required=False)
    button_url_input = discord.ui.TextInput(label="URL du bouton", placeholder="https://exemple.com", max_length=200, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        embed_data = {}
        title = self.title_input.value.strip()
        description = self.desc_input.value.strip()
        color = self.color_input.value.strip().replace("#", "")
        button_label_value = self.button_label_input.value.strip()
        button_url_value = self.button_url_input.value.strip()

        if title:
            embed_data["title"] = title
        if description:
            embed_data["description"] = description
        if color:
            try:
                embed_data["color"] = int(color, 16)
            except ValueError:
                return await interaction.response.send_message("❌ Couleur hex invalide.", ephemeral=True)

        config["embed"] = embed_data or None
        config["button_label"] = button_label_value or None
        config["button_url"] = button_url_value or None
        await interaction.response.send_message("✅ Embed builder enregistré !", ephemeral=True)
        await refresh_panel()


class DmOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        options = [
            discord.SelectOption(label="🟢 En ligne", value="online", default="online" in config["status_filter"]),
            discord.SelectOption(label="🟡 Inactif", value="idle", default="idle" in config["status_filter"]),
            discord.SelectOption(label="🔴 DND", value="dnd", default="dnd" in config["status_filter"]),
            discord.SelectOption(label="⚫ Hors ligne", value="offline", default="offline" in config["status_filter"]),
        ]
        select = discord.ui.Select(placeholder="Sélectionne les statuts ciblés...", min_values=1, max_values=4, options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)

        select = self.children[0]
        config["status_filter"] = list(select.values)

        await interaction.response.defer(ephemeral=True)

        if interaction.guild:
            try:
                await interaction.guild.chunk(cache=True)
            except Exception:
                pass
            total = len([member for member in interaction.guild.members if is_member_targeted(member)])
        else:
            total = 0

        await interaction.followup.send(f"Membre recuperer : `{total}`", ephemeral=True)
        await refresh_panel()


class StatusModal(discord.ui.Modal, title="🎮 Statut du Bot"):
    type_input = discord.ui.TextInput(label="Type", placeholder="joue / regarde / ecoute / stream", max_length=10)
    text_input = discord.ui.TextInput(label="Texte", placeholder="ex: avec vos DMs", max_length=128)

    async def on_submit(self, interaction: discord.Interaction):
        type_str = self.type_input.value.strip().lower()
        text = self.text_input.value.strip()
        activity_type = ACTIVITY_TYPES.get(type_str)
        if not activity_type:
            return await interaction.response.send_message("❌ Utilise : `joue`, `regarde`, `ecoute` ou `stream`", ephemeral=True)
        await bot.change_presence(activity=discord.Activity(type=activity_type, name=text))
        await interaction.response.send_message(f"✅ Statut : **{type_str} {text}**", ephemeral=True)


class MessageConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID

    @discord.ui.button(label="Saisir un message", style=discord.ButtonStyle.primary, custom_id="simple_message_btn")
    async def simple_message_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(SimpleMessageModal())

    @discord.ui.button(label="Embed JSON", style=discord.ButtonStyle.primary, custom_id="embed_json_btn")
    async def embed_json_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(EmbedJsonModal())

    @discord.ui.button(label="Embed Builder", style=discord.ButtonStyle.primary, custom_id="embed_builder_btn")
    async def embed_builder_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(EmbedBuilderModal())

    @discord.ui.button(label="Aperçu", style=discord.ButtonStyle.secondary, custom_id="preview_message_btn")
    async def preview_message_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)

        payload = build_dm_payload(interaction.user)
        if not payload:
            return await interaction.response.send_message("❌ Aucun message ou embed configuré.", ephemeral=True)

        preview_content = payload.get("content") or "👀 Aperçu du message configuré :"
        if payload.get("content"):
            preview_content = f"👀 Aperçu du message configuré :\n\n{payload['content']}"

        embed = discord.Embed.from_dict(payload["embeds"][0]) if payload.get("embeds") else None
        view = None

        if config["button_label"] and config["button_url"]:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=config["button_label"], url=config["button_url"]))

        await interaction.response.send_message(preview_content, embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, custom_id="reset_message_btn")
    async def reset_message_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)

        config["message"] = None
        config["embed"] = None
        config["button_label"] = None
        config["button_url"] = None

        await interaction.response.send_message("✅ Message et embed réinitialisés.", ephemeral=True)
        await refresh_panel()


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID

    @discord.ui.button(label="🤖 Ajouter Token", style=discord.ButtonStyle.primary, custom_id="add_token_btn")
    async def add_token_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(TokenModal())

    @discord.ui.button(label="📝 Définir le message", style=discord.ButtonStyle.primary, custom_id="open_message_config_btn")
    async def open_message_config_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await send_ephemeral_components(interaction, build_message_config_components())

    @discord.ui.button(label="⚙️ Options DM", style=discord.ButtonStyle.secondary, custom_id="dm_options_btn")
    async def dm_options_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_message("Sélectionne les statuts ciblés :", view=DmOptionsView(), ephemeral=True)

    @discord.ui.button(label="⭐ Statut", style=discord.ButtonStyle.secondary, custom_id="set_status_btn")
    async def set_status_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(StatusModal())

    @discord.ui.button(label="📨 DM All", style=discord.ButtonStyle.danger, custom_id="dmall_execute_btn")
    async def dmall_execute_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.is_owner(interaction):
            return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)

        if not config["tokens"]:
            return await interaction.response.send_message("❌ Aucun token ajouté. Ajoute au moins un token avant de lancer DM All.", ephemeral=True)

        if not config["message"] and not config["embed"]:
            return await interaction.response.send_message("❌ Aucun message configuré. Clique sur 📝 Définir le message avant de lancer DM All.", ephemeral=True)

        if not interaction.guild:
            return await interaction.response.send_message("❌ Cette action doit être lancée dans un serveur.", ephemeral=True)

        await interaction.response.send_message("⏳ Préparation de l'envoi...", ephemeral=True)

        try:
            await interaction.guild.chunk(cache=True)
        except Exception:
            pass

        members = [member for member in interaction.guild.members if is_member_targeted(member)]
        total = len(members)

        if total == 0:
            return await interaction.followup.send("❌ Aucun membre ne correspond aux statuts sélectionnés.", ephemeral=True)

        sent = 0
        failed = 0
        progress_message = await interaction.followup.send(f"📨 Progression : **0/{total}** envoyé(s)", ephemeral=True, wait=True)

        for index, member in enumerate(members, start=1):
            token = config["tokens"][(index - 1) % len(config["tokens"])]
            payload = build_dm_payload(member)
            ok = await send_dm_via_token(token, member.id, payload)

            if ok:
                sent += 1
            else:
                failed += 1

            if index == total or index % 5 == 0:
                await progress_message.edit(content=f"📨 Progression : **{index}/{total}** traité(s)\n✅ Envoyés : **{sent}**\n❌ Échecs : **{failed}**")

            await asyncio.sleep(0.8)

        await progress_message.edit(content=f"✅ DM All terminé.\n📨 Total : **{total}**\n✅ Envoyés : **{sent}**\n❌ Échecs : **{failed}**")


@bot.command(name="dmall")
async def dmall_command(ctx: commands.Context):
    if ctx.author.id != OWNER_ID:
        return

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    try:
        panel = await send_panel_v2(ctx.channel.id)
    except Exception as exc:
        await ctx.send(f"❌ Impossible d'envoyer le panneau : `{exc}`", delete_after=10)
        return

    config["panel_message_id"] = int(panel["id"])
    config["panel_channel_id"] = int(ctx.channel.id)


@bot.event
async def on_ready():
    global VIEWS_READY

    if not VIEWS_READY:
        bot.add_view(PanelView())
        bot.add_view(MessageConfigView())
        VIEWS_READY = True

    print(f"Connecté en tant que {bot.user} ({bot.user.id})")


def main():
    token = os.environ.get("TOKEN")

    if not token:
        raise RuntimeError("Variable d'environnement TOKEN manquante.")

    bot.run(token)


if __name__ == "__main__":
    main()
