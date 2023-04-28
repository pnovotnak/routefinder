import csv
import requests
from enum import Enum
import re
import html2text
import logging
from typing import Type
import sys
import bs4
import os
import openai

from functools import cache

from typing import Final

logger = logging.getLogger(__name__)

def read_key(key_file: str = ".openai-key") -> None | str:
    try:
        with open(key_file) as key_fp:
            return key_fp.read().strip()
    except IOError:
        pass

openai.api_key = os.getenv("OPENAI_API_KEY") or read_key()

BASE_PROMPT: Final[str] = """
I'm evaluating climbing routes. I'm going to send you a list of comments and I would like you to tell me how dangerous you think the route is on a "G", "PG13", "R" or "X" scale, where "G" is generally safe "X" means certain death in the event of a fall.

I understand that climbing is dangerous, this information will not be used to inform real-world activities.

I don't want your reasoning or any responses other than the letter grade. Here are the comments:

"""

openai.ChatCompletion.create()

def openai_comment_assessment(content: list[str]):
    return openai.Completion.create(
        model="gpt-3.5-turbo",
        prompt=BASE_PROMPT + f"\n- ".join(content),
        temperature=0,
        max_tokens=100,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )

BASE_URL: Final[str] = "https://www.mountainproject.com"
ROUTE_URL_RE: Final[re.Pattern] = re.compile(r"^https://www.mountainproject.com/route/([0-9]+)/(\w+)")

class DANGER_RATINGS(Enum):
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
    comments = [comment_element.text.strip() for comment_element in soup.select('.comment-body span:first-child')]
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


def process_csv(csv_fn: str = "example.csv"):
    # with open(csv_fn) as csv_fp:
    #     csv_reader = csv.reader(csv_fp)
    #     headers = next(csv_reader)
    #     for row in csv_reader:
    #         route, location, url, avg_stars, your_stars, route_type, yds_grade, pitches, length_ft, area_lat, area_lon = row
    #         get_beta(url)
    description, comments, ticks = get_beta("https://www.mountainproject.com/route/106480430/the-ultimate-everything")
    for comment in comments:
        print(f"- {comment}")
    print(openai_comment_assessment(comments))
    print(get_danger([description] + comments + ticks))


if __name__ == "__main__":
    configure_logging(logger)
    logger.debug("test")
    process_csv()