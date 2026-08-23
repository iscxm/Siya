from pyrogram import types

from Dev import app, config, lang
from Dev.core.lang import lang_codes


def _safe_btn(**kwargs) -> types.InlineKeyboardButton:
    try:
        return types.InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        try:
            return types.InlineKeyboardButton(**kwargs)
        except Exception:
            safe = {k: v for k, v in kwargs.items()
                    if k in ("text", "callback_data", "url", "web_app",
                              "copy_text", "user_id")}
            return types.InlineKeyboardButton(**safe)


class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = _safe_btn

    def cancel_dl(self, text) -> types.InlineKeyboardMarkup:
        return self.ikm([[self.ikb(text=text, callback_data="cancel_dl", style="danger")]])

    def controls(
        self,
        chat_id: int,
        status: str = None,
        timer: str = None,
        remove: bool = False,
    ) -> types.InlineKeyboardMarkup:
        keyboard = []
        if status:
            keyboard.append(
                [self.ikb(text=status, callback_data=f"controls status {chat_id}")]
            )
        elif timer:
            keyboard.append(
                [self.ikb(text=timer, callback_data=f"controls status {chat_id}")]
            )

        if not remove:
            keyboard.append(
                [
                    self.ikb(text="\u25b7", callback_data=f"controls resume {chat_id}", style="success"),
                    self.ikb(text="II",    callback_data=f"controls pause {chat_id}",  style="secondary"),
                    self.ikb(text="\u2941", callback_data=f"controls replay {chat_id}", style="primary"),
                    self.ikb(text="\u2023\u2023I", callback_data=f"controls skip {chat_id}", style="secondary"),
                    self.ikb(text="\u25a2", callback_data=f"controls stop {chat_id}",  style="danger"),
                ]
            )

        return self.ikm(keyboard)

    def help_markup(
        self, _lang: dict, back: bool = False
    ) -> types.InlineKeyboardMarkup:
        if back:
            rows = [
                [
                    self.ikb(text="back",  callback_data="help back"),
                    self.ikb(text="close", callback_data="help close"),
                ]
            ]
        else:
            cbs    = ["admins", "auth", "blist", "lang", "ping", "play",
                      "queue", "stats", "sudo", "Insta", "playlist"]
            labels = ["Admins", "Auth", "Blacklist", "Language", "Ping", "Play",
                      "Queue", "Stats", "Sudo", "Insta", "Playlist"]
            buttons = [
                self.ikb(text=labels[i], callback_data=f"help {cb}")
                for i, cb in enumerate(cbs)
            ]
            rows = [buttons[i: i + 3] for i in range(0, len(buttons), 3)]

        return self.ikm(rows)

    def lang_markup(self, _lang: str) -> types.InlineKeyboardMarkup:
        langs = lang.get_languages()
        buttons = [
            self.ikb(
                text=f"{name} ({code}) {'✔️' if code == _lang else ''}",
                callback_data=f"lang_change {code}",
            )
            for code, name in langs.items()
        ]
        rows = [buttons[i: i + 2] for i in range(0, len(buttons), 2)]
        return self.ikm(rows)

    def ping_markup(self, text: str) -> types.InlineKeyboardMarkup:
        return self.ikm([[self.ikb(text=text, url=config.SUPPORT_CHAT, style="primary")]])

    def play_queued(
        self, chat_id: int, item_id: str, _text: str
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [[self.ikb(text=_text, callback_data=f"controls force {chat_id} {item_id}", style="success")]]
        )

    def queue_markup(
        self, chat_id: int, _text: str, playing: bool
    ) -> types.InlineKeyboardMarkup:
        _action = "pause" if playing else "resume"
        _style  = "secondary" if playing else "success"
        return self.ikm(
            [[self.ikb(text=_text, callback_data=f"controls {_action} {chat_id} q", style=_style)]]
        )

    def settings_markup(
        self, lang: dict, admin_only: bool, language: str, chat_id: int
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(text=lang["play_mode"] + " \u279c", callback_data="settings"),
                    self.ikb(text=admin_only, callback_data="settings play"),
                ],
                [
                    self.ikb(text=lang["language"] + " \u279c", callback_data="settings"),
                    self.ikb(text=lang_codes[language], callback_data="language"),
                ],
            ]
        )

    def start_key(
        self, lang: dict, private: bool = False
    ) -> types.InlineKeyboardMarkup:
        rows = [
            [self.ikb(text=lang["add_me"], url=f"https://t.me/{app.username}?startgroup=true", style="primary")],
            [self.ikb(text="\u029cᴇʟᴘ", callback_data="help",
                      icon_custom_emoji_id=5337147651609610232, style="success")],
            [
                self.ikb(text=lang["support"], url=config.SUPPORT_CHAT, style="danger"),
                self.ikb(text=lang["dev"], user_id=config.OWNER_ID, style="primary"),
            ],
        ]
        if private:
            rows += [[self.ikb(text=lang["love"], url="https://t.me/Toxic_bots", style="primary")]]
        else:
            rows += [[self.ikb(text=lang["language"], callback_data="language", style="primary")]]
        return self.ikm(rows)

    def yt_key(self, link: str) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(text="\u2750", copy_text=link, style="secondary"),
                    self.ikb(text="\u25b6 YouTube", url=link, style="danger"),
                ],
            ]
        )
