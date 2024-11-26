from bs4 import BeautifulSoup as bs
import requests
from datetime import datetime
import logging
import time

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

USER_ID = 19185715
BASE_URL = f"https://www.kinopoisk.ru/user/{USER_ID}/votes"
RATINGS_TO_LETTERBOXD = {
    "1": "0.5",
    "2": "1",
    "3": "1.5",
    "4": "2",
    "5": "2.5",
    "6": "3",
    "7": "3.5",
    "8": "4",
    "9": "4.5",
    "10": "5",
}
FILENAME = "films.csv"


def has_pagination(soup) -> bool:
    return any(
        div.find("ul", class_="list")
        for div in soup.find_all("div", class_="navigator")
    )


def get_last_page_number(soup) -> int | None:
    arr_elements = soup.find_all("li", class_="arr")
    last_page_link = next(
        (element.a for element in arr_elements if element.a and "»»" in element.a.text),
        None,
    )

    if last_page_link:
        href = last_page_link["href"]
        last_page_number = href.split("/")[-2]
        return int(last_page_number)
    else:
        logging.warning("No last page link found")
        return None


def transform_to_iso_date(input_string):
    try:
        dt = datetime.strptime(input_string, "%d.%m.%Y, %H:%M")

        iso_date = dt.date().isoformat()

        return iso_date
    except ValueError as ve:
        logging.warning(f"{ve}, Invalid date format: {input_string}. Skipping.")
        return None


def parse(url: str, soup) -> list:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except requests.RequestException as req_err:
        logging.error(f"Request error for {url}: {req_err}")
        return []

    films = []
    for item in soup.find_all("div", class_="item"):
        try:
            title = item.find("div", class_="nameEng").text.strip()
            year = (
                item.find("div", class_="nameRus")
                .text.split()[-1]
                .strip()
                .replace(")", "")
                .replace("(", "")
            )
            date = transform_to_iso_date(item.find("div", class_="date").text.strip())
            rating = item.find("div", class_="vote").text.strip()

            if year == "...":
                continue

            rating = RATINGS_TO_LETTERBOXD.get(rating, "Unknown")

            films.append((title, year, rating, date))
        except AttributeError as ae:
            logging.warning(f"Missing attribute in item: {ae}")

    return films


def write_to_file(films):
    try:
        with open(FILENAME, "a", encoding="utf-8") as file:
            for film in films:
                if all(film):
                    print(film)
                    file.write(",".join(map(str, film)) + "\n")
    except IOError as io_err:
        logging.error(f"Error writing to file: {io_err}")


def main():
    try:
        with open(FILENAME, "w", encoding="utf-8") as file:
            file.write("Title,Year,Rating,WatchedDate\n")
    except IOError as io_err:
        logging.error(f"Error creating header in file: {io_err}")
        return

    try:
        response = requests.get(f"{BASE_URL}/list/vs/vote/page/1/#list")
        response.raise_for_status()
        if "showcaptcha" in response.url:
            logging.warning("Captcha detected. Handling manually...")
            # TODO handle captcha
            return

        try:
            soup = bs(response.text, "html.parser")
        except bs.FeatureNotFound as fe:
            logging.error(f"Parser error: {fe}")
            return []

        if has_pagination(soup):
            logging.info("Pagination detected")
            last_page = get_last_page_number(soup)

            for url in [
                f"{BASE_URL}/list/vs/vote/page/{i}/#list" for i in range(1, last_page)
            ]:
                logging.info(f"Parsing URL: {url}")

                films = parse(url, soup=soup)
                write_to_file(films)
                time.sleep(2)
        else:
            logging.info("No pagination detected")

            films = parse(BASE_URL, soup=soup)
            write_to_file(films)
    except Exception as e:
        logging.error(f"Error: {e}")


if __name__ == "__main__":
    main()
