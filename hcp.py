import requests
from bs4 import BeautifulSoup
import pandas as pd
import time, re, logging
from datetime import datetime
from deep_translator import GoogleTranslator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "de-DE"}

# Cache — avoids translating the same word twice
translation_cache = {}

def translate(word):
    if word in translation_cache:
        return translation_cache[word]
    try:
        result = GoogleTranslator(source="de", target="en").translate(word)
        translation_cache[word] = result.title()
        return result.title()
    except Exception:
        return f"UNTRANSLATED: {word}"

URLS = [
    "https://www.jameda.de/vittorio-grandi/zahnarzt/muenchen",
    "https://www.jameda.de/peter-maier/zahnarzt/muenchen",
    "https://www.jameda.de/stefan-wolf/zahnarzt/muenchen",
    "https://www.jameda.de/michael-schmidt/zahnarzt/muenchen",
    "https://www.jameda.de/julia-bauer/zahnarzt/muenchen",
]


def split_street(address):
    """Splits 'Herterichstr. 61' -> ('Herterichstr.', '61')"""
    address = address.replace(",", "").strip()
    match = re.search(r'(\d+\s?[a-zA-Z]?)$', address)
    return (address[:match.start()].strip(), match.group(0).strip()) if match else (address, "N/A")


def get_text(soup, tag, attr={}):
    t = soup.find(tag, attr)
    return t.text.strip() if t else "N/A"


def get_attr(soup, tag, attr={}, key=""):
    t = soup.find(tag, attr)
    return t.get(key, "N/A") if t else "N/A"


def scrape(url):
    """Visits one jameda doctor profile and extracts key fields"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        if r.status_code != 200:
            log.warning(f"  Status {r.status_code} — skipped")
            return None

        s = BeautifulSoup(r.text, "html.parser")

        # Get specialty and translate it
        spec = get_text(s, "a", {"title": True, "class": "text-base-size"})
        specialty = translate(spec)

        # Split street into name and house number
        full_street = get_text(s, "span", {"data-test-id": "address-info-street"})
        street, number = split_street(full_street)

        return {
            "Full Name":      get_text(s, "span", {"itemprop": "name"}),
            "Specialty (DE)": spec,
            "Specialty (EN)": specialty,
            "Street":         street,
            "House No":       number,
            "City":           get_attr(s, "span", {"itemprop": "addressLocality"}, "content"),
            "Postcode":       get_attr(s, "span", {"itemprop": "postalCode"}, "content"),
            "Country":        get_attr(s, "span", {"itemprop": "addressCountry"}, "content"),
            "Phone":          "Yes" if s.find("button", {"data-id": "show-phone-number-modal"}) else "No",
            "Rating":         get_attr(s, "div", {"itemprop": "ratingValue"}, "data-score"),
            "Reviews":        get_attr(s, "meta", {"itemprop": "reviewCount"}, "content"),
            "Scraped At":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    except Exception as e:
        log.error(f"  Error: {e}")
        return None


# --- Main ---
if __name__ == "__main__":
    log.info("jameda.de HCP Scraper — starting")
    records = []

    for i, url in enumerate(URLS, 1):
        log.info(f"[{i}/{len(URLS)}] {url}")
        result = scrape(url)
        if result:
            records.append(result)
            log.info(f"  ✓ {result['Full Name']} | {result['Specialty (EN)']} | {result['City']}")
        else:
            log.warning("  ✗ Skipped")
        if i < len(URLS):
            time.sleep(2)

    df = pd.DataFrame(records)
    df.to_excel("jameda_hcp_records.xlsx", index=False)
    log.info(f"Done — {len(df)}/{len(URLS)} records saved")
    print(df[["Full Name", "Specialty (EN)", "Street", "House No", "City", "Postcode"]].to_string())