from collections import defaultdict, deque
from typing import Union

from ._dataclass import Media, Track

MediaItem = Union[Media, Track]


class Queue:
    def __init__(self):
        self.queues: dict[int, deque[MediaItem]] = defaultdict(deque)

    def add(self, chat_id: int, item: MediaItem) -> int:
        self.queues[chat_id].append(item)
        return len(self.queues[chat_id]) - 1

    def check_item(self, chat_id: int, item_id: str) -> tuple[int, MediaItem | None]:
        pos, track = next(
            (
                (i, track)
                for i, track in enumerate(list(self.queues[chat_id]))
                if track.id == item_id
            ),
            (-1, None),
        )
        return pos, track

    def force_add(
        self, chat_id: int, item: MediaItem, remove: int | bool = False
    ) -> None:
        self.remove_current(chat_id)
        self.queues[chat_id].appendleft(item)
        if remove:
            self.queues[chat_id].rotate(-remove)
            self.queues[chat_id].popleft()
            self.queues[chat_id].rotate(remove)

    def get_current(self, chat_id: int) -> MediaItem | None:
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_next(self, chat_id: int, check: bool = False) -> MediaItem | None:
        if not self.queues[chat_id]:
            return None
        if check:
            return self.queues[chat_id][1] if len(self.queues[chat_id]) > 1 else None

        self.queues[chat_id].popleft()
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_queue(self, chat_id: int) -> list[MediaItem]:
        return list(self.queues[chat_id])

    def remove_current(self, chat_id: int) -> None:
        if self.queues[chat_id]:
            self.queues[chat_id].popleft()

    def clear(self, chat_id: int) -> None:
        self.queues[chat_id].clear()
