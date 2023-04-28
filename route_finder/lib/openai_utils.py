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


def openai_comment_maturity_assessment(description: str, comments: list[str], ticks: list[str]):
    """Send the comments to OpenAI to get an assessment of the danger"""
    base_prompt = f"""
I'm evaluating climbing routes. I'm going to send you a list of comments about a route. Tell me how dangerous it is based on the protection available throughout the route.

Grade on the following scale:
- "G": Whole route is easily protected
- "PG13": In places a fall would likely result in a minor injury
- "R": In places a fall would likely result in serious injury
- "X": In places a fall would certainly result in devastating injury or death

Things to know about climbing:
- It's normal and safe to protect a route with trees and other natural features
- Gear is easy to acquire

Danger rating:
- Consider only "Route description" if it claims the route is well protected or beginner friendly
- Runouts of more than 15 feet are an automatic "PG13" rating
- Runouts of more than 30 feet are an automatic "R" rating
- If comment(s) mention good protection, gear, or plentiful bolts throughout, then the route should be assumed to be "G", even if it can be small or hard to place
- Ignore sentiment about:
    - Difficult placements
    - Specialized gear
    - Routefinding
    - Getting off route
    - Approach
    - Descent
    - Rappel
- If the comment says it is hard to protect, but mentions a specific piece of gear that would help or work, ignore the comment
- No safety assements based on the behavior of the commenters or community at large. Eg, ignore comments about simulclimbing
- Ignore all information about the route being dirty or wet
- If there is not enough data to tell, rate it "UNKNOWN"

Additional notes:
- List any specialized gear requirements (eg sizes, what brands work well)
- Note any places where climbers often get lost
- Note rope length
- Note if the route is dirty

Input:
- Everything is in cronological order

Output:
- The single highest (closest to "X") grade identified should be returned
- Reasoning and notes sections should ideally be less than a sentence, or 150 chars

I want results formatted as JSON list in the following way:

["{{danger rating}}", "{{danger reasoning}}", "{{additional notes, unrelated to danger}}"]

Escape single quotes in your response with a backslash ("\") character.
"""
    messages = [
        {"role": "user", "content": base_prompt},
        {"role": "user", "content": "Route description:\n{description}"},
    ]
    if comments:
        comments_prompt = "\n- ".join(comments)
        messages.append({
            "role": "user", 
            "content":f"Comments about the route:\n{comments_prompt}"
        })
    if ticks:
        ticks_prompt = "\n- ".join(ticks)
        messages.append({
            "role": "user", 
            "content": f"Personal notes about completions and attempts:\n{ticks_prompt}"
        })

    tokens = sum([len((m['content'].split())) for m in messages])
    log_message = f"{tokens} / 8192 tokens used"
    if tokens / 8192 > 0.9:
        logger.warning(log_message)
    elif tokens / 8192 > 1:
        logger.error(log_message)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
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