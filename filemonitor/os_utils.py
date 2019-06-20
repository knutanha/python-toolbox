import os


def persist_file_path(file_path: str, is_file=False) -> None:
    if is_file:
        file_path = remove_last_part_of_path(file_path)
    if not os.path.exists(file_path):
        os.makedirs(file_path)


def remove_last_part_of_path(file_path: str, repetitions=1) -> str:
    for i in range(repetitions):
        sep_loc = file_path.rfind(os.sep)
        altsep_loc = file_path.rfind(os.altsep)
        loc = max(sep_loc, altsep_loc)
        file_path = file_path[:max(sep_loc, altsep_loc)] if loc != -1 else ''
    return file_path
