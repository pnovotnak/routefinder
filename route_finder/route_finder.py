import csv
import requests
from enum import Enum
import re
import logging
from typing import Type
import sys
import bs4
from lib.openai_utils import openai_comment_maturity_assessment

from functools import cache

from typing import Final

logger = logging.getLogger(__name__)

BASE_URL: Final[str] = "https://www.mountainproject.com"
ROUTE_URL_RE: Final[re.Pattern] = re.compile(r"^https://www.mountainproject.com/route/([0-9]+)/(\w+)")

class DANGER_RATINGS(Enum):
    UNKNOWN = -1
    G = 0
    PG13 = 1
    R = 2
    X = 3


DANGER_REGEXES = {
    DANGER_RATINGS.G: re.compile(r"(great|good|well) (gear|protect(ed|ion))+|protects well"),
    DANGER_RATINGS.PG13: re.compile(r"spicy|scary|run( |-)?out"),
    DANGER_RATINGS.R: re.compile(r"long run( |-)?out|unprotected"),
    DANGER_RATINGS.X: re.compile(r"very long run( |-)?out|suicidal"),
}


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


def get_description(route_id) -> str:
    return ""


def get_danger(content: list[str]) -> None | DANGER_RATINGS:
    """ Determine the danger of the route from the content. Highest level is matched first """
    for c in content:
        for danger_rating in reversed(DANGER_RATINGS):
            search_results = DANGER_REGEXES[danger_rating].search(c)
            if search_results:
                return danger_rating


def get_comments(route_id: int) -> list[str]:
    referer = f"{BASE_URL}/route/{route_id}/"
    response = requests.get(
        f"{BASE_URL}/comments/forObject/Climb-Lib-Models-Route/{route_id}?sortOrder=oldest&showAll=true", 
        allow_redirects=True,
        headers={
            # "referer": referer,
            "authority": "www.mountainproject.com",
            "user-agent": "'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'"
        }
    )
    response.raise_for_status()
    if not response.content:
        return ""
    soup = bs4.BeautifulSoup(response.content, features="html.parser")
    # TODO find second child if there are 3 children ("more..." link)
    comments: list[str] = []
    for comment_container in soup.select('.comment-body'):
        comment = comment_container.find('span', id=lambda x: x and x.endswith('-full')).text
        comments.append(comment.strip())
    return comments


def get_ticks(route_id: int) -> list[str]:
    return []


Description = Type[str]
Comments = list[str]
Ticks = list[str]

def get_beta(route_url) -> tuple[Description, Comments, Ticks]:
    route_id, _ = parse_url(route_url)
    return (
        get_description(route_id),
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
            description, comments, ticks = get_beta(url)
            maturity_rating, maturity_reason = openai_comment_maturity_assessment(comments) if comments else ["UNKNOWN", "No comments"]
            csv_writer.writerow(row[:7] + [maturity_rating, maturity_reason] + row[7:])
            logger.info("Wrote row for route \"%s\"", route)


if __name__ == "__main__":
    configure_logging(logger)
    process_csv()