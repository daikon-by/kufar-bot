from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UrlPollStats:
    url: str
    fetched: int = 0
    already_seen: int = 0
    minus_filtered: int = 0
    sent: int = 0
    skipped_limit: int = 0
    watermark_found: bool = True
    digest_sent: bool = False
    first_run: bool = False
    error: str | None = None


@dataclass
class GroupPollStats:
    group_id: int
    group_name: str
    urls: list[UrlPollStats] = field(default_factory=list)

    @property
    def sent(self) -> int:
        return sum(u.sent for u in self.urls)

    @property
    def fetched(self) -> int:
        return sum(u.fetched for u in self.urls)


@dataclass
class PollStats:
    user_id: int
    since_iso: str
    groups: list[GroupPollStats] = field(default_factory=list)
    favorites_checked: int = 0
    fatal_error: str | None = None
    cancelled: bool = False

    @property
    def sent(self) -> int:
        return sum(g.sent for g in self.groups)

    @property
    def errors(self) -> list[str]:
        result: list[str] = []
        if self.fatal_error:
            result.append(self.fatal_error)
        for group in self.groups:
            for url_stats in group.urls:
                if url_stats.error:
                    result.append(f"{group.group_name}: {url_stats.error}")
        return result

    def summary_text(self) -> str:
        title = "<b>Опрос остановлен</b>" if self.cancelled else "<b>Опрос завершён</b>"
        lines = [f"{title} (с {self.since_iso})"]
        if not self.groups:
            lines.append("Нет активных групп с ссылками.")
        for group in self.groups:
            lines.append(f"\n📁 <b>{group.group_name}</b>")
            for url_stats in group.urls:
                short_url = url_stats.url[:60] + "…" if len(url_stats.url) > 60 else url_stats.url
                if url_stats.error:
                    lines.append(f"  ❌ {short_url}\n     {url_stats.error}")
                else:
                    anchor = "якорь ✓" if url_stats.watermark_found else "якорь ✗"
                    mode = "список" if url_stats.digest_sent else "карточки"
                    first = ", первый опрос" if url_stats.first_run else ""
                    lines.append(
                        f"  • {short_url}\n"
                        f"    API: {url_stats.fetched}, видели: {url_stats.already_seen}, "
                        f"минус: {url_stats.minus_filtered}, отправлено: {url_stats.sent} ({mode}{first}), "
                        f"{anchor}"
                    )
                    if url_stats.skipped_limit:
                        lines.append(f"    пропущено (лимит): {url_stats.skipped_limit}")
        lines.append(f"\n<b>Итого отправлено:</b> {self.sent}")
        if self.errors:
            lines.append(f"<b>Ошибки:</b> {len(self.errors)} (см. data/kufar_bot.log)")
        return "\n".join(lines)
