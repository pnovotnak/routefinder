import csv
import requests
import re
import logging
from typing import Type
import sys
from functools import reduce
import bs4
import html
from lib.openai_utils import openai_comment_maturity_assessment

from functools import cache

from typing import Final

logger = logging.getLogger(__name__)

BASE_URL: Final[str] = "https://www.mountainproject.com"
ROUTE_URL_RE: Final[re.Pattern] = re.compile(r"^https://www.mountainproject.com/route/([0-9]+)/(\w+)")
TICK_CLEANUP_RE: Final[re.Pattern] = re.compile("^\W*·\W*([\d]+ pitches)?\W*(?:Lead|Follow)?(?:[^\.]+)?.")

"6 pitches. Lead / Redpoint. Led everything"

def configure_logging(root_logger):
    root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    prod_fmt = '%(asctime)s - %(pathname)s:%(lineno)d [%(levelname)s] %(message)s'
    dev_fmt = '%(filename)s:%(lineno)d [%(levelname)s] %(message)s'
    formatter = logging.Formatter(dev_fmt)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


@cache
def parse_url(url: str) -> tuple[str, str]:
    route_id, slug = ROUTE_URL_RE.match(url).groups()
    return int(route_id), slug


MaturityRating = Type[str]

def get_description(route_url: str) -> str:
    response = requests.get(
        route_url, 
        allow_redirects=True
    )
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, features="html.parser")
    maturity_rating = None
    if title := soup.find("h2", {"class": "mr-2"}):
        possible_maturity_rating_element = title.contents[-1]
        if isinstance(possible_maturity_rating_element, bs4.element.NavigableString):
            maturity_rating = str(possible_maturity_rating_element.text).strip()

    # There seem to be three "fr-view" divs:
    # - Description
    # - Location
    # - Protection
    description = soup.find("div", {"class": "fr-view"}).text
    return description, maturity_rating


def get_comments(route_id: int | str) -> list[str]:
    response = requests.get(
        f"{BASE_URL}/comments/forObject/Climb-Lib-Models-Route/{route_id}?sortOrder=oldest&showAll=true", 
        allow_redirects=True,
    )
    response.raise_for_status()
    if not response.content:
        return ""
    soup = bs4.BeautifulSoup(response.content, features="html.parser")
    comments: list[str] = []
    for comment_container in soup.select('.comment-body'):
        comment = comment_container.find('span', id=lambda x: x and x.endswith('-full')).text
        comments.append(comment.strip())
    return comments


def get_ticks(route_id: int | str) -> list[str]:
    response = requests.get(
        f"{BASE_URL}/api/v2/routes/{route_id}/ticks?per_page=250&page=1",
        allow_redirects=True,
    )
    response.raise_for_status()
    ticks: list[str] = []
    for tick in response.json().get('data', {}):
        if not (tick_text := tick.get('text', '')):
            continue
        tick_text = html.unescape(tick_text)
        tick_text = TICK_CLEANUP_RE.sub("", tick_text)
        tick_text = tick_text.strip()
        if not tick_text:
            continue
        ticks.append(tick_text)
    return ticks

Description = Type[str]
Comments = list[str]
Ticks = list[str]

def get_beta(route_url) -> tuple[MaturityRating | None, Description, Comments, Ticks]:
    route_id, _ = parse_url(route_url)
    description, maturity_rating = get_description(route_url)
    return (
        maturity_rating,
        description,
        get_comments(route_id),
        get_ticks(route_id),
    )


def process_csv(csv_in_fn: str = "example.csv", csv_out_fn: str = "example-out.csv"):
    with open(csv_in_fn) as csv_in_fp, open(csv_out_fn, "w+") as csv_out_fp:
        csv_reader = csv.reader(csv_in_fp)
        csv_writer = csv.writer(csv_out_fp)
        in_headers = next(csv_reader)
        in_headers[6] = "Difficulty"
        out_headers = in_headers[:7] + ["Maturity Rating", "Maturity Reason"] + in_headers[7:]
        csv_writer.writerow(out_headers)
        for i, row in enumerate(csv_reader):
            row = [route, location, url, avg_stars, your_stars, route_type, yds_difficulty, pitches, length_ft, area_lat, area_lon] = row
            logger.info("Processing route \"%s\"", route)
            maturity_rating, description, comments, ticks = get_beta(url)
            if not maturity_rating:
                maturity_rating, maturity_reason = (
                    openai_comment_maturity_assessment(description, comments, ticks) 
                    if comments or ticks 
                    else ["UNKNOWN", "No comments"]
                )
            else:
                maturity_reason = "(Route description)"
            csv_writer.writerow(row[:7] + [maturity_rating, maturity_reason] + row[7:])


if __name__ == "__main__":
    configure_logging(logger)
    process_csv()