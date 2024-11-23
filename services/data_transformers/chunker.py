from itertools import batched
import re

class StringChunker:
    def __init__(self, text: str) -> None:
        self._text = text

    def chunk_by_regex(self, reg: str):
        return re.split(reg, self._text)

class BasicChunker:
    _data: dict | list | str

    def __init__(self, iter: str) -> None:
        self._data = iter

    def chunk(self, number_of_items: int):
        if isinstance(self._data, dict):
            res = []
            curr_dict = {}
            for k, v in self._data.items():
                if len(curr_dict) < number_of_items:
                    curr_dict[k] = v
                else:
                    res.append(curr_dict)
                    curr_dict = {k: v}
            res.append(curr_dict)
            return res
        else:
            return list(batched(self._data, number_of_items))

def test_simple_array_n2():
    simple_arr = '[1,2,3,4,5,6,7]'
    chunker = BasicChunker(simple_arr)
    out = chunker.chunk(2)
    assert len(out[1]) == 2
    assert len(out[-1]) == 1


def test_simple_array_n3():
    simple_arr = '[1,2,3,4,5,6,7]'
    chunker = BasicChunker(simple_arr)
    out = chunker.chunk(3)
    assert len(out[1]) == 3

def test_simple_dict():
    simple_dict = '{"a":"1","b":"2","c":"3"}'
    chunker = BasicChunker(simple_dict)
    out = chunker.chunk(2)
    assert len(out[0]) == 2
    assert len(out[1]) == 1
