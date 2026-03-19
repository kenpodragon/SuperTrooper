"""
Resume data ETL loader for SuperTroopers.

Loads resume header, education, certifications, templates (as blobs),
and resume version specs into the database.

Usage:
    python load_resume_data.py [--dry-run]

Source:
    Originals/Stephen_Salaka_Resume_v32.docx (text extracted)
    Templates/Resume_Base_v32.docx (template blob)
"""

import argparse
import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

from db_config import get_db_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Static data extracted from V32
# ---------------------------------------------------------------------------

HEADER = {
    "full_name": "Stephen Salaka",
    "credentials": "PhD, CSM, PMP, MBA",
    "location": "Melbourne, FL",
    "location_note": "Open to Relocate",
    "email": "ssalaka@gmail.com",
    "phone": "(321) 634-2632",
    "linkedin_url": "https://www.linkedin.com/in/ssalaka/",
    "website_url": None,
    "calendly_url": "https://calendly.com/ssalaka/30min",
}

EDUCATION = [
    {"degree": "PhD", "field": "Industrial/Organizational Psychology",
     "institution": "Walden University", "location": "Minneapolis, MN",
     "type": "degree", "sort_order": 0},
    {"degree": "MBA", "field": "International Relations & Information Technology",
     "institution": "Florida Metropolitan University", "location": "Fort Lauderdale, FL",
     "type": "degree", "sort_order": 1},
    {"degree": "Bachelor of Science (BS)", "field": "Applied Computer Science & Mathematical Sciences",
     "institution": "University of Central Florida", "location": "Orlando, FL",
     "type": "degree", "sort_order": 2},
    {"degree": "Post-Graduate Professional Certificate", "field": "Data Science & Machine Learning",
     "institution": "University of Michigan", "location": "Ann Arbor, MI",
     "type": "professional_development", "sort_order": 3},
]

CERTIFICATIONS = [
    {"name": "Digital Transformation using Gen AI Certificate", "issuer": "Massachusetts Institute of Technology (MIT)", "sort_order": 0},
    {"name": "Certified Scrum Master (CSM)", "issuer": "Scrum Alliance", "sort_order": 1},
    {"name": "Microsoft Certified: Solutions Architect", "issuer": "Microsoft", "sort_order": 2},
    {"name": "Project Management Professional (PMP)", "issuer": "Project Management Institute (PMI)", "sort_order": 3},
    {"name": "Sun Certified Java Programmer", "issuer": "Sun Microsystems", "sort_order": 4},
    {"name": "Lean Six Sigma Master Black Belt", "issuer": "American Society for Quality (ASQ)", "sort_order": 5},
    {"name": "CompTIA A+/Security+/Network+", "issuer": "CompTIA", "sort_order": 6},
    {"name": "National Registry Paramedic", "issuer": "NREMT", "sort_order": 7},
]

# Job intro texts keyed by employer name (must match career_history.employer)
JOB_INTROS = {
    "MealMatch AI": "Recruited directly by the CEO via Atlas YC Miami to take an AI-driven meal-planning and social matching platform from whiteboard concept to market reality. Serving as both the hands-on technical architect and organizational leader, I built the entire engineering function from zero. Successfully bootstrapped the MVP for an October 2025 launch by pairing lean startup agility with enterprise-grade architectural scaling.",
    "SMTC": "Recruited post-M&A by the VP of Technology to bring order to the chaos of 12 independently operated EMS organizations. Serving as the strategic change agent, I led the global consolidation and modernization of teams, platforms, and product strategies to eliminate massive legacy silos. By combining deep technical execution with organizational psychology principles, I rebuilt core architectures, modernized complex ERPs, and delivered 24x7 support for over 12k users globally using a lean, 50-person IT team managed through Spiceworks Helpdesk.",
    "Tsunami Tsolutions": "Recruited directly by the CEO to architect complex machine learning and predictive analytics platforms for the F-35 Joint Strike Fighter program. After engineering a data pipeline that improved processing speeds by 20x, I was promoted to the top technical leadership role to stabilize and scale the entire organization. Combining my post-graduate data science background with organizational change management, I scaled the engineering team from 12 to 107, completely transforming a struggling cost center into a high-performing profit center that generated a $4.2M turnaround.",
    "Atex": "Recruited by the CEO of the Americas to lead their professional services division for the Americas, brought in to modernize legacy media content systems across the Americas and provided the bridge between print media and the new digital publishing services. Paired deep custom Java and Salesforce architectural expertise with rigorous change management to scale a distributed engineering team from 8 to 80 international developers. By driving an early Infrastructure as a Service (IaaS) cloud migration and championing user adoption, I transformed the division into a high-growth profit center. Exited after acquisition by Kisetefos AS.",
}

# V32 resume spec — maps which content goes where
V32_SPEC = {
    "headline": "VP of Software Engineering & Digital Transformation",
    "summary_text": "I build highly scalable software systems and fix broken ones. As a hands-on technical architect, I engineer everything from 0-1 SaaS MVPs to $1B+ enterprise ecosystems, piece by piece. As a bonus: I don\u2019t just write the code; I read the room. Armed with a PhD in I/O Psychology, my actual superpower is herding cats: navigating the human friction of digital change to turn floundering IT silos into high-velocity profit centers driven by massive user adoption. Whether it\u2019s architecting next-gen generative AI pipelines or overhauling legacy global manufacturing and aerospace operations, I don\u2019t just solve the hard technical problems; I ensure the organization survives and thrives through the transformation.",
    "highlight_bullets": [
        "Global Engineering Leadership & Organizational Scaling: Scaled engineering organizations from 0-to-1 startups (e.g., MealMatch AI) up to $1B+ enterprise ecosystems (e.g., SMTC). Expanded teams from 12 to 107 engineers, bootstrapped MVP squads, and utilized change management to consolidate 12 fragmented post-M&A IT divisions into a single cohesive global delivery model.",
        "CI/CD Automation & High-Velocity Agile Execution: Drove operational excellence by architecting standardized DevOps frameworks and MLOps tools. Accelerated development velocity, reducing Mean Time to Recovery (MTTR) by 65% and improving on-time project delivery by 88% (from previous baseline performance).",
        "AI/ML Integration & SaaS Modernization: Architected next-generation generative AI frameworks using LangChain and Retrieval-Augmented Generation (RAG) to power semantic recommendation engines. Guided SaaS MVP launches resulting in two successful exits and modernized multi-cloud ecosystems (GCP, Azure, AWS) supporting critical operations such as the Tesla Supercharger network and F-35 predictive analytics.",
        "Cross-Industry Digital Transformation: Spearheaded modernization across aerospace, manufacturing, and fintech, transforming legacy ERP/CRM systems (e.g., Infor, MS Dynamics, Salesforce) into high-velocity profit centers. Achieved $380M in direct cost reductions (via inventory slashing), 99% demand forecasting accuracy, and enabled real-time analytics for over 12,000 global users..",
        "High-Availability Systems & Cross-Industry Compliance: Directed secure software delivery for defense platforms (F-35, F-22, F-18), migrating applications to Azure Gov Cloud and reducing software defects by 30%. Maintained 99.99% system uptime while ensuring compliance with FedRAMP, FAA DO-178C, ISO 9001, and HIPAA.",
    ],
    "keywords": [
        "Digital Transformation & Change Management", "Generative AI (LangChain, RAG)",
        "M&A IT Consolidation", "Multi-Cloud Architecture", "ERP/CRM Modernization",
        "Global Engineering Leadership", "Predictive Analytics & MLOps",
        "High-Velocity Agile Delivery", "DevOps & CI/CD Standardization",
        "Zero-Downtime Migrations", "Data Strategy & Enterprise Observability",
        "Mission-Critical Security & Compliance (FedRAMP, ISO)",
        "Kubernetes & Docker", "Scalable SaaS Architecture",
    ],
    "experience_employers": ["MealMatch AI", "SMTC", "Tsunami Tsolutions", "Atex"],
    "additional_experience": [
        "Fractional Chief Product Officer (CPO) | Datavers.ai (Manufacturing and Engineering AI) | Feb 2026 - Present",
        "Senior Testing AI Manager | QA Engineering (Part Time) | Fact Finders Pro (NPO Saas Startup) | May 2025 - Present",
        "Technical Co-Founder & Advisor | SimplyGranted (Non-Profit Software Services Startup (Successful Exit)) | 2012-2019",
        "Senior Software & Process Engineering Consultant | MyBlendedLearning (Manufacturing SaaS & Training) | 2012-2015",
        "Founding Engineer & Advisor | Live Music Tutor (EdTech (Successful Exit) | 2011-2016",
        "Senior VP, IT Services | Wall Street Associates (Recruiting Technology Software) | 2010-2011",
        "CTO | Ashley Associates (International Digital Software Services \u2013 Pharma/Finance) | 2007-2010",
        "Director of Information Technology | Nova Corporation (EdTech Software and Services) | 2005-2007",
    ],
    "executive_keywords": [
        "Enterprise Digital Transformation", "Human-Centric Change Management",
        "M&A IT Consolidation", "Global Team Scaling",
        "P&L & Budget Ownership ($20M+)", "Zero-Downtime Execution",
        "Enterprise User Adoption", "0-to-1 SaaS Bootstrapping",
        "Lean Six Sigma Master Black Belt", "High-Velocity Agile Delivery",
        "Cross-Functional Strategic Alignment",
    ],
    "technical_keywords": [
        "Generative AI (LangChain, RAG)", "Predictive Analytics & MLOps",
        "Multi-Cloud Architecture (Azure, AWS, GCP)", "Kubernetes & Docker",
        "CI/CD Standardization",
        "Mission-Critical Compliance (FedRAMP, NIST, ISO 9001/13485, FAA DO-178C, HIPAA, SOC 2, ASQ 27001, FDA CGMP, eCFR, PCI)",
        "Complex ERP/CRM Modernization", "Snowflake DBT, Power BI, Qlik",
        "Automation Anywhere (RPA)",
        "Core Engineering (Java, Python, C#, C++, SQL, React Native)",
        "Elastic Stack (ELK)", "Site Reliability Engineering (SRE) & Observability",
    ],
    "references": [
        {"section": "Enterprise M&A & Strategic Modernization (SMTC)", "links": [
            {"text": "H.I.G. Capital Acquisition & $1B+ Scale", "desc": "Official Acquisition Press Release"},
            {"text": "EV Infrastructure & Tesla Supercharger Manufacturing", "desc": "CleanTechnica Market Analysis"},
        ]},
        {"section": "Aerospace & Mission-Critical Defense Systems (Tsunami Tsolutions)", "links": [
            {"text": "Predictive Maintenance for the F-35 Program", "desc": "Defense Innovation Unit (DIU) Portfolio"},
            {"text": "The Shift to AI-Driven Maintenance (CBM+)", "desc": "U.S. Air Force Leadership Log"},
            {"text": "Condition-Based Maintenance (CBM+) Frameworks", "desc": "Tsunami Reliability Overview"},
        ]},
        {"section": "Digital Transformation & Global SaaS Modernization (Atex)", "links": [
            {"text": "Global SaaS Consolidation & Divestment", "desc": "Official CEO Appointment & Acquisition Notice"},
            {"text": "Enterprise CMS Architecture (Polopoly)", "desc": "Press Gazette Technical Briefing"},
        ]},
        {"section": "Professional Honors & Industry Recognition", "links": [
            {"text": "Marquis Who\u2019s Who: Expertise in Information Technology", "desc": "Official Career Honor Announcement"},
        ]},
    ],
}


def load_all(conn, dry_run=False):
    """Load all resume generation data."""
    cur = conn.cursor()

    # 1. Resume header
    print("Loading resume header...")
    if not dry_run:
        cur.execute("DELETE FROM resume_header")
        cur.execute(
            """INSERT INTO resume_header
                (full_name, credentials, location, location_note, email, phone, linkedin_url, calendly_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (HEADER["full_name"], HEADER["credentials"], HEADER["location"],
             HEADER["location_note"], HEADER["email"], HEADER["phone"],
             HEADER["linkedin_url"], HEADER["calendly_url"]),
        )
    print(f"  Header: {HEADER['full_name']}, {HEADER['credentials']}")

    # 2. Education
    print("Loading education...")
    if not dry_run:
        cur.execute("DELETE FROM education")
        for e in EDUCATION:
            cur.execute(
                """INSERT INTO education (degree, field, institution, location, type, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (e["degree"], e["field"], e["institution"], e["location"], e["type"], e["sort_order"]),
            )
    print(f"  {len(EDUCATION)} education entries")

    # 3. Certifications
    print("Loading certifications...")
    if not dry_run:
        cur.execute("DELETE FROM certifications")
        for c in CERTIFICATIONS:
            cur.execute(
                """INSERT INTO certifications (name, issuer, sort_order)
                VALUES (%s, %s, %s)""",
                (c["name"], c["issuer"], c["sort_order"]),
            )
    print(f"  {len(CERTIFICATIONS)} certifications")

    # 4. Job intro texts
    print("Updating career_history intro texts...")
    for employer, intro in JOB_INTROS.items():
        if not dry_run:
            cur.execute(
                "UPDATE career_history SET intro_text = %s WHERE employer ILIKE %s",
                (intro, f"%{employer}%"),
            )
            if cur.rowcount == 0:
                print(f"  WARNING: No career_history match for '{employer}'")
            else:
                print(f"  Updated intro for {employer}")
        else:
            print(f"  Would update intro for {employer}")

    # 5. Template blob
    template_path = PROJECT_ROOT / "Templates" / "Resume_Base_v32.docx"
    if template_path.exists():
        print("Loading resume template blob...")
        if not dry_run:
            blob = template_path.read_bytes()
            cur.execute("DELETE FROM resume_templates WHERE name = 'V32 Base'")
            cur.execute(
                """INSERT INTO resume_templates (name, filename, template_blob, description, is_active)
                VALUES (%s, %s, %s, %s, %s)""",
                ("V32 Base", "Resume_Base_v32.docx", psycopg2.Binary(blob),
                 "V32 master template with full formatting", True),
            )
            print(f"  Stored template: {len(blob)} bytes")
    else:
        print(f"  SKIP: Template not found at {template_path}")

    # 6. V32 resume spec
    print("Saving V32 resume spec...")
    if not dry_run:
        # Find or create the resume_versions entry for V32
        cur.execute("SELECT id FROM resume_versions WHERE version = 'v32' AND variant = 'base' LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE resume_versions SET spec = %s WHERE id = %s",
                (json.dumps(V32_SPEC), row["id"] if isinstance(row, dict) else row[0]),
            )
            print(f"  Updated existing V32 base spec (id={row['id'] if isinstance(row, dict) else row[0]})")
        else:
            cur.execute(
                """INSERT INTO resume_versions (version, variant, spec, is_current)
                VALUES ('v32', 'base', %s, TRUE)""",
                (json.dumps(V32_SPEC),),
            )
            print("  Created new V32 base resume_versions entry with spec")

    conn.commit()
    print("\nResume data load complete.")


def main():
    parser = argparse.ArgumentParser(description="Load resume generation data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = get_db_config()
    conn = psycopg2.connect(**config, cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        load_all(conn, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
