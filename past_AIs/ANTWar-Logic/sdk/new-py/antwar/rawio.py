import sys


def write_to_judger(msg: str) -> None:
    """
    按照4+N协议将消息输出给评测机
    :param msg: 需要输出的消息
    :type msg: str
    """
    msg = int.to_bytes(len(msg), length=4, byteorder="big", signed=False).decode("UTF-8") + msg
    print(msg, end="", flush=True)


def debug(msg: str) -> None:
    """
    输出调试信息到标准错误流。标准输入输出被评测任务占用，你可以使用标准错误流输出调试信息，这些信息也可以在Saiblo平台上显示。
    :param msg: 需要输出的调试信息
    :type msg: str
    """
    print(msg, file=sys.stderr, flush=True)
