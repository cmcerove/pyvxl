#!/usr/bin/env python3

"""Download the latest 32 bit version of python 3."""

from __future__ import print_function
import logging
import re
from urllib.request import urlopen
from bs4 import BeautifulSoup
from os import remove
from os import system as run


def find_url(url, tag_text):
    """Find a url based on associated text."""
    html = urlopen(url).read()
    parsed_html = BeautifulSoup(html, "html.parser")
    found_url = ''
    txt = ''
    for anchor in parsed_html.find_all('a'):
        txt = anchor.get_text()
        if tag_text in txt:
            logging.debug('Tag: {}\t URL:{}'.format(anchor.get_text(),
                                                    anchor.get('href')))
            found_url = anchor.get('href')
            break
    return found_url, txt


def main():
    """."""
    # Find the latest 32-bit python 2.7 download link for windows
    ver_pat = re.compile(r'\d+\.\d+\.\d+')
    base_url = 'https://www.vector.com'
    lib = '/int/en/products/products-a-z/libraries-drivers/xl-driver-library/'
    print('Searching for the latest version of the XL Driver Library: {}'
          ''.format(base_url + lib))
    ver_url, version = find_url(base_url + lib, 'XL Driver Library')
    print(version)
    print(ver_pat.search(version).group(0))
    print(ver_url)
    download_url, dl_tag = find_url(base_url + ver_url, 'Download now')
    print(download_url)
    print(dl_tag)

    # Download the file
    file_name = download_url.split('/')[-1]
    print(file_name)
    if not file_name:
        raise ValueError('Failed finding {}')
    print('Downloading {}... '.format(file_name), end='')
    with open(file_name, 'wb') as f:
        f.write(urlopen(download_url).read())
    print('\r{} successfully downloaded!'.format(file_name))
    # run(file_name)
    # remove(file_name)


if __name__ == '__main__':
    main()
