import re
import logging
from fuzzywuzzy import fuzz
import json


def getInstructionInJson(filename):
    with open(filename, "r") as file:
        filetext = file.read()
        paragraphs = filetext.split("\n")
        jsonInstructions = []
        for paragraph in paragraphs:
            if paragraph.strip() == "":
                continue
            jsonInstructions.append({"instruction": paragraph})
        return jsonInstructions


def remove_instruction_text(inputString, jsonInstructions, logs):
    cleaned_text = inputString
    for instruction in jsonInstructions:
        instruction_text = instruction["instruction"].lower()
        input_lower = cleaned_text.lower()

        instruction_words = instruction_text.split()
        input_words = input_lower.split()

        i = 0
        while i < len(input_words):
            match_length = 0
            for j in range(len(instruction_words)):
                if (
                    i + j < len(input_words)
                    and fuzz.ratio(input_words[i + j], instruction_words[j]) > 80
                ):
                    match_length += 1
                else:
                    break

            if match_length >= 3:
                matched_text = " ".join(cleaned_text.split()[i: i + match_length])
                cleaned_text = cleaned_text.replace(matched_text, " ")
                logs.append(f"Removed instruction sequence: {matched_text}")
                i += match_length
            else:
                i += 1

        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    return cleaned_text, logs


def cleanString(inputString, jsonInstructions):
    logs = []
    inputString = inputString.replace("\n", " ")
    inputString = inputString.replace("’", "'")
    inputString = inputString.replace("“", '"')
    inputString = inputString.replace("”", '"')
    # legacy mojibake replacements
    inputString = inputString.replace("â€™", "'")
    inputString = inputString.replace("â€œ", '"')
    inputString = inputString.replace("â€", '"')
    inputString = re.sub(r"\s+", " ", inputString).strip()

    inputString, logs = remove_instruction_text(inputString, jsonInstructions, logs)

    wc = len(inputString.split())
    return inputString, wc, logs
