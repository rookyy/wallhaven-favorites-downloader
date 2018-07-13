import os
import sys
from contextlib import suppress

import requests
from bs4 import BeautifulSoup

# Control characters used to colorize console output
COLOR_YELLOW = '\033[93m'
COLOR_RED = '\033[91m'
END_COLOR = '\033[0m'


def login():
    login_url = 'https://alpha.wallhaven.cc/auth/login'

    while True:
        username = input('Username: ')
        password = input('Password: ')
        response = requests.post(login_url, data={'username': username, 'password': password})

        if response.url != login_url:
            print('Login successful.')
            return response.cookies

        print('Incorrect username/password. Try again.\n')


def fetch_filename(wp_id, session=None):
    '''This function is basically used to determine wallpaper's file extension,
    which, unfortunately, can't be deduced when fetching wallpaper ids.
    `session` parameter containing cookies of a successful login is required
    to run this function on an NSFW wallpaper.
    '''
    wallpaper_url = f'https://alpha.wallhaven.cc/wallpaper/{wp_id}'
    markup = requests.get(wallpaper_url, cookies=session).text
    soup = BeautifulSoup(markup, 'lxml')

    image_path = soup.find('img', id='wallpaper')['src']
    return image_path.rpartition('/')[-1]


def fetch_wallpaper_ids(page):
    '''Given a BeautifulSoup object containing a page with wallpaper thumbnails
    (e.g. collection, search result) return the list of wallpaper ids on that page.
    '''
    thumbnails = page.find('section', class_='thumb-listing-page').ul
    return [li.figure['data-wallpaper-id'] for li in thumbnails.find_all('li')]


def fetch_collections(session):
    favs_url = 'https://alpha.wallhaven.cc/favorites'
    favs_html = requests.get(favs_url, cookies=session).text
    favs_soup = BeautifulSoup(favs_html, 'lxml')
    collections = favs_soup.find('ul', class_='blocklist collections-list').find_all('li')
    del collections[-1]  # drop "trash" collection

    for collection in collections:
        yield collection['data-collection-id']


def download_collection(collection_id, session):
    collection_url = f'https://alpha.wallhaven.cc/favorites/{collection_id}'
    wallpaper_base_url = 'https://wallpapers.wallhaven.cc/wallpapers/full/'

    markup = requests.get(collection_url, cookies=session).text
    soup = BeautifulSoup(markup, 'lxml')

    collection_name = soup.find('header', class_='listing-header collection-header').h1.text
    num_pages_section = soup.find('header', class_='thumb-listing-page-header')

    # Get wallpaper ids from the first page of the collection
    print(f'Fetching wallpaper ids for collection "{collection_name}"')
    wallpaper_ids = fetch_wallpaper_ids(soup)

    if num_pages_section is not None:
        # Collection contains more than one page, need to fetch the rest
        num_pages = int(num_pages_section.text.split('/')[-1])

        for page_num in range(2, num_pages + 1):
            markup = requests.get(collection_url,
                                  params={'page': page_num},
                                  cookies=session).text
            soup = BeautifulSoup(markup, 'lxml')
            wallpaper_ids.extend(fetch_wallpaper_ids(soup))

    with suppress(FileExistsError):
        os.mkdir(collection_name)
    os.chdir(collection_name)

    wallpaper_count = len(wallpaper_ids)
    for i, wp_id in enumerate(wallpaper_ids, start=1):
        filename = fetch_filename(wp_id, session)
        response = requests.get(wallpaper_base_url + filename)

        with open(filename, 'wb') as image:
            image.write(response.content)

        print(f'\rDownloading collection "{collection_name}": {i}/{wallpaper_count}', end='')

    print()
    os.chdir('..')


def main():
    try:
        dowload_dir = sys.argv[1]
    except IndexError:
        print(f'{COLOR_YELLOW}Warning:{END_COLOR} '
              'No download folder specified. '
              'Using current working directory.')
        dowload_dir = os.getcwd()
        print(f'Current working directory is {dowload_dir}\n')

    try:
        os.chdir(dowload_dir)
    except FileNotFoundError:
        print(f'{COLOR_RED}Fatal error:{END_COLOR} '
              'Download folder not found.')
        return

    if not os.access(dowload_dir, os.W_OK):
        print(f'{COLOR_RED}Fatal error:{END_COLOR} '
              'Not enough permissions to write to download folder.')
        return

    try:
        session = login()
        print('Fetching collection ids...')
        collection_ids = fetch_collections(session)

        for collection in collection_ids:
            download_collection(collection, session)
    except requests.ConnectionError:
        print(f'{COLOR_RED}Fatal error:{END_COLOR} '
              'There was a problem with network.')


if __name__ == '__main__':
    main()
