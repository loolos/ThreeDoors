"""供子模块在运行时解析 `models.events` 上的可 patch 符号（random、create_*_item）。"""


def rng():
    import models.events as ev

    return ev.random


def mk_random_item(*args, **kwargs):
    import models.events as ev

    return ev.create_random_item(*args, **kwargs)


def mk_reward_item(*args, **kwargs):
    import models.events as ev

    return ev.create_reward_door_item(*args, **kwargs)
