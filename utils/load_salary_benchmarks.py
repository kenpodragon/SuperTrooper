"""
Salary benchmarks ETL loader for SuperTroopers.

Parses SALARY_RESEARCH.md into salary_benchmarks and cola_markets tables.

Usage:
    python load_salary_benchmarks.py [--file PATH] [--dry-run]

Source:
    Notes/SALARY_RESEARCH.md
"""

import argparse
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from db_config import get_db_config

DEFAULT_FILE = str(
    Path(__file__).resolve().parent.parent.parent / "Notes" / "SALARY_RESEARCH.md"
)

# COLA markets data (hardcoded from the doc since it's a fixed reference table)
COLA_MARKETS = [
    {"market_name": "Melbourne, FL", "col_index_approx": "96-98", "cola_factor": 1.00,
     "melbourne_200k_equiv": 200000, "melbourne_250k_equiv": 250000, "notes": "Baseline. No state income tax."},
    {"market_name": "National Average", "col_index_approx": "100", "cola_factor": 1.03,
     "melbourne_200k_equiv": 206000, "melbourne_250k_equiv": 258000, "notes": None},
    {"market_name": "Austin, TX", "col_index_approx": "105", "cola_factor": 1.08,
     "melbourne_200k_equiv": 216000, "melbourne_250k_equiv": 270000, "notes": "No state income tax."},
    {"market_name": "Boston, MA", "col_index_approx": "150", "cola_factor": 1.55,
     "melbourne_200k_equiv": 310000, "melbourne_250k_equiv": 388000, "notes": None},
    {"market_name": "Seattle, WA", "col_index_approx": "150", "cola_factor": 1.55,
     "melbourne_200k_equiv": 310000, "melbourne_250k_equiv": 388000, "notes": "No state income tax."},
    {"market_name": "San Francisco, CA", "col_index_approx": "180", "cola_factor": 1.86,
     "melbourne_200k_equiv": 372000, "melbourne_250k_equiv": 465000, "notes": None},
    {"market_name": "New York, NY", "col_index_approx": "190", "cola_factor": 1.96,
     "melbourne_200k_equiv": 392000, "melbourne_250k_equiv": 490000, "notes": None},
]

# Salary benchmarks data (parsed from the tables in the doc)
SALARY_BENCHMARKS = [
    # Tier 1: Executive / C-Suite
    {"role_title": "CTO", "tier": 1, "tier_name": "Executive / C-Suite",
     "national_median_range": "$285,000 - $327,000",
     "melbourne_range": "$180,000 - $260,000",
     "remote_range": "$220,000 - $350,000",
     "hcol_range": "$350,000 - $500,000+",
     "target_realistic": "YES. Sweet spot for mid-market and growth-stage companies."},
    {"role_title": "SVP / VP of Software Engineering", "tier": 1, "tier_name": "Executive / C-Suite",
     "national_median_range": "$240,000 - $345,000",
     "melbourne_range": "$180,000 - $280,000",
     "remote_range": "$200,000 - $400,000",
     "hcol_range": "$300,000 - $530,000+",
     "target_realistic": "YES. This is the bullseye range. National median sits right in target."},
    {"role_title": "VP of Digital Transformation / VP of Technology", "tier": 1, "tier_name": "Executive / C-Suite",
     "national_median_range": "$210,000 - $298,000",
     "melbourne_range": "$165,000 - $250,000",
     "remote_range": "$190,000 - $320,000",
     "hcol_range": "$280,000 - $400,000+",
     "target_realistic": "YES, at the upper end. Digital transformation is a premium title."},
    # Tier 2: Director-Level
    {"role_title": "Senior Director of Engineering / IT", "tier": 2, "tier_name": "Director-Level",
     "national_median_range": "$197,000 - $330,000",
     "melbourne_range": "$160,000 - $240,000",
     "remote_range": "$180,000 - $300,000",
     "hcol_range": "$255,000 - $437,000+",
     "target_realistic": "YES, but depends on company tier. Tech companies and large enterprises pay $200K+."},
    {"role_title": "Director of Software Engineering", "tier": 2, "tier_name": "Director-Level",
     "national_median_range": "$198,000 - $300,000",
     "melbourne_range": "$155,000 - $230,000",
     "remote_range": "$175,000 - $280,000",
     "hcol_range": "$270,000 - $453,000+",
     "target_realistic": "LIKELY YES. National median is near or above $200K."},
    {"role_title": "Head of Engineering", "tier": 2, "tier_name": "Director-Level",
     "national_median_range": "$210,000 - $282,000",
     "melbourne_range": "$160,000 - $240,000",
     "remote_range": "$180,000 - $300,000",
     "hcol_range": "$260,000 - $382,000+",
     "target_realistic": "YES. Common at startups/growth-stage where $200-250K base is standard."},
    # Tier 3: Senior IC / Manager (FAANG-Scale)
    {"role_title": "Senior Manager, SWE (FAANG)", "tier": 3, "tier_name": "Senior IC / Manager (FAANG-Scale)",
     "national_median_range": "$220,000 - $280,000 (base)",
     "melbourne_range": "N/A (FAANG has few FL offices)",
     "remote_range": "$220,000 - $280,000 (base) + $300-500K+ TC",
     "hcol_range": "$250,000 - $300,000 (base) + $400-700K+ TC",
     "target_realistic": "YES for base. FAANG Sr. Manager base regularly exceeds $200K."},
    {"role_title": "Senior Software Engineer / Staff Engineer", "tier": 3, "tier_name": "Senior IC / Manager (FAANG-Scale)",
     "national_median_range": "$165,000 - $230,000",
     "melbourne_range": "$130,000 - $185,000",
     "remote_range": "$160,000 - $250,000",
     "hcol_range": "$200,000 - $326,000+",
     "target_realistic": "STRETCH. Need Staff+ or FAANG to reliably hit $200K base."},
    {"role_title": "Software Architect / Principal Architect", "tier": 3, "tier_name": "Senior IC / Manager (FAANG-Scale)",
     "national_median_range": "$191,000 - $253,000",
     "melbourne_range": "$150,000 - $210,000",
     "remote_range": "$170,000 - $280,000",
     "hcol_range": "$232,000 - $393,000+",
     "target_realistic": "POSSIBLE. Principal Architects at large enterprises can hit $200K+."},
    {"role_title": "AI Architect / AI Engineering Lead", "tier": 3, "tier_name": "Senior IC / Manager (FAANG-Scale)",
     "national_median_range": "$179,000 - $260,000",
     "melbourne_range": "$150,000 - $220,000",
     "remote_range": "$180,000 - $330,000",
     "hcol_range": "$220,000 - $350,000+",
     "target_realistic": "YES, and trending higher. AI roles command significant premiums."},
    # Tier 4: Program Management
    {"role_title": "Technical Program Manager / Director of PM", "tier": 4, "tier_name": "Program Management",
     "national_median_range": "$162,000 - $210,000",
     "melbourne_range": "$135,000 - $185,000",
     "remote_range": "$150,000 - $230,000",
     "hcol_range": "$200,000 - $265,000+",
     "target_realistic": "AT DIRECTOR LEVEL, YES. Individual TPM roles top out at $160-180K base."},
    # Tier 5: Academia
    {"role_title": "Adjunct Faculty / Instructor (CS, AI)", "tier": 5, "tier_name": "Academia",
     "national_median_range": "$52,000 - $65,000 FTE-equivalent",
     "melbourne_range": "$40,000 - $55,000 (adjunct); $80,000 - $120,000 (full-time)",
     "remote_range": "$45,000 - $65,000 (adjunct, online)",
     "hcol_range": "$55,000 - $80,000 (adjunct)",
     "target_realistic": "NO. Not as primary income. Best as supplement or passion play."},
]


def load_data(conn, dry_run: bool = False):
    """Load salary benchmarks and COLA markets into the database."""
    cur = conn.cursor()

    if dry_run:
        print(f"DRY RUN: {len(COLA_MARKETS)} COLA markets, {len(SALARY_BENCHMARKS)} salary benchmarks")
        return

    # Clear and reload COLA markets
    cur.execute("DELETE FROM cola_markets")
    for m in COLA_MARKETS:
        cur.execute(
            """INSERT INTO cola_markets
                (market_name, col_index_approx, cola_factor, melbourne_200k_equiv, melbourne_250k_equiv, notes)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (m["market_name"], m["col_index_approx"], m["cola_factor"],
             m["melbourne_200k_equiv"], m["melbourne_250k_equiv"], m["notes"]),
        )
    print(f"Loaded {len(COLA_MARKETS)} COLA markets")

    # Clear and reload salary benchmarks
    cur.execute("DELETE FROM salary_benchmarks")
    for i, b in enumerate(SALARY_BENCHMARKS):
        cur.execute(
            """INSERT INTO salary_benchmarks
                (role_title, tier, tier_name, national_median_range, melbourne_range,
                 remote_range, hcol_range, target_realistic, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (b["role_title"], b["tier"], b["tier_name"],
             b["national_median_range"], b["melbourne_range"],
             b["remote_range"], b["hcol_range"], b["target_realistic"], i),
        )
    print(f"Loaded {len(SALARY_BENCHMARKS)} salary benchmarks")

    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Load salary benchmarks and COLA data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = get_db_config()
    conn = psycopg2.connect(**config)

    try:
        load_data(conn, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
