import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SELLER_URL = "https://www.ebay.com/sch/getzappy/m.html?_rss=1"
OUTPUT = Path("products.xml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) "
        "AppleWebKit/537.36 Chrome/154 Mobile Safari/537.36"
    )
}

NS = "http://base.google.com/ns/1.0"


def fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_json_value(text, key):
    pattern = (
        r'"'
        + re.escape(key)
        + r'"\s*:\s*"((?:\\.|[^"\\])*)"'
    )

    match = re.search(pattern, text, re.I)

    if not match:
        return ""

    value = match.group(1)

    value = value.replace('\\"', '"')
    value = value.replace("\\/", "/")
    value = value.replace("\\u002F", "/")

    return clean(value)


def extract_price(text):
    patterns = [
        r'"price"\s*:\s*"([0-9,]+\.[0-9]{2})"',
        r'\$([0-9,]+\.[0-9]{2})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            return match.group(1).replace(",", "")

    return ""


def extract_image(text):
    patterns = [
        r'https://i\.ebayimg\.com/images/g/[^"\'<>\s\\]+',
        r'https://i\.ebayimg\.com/[^"\'<>\s\\]+',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            return (
                match.group(0)
                .replace("\\/", "/")
                .replace("\\u002F", "/")
            )

    return ""


def extract_items(page):
    items = []
    seen = set()

    pattern = re.compile(
        r'https://www\.ebay\.com/itm/'
        r'(?:[^"\'<>\s]*/)?'
        r'(\d{9,15})',
        re.I,
    )

    for match in pattern.finditer(page):

        item_id = match.group(1)

        if item_id in seen:
            continue

        seen.add(item_id)

        start = max(0, match.start() - 3000)
        end = min(len(page), match.end() + 7000)

        block = page[start:end]

        title = (
            extract_json_value(block, "title")
            or extract_json_value(block, "name")
        )

        price = extract_price(block)

        image = extract_image(block)

        if not title:
            continue

        items.append(
            {
                "id": item_id,
                "title": title,
                "description": (
                    f"{title}. "
                    "See the eBay listing for complete "
                    "description, condition, photos and details."
                ),
                "price": price,
                "image": image,
                "url": f"https://www.ebay.com/itm/{item_id}",
            }
        )

    return items


def xml_element(parent, name, value):
    if not value:
        return

    element = ET.SubElement(parent, f"{{{NS}}}{name}")
    element.text = str(value)


def build_feed(items):

    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:g": NS,
        },
    )

    channel = ET.SubElement(rss, "channel")

    title = ET.SubElement(channel, "title")
    title.text = "Zappy's Closet - eBay Store"

    link = ET.SubElement(channel, "link")
    link.text = "https://www.ebay.com/usr/getzappy"

    description = ET.SubElement(channel, "description")
    description.text = (
        "Vintage collectibles, toys, ornaments "
        "and unique finds from Zappy's Closet."
    )

    for item in items:

        product = ET.SubElement(channel, "item")

        xml_element(product, "id", item["id"])
        xml_element(product, "title", item["title"])
        xml_element(product, "description", item["description"])
        xml_element(product, "link", item["url"])

        xml_element(
            product,
            "image_link",
            item["image"],
        )

        if item["price"]:
            xml_element(
                product,
                "price",
                f'{item["price"]} USD',
            )

        xml_element(
            product,
            "availability",
            "in stock",
        )

        # eBay's seller page does not reliably expose
        # condition in a machine-readable form.
        # We therefore don't invent condition data.

        xml_element(
            product,
            "product_type",
            "Collectibles",
        )

    tree = ET.ElementTree(rss)

    ET.indent(tree, space="  ")

    tree.write(
        OUTPUT,
        encoding="utf-8",
        xml_declaration=True,
    )


def main():

    print("Fetching Zappy's Closet eBay listings...")

    page = fetch(SELLER_URL)

    print(f"Downloaded {len(page):,} characters.")

    items = extract_items(page)

    print(f"Found {len(items)} listings.")

    if not items:
        raise RuntimeError(
            "No eBay listings were found. "
            "The eBay page format may have changed."
        )

    build_feed(items)

    print(f"Created {OUTPUT}")

    time.sleep(1)


if __name__ == "__main__":
    main()
