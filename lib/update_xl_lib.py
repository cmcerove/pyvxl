#!/usr/bin/env python

"""Download the latest Vector's XL Driver Library."""

import logging
import re
from sys import exit
from urllib.request import urlopen
from bs4 import BeautifulSoup
from zipfile import ZipFile
from os import remove, path


def find_urls(url, tag_text):
    """Find all urls including tag_text in the tag on the source url."""
    html = urlopen(url).read()
    parsed_html = BeautifulSoup(html, "html.parser")
    found_urls = []
    txt = ''
    for anchor in parsed_html.find_all('a'):
        txt = anchor.get_text()
        if tag_text in txt:
            logging.debug('Tag: {}\t URL:{}'.format(anchor.get_text(),
                                                    anchor.get('href')))
            found_urls.append((anchor.get('href'), txt))
    return found_urls


def main():
    """."""
    # Find the latest 32-bit python 2.7 download link for windows
    # ver_pat = re.compile(r'\d+\.\d+\.\d+')
    # base_url = 'https://www.vector.com'
    # lib = '/int/en/products/products-a-z/libraries-drivers/xl-driver-library/'
    # print('Searching for the latest version of the XL Driver Library: {}'
    #       ''.format(base_url + lib))
    # for url, txt in find_urls(base_url + lib, 'XL Driver Library'):
    #     # print(txt)
    #     match = ver_pat.search(txt)
    #     if match is not None:
    #         new_version = match.group(0)
    #         ver_url = url
    #         break
    # else:
    #     raise AssertionError('Failed finding the url to download the XL Driver Library.')
    # # print(ver_url)
    # for url, txt in find_urls(base_url + ver_url, 'Download now'):
    #     # print(txt, url)
    #     download_url = url

    # Download the file
    lib_path = path.normpath(path.dirname(__file__))
    exe_name = path.join(lib_path, 'Vector XL Driver Library Setup.exe')
    zip_name = path.join(lib_path, 'Vector XL Driver Library Setup.zip')
    if path.isfile(exe_name):
        remove(exe_name)
    download_url = r'https://www.vector.com/int/en/download/download-action/?tx_vecdownload_download%5Baction%5D=download&tx_vecdownload_download%5Bcontroller%5D=Download&tx_vecdownload_download%5Bdownload%5D=57590&cHash=f3162edec01452300f4f09d54248bdff'
    print(f'Downloading {zip_name}... ')
    with open(zip_name, 'wb') as f:
        f.write(urlopen(download_url).read())
    print(f'{zip_name} successfully downloaded!')
    ZipFile(zip_name).extractall(lib_path)
    remove(zip_name)
    if not path.isfile(exe_name):
        raise AssertionError(f'Executable extracted from {zip_name} is no '
                             f'longer called {exe_name}! This breaks setup.py')

    with open(path.join(lib_path, 'version.txt'), 'w') as f:
        # f.write(new_version)
        f.write('20.30.14')


if __name__ == '__main__':
    main()
