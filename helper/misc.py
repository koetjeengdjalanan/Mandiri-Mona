"""Miscellaneous helper functions."""

from typing import Any

__all__: list[str] = ["split_equally"]


def split_equally(item: list[Any], n: int) -> list[list[Any]]:
    """
    Split a list into n approximately equal parts.

    Args:
        item (list[Any]): The list to be split.
        n (int): The number of parts to split the list into.

    Returns:
        item[list[Any]]: A list containing n sublists, each being a part of the original list.
    """
    k, m = divmod(len(item), n)
    return [item[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n)]
