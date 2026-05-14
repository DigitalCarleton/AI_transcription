import argparse
import csv
import os
import re


def normalize_text(text):
    
    text = text.lower()
    text = text.replace("£", "pounds")
    text = re.sub(r"[.,]", "", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
    


def read_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_csv_column(path, column_name):
    texts = []

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if column_name not in reader.fieldnames:
            raise ValueError(
                f"Column '{column_name}' not found in {path}. "
                f"Available columns: {reader.fieldnames}"
            )

        for row in reader:
            if row[column_name] is not None:
                texts.append(row[column_name])

    return " ".join(texts)


def read_transcript(path, column_name=None):
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        return read_txt(path)

    elif ext == ".csv":
        if column_name is None:
            raise ValueError(
                f"{path} is a CSV file, so you must provide --ai-column or --truth-column."
            )
        return read_csv_column(path, column_name)

    else:
        raise ValueError("Only .txt and .csv files are supported.")


def edit_distance_counts(reference_tokens, hypothesis_tokens):
    """
    Computes S, D, I using dynamic programming.

    reference_tokens = correct transcript tokens
    hypothesis_tokens = AI transcript tokens
    """

    n = len(reference_tokens)
    m = len(hypothesis_tokens)

    # dp[i][j] = minimum edit distance between
    # reference_tokens[:i] and hypothesis_tokens[:j]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    backtrace = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
        backtrace[i][0] = "D"

    for j in range(1, m + 1):
        dp[0][j] = j
        backtrace[0][j] = "I"

    for i in range(1, n + 1):
        for j in range(1, m + 1):

            if reference_tokens[i - 1] == hypothesis_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
                backtrace[i][j] = "OK"
            else:
                substitution = dp[i - 1][j - 1] + 1
                deletion = dp[i - 1][j] + 1
                insertion = dp[i][j - 1] + 1

                best = min(substitution, deletion, insertion)
                dp[i][j] = best

                if best == substitution:
                    backtrace[i][j] = "S"
                elif best == deletion:
                    backtrace[i][j] = "D"
                else:
                    backtrace[i][j] = "I"

    # Count S, D, I by walking backward
    i, j = n, m
    substitutions = 0
    deletions = 0
    insertions = 0

    while i > 0 or j > 0:
        action = backtrace[i][j]

        if action == "OK":
            i -= 1
            j -= 1
        elif action == "S":
            substitutions += 1
            i -= 1
            j -= 1
        elif action == "D":
            deletions += 1
            i -= 1
        elif action == "I":
            insertions += 1
            j -= 1
        else:
            break

    return substitutions, deletions, insertions


def calculate_wer(reference_text, hypothesis_text):
    reference_words = reference_text.split()
    hypothesis_words = hypothesis_text.split()

    s, d, i = edit_distance_counts(reference_words, hypothesis_words)

    n = len(reference_words)
    wer = (s + d + i) / n if n > 0 else 0

    return {
        "WER": wer,
        "WER_percent": wer * 100,
        "S": s,
        "D": d,
        "I": i,
        "N": n,
    }


def calculate_cer(reference_text, hypothesis_text):
    # Remove spaces for character-level comparison.
    # If you want spaces to count as characters, delete these two lines.
    reference_chars = list(reference_text.replace(" ", ""))
    hypothesis_chars = list(hypothesis_text.replace(" ", ""))

    s, d, i = edit_distance_counts(reference_chars, hypothesis_chars)

    n = len(reference_chars)
    cer = (s + d + i) / n if n > 0 else 0

    return {
        "CER": cer,
        "CER_percent": cer * 100,
        "S": s,
        "D": d,
        "I": i,
        "N": n,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Calculate WER and CER between AI transcription and ground truth."
    )

    parser.add_argument(
        "--ai",
        required=True,
        help="Path to AI transcription file, .txt or .csv",
    )

    parser.add_argument(
        "--truth",
        required=True,
        help="Path to correct transcription file, .txt or .csv",
    )

    parser.add_argument(
        "--ai-column",
        default=None,
        help="Column name for AI transcript if AI file is CSV",
    )

    parser.add_argument(
        "--truth-column",
        default=None,
        help="Column name for correct transcript if truth file is CSV",
    )

    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Do not lowercase or normalize whitespace",
    )

    args = parser.parse_args()

    ai_text = read_transcript(args.ai, args.ai_column)
    truth_text = read_transcript(args.truth, args.truth_column)
    print("args:", args)
    print("AI path:", repr(args.ai))
    print("Truth path:", repr(args.truth))
    print("Current working directory:", os.getcwd())
    print("AI exists?", os.path.exists(args.ai))
    print("Truth exists?", os.path.exists(args.truth))

    print("AI text raw:", repr(ai_text))
    print("Truth text raw:", repr(truth_text))
    print("AI length:", len(ai_text))
    print("Truth length:", len(truth_text))
    if not args.no_normalize:
        ai_text = normalize_text(ai_text)
        truth_text = normalize_text(truth_text)

    wer_result = calculate_wer(truth_text, ai_text)
    cer_result = calculate_cer(truth_text, ai_text)

    print("\n=== Transcription Evaluation ===")

    print("\nWER: Word Error Rate")
    print(f"WER: {wer_result['WER_percent']:.2f}%")
    print(f"S substitutions: {wer_result['S']}")
    print(f"D deletions:     {wer_result['D']}")
    print(f"I insertions:    {wer_result['I']}")
    print(f"N total words:   {wer_result['N']}")

    print("\nCER: Character Error Rate")
    print(f"CER: {cer_result['CER_percent']:.2f}%")
    print(f"S substitutions:     {cer_result['S']}")
    print(f"D deletions:         {cer_result['D']}")
    print(f"I insertions:        {cer_result['I']}")
    print(f"N total characters:  {cer_result['N']}")

    print("\nAccuracy-style estimate")
    print(f"Word accuracy:      {100 - wer_result['WER_percent']:.2f}%")
    print(f"Character accuracy: {100 - cer_result['CER_percent']:.2f}%")

    print()
#python accuracy.py --ai ai.txt --truth truth.txt


if __name__ == "__main__":
    main()