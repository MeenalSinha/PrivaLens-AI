"""
Synthetic dataset generator.

Produces demonstration datasets for healthcare, education and finance
presets, plus a matching auxiliary "attacker" dataset with overlapping
quasi-identifiers, so judges/users can run the full demo without
uploading real personal data. Vulnerabilities (small equivalence classes)
are intentionally created via a Zipf-like skew in the occupation/region
fields, not by directly writing risk numbers anywhere.
"""
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kabir",
               "Meera", "Nikhil", "Priya", "Rohan", "Saanvi", "Tara", "Yash", "Zara"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Gupta", "Reddy", "Nair", "Chatterjee",
              "Mehta", "Bose", "Kapoor"]
OCCUPATIONS = ["Software Engineer", "Nurse", "Teacher", "Accountant", "Doctor",
               "Electrician", "Architect", "Lawyer", "Pilot", "Chef", "Farmer", "Artist"]
HOSPITALS = ["City General", "St. Mary Hospital", "Metro Health Center", "Sunrise Clinic"]
DIAGNOSES = ["Hypertension", "Type 2 Diabetes", "Asthma", "Migraine", "Fracture",
             "Anxiety Disorder", "HIV", "Depression", "Arthritis", "Influenza"]
INSTITUTIONS = ["Delta University", "Northfield College", "Central Institute of Technology",
                 "Riverside University"]
COURSES = ["Computer Science", "Mechanical Engineering", "Economics", "Biology", "Law"]
CREDIT_CATEGORIES = ["Excellent", "Good", "Fair", "Poor"]
REGIONS = ["North", "South", "East", "West", "Central"]

PINCODE_PREFIXES = ["1100", "4000", "5600", "6000", "7000"]


def _rand_pincode():
    return random.choice(PINCODE_PREFIXES) + str(random.randint(10, 99))


def _rand_date(start_year=2023, end_year=2026):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return (start + timedelta(days=random.randint(0, delta.days))).strftime("%Y-%m-%d")


def _skewed_choice(options, skew=0.6):
    """Zipf-like skew so a handful of combinations become rare/unique -
    this is what creates genuine small equivalence classes downstream."""
    weights = [skew ** i for i in range(len(options))]
    total = sum(weights)
    weights = [w / total for w in weights]
    return random.choices(options, weights=weights, k=1)[0]


def generate_healthcare_dataset(n=500):
    rows = []
    for i in range(n):
        age = int(np.clip(np.random.normal(45, 18), 1, 95))
        rows.append({
            "PatientID": f"P{i:05d}",
            "Age": age,
            "Gender": random.choice(["Male", "Female"]),
            "Pincode": _rand_pincode(),
            "Occupation": _skewed_choice(OCCUPATIONS),
            "AdmissionDate": _rand_date(),
            "Hospital": random.choice(HOSPITALS),
            "Diagnosis": _skewed_choice(DIAGNOSES),
        })
    return pd.DataFrame(rows)


def generate_healthcare_auxiliary(main_df: pd.DataFrame, coverage=0.7):
    """Auxiliary attacker dataset: overlapping QI columns, no diagnosis,
    but includes name (this is the 'public' dataset an attacker already has)."""
    n = len(main_df)
    sample = main_df.sample(int(n * coverage), random_state=7)
    rows = []
    for _, r in sample.iterrows():
        rows.append({
            "FullName": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "Age": r["Age"] + random.choice([-1, 0, 0, 1]),
            "Gender": r["Gender"],
            "Pincode": r["Pincode"],
            "Occupation": r["Occupation"],
        })
    # add some noise records with no real match
    for _ in range(int(n * 0.2)):
        rows.append({
            "FullName": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "Age": random.randint(18, 90),
            "Gender": random.choice(["Male", "Female"]),
            "Pincode": _rand_pincode(),
            "Occupation": random.choice(OCCUPATIONS),
        })
    return pd.DataFrame(rows)


def generate_education_dataset(n=500):
    rows = []
    for i in range(n):
        rows.append({
            "StudentID": f"S{i:05d}",
            "Age": int(np.clip(np.random.normal(21, 3), 17, 40)),
            "Gender": random.choice(["Male", "Female"]),
            "Pincode": _rand_pincode(),
            "Institution": random.choice(INSTITUTIONS),
            "Course": _skewed_choice(COURSES),
            "Score": round(np.clip(np.random.normal(70, 15), 0, 100), 1),
            "AdmissionYear": random.randint(2021, 2026),
        })
    return pd.DataFrame(rows)


def generate_finance_dataset(n=500):
    rows = []
    for i in range(n):
        rows.append({
            "AccountID": f"A{i:05d}",
            "Age": int(np.clip(np.random.normal(40, 12), 18, 85)),
            "Region": random.choice(REGIONS),
            "Occupation": _skewed_choice(OCCUPATIONS),
            "IncomeBand": _skewed_choice(["<5L", "5-10L", "10-20L", "20-50L", "50L+"]),
            "TransactionDate": _rand_date(),
            "CreditCategory": _skewed_choice(CREDIT_CATEGORIES),
        })
    return pd.DataFrame(rows)


GENERATORS = {
    "healthcare": generate_healthcare_dataset,
    "education": generate_education_dataset,
    "finance": generate_finance_dataset,
}


def generate_preset(preset: str, n: int = 500):
    fn = GENERATORS.get(preset)
    if not fn:
        raise ValueError(f"Unknown preset '{preset}'. Choose from {list(GENERATORS)}")
    return fn(n)


def inject_quality_issues(df: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Deterministically injects REAL, detectable data-quality problems
    into an otherwise-clean synthetic dataset, for Judge Mode. Every
    problem introduced here is a genuine dataframe corruption (actual
    duplicate rows appended, actual NaNs written, actual malformed date
    strings written, actual mixed-case strings written) - the Quality
    Agent then has to find them for real, nothing is pre-labeled or
    faked as already-detected.
    """
    rng = random.Random(seed)
    out = df.copy()
    n = len(out)
    if n < 20:
        return out

    # 1. Duplicate rows: append exact copies of a random sample.
    dup_sample = out.sample(min(max(3, n // 15), 40), random_state=seed)
    out = pd.concat([out, dup_sample], ignore_index=True)

    # 2. Missing values: null out a chunk of a numeric-ish column and a
    #    categorical column, if present.
    numeric_cols = out.select_dtypes(include="number").columns.tolist()
    text_cols = out.select_dtypes(include="object").columns.tolist()
    if numeric_cols:
        col = numeric_cols[0]
        idx = out.sample(frac=0.12, random_state=seed).index
        out.loc[idx, col] = np.nan
    if len(text_cols) > 1:
        col = text_cols[1]
        idx = out.sample(frac=0.08, random_state=seed + 1).index
        out.loc[idx, col] = np.nan

    # 3. Case inconsistency: randomly re-case some values in a
    #    categorical text column (e.g. Gender: 'Male' -> 'MALE'/'male').
    case_col = next((c for c in text_cols if out[c].nunique(dropna=True) <= 10), None)
    if case_col:
        idx = out.sample(frac=0.3, random_state=seed + 2).index
        variants = [str.upper, str.lower, str.title]
        out.loc[idx, case_col] = out.loc[idx, case_col].astype(str).apply(
            lambda v: rng.choice(variants)(v)
        )

    # 4. Whitespace: pad some values in a text column with stray spaces.
    ws_col = next((c for c in text_cols if c != case_col), text_cols[0] if text_cols else None)
    if ws_col:
        idx = out.sample(frac=0.15, random_state=seed + 3).index
        out.loc[idx, ws_col] = out.loc[idx, ws_col].astype(str).apply(lambda v: f"  {v}  ")

    # 5. Malformed / inconsistent date formats, if a date-like column exists.
    date_col = next((c for c in out.columns if "date" in c.lower()), None)
    if date_col:
        idx = out.sample(frac=0.2, random_state=seed + 4).index

        def _reformat(v):
            try:
                d = pd.to_datetime(v)
            except Exception:
                return v
            fmt = rng.choice(["%d/%m/%Y", "%m-%d-%Y", "%Y.%m.%d", "%d %b %Y"])
            return d.strftime(fmt)

        out.loc[idx, date_col] = out.loc[idx, date_col].apply(_reformat)
        # and a handful of genuinely unparseable strings
        broken_idx = out.sample(min(5, n // 50 + 1), random_state=seed + 5).index
        out.loc[broken_idx, date_col] = "not-a-date"

    # 6. An outright constant column, to exercise that detector too.
    out["DataSource"] = "SyntheticGenerator"

    return out.reset_index(drop=True)
