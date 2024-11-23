import re

import pytest

class MarkdownLink:
    def __init__(self, link: str) -> None:
        self._link_str = link
        self.text: str = ''
        self.url: str = ''
        self.resource_type: str = ''
        self.is_image_link = self._link_str.startswith('!')
        self._extract_link_data()

    def _extract_link_data(self):
        text = re.search(r'\[.*\]', self._link_str)
        if text is None:
            raise ValueError(f'Incorrect markdown link {self._link_str}')
        self.text: str = text[0].strip('[]')

        url = re.search(r'\(.*\)', self._link_str)
        if url is None:
            raise ValueError(f'Incorrect markdown link {self._link_str}')
        self.url = url[0].strip('()')

        path_elements = self.url.strip('https://').split('/')
        if path_elements:
            # Only the domain part exists
            if len(path_elements) == 1:
                self.resource_type = 'html'
                return
            try:
                # Check if there is a file extension in the last element
                last_path_element = path_elements[-1]
                if '.' not in last_path_element:
                    self.resource_type = 'html'
                else:
                    self.resource_type = last_path_element.split('.')[-1]
            except IndexError:
                self.resource_type = 'html'

    def is_relative(self):
        '''Checks if the link is relative to the page'''
        return not self.url.startswith(('https','http'))

def test_markdown_image_link():
    link = '![some_text](https://xyz.abc)'
    md_link = MarkdownLink(link)
    assert md_link.is_image_link
    assert md_link.text == 'some_text'
    assert md_link.url == 'https://xyz.abc'


def test_markdown_hyperlink():
    link = '[some_text](https://xyz.abc)'
    md_link = MarkdownLink(link)
    assert not md_link.is_image_link
    assert md_link.text == 'some_text'
    assert md_link.url == 'https://xyz.abc'

def test_markdown_relative_link():
    link = '[some_text](xyz/some_file.txt)'
    md_link = MarkdownLink(link)
    assert md_link.is_relative()

@pytest.mark.parametrize(
    'resource, link', 
    (
        ('html','[](https://xyz.abc)' ),
        ('html','[](https://xyz.abc/some)' ),
        ('html','[](https://xyz.abc/some/other)' ),
        ('html','[](https://xyz.abc/some/other.html)' ),
        ('png','[](https://xyz.abc/some/outer/image.png)' ),
        ('mp3','[](https://xyz.abc/some.mp3)' ),
        ('nvim','[](https://github.com/yetone/avante.nvim)' ),
    )
)
def test_markdown_link_resource_types(resource: str, link: str):
    md_link = MarkdownLink(link)
    assert resource == md_link.resource_type

