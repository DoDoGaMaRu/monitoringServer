from time import time, localtime, strftime


def get_time() -> str:
    return strftime('%Y%m%d%H', localtime(time()))


def get_day() -> str:
    return day(get_time())


def day(time_str: str) -> str:
    return time_str[:-2]


class TimeController:
    def __init__(self):
        self.pre = get_time()

    def update(self):
        self.pre = get_time()

    def is_day_change(self):
        now = day(get_time())
        is_day_changed = day(self.pre) != now

        if is_day_changed:
            self.update()

        return is_day_changed

    def is_hour_change(self):
        now = get_time()
        is_hour_changed = self.pre != now

        if is_hour_changed:
            self.update()

        return is_hour_changed
