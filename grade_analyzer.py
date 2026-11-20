import csv
import json
import statistics
from pathlib import Path

BASE_FOLDER = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_FOLDER / "settings.json"
PREVIOUS_TERM_FILE = BASE_FOLDER / "term1.csv"
CURRENT_TERM_FILE = BASE_FOLDER / "term2.csv"
OUTPUT_FOLDER = BASE_FOLDER / "output"

SUBJECTS = ["Maths", "English", "Science"]
COMPONENTS = ["Coursework", "Exam"]
HIGH_SCORE_MARK = 80

DEFAULT_SETTINGS = {
    "weights": {"Coursework": 0.4, "Exam": 0.6},
    "pass_mark": 60,
    "grade_boundaries": {"A": 90, "B": 80, "C": 70, "D": 60, "F": 0},
}

MENU = """
1  View class report
2  Add student
3  Edit a score
4  Remove student
5  Search and filter
6  Grade chart
7  Compare with previous term
8  Save reports and report cards
9  Quit"""

CHOICES_THAT_NEED_STUDENTS = ["1", "5", "6", "8"]


def load_settings(path):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Could not read {path.name}, using default settings.")
        return DEFAULT_SETTINGS


def parse_score(text):
    text = text.strip()
    if text == "":
        raise ValueError("blank cell")
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a number")
    if not 0 <= number <= 100:
        raise ValueError(f"{text} is not between 0 and 100")
    return number


def read_student_row(row):
    name = (row.get("Name") or "").strip()
    if name == "":
        raise ValueError("Name is blank")
    subjects = {}
    for subject in SUBJECTS:
        subjects[subject] = {}
        for component in COMPONENTS:
            column = f"{subject}_{component}"
            try:
                subjects[subject][component] = parse_score(row.get(column) or "")
            except ValueError as problem:
                raise ValueError(f"{column}: {problem}")
    return name, subjects


def load_students(path):
    students = {}
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    except FileNotFoundError:
        print(f"File not found: {path.name}")
        return students
    for row_number, row in enumerate(rows, start=2):
        try:
            name, subjects = read_student_row(row)
            students[name] = subjects
        except ValueError as problem:
            print(f"{path.name} row {row_number} skipped: {problem}")
    return students


def remove_float_noise(number):
    return round(number, 10)


def weighted_score(parts, weights):
    return remove_float_noise(sum(parts[component] * weights[component] for component in COMPONENTS))


def grade_letters_best_first(settings):
    boundaries = settings["grade_boundaries"]
    return sorted(boundaries, key=lambda letter: boundaries[letter], reverse=True)


def letter_grade(average, settings):
    for letter in grade_letters_best_first(settings):
        if average >= settings["grade_boundaries"][letter]:
            return letter


def rank_students(results):
    best_first = sorted(results, key=lambda result: (-result["average"], result["name"].casefold()))
    for result in best_first:
        result["rank"] = 1 + sum(other["average"] > result["average"] for other in best_first)
    return best_first


def score_students(students, settings):
    results = []
    for name, subjects in students.items():
        subject_scores = {
            subject: weighted_score(subjects[subject], settings["weights"])
            for subject in SUBJECTS
        }
        average = remove_float_noise(statistics.mean(subject_scores.values()))
        results.append({
            "name": name,
            "subject_scores": subject_scores,
            "average": average,
            "grade": letter_grade(average, settings),
        })
    return rank_students(results)


def class_summary(results):
    averages = [result["average"] for result in results]
    subject_means = {
        subject: statistics.mean(result["subject_scores"][subject] for result in results)
        for subject in SUBJECTS
    }
    return {
        "average": statistics.mean(averages),
        "median": statistics.median(averages),
        "std_dev": statistics.pstdev(averages),
        "top": results[0],
        "lowest": results[-1],
        "subject_means": subject_means,
        "strongest_subject": max(subject_means, key=subject_means.get),
        "weakest_subject": min(subject_means, key=subject_means.get),
    }


def names_or_none(names):
    return ", ".join(sorted(names)) or "None"


def table_row(result, name_width):
    subject_columns = "".join(f"{result['subject_scores'][subject]:>10.2f}" for subject in SUBJECTS)
    return (
        f"{result['rank']:<6}{result['name']:<{name_width}}"
        f"{subject_columns}{result['average']:>10.2f}{result['grade']:>8}"
    )


def results_table(results):
    name_width = max([len("Student")] + [len(result["name"]) for result in results]) + 2
    subject_headers = "".join(f"{subject:>10}" for subject in SUBJECTS)
    header = f"{'Rank':<6}{'Student':<{name_width}}{subject_headers}{'Average':>10}{'Grade':>8}"
    return "\n".join([header] + [table_row(result, name_width) for result in results])


def class_report(results, settings):
    summary = class_summary(results)
    top, lowest = summary["top"], summary["lowest"]
    below_pass_mark = [r["name"] for r in results if r["average"] < settings["pass_mark"]]
    above_high_mark = [r["name"] for r in results if r["average"] > HIGH_SCORE_MARK]
    subject_averages = "    ".join(
        f"{subject} {mean:.1f}" for subject, mean in summary["subject_means"].items()
    )
    return "\n".join([
        results_table(results),
        "",
        f"Class average: {summary['average']:.1f}    "
        f"Top: {top['name']} ({top['average']:.1f})    "
        f"Lowest: {lowest['name']} ({lowest['average']:.1f})",
        f"Median: {summary['median']:.1f}    Standard deviation: {summary['std_dev']:.1f}",
        f"Subject averages: {subject_averages}",
        f"Strongest subject: {summary['strongest_subject']}    Weakest subject: {summary['weakest_subject']}",
        f"Below pass mark ({settings['pass_mark']}): {names_or_none(below_pass_mark)}",
        f"Above {HIGH_SCORE_MARK}: {names_or_none(above_high_mark)}",
    ])


def grade_chart(results, settings):
    lines = []
    for letter in grade_letters_best_first(settings):
        students_with_grade = sum(result["grade"] == letter for result in results)
        lines.append(f"{letter} | {'#' * students_with_grade} {students_with_grade}")
    return "\n".join(lines)


def report_card(result, summary):
    lines = [
        f"Report card: {result['name']}",
        f"Rank: {result['rank']}    Average: {result['average']:.2f}    Grade: {result['grade']}",
        "",
    ]
    for subject in SUBJECTS:
        score = result["subject_scores"][subject]
        class_mean = summary["subject_means"][subject]
        lines.append(f"{subject:<10}{score:>8.2f}    class average {class_mean:.2f}    ({score - class_mean:+.2f})")
    return "\n".join(lines)


def safe_filename(name):
    return "".join(letter if letter.isalnum() else "_" for letter in name)


def save_results_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Rank", "Name"] + SUBJECTS + ["Average", "Grade"])
        for result in results:
            subject_scores = [round(result["subject_scores"][subject], 2) for subject in SUBJECTS]
            writer.writerow([result["rank"], result["name"]] + subject_scores + [round(result["average"], 2), result["grade"]])


def save_report_cards(results):
    cards_folder = OUTPUT_FOLDER / "report_cards"
    cards_folder.mkdir(parents=True, exist_ok=True)
    summary = class_summary(results)
    for result in results:
        card_file = cards_folder / f"{safe_filename(result['name'])}.txt"
        card_file.write_text(report_card(result, summary), encoding="utf-8")


def save_everything(results, settings):
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    (OUTPUT_FOLDER / "class_report.txt").write_text(class_report(results, settings), encoding="utf-8")
    save_results_csv(results, OUTPUT_FOLDER / "calculated_results.csv")
    save_report_cards(results)
    print(f"Saved class report, results CSV and report cards to {OUTPUT_FOLDER}")


def most_improved(changes):
    biggest_gain = max(changes.values())
    return [name for name, change in changes.items() if change == biggest_gain] if biggest_gain > 0 else []


def most_declined(changes):
    biggest_drop = min(changes.values())
    return [name for name, change in changes.items() if change == biggest_drop] if biggest_drop < 0 else []


def compare_terms(previous_students, current_students, settings):
    before = {r["name"]: r["average"] for r in score_students(previous_students, settings)}
    after = {r["name"]: r["average"] for r in score_students(current_students, settings)}
    changes = {name: after[name] - before[name] for name in after if name in before}
    if not changes:
        return "No students appear in both terms."
    lines = [
        f"{name}: {before[name]:.2f} -> {after[name]:.2f} ({change:+.2f})"
        for name, change in sorted(changes.items())
    ]
    lines.append(f"Most improved: {names_or_none(most_improved(changes))}")
    lines.append(f"Most declined: {names_or_none(most_declined(changes))}")
    lines.append(f"Only in previous term: {names_or_none(before.keys() - after.keys())}")
    lines.append(f"Only in current term: {names_or_none(after.keys() - before.keys())}")
    return "\n".join(lines)


def ask_score(prompt):
    while True:
        try:
            return parse_score(input(prompt))
        except ValueError as problem:
            print(f"Invalid score: {problem}")


def ask_choice(prompt, options):
    while True:
        answer = input(f"{prompt} ({'/'.join(options)}): ").strip().title()
        if answer in options:
            return answer
        print(f"Please choose one of: {', '.join(options)}")


def ask_all_scores():
    scores = {}
    for subject in SUBJECTS:
        scores[subject] = {}
        for component in COMPONENTS:
            scores[subject][component] = ask_score(f"{subject} {component.lower()} score: ")
    return scores


def ask_existing_student(students):
    name = input("Student name: ").strip()
    if name not in students:
        print(f"No student called '{name}'.")
        return None
    return name


def add_student(students):
    name = input("New student name: ").strip()
    if name == "":
        print("Name cannot be blank.")
    elif name in students:
        print(f"{name} already exists.")
    else:
        students[name] = ask_all_scores()


def edit_score(students):
    name = ask_existing_student(students)
    if name is None:
        return
    subject = ask_choice("Subject", SUBJECTS)
    component = ask_choice("Component", COMPONENTS)
    students[name][subject][component] = ask_score("New score: ")


def remove_student(students):
    name = ask_existing_student(students)
    if name is not None:
        del students[name]
        print(f"Removed {name}.")


def search_students(results):
    choice = input("Search by 1) name  2) grade  3) subject score range: ").strip()
    if choice == "1":
        text = input("Name contains: ").strip().casefold()
        matches = [result for result in results if text in result["name"].casefold()]
    elif choice == "2":
        letter = input("Grade: ").strip().upper()
        matches = [result for result in results if result["grade"] == letter]
    elif choice == "3":
        subject = ask_choice("Subject", SUBJECTS)
        lowest = ask_score("Minimum score: ")
        highest = ask_score("Maximum score: ")
        matches = [result for result in results if lowest <= result["subject_scores"][subject] <= highest]
    else:
        print("Please choose 1, 2 or 3.")
        return
    print(results_table(matches) if matches else "No students match.")


def handle_choice(choice, students, settings):
    results = score_students(students, settings)
    if choice in CHOICES_THAT_NEED_STUDENTS and not results:
        print("No students loaded.")
    elif choice == "1":
        print(class_report(results, settings))
    elif choice == "2":
        add_student(students)
    elif choice == "3":
        edit_score(students)
    elif choice == "4":
        remove_student(students)
    elif choice == "5":
        search_students(results)
    elif choice == "6":
        print(grade_chart(results, settings))
    elif choice == "7":
        print(compare_terms(load_students(PREVIOUS_TERM_FILE), students, settings))
    elif choice == "8":
        save_everything(results, settings)
    else:
        print("Please choose a number from 1 to 9.")


def main():
    settings = load_settings(SETTINGS_FILE)
    students = load_students(CURRENT_TERM_FILE)
    while True:
        print(MENU)
        choice = input("Menu choice: ").strip()
        if choice == "9":
            break
        handle_choice(choice, students, settings)


if __name__ == "__main__":
    main()
