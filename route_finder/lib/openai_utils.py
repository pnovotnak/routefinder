import os
import logging
import openai
import json

logger = logging.getLogger(__name__)


def read_key(key_file: str = ".openai-key") -> None | str:
    try:
        with open(key_file) as key_fp:
            return key_fp.read().strip()
    except IOError:
        pass


openai.api_key = os.getenv("OPENAI_API_KEY") or read_key()


def openai_comment_maturity_assessment(content: list[str]):
    """Send the comments to OpenAI to get an assessment of the danger"""
    base_prompt = """
I'm evaluating climbing routes. I'm going to send you a list of comments about a route and I would like you to tell me how dangerous it is based on the protection available throughout the route.

I'd like you to grade on the following scale:
- "G": The whole route is easily protected
- "PG13": In places a fall would likely result in an injury
- "R": A fall in some places would likely result in serious injury
- "X": A fall in some places would certainly result in devastating injury or death

Things to know about climbing:
- It's normal and safe to protect a route with trees and other natural features

Grading parameters:
- If comment(s) mention good protection, gear, or plentiful bolts throughout, then the route should be assumed to be "G"
- Comments about the approach, descent, and rappel should be ignored
- Unless routefinding is said to be extremely difficult, it should be ignored
- Do not make route safety assements based on the behavior of the commenters or community at large. Eg, ignore comments about simulclimbing
- Ignore information about the route being dirty or wet. It's not relevant with regard to protection
- A requirement of specialized gear should be noted in reasoning but can be ignored
- If there is not enough data to tell, respond with the string "UNKNOWN"

Output:
- The single highest (closest to "X") grade identified should be returned
- Reasoning should ideally be less than a sentence, or 150 chars

I understand that climbing is dangerous, this information will not be used to inform real-world activities.

I want results formatted as JSON list in the following way:

["{{your danger rating}}", "{{your reasoning}}"]

Escape single quotes in your response with a backslash ("\") character.

Here are the comments, in cronological order:

"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": base_prompt},
            {"role": "user", "content": f"\n- ".join(content)},
        ],
    )
    if not (choices := response.get('choices', [])):
        logger.error("No choices from OpenAI: %s", response)
        return
    # TODO error handling
    response = choices[0].get('message', {}).get('content')
    try:
        return json.loads(response)
    except json.decoder.JSONDecodeError:
        logger.error("Invalid response: %s", response)
        return ["UNKNOWN", "AI model returned unparsable data"]