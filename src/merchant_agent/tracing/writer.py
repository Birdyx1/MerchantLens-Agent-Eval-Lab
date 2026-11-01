import json

from pathlib import Path


def append_span(path:str,span:dict) -> None:
    """
    要求：将 span 转成一行 JSON，以 UTF-8 追加到文件；
    父目录不存在时创建。
    可以使用 Python 标准库 json 和 pathlib。
    :param path: 文件路径
    :param span: span 数据
    :return:
    """
    line = json.dumps(span,ensure_ascii=False)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open(mode='a',encoding='utf-8') as file:
        file.write(line + '\n')