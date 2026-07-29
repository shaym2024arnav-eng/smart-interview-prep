import re


def evaluate_answer(answer, keywords):

    answer = answer.lower()

    answer = re.sub(r"[^a-zA-Z0-9 ]", "", answer)

    matched_keywords = []

    for keyword in keywords:
        if keyword.lower() in answer:
            matched_keywords.append(keyword)

    score = int(
        (len(matched_keywords) / len(keywords)) * 100
    )

    if score >= 80:
        feedback = "Excellent answer."

    elif score >= 50:
        feedback = "Good answer, but add more details."

    else:
        feedback = "Needs improvement. Cover more key concepts."

    return {
        "score": score,
        "feedback": feedback,
        "matched_keywords": matched_keywords
    }