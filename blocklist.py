from typing import List, AnyStr
import validators


def is_valid_url_string(url):
    return validators.url(url)


def read_blocklist():
    f = open("blocklist.txt", "r")
    lines = f.readlines()
    items = []
    for line in lines:
        line = line[:-1] # remove line ending
        if is_valid_url_string(line):
            items.append(line)
    return items


def add_to_blocklist(urls: List[AnyStr]):
    f = open("blocklist.txt", "a")
    items: List[AnyStr] = []
    for url in urls:
        if is_valid_url_string(url):
            print(f"Added '{url}' to blocklist.")
            items.append(url + "\n")
        else:
            print(f"Couldn't add '{url}' to blocklist as it wasn't in the expected format.")
    f.writelines(items)
    f.close()


def remove_from_blocklist(urls: List[AnyStr]):
    f = open("blocklist.txt", "r+")
    items = f.readlines()
    for url in urls:
        try:
            temp = url + "\n"  # add because of the separator we have to add to read in separately
            items.remove(temp)
        except ValueError:
            print(f"Couldn't remove '{url}' from blocklist as it was never there in the first place.")
    f.truncate(0)
    f.writelines(items)
    f.close()
