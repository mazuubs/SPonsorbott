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
GREEN = 3
GRAY = 2
RED = 4
COMPONENTS_V2 = 32768
EPHEMERAL = 64
VIEWS_READY = False
DMALL_RUNNING = False
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

config = {
    "tokens": [], "token_infos": [], "message": None, "embed": None,
    "button_label": None, "button_url": None, "ignored_ids": [],
    "status_filter": ["online", "idle", "dnd", "offline"],
    "selected_token_index": 0, "target_ids": [], "member_count": 0,
    "panel_message_id": None, "panel_channel_id": None,
}

ACTIVITY_TYPES = {
    "joue": discord.ActivityType.playing, "regarde": discord.ActivityType.watching,
    "ecoute": discord.ActivityType.listening, "stream": discord.ActivityType.streaming,
}

PERSIST_KEYS = [
    "tokens", "token_infos", "message", "embed", "button_label", "button_url",
    "ignored_ids", "status_filter", "selected_token_index", "target_ids", "member_count",
]

def save_config() -> None:
    data = {k: config[k] for k in PERSIST_KEYS}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config() -> None:
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in PERSIST_KEYS:
            if k in data:
                config[k] = data[k]
    except Exception:
        pass

def text_component(content): return {"type": 10, "content": content}
def separator(): return {"type": 14, "divider": True, "spacing": 1}
def button(label, style, custom_id): return {"type": 2, "label": label, "style": style, "custom_id": custom_id}
def link_button(label, url): return {"type": 2, "label": label, "style": 5, "url": url}
def action_row(*items): return {"type": 1, "components": list(items)}
def short_text(value, empty, limit=90):
    if not value: return empty
    return value[:limit] + "..." if len(value) > limit else value

def get_member_from_id(user_id: int) -> discord.Member | None:
    for guild in bot.guilds:
        m = guild.get_member(user_id)
        if m: return m
    return None

def set_target_ids(ids: list[int]) -> None:
    filtered = [i for i in ids if i not in config["ignored_ids"]]
    config["target_ids"] = filtered
    config["member_count"] = len(filtered)
    save_config()

def build_token_text() -> str:
    if not config["tokens"]: return "Aucun token ajouté"
    lines = []
    for i, info in enumerate(config["token_infos"], 1):
        name = info.get("name", f"Bot {i}")
        bid = info.get("id")
        if bid:
            invite = f"https://discord.com/oauth2/authorize?client_id={bid}&scope=bot&permissions=8"
            lines.append(f"`{i}.` **{name}** • [Inviter]({invite})")
        else:
            lines.append(f"`{i}.` **{name}**")
    for i in range(len(config["token_infos"]) + 1, len(config["tokens"]) + 1):
        lines.append(f"`{i}.` **Bot inconnu**")
    return "\n".join(lines)

def build_panel_components() -> list[dict]:
    token_text = build_token_text()
    message_text = short_text(config["message"], "Aucun message texte défini")
    embed_text = "Embed configuré" if config["embed"] else "Aucun embed défini"
    return [{
        "type": 17, "accent_color": 0x5865F2,
        "components": [
            text_component("## `💎` 〃 Configuration du UhqZkDmall\n**__Utilisez les boutons ci-dessous pour configurer votre Dmall.__**"),
            separator(),
            text_component(f"🤖 **Tokens** — {token_text}"),
            action_row(button("🤖 Ajouter Token", BLUE, "add_token_btn")),
            separator(),
            text_component(f"📝 **Message à envoyer**\n```{message_text}```\n✏️ **Embed**\n```{embed_text}```"),
            action_row(button("📝 Définir le message", GREEN, "open_message_config_btn")),
            separator(),
            text_component(f"👥 **User IDs — Total : {config['member_count']} ID**　　👥 **User IDs à Ignorer — Total : {len(config['ignored_ids'])} ID**"),
            action_row(button("⚙️ Options DM", GRAY, "dm_options_btn")),
            separator(),
            action_row(button("⭐ Définir le statut", BLUE, "set_status_btn"), button("🚀 Dmall", RED, "dmall_execute_btn")),
            separator(),
            text_component("-# UhqZkDmall • Crée par **mazuu.bs**"),
        ],
    }]

def build_message_config_components() -> list[dict]:
    return [{"type": 17, "accent_color": 0x5865F2, "components": [
        text_component("## :pencil: 〃 Définir le Message à Envoyer\nChoisissez une méthode :"),
        separator(),
        text_component(":one: **Message texte simple**"),
        action_row(button("✏️ Saisir un message", BLUE, "simple_message_btn")),
        separator(),
        text_component(":two: **Embed personnalisé**"),
        action_row(button("📝 Embed JSON", BLUE, "embed_json_btn"), button("🎨 Embed Builder", GRAY, "embed_builder_btn")),
        separator(),
        text_component(":bulb: **Variables** : `{user}` `{user.id}` `{timestamp}`"),
        separator(),
        action_row(button("Aperçu", GRAY, "preview_message_btn"), button("Reset", RED, "reset_message_btn")),
    ]}]

def bot_headers(token=None):
    return {"Authorization": f"Bot {token or os.environ.get('TOKEN', '')}", "Content-Type": "application/json"}

async def send_panel_v2(channel_id: int) -> dict:
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.post(f"{DISCORD_API}/channels/{channel_id}/messages",
            json={"flags": COMPONENTS_V2, "components": build_panel_components()},
            headers=bot_headers()) as r:
            data = await r.json()
            if r.status >= 400: raise RuntimeError(f"Erreur {r.status}: {data}")
            return data

async def refresh_panel() -> None:
    if not config["panel_message_id"] or not config["panel_channel_id"]: return
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.patch(
            f"{DISCORD_API}/channels/{config['panel_channel_id']}/messages/{config['panel_message_id']}",
            json={"flags": COMPONENTS_V2, "components": build_panel_components()},
            headers=bot_headers()): pass

async def get_token_bot_info(token: str) -> dict | None:
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.get(f"{DISCORD_API}/users/@me", headers=bot_headers(token)) as r:
            if r.status != 200: return None
            data = await r.json()
            uid = data.get("id")
            name = data.get("global_name") or data.get("username") or "Bot inconnu"
            disc = data.get("discriminator")
            if disc and disc != "0": name = f"{name}#{disc}"
            return {"id": uid, "name": name}

async def send_ephemeral_components(interaction, components):
    payload = {"type": 4, "data": {"flags": EPHEMERAL | COMPONENTS_V2, "components": components}}
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.post(f"{DISCORD_API}/interactions/{interaction.id}/{interaction.token}/callback", json=payload) as r:
            if r.status >= 400:
                err = await r.text()
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ {err}", ephemeral=True)

def apply_variables(value, member):
    if value is None: return None
    return value.replace("{user}", member.mention).replace("{user.id}", str(member.id)).replace("{timestamp}", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

def build_embed_for_member(member):
    if not config["embed"]: return None
    ed = json.loads(json.dumps(config["embed"]))
    for k in ("title", "description", "url"):
        if k in ed and isinstance(ed[k], str): ed[k] = apply_variables(ed[k], member)
    for f in ed.get("fields", []):
        if isinstance(f, dict):
            for k in ("name", "value"):
                if k in f and isinstance(f[k], str): f[k] = apply_variables(f[k], member)
    return ed

def build_dm_payload(member):
    p = {}
    c = apply_variables(config["message"], member)
    e = build_embed_for_member(member)
    if c: p["content"] = c
    if e: p["embeds"] = [e]
    if config["button_label"] and config["button_url"]:
        p["components"] = [action_row(link_button(config["button_label"], config["button_url"]))]
    return p

def build_dm_payload_for_id(user_id):
    m = get_member_from_id(user_id)
    if m: return build_dm_payload(m)
    p = {}
    if config["message"]: p["content"] = config["message"]
    if config["embed"]: p["embeds"] = [config["embed"]]
    if config["button_label"] and config["button_url"]:
        p["components"] = [action_row(link_button(config["button_label"], config["button_url"]))]
    return p

async def send_dm_via_token(token, user_id, payload) -> bool:
    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            async with session.post(f"{DISCORD_API}/users/@me/channels",
                json={"recipient_id": str(user_id)}, headers=bot_headers(token)) as r:
                if r.status != 200: return False
                channel_id = (await r.json()).get("id")
                if not channel_id: return False
            async with session.post(f"{DISCORD_API}/channels/{channel_id}/messages",
                json=payload, headers=bot_headers(token)) as r:
                return r.status in (200, 201)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False

# ─── DM_OPTIONS_CONTENT ──────────────────────────────────────────────────────

DM_OPTIONS_CONTENT = (
    "## ⚙️ 〃 Options de DM\n"
    "Choisissez une option pour récupérer les membres à qui envoyer des messages :\n\n"
    "**1️⃣ Ajouter des IDs**\nPermet d'ajouter un ou plusieurs IDs manuellement.\n\n"
    "**2️⃣ Fetch des membres**\nRécupère tous les membres du serveur (vous pouvez choisir le statut).\n\n"
    "**3️⃣ Fetch par rôles**\nRécupère les membres ayant certains rôles spécifiques.\n\n"
    "**4️⃣ Fetch Vocal**\nRécupère soit les membres en vocal ou ceux pas en vocal.\n\n"
    "**5️⃣ Autres**\nAffiche d'autres options."
)

# ─── Option 1 : Ajouter IDs ──────────────────────────────────────────────────

class AddIdsModal(discord.ui.Modal, title="1️⃣ Ajouter des IDs"):
    ids_input = discord.ui.TextInput(label="IDs à ajouter", placeholder="Un ID par ligne ou séparés par virgules", style=discord.TextStyle.paragraph, max_length=4000)
    async def on_submit(self, interaction):
        raw = self.ids_input.value.replace(",", "\n")
        new_ids, invalid = [], 0
        for p in raw.splitlines():
            p = p.strip()
            if not p: continue
            try: new_ids.append(int(p))
            except ValueError: invalid += 1
        added = sum(1 for uid in new_ids if uid not in config["target_ids"] and not config["target_ids"].append(uid))
        config["member_count"] = len(config["target_ids"])
        save_config()
        msg = f"✅ **{added}** ID(s) ajouté(s) — Total : **{config['member_count']}** ID(s)"
        if invalid: msg += f"\n⚠️ {invalid} valeur(s) invalide(s) ignorée(s)"
        await interaction.response.send_message(msg, ephemeral=True)
        await refresh_panel()

# ─── Option 2 : Fetch membres ────────────────────────────────────────────────

class DmWizardStatusSelect(discord.ui.View):
    def __init__(self, token_index, guild_ids):
        super().__init__(timeout=120)
        self.token_index = token_index
        self.guild_ids = guild_ids
        options = [
            discord.SelectOption(label="🟢 En ligne", value="online", default="online" in config["status_filter"]),
            discord.SelectOption(label="🟡 Inactif", value="idle", default="idle" in config["status_filter"]),
            discord.SelectOption(label="🔴 DND", value="dnd", default="dnd" in config["status_filter"]),
            discord.SelectOption(label="⚫ Hors ligne", value="offline", default="offline" in config["status_filter"]),
        ]
        s = discord.ui.Select(placeholder="Sélectionne les statuts...", min_values=1, max_values=4, options=options)
        s.callback = self.on_select
        self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        config["status_filter"] = list(self.children[0].values)
        config["selected_token_index"] = self.token_index
        await interaction.response.defer()
        ids, seen = [], set()
        for guild_id in self.guild_ids:
            guild = bot.get_guild(guild_id)
            if not guild: continue
            try: await asyncio.wait_for(guild.chunk(cache=True), timeout=8)
            except Exception: pass
            for m in guild.members:
                if m.id not in seen and not m.bot and str(m.status) in config["status_filter"]:
                    seen.add(m.id); ids.append(m.id)
        set_target_ids(ids)
        sl = {"online": "🟢 En ligne", "idle": "🟡 Inactif", "dnd": "🔴 DND", "offline": "⚫ Hors ligne"}
        st = ", ".join(sl.get(s, s) for s in config["status_filter"])
        await interaction.edit_original_response(content=f"✅ Membres récupérés.\n👥 **{config['member_count']}** membre(s) — {st}", view=None)
        await refresh_panel()

class DmWizardGuildSelect(discord.ui.View):
    def __init__(self, token_index):
        super().__init__(timeout=120)
        self.token_index = token_index
        guilds = bot.guilds
        opts = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in guilds[:25]]
        if not opts: opts = [discord.SelectOption(label="Aucun serveur", value="0")]
        s = discord.ui.Select(placeholder="Sélectionne un ou plusieurs serveurs...", min_values=1, max_values=min(len(opts), 25), options=opts)
        s.callback = self.on_select; self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        ids = [int(v) for v in self.children[0].values if v != "0"]
        if not ids: return await interaction.response.send_message("❌ Aucun serveur valide.", ephemeral=True)
        await interaction.response.edit_message(content="⚪ 〃 Sélectionnez les statuts à inclure", view=DmWizardStatusSelect(self.token_index, ids))

class DmWizardBotSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        opts = [discord.SelectOption(label=info.get("name", f"Bot {i+1}"), value=str(i)) for i, info in enumerate(config["token_infos"])]
        if not opts: opts = [discord.SelectOption(label="Aucun bot configuré", value="-1")]
        s = discord.ui.Select(placeholder="Sélectionne un bot...", min_values=1, max_values=1, options=opts[:25])
        s.callback = self.on_select; self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        idx = int(self.children[0].values[0])
        if idx == -1: return await interaction.response.send_message("❌ Aucun bot.", ephemeral=True)
        if not bot.guilds: return await interaction.response.edit_message(content="❌ Aucun serveur.", view=None)
        await interaction.response.edit_message(content="🌐 〃 Sélectionnez les serveurs\n🌐 Sélectionnez un ou plusieurs serveurs", view=DmWizardGuildSelect(idx))

# ─── Option 3 : Fetch par rôles ──────────────────────────────────────────────

class FetchByRolesRoleSelect(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=120)
        self.guild = guild
        roles = [r for r in guild.roles if r.name != "@everyone"][:25]
        opts = [discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in roles]
        if not opts: opts = [discord.SelectOption(label="Aucun rôle", value="0")]
        s = discord.ui.Select(placeholder="Sélectionne les rôles...", min_values=1, max_values=min(len(opts), 25), options=opts)
        s.callback = self.on_select; self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        role_ids = {int(v) for v in self.children[0].values if v != "0"}
        await interaction.response.defer()
        try: await asyncio.wait_for(self.guild.chunk(cache=True), timeout=8)
        except Exception: pass
        ids = [m.id for m in self.guild.members if not m.bot and any(r.id in role_ids for r in m.roles)]
        set_target_ids(ids)
        rnames = [r.name for r in self.guild.roles if r.id in role_ids]
        await interaction.edit_original_response(content=f"✅ Fetch par rôles.\n👥 **{config['member_count']}** membre(s) — {', '.join(rnames)}", view=None)
        await refresh_panel()

class FetchByRolesGuildSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        opts = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in bot.guilds[:25]]
        if not opts: opts = [discord.SelectOption(label="Aucun serveur", value="0")]
        s = discord.ui.Select(placeholder="Sélectionne un serveur...", min_values=1, max_values=1, options=opts)
        s.callback = self.on_select; self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        guild = bot.get_guild(int(self.children[0].values[0]))
        if not guild: return await interaction.response.send_message("❌ Serveur introuvable.", ephemeral=True)
        await interaction.response.edit_message(content=f"🎭 〃 Fetch par rôles — **{guild.name}**\n🎭 Sélectionnez les rôles", view=FetchByRolesRoleSelect(guild))

# ─── Option 4 : Fetch Vocal ──────────────────────────────────────────────────

class FetchVocalOptionView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=120)
        self.guild = guild

    @discord.ui.button(label="🔊 En vocal", style=discord.ButtonStyle.primary)
    async def in_vocal(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.defer()
        try: await asyncio.wait_for(self.guild.chunk(cache=True), timeout=8)
        except Exception: pass
        ids = [m.id for m in self.guild.members if not m.bot and m.voice is not None]
        set_target_ids(ids)
        await interaction.edit_original_response(content=f"✅ **{config['member_count']}** membre(s) en vocal sur **{self.guild.name}**", view=None)
        await refresh_panel()

    @discord.ui.button(label="🔇 Pas en vocal", style=discord.ButtonStyle.secondary)
    async def not_in_vocal(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.defer()
        try: await asyncio.wait_for(self.guild.chunk(cache=True), timeout=8)
        except Exception: pass
        ids = [m.id for m in self.guild.members if not m.bot and m.voice is None]
        set_target_ids(ids)
        await interaction.edit_original_response(content=f"✅ **{config['member_count']}** membre(s) hors vocal sur **{self.guild.name}**", view=None)
        await refresh_panel()

class FetchVocalGuildSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        opts = [discord.SelectOption(label=g.name[:100], value=str(g.id)) for g in bot.guilds[:25]]
        if not opts: opts = [discord.SelectOption(label="Aucun serveur", value="0")]
        s = discord.ui.Select(placeholder="Sélectionne un serveur...", min_values=1, max_values=1, options=opts)
        s.callback = self.on_select; self.add_item(s)

    async def on_select(self, interaction):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        guild = bot.get_guild(int(self.children[0].values[0]))
        if not guild: return await interaction.response.send_message("❌ Serveur introuvable.", ephemeral=True)
        await interaction.response.edit_message(content=f"🔊 〃 Fetch Vocal — **{guild.name}**\nChoisissez les membres à cibler", view=FetchVocalOptionView(guild))

# ─── Option 5 : Autres ───────────────────────────────────────────────────────

class AddIgnoredIdsModal(discord.ui.Modal, title="🚫 Ajouter IDs ignorés"):
    ids_input = discord.ui.TextInput(label="IDs à ignorer", placeholder="Un ID par ligne ou virgules", style=discord.TextStyle.paragraph, max_length=4000)
    async def on_submit(self, interaction):
        raw = self.ids_input.value.replace(",", "\n")
        added = 0
        for p in raw.splitlines():
            try:
                uid = int(p.strip())
                if uid not in config["ignored_ids"]: config["ignored_ids"].append(uid); added += 1
            except ValueError: pass
        save_config()
        await interaction.response.send_message(f"🚫 **{added}** ID(s) ajouté(s) aux ignorés.", ephemeral=True)
        await refresh_panel()

class RemoveIgnoredIdsModal(discord.ui.Modal, title="✅ Retirer IDs ignorés"):
    ids_input = discord.ui.TextInput(label="IDs à retirer des ignorés", placeholder="Un ID par ligne ou virgules", style=discord.TextStyle.paragraph, max_length=4000)
    async def on_submit(self, interaction):
        raw = self.ids_input.value.replace(",", "\n")
        removed = 0
        for p in raw.splitlines():
            try:
                uid = int(p.strip())
                if uid in config["ignored_ids"]: config["ignored_ids"].remove(uid); removed += 1
            except ValueError: pass
        save_config()
        await interaction.response.send_message(f"✅ **{removed}** ID(s) retirés des ignorés.", ephemeral=True)
        await refresh_panel()

class AutresView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🗑️ Vider la liste", style=discord.ButtonStyle.danger, row=0)
    async def clear_list(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        config["target_ids"] = []; config["member_count"] = 0; save_config()
        await interaction.response.edit_message(content="🗑️ Liste vidée. 👥 **0** ID(s).", view=None)
        await refresh_panel()

    @discord.ui.button(label="📋 Voir le total", style=discord.ButtonStyle.secondary, row=0)
    async def show_count(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_message(f"📋 **{config['member_count']}** ID(s) cible\n🚫 **{len(config['ignored_ids'])}** ID(s) ignoré(s)", ephemeral=True)

    @discord.ui.button(label="🚫 Ajouter IDs ignorés", style=discord.ButtonStyle.secondary, row=1)
    async def add_ignored(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(AddIgnoredIdsModal())

    @discord.ui.button(label="✅ Retirer IDs ignorés", style=discord.ButtonStyle.secondary, row=1)
    async def remove_ignored(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(RemoveIgnoredIdsModal())

# ─── Menu principal Options DM ───────────────────────────────────────────────

class DmOptionsMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="1️⃣ Ajouter des IDs", style=discord.ButtonStyle.primary, row=0)
    async def add_ids(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.send_modal(AddIdsModal())

    @discord.ui.button(label="2️⃣ Fetch des membres", style=discord.ButtonStyle.primary, row=0)
    async def fetch_members(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        if not config["tokens"]: return await interaction.response.send_message("❌ Aucun token configuré.", ephemeral=True)
        await interaction.response.edit_message(content="🤖 〃 Sélectionnez un bot pour continuer.\n🤖 Sélectionnez un bot", view=DmWizardBotSelect())

    @discord.ui.button(label="3️⃣ Fetch par rôles", style=discord.ButtonStyle.secondary, row=1)
    async def fetch_roles(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        if not bot.guilds: return await interaction.response.send_message("❌ Aucun serveur.", ephemeral=True)
        await interaction.response.edit_message(content="🌐 〃 Fetch par rôles — Étape 1\n🌐 Sélectionnez un serveur", view=FetchByRolesGuildSelect())

    @discord.ui.button(label="4️⃣ Fetch Vocal", style=discord.ButtonStyle.secondary, row=1)
    async def fetch_vocal(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        if not bot.guilds: return await interaction.response.send_message("❌ Aucun serveur.", ephemeral=True)
        await interaction.response.edit_message(content="🔊 〃 Fetch Vocal — Étape 1\n🌐 Sélectionnez un serveur", view=FetchVocalGuildSelect())

    @discord.ui.button(label="5️⃣ Autres", style=discord.ButtonStyle.secondary, row=2)
    async def autres(self, interaction, _):
        if interaction.user.id != OWNER_ID: return await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        await interaction.response.edit_message(
            content=f"## 5️⃣ 〃 Autres options\n\n📋 **{config['member_count']}** ID(s) chargé(s)\n🚫 **{len(config['ignored_ids'])}** ID(s) ignoré(s)",
            view=AutresView())

# ─── Modals message ──────────────────────────────────────────────────────────

class TokenModal(discord.ui.Modal, title="🤖 Ajouter un Token"):
    token_input = discord.ui.TextInput(label="Token du bot", style=discord.TextStyle.short, max_length=120)
    async def on_submit(self, interaction):
        token = self.token_input.value.strip()
        if not token: return await interaction.response.send_message("❌ Token vide.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        info = await get_token_bot_info(token)
        if not info: return await interaction.followup.send("❌ Token invalide.", ephemeral=True)
        config["tokens"].append(token); config["token_infos"].append(info); save_config()
        invite = f"https://discord.com/oauth2/authorize?client_id={info['id']}&scope=bot&permissions=8"
        await interaction.followup.send(f"✅ Token ajouté : **{info['name']}**\n[Inviter]({invite})", ephemeral=True)
        await refresh_panel()

class SimpleMessageModal(discord.ui.Modal, title="📝 Message texte simple"):
    message_input = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=2000, required=False)
    async def on_submit(self, interaction):
        config["message"] = self.message_input.value.strip() or None; save_config()
        await interaction.response.send_message("✅ Message défini !", ephemeral=True); await refresh_panel()

class EmbedJsonModal(discord.ui.Modal, title="Embed JSON"):
    json_input = discord.ui.TextInput(label="JSON de l'embed", style=discord.TextStyle.paragraph, max_length=4000)
    async def on_submit(self, interaction):
        try:
            ed = json.loads(self.json_input.value.strip())
            if not isinstance(ed, dict): raise ValueError
            discord.Embed.from_dict(ed)
        except Exception: return await interaction.response.send_message("❌ JSON invalide.", ephemeral=True)
        config["embed"] = ed; save_config()
        await interaction.response.send_message("✅ Embed JSON défini !", ephemeral=True); await refresh_panel()

class EmbedBuilderModal(discord.ui.Modal, title="Embed Builder"):
    title_input = discord.ui.TextInput(label="Titre", max_length=256, required=False)
    desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=4000, required=False)
    color_input = discord.ui.TextInput(label="Couleur hex", placeholder="5865f2", max_length=7, required=False)
    button_label_input = discord.ui.TextInput(label="Texte du bouton", max_length=80, required=False)
    button_url_input = discord.ui.TextInput(label="URL du bouton", max_length=200, required=False)
    async def on_submit(self, interaction):
        ed = {}
        if self.title_input.value.strip(): ed["title"] = self.title_input.value.strip()
        if self.desc_input.value.strip(): ed["description"] = self.desc_input.value.strip()
        c = self.color_input.value.strip().replace("#", "")
        if c:
            try: ed["color"] = int(c, 16)
            except ValueError: return await interaction.response.send_message("❌ Couleur invalide.", ephemeral=True)
        config["embed"] = ed or None
        config["button_label"] = self.button_label_input.value.strip() or None
        config["button_url"] = self.button_url_input.value.strip() or None
        save_config()
        await interaction.response.send_message("✅ Embed builder enregistré !", ephemeral=True); await refresh_panel()

class StatusModal(discord.ui.Modal, title="🎮 Statut du Bot"):
    type_input = discord.ui.TextInput(label="Type", placeholder="joue / regarde / ecoute / stream", max_length=10)
    text_input = discord.ui.TextInput(label="Texte", max_length=128)
    async def on_submit(self, interaction):
        t = self.type_input.value.strip().lower()
        act = ACTIVITY_TYPES.get(t)
        if not act: return await interaction.response.send_message("❌ Utilise : joue / regarde / ecoute / stream", ephemeral=True)
        await bot.change_presence(activity=discord.Activity(type=act, name=self.text_input.value.strip()))
        await interaction.response.send_message(f"✅ Statut : **{t} {self.text_input.value.strip()}**", ephemeral=True)

# ─── MessageConfigView ───────────────────────────────────────────────────────

class MessageConfigView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    def is_owner(self, i): return i.user.id == OWNER_ID

    @discord.ui.button(label="Saisir un message", style=discord.ButtonStyle.primary, custom_id="simple_message_btn")
    async def simple_message_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_modal(SimpleMessageModal())

    @discord.ui.button(label="Embed JSON", style=discord.ButtonStyle.primary, custom_id="embed_json_btn")
    async def embed_json_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_modal(EmbedJsonModal())

    @discord.ui.button(label="Embed Builder", style=discord.ButtonStyle.primary, custom_id="embed_builder_btn")
    async def embed_builder_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_modal(EmbedBuilderModal())

    @discord.ui.button(label="Aperçu", style=discord.ButtonStyle.secondary, custom_id="preview_message_btn")
    async def preview_message_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        payload = build_dm_payload(i.user)
        if not payload: return await i.response.send_message("❌ Aucun message configuré.", ephemeral=True)
        c = f"👀 Aperçu :\n\n{payload['content']}" if payload.get("content") else "👀 Aperçu :"
        e = discord.Embed.from_dict(payload["embeds"][0]) if payload.get("embeds") else None
        v = None
        if config["button_label"] and config["button_url"]:
            v = discord.ui.View(); v.add_item(discord.ui.Button(label=config["button_label"], url=config["button_url"]))
        await i.response.send_message(c, embed=e, view=v, ephemeral=True)

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, custom_id="reset_message_btn")
    async def reset_message_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        config["message"] = config["embed"] = config["button_label"] = config["button_url"] = None; save_config()
        await i.response.send_message("✅ Réinitialisé.", ephemeral=True); await refresh_panel()

# ─── PanelView ───────────────────────────────────────────────────────────────

class PanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    def is_owner(self, i): return i.user.id == OWNER_ID

    @discord.ui.button(label="🤖 Ajouter Token", style=discord.ButtonStyle.primary, custom_id="add_token_btn")
    async def add_token_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_modal(TokenModal())

    @discord.ui.button(label="📝 Définir le message", style=discord.ButtonStyle.primary, custom_id="open_message_config_btn")
    async def open_message_config_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await send_ephemeral_components(i, build_message_config_components())

    @discord.ui.button(label="⚙️ Options DM", style=discord.ButtonStyle.secondary, custom_id="dm_options_btn")
    async def dm_options_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_message(DM_OPTIONS_CONTENT, view=DmOptionsMainView(), ephemeral=True)

    @discord.ui.button(label="⭐ Statut", style=discord.ButtonStyle.secondary, custom_id="set_status_btn")
    async def set_status_btn(self, i, _):
        if not self.is_owner(i): return await i.response.send_message("❌", ephemeral=True)
        await i.response.send_modal(StatusModal())

    @discord.ui.button(label="📨 DM All", style=discord.ButtonStyle.danger, custom_id="dmall_execute_btn")
    async def dmall_execute_btn(self, interaction, _):
        global DMALL_RUNNING
        if not self.is_owner(interaction): return await interaction.response.send_message("❌", ephemeral=True)
        if DMALL_RUNNING: return await interaction.response.send_message("⏳ Déjà en cours.", ephemeral=True)
        if not config["tokens"]: return await interaction.response.send_message("❌ Aucun token.", ephemeral=True)
        if not config["message"] and not config["embed"]: return await interaction.response.send_message("❌ Aucun message.", ephemeral=True)
        if not config["target_ids"]: return await interaction.response.send_message("❌ Aucun membre. Configure via **⚙️ Options DM**.", ephemeral=True)

        token_index = config.get("selected_token_index", 0)
        if token_index >= len(config["tokens"]): token_index = 0
        send_token = config["tokens"][token_index]
        target_ids = [uid for uid in config["target_ids"] if uid not in config["ignored_ids"]]

        DMALL_RUNNING = True
        progress_message = None

        def pbar(idx, total, length=10):
            filled = round((idx / total) * length) if total > 0 else 0
            return "🟩" * filled + "⬛" * (length - filled)

        def fmt(sent, failed, idx, total, uid=None):
            bar = pbar(idx, total)
            mp = ""
            if config["message"]:
                prev = config["message"][:60].replace("\n", " ")
                mp = f"\n\n**📝 Message**\n{prev}{'...' if len(config['message']) > 60 else ''}"
            cur = ""
            if uid:
                m = get_member_from_id(uid)
                name = f"{m.mention} ({m.name})" if m else f"<@{uid}>"
                cur = f"\n\n**📤 En cours**\n{name}"
            return f"**📨 Envoi en cours...**\n\n**✅ Envoyés**\n{sent}\n\n**❌ Échoués**\n{failed}\n\n**📊 Progression**\n{bar} {idx}/{total}{cur}{mp}"

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            progress_message = await interaction.followup.send("⏳ Préparation...", ephemeral=True, wait=True)
            total = len(target_ids)
            if total == 0:
                await progress_message.edit(content="❌ Liste vide après filtrage des ignorés."); return
            sent = failed = 0
            for idx, uid in enumerate(target_ids, 1):
                payload = build_dm_payload_for_id(uid)
                ok = await send_dm_via_token(send_token, uid, payload)
                if ok: sent += 1
                else: failed += 1
                if idx == 1 or idx == total or idx % 2 == 0:
                    await progress_message.edit(content=fmt(sent, failed, idx, total, uid))
                await asyncio.sleep(0.8)
            mp = ""
            if config["message"]:
                prev = config["message"][:60].replace("\n", " ")
                mp = f"\n\n**📝 Message**\n{prev}{'...' if len(config['message']) > 60 else ''}"
            await progress_message.edit(content=f"**✅ DM All terminé !**\n\n**✅ Envoyés**\n{sent}\n\n**❌ Échoués**\n{failed}\n\n**📊 Progression**\n{'🟩'*10} {total}/{total}{mp}")
        except Exception as exc:
            err = f"❌ Dmall arrêté : `{type(exc).__name__}: {exc}`"
            if progress_message: await progress_message.edit(content=err)
            else: await interaction.followup.send(err, ephemeral=True)
        finally:
            DMALL_RUNNING = False

# ─── Commandes ───────────────────────────────────────────────────────────────

@bot.command(name="dmall")
async def dmall_command(ctx):
    if ctx.author.id != OWNER_ID: return
    try: await ctx.message.delete()
    except discord.Forbidden: pass
    try:
        panel = await send_panel_v2(ctx.channel.id)
        config["panel_message_id"] = int(panel["id"])
        config["panel_channel_id"] = int(ctx.channel.id)
    except Exception as exc:
        await ctx.send(f"❌ Impossible d'envoyer le panneau : `{exc}`", delete_after=10)

@bot.event
async def on_ready():
    global VIEWS_READY
    if not VIEWS_READY:
        bot.add_view(PanelView()); bot.add_view(MessageConfigView()); VIEWS_READY = True
    print(f"Connecté en tant que {bot.user} ({bot.user.id})")

def main():
    load_config()
    token = os.environ.get("TOKEN")
    if not token: raise RuntimeError("Variable TOKEN manquante.")
    bot.run(token)

if __name__ == "__main__":
    main()
