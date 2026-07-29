import json
import random
import os


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


def generate_questions(role, count=5):

    file_path = os.path.join(
        BASE_DIR,
        "data",
        f"{role}.json"
    )

    with open(file_path, "r", encoding="utf-8") as file:
        questions = json.load(file)

    return random.sample(
        questions,
        min(count, len(questions))
    )