import discord
import os
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents)

OWNER_ID = 1471476071290634305

ACTIVITY_TYPES = {
    "joue": discord.ActivityType.playing,
    "regarde": discord.ActivityType.watching,
    "ecoute": discord.ActivityType.listening,
    "stream": discord.ActivityType.streaming,
}


class DmallModal(discord.ui.Modal, title="📨 Envoyer un DM à tous"):
    message = discord.ui.TextInput(
        label="Message",
        placeholder="Écris ton message ici...",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild or (bot.guilds[0] if bot.guilds else None)
        if guild is None:
            await interaction.followup.send("❌ Aucun serveur trouvé.", ephemeral=True)
            return
        msg_text = self.message.value
        members = [m for m in guild.members if not m.bot]
        total = len(members)
        icon_url = guild.icon.url if guild.icon else None
        embed_status = discord.Embed(title="📨 Envoi en cours...", description=f"Envoi à **{total}** membre(s)...", color=0xfee75c)
        status_msg = await interaction.followup.send(embed=embed_status, ephemeral=True)
        sent = 0
        failed = 0

        def build_progress_embed(current_member=None, done=False):
            processed = sent + failed
            filled = int((processed / total) * 10) if total > 0 else 0
            bar = "🟩" * filled + "⬛" * (10 - filled)
            e = discord.Embed(title="✅ Dmall terminé" if done else "📨 Envoi en cours...", color=0x57f287 if done else 0xfee75c)
            e.add_field(name="✅ Envoyés", value=str(sent), inline=True)
            e.add_field(name="❌ Échoués", value=str(failed), inline=True)
            e.add_field(name="📊 Progression", value=f"{bar} `{processed}/{total}`", inline=False)
            if current_member and not done:
                e.add_field(name="📤 En cours", value=f"{current_member.mention} (`{current_member}`)", inline=False)
            e.add_field(name="📝 Message", value=msg_text[:200], inline=False)
            e.set_footer(text="UhqZkDmall")
            return e

        for i, member in enumerate(members):
            try:
                dm_embed = discord.Embed(title=f"📩 Message de {guild.name}", description=msg_text, color=0x5865f2)
                if icon_url:
                    dm_embed.set_thumbnail(url=icon_url)
                dm_embed.set_footer(text="UhqZkDmall")
                await member.send(embed=dm_embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except discord.HTTPException:
                failed += 1
            if i % 3 == 0:
                await status_msg.edit(embed=build_progress_embed(current_member=member))
        await status_msg.edit(embed=build_progress_embed(done=True))


class StatusModal(discord.ui.Modal, title="🎮 Définir le statut du bot"):
    type_input = discord.ui.TextInput(label="Type", placeholder="joue / regarde / ecoute / stream", max_length=10)
    text_input = discord.ui.TextInput(label="Texte du statut", placeholder="ex: avec vos DMs 💀", max_length=128)

    async def on_submit(self, interaction: discord.Interaction):
        type_str = self.type_input.value.strip().lower()
        text = self.text_input.value.strip()
        activity_type = ACTIVITY_TYPES.get(type_str)
        if activity_type is None:
            await interaction.response.send_message("❌ Utilise : `joue`, `regarde`, `ecoute` ou `stream`", ephemeral=True)
            return
        await bot.change_presence(activity=discord.Activity(type=activity_type, name=text))
        await interaction.response.send_message(f"✅ Statut : **{type_str} {text}**", ephemeral=True)


class DmallView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📨 DM All", style=discord.ButtonStyle.primary, custom_id="dmall_button")
    async def dmall_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Tu n'as pas la permission.", ephemeral=True)
            return
        await interaction.response.send_modal(DmallModal())

    @discord.ui.button(label="🎮 Statut", style=discord.ButtonStyle.secondary, custom_id="status_button")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Tu n'as pas la permission.", ephemeral=True)
            return
        await interaction.response.send_modal(StatusModal())


def build_panel_embed(guild):
    e = discord.Embed(title="🤖 UhqZkDmall — Panneau", description="**📨 DM All** — Envoie un DM à tous les membres.\n**🎮 Statut** — Change le statut du bot.", color=0x5865f2)
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="UhqZkDmall • Réservé au propriétaire")
    return e


@bot.event
async def on_ready():
    bot.add_view(DmallView())
    print(f"[BOT] Connecté : {bot.user}")

@bot.event
async def on_guild_join(guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(embed=build_panel_embed(guild), view=DmallView())
            break

@bot.command(name="dmall")
async def dmall_panel(ctx):
    if ctx.author.id != OWNER_ID:
        return
    guild = ctx.guild or (bot.guilds[0] if bot.guilds else None)
    await ctx.send(embed=build_panel_embed(guild), view=DmallView())

bot.run(os.environ.get("TOKEN", "TON_TOKEN_ICI"))
