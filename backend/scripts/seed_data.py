"""Deterministic, idempotent demo-data seeder for the Nitivayu platform.

Seeds every sector the application supports so all portals are populated:
  * Universities (Jharkhand academic network)
  * Officers / admins
  * CSR industries
  * Citizen submissions + triaged problems with stable tracking tokens
  * Route assignments in every workflow state (pending review, offered, accepted)
  * Project teams with milestones for accepted challenges
  * CSR funding pledges

Safe to run repeatedly: existing demo records (tracking tokens prefixed
NITIVAYU-2026-JH-DEMO) are detected and skipped.

Run:  python -m scripts.seed_data
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select

from app.db.models import (
    AuditLog, Citizen, FundingLink, Industry, Milestone, Officer,
    Problem, ProjectTeam, RouteAssignment, Submission, University,
)
from app.db.session import AsyncSessionLocal

DEMO_TOKEN_PREFIX = "NITIVAYU-2026-JH-DEMO"
EMBEDDING_SEED = 26043  # deterministic vectors so reseeding is reproducible


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def fake_embedding() -> list[float]:
    rng = random.Random(EMBEDDING_SEED)
    return [rng.uniform(-1, 1) for _ in range(384)]


UNIVERSITIES = [
    {"name": "Birla Institute of Technology (BIT), Mesra", "short_code": "BIT_MESRA", "iic_code": "IIC-JH-BIT-01", "district": "Ranchi", "geo_lat": 23.4123, "geo_lng": 85.4399, "domain_specializations": ["Water Purification", "Remote Sensing & GIS", "Solid Waste Management", "Renewable Energy", "Environmental Engineering"], "active_capacity": 15, "nodal_contact_email": "iic.head@bitmesra.ac.in"},
    {"name": "National Institute of Technology (NIT), Jamshedpur", "short_code": "NIT_JSR", "iic_code": "IIC-JH-NIT-02", "district": "East Singhbhum", "geo_lat": 22.7766, "geo_lng": 86.1444, "domain_specializations": ["Industrial Effluent Treatment", "Metallurgical Innovation", "Civil Infrastructure", "IoT Sensor Networks"], "active_capacity": 12, "nodal_contact_email": "iic.coord@nitjsr.ac.in"},
    {"name": "Indian Institute of Technology (IIT-ISM), Dhanbad", "short_code": "IIT_ISM", "iic_code": "IIC-JH-ISM-03", "district": "Dhanbad", "geo_lat": 23.8143, "geo_lng": 86.4412, "domain_specializations": ["Mine Dust Suppression", "Heavy Metal Soil Remediation", "Clean Coal Technology", "Geotechnical Engineering"], "active_capacity": 15, "nodal_contact_email": "dean.rnd@iitism.ac.in"},
    {"name": "Central University of Jharkhand (CUJ)", "short_code": "CUJ_RANCHI", "iic_code": "IIC-JH-CUJ-04", "district": "Ranchi (Brambe)", "geo_lat": 23.3644, "geo_lng": 85.1581, "domain_specializations": ["Tribal Livelihoods", "Solar Microgrids", "Indigenous Forest Produce Processing", "Rural Healthcare Tech"], "active_capacity": 10, "nodal_contact_email": "iic@cuj.ac.in"},
    {"name": "Ranchi University", "short_code": "RANCHI_UNIV", "iic_code": "IIC-JH-RU-05", "district": "Ranchi", "geo_lat": 23.3700, "geo_lng": 85.3250, "domain_specializations": ["Community Health Monitoring", "Primary Education Technologies", "Botanical Herb Formulations", "Groundwater Surveying"], "active_capacity": 8, "nodal_contact_email": "research@ranchiuniversity.ac.in"},
    {"name": "XLRI Xavier School of Management", "short_code": "XLRI_JSR", "iic_code": "IIC-JH-XLRI-06", "district": "East Singhbhum", "geo_lat": 22.8028, "geo_lng": 86.1854, "domain_specializations": ["Dokra Artisan Supply Chains", "Rural Self-Help Group Economics", "CSR Policy Evaluation", "Public Administration Logistics"], "active_capacity": 10, "nodal_contact_email": "social.innovation@xlri.ac.in"},
]

OFFICERS = [
    {"name": "Anil Kumar", "department": "District Administration", "district": "Ranchi", "role": "district_officer", "email": "officer@nitivayu.gov.in", "password": "password123"},
    {"name": "Sunita Devi", "department": "Urban Development", "district": "Statewide", "role": "senior_officer", "email": "sunita.devi@jharkhand.gov.in", "password": "password123"},
    {"name": "Ramesh Singh", "department": "IT & E-Governance", "district": "Statewide", "role": "state_admin", "email": "admin@nitivayu.in", "password": "admin"},
]

INDUSTRIES = [
    {"name": "Tata Steel", "sector": "Steel", "csr_focus_areas": ["Healthcare", "Education", "Livelihood", "Environment"], "csr_budget_inr": 500000000.00, "contact_person": "J. Irani", "contact_email": "csr@tatasteel.com"},
    {"name": "Central Coalfields Limited (CCL)", "sector": "Mining", "csr_focus_areas": ["Environment", "Infrastructure", "Health"], "csr_budget_inr": 300000000.00, "contact_person": "R. Sharma", "contact_email": "csr@ccl.gov.in"},
    {"name": "Bharat Coking Coal Limited (BCCL)", "sector": "Mining", "csr_focus_areas": ["Environment", "Education", "Sanitation"], "csr_budget_inr": 250000000.00, "contact_person": "K. Singh", "contact_email": "csr@bccl.gov.in"},
    {"name": "Vedanta Resources", "sector": "Mining", "csr_focus_areas": ["Livelihood", "Health", "Education"], "csr_budget_inr": 400000000.00, "contact_person": "M. Agarwal", "contact_email": "csr@vedanta.com"},
]

# Pipeline stages exercised by the demo:
#   pending  -> officer review queue (PENDING_OFFICER_REVIEW, PENDING_APPROVAL assignment)
#   offered  -> university inbox     (ROUTED problem, OFFERED assignment)
#   accepted -> university projects  (ACCEPTED problem, team + milestones)
#   funded   -> CSR portal           (ROUTED/ACCEPTED problem + funding pledge)
CHALLENGES = [
    {"title": "Water Contamination in Garhwa", "summary": "Garhwa block ke handpump mein fluoride aur peela rang aa raha hai, baccho ke daant kharab ho rahe hain.", "category": "Water", "severity": 5, "district": "Garhwa", "stage": "accepted", "university": "BIT_MESRA", "team": {"mentor": "Dr. P. Sharma", "lead": "Anjali Kumari", "proposal": "Low-cost Fluoride Mitigation Units for Garhwa Handpumps"}, "pledges": [("csr@tatasteel.com", 1500000.00)]},
    {"title": "Industrial Pollution at Adityapur", "summary": "Adityapur industrial area toxic effluent is being discharged into Subarnarekha River.", "category": "Environment", "severity": 5, "district": "East Singhbhum", "stage": "accepted", "university": "NIT_JSR", "team": {"mentor": "Prof. R. Verma", "lead": "Saurabh Mahato", "proposal": "Effluent Quality Sensor Network for Subarnarekha Basin"}, "pledges": [("csr@ccl.gov.in", 2500000.00), ("csr@tatasteel.com", 1000000.00)]},
    {"title": "Coal Mining Dust in Jharia", "summary": "झरिया कोयला ढुलाई से भारी धूल प्रदूषण और बच्चों में अस्थमा बढ़ रहा है।", "category": "Environment", "severity": 4, "district": "Dhanbad", "stage": "offered", "university": "IIT_ISM"},
    {"title": "Exploitation of Tribal Handicrafts", "summary": "Khunti Dokra and Lac artisans getting exploited by middlemen, need direct catalog linkage.", "category": "Livelihood", "severity": 3, "district": "Khunti", "stage": "offered", "university": "XLRI_JSR"},
    {"title": "Poor School Infrastructure in Torpa", "summary": "तोरपा आवासीय विद्यालय में बरसात की वजह से छत टपक रही है और बिजली बैकअप नहीं है।", "category": "Education", "severity": 4, "district": "Khunti", "stage": "offered", "university": "BIT_MESRA"},
    {"title": "Lack of Primary Healthcare", "summary": "No functioning PHC in block, villagers rely on quacks for emergency care.", "category": "Health", "severity": 5, "district": "Simdega", "stage": "offered", "university": "RANCHI_UNIV"},
    {"title": "Crop Failure due to unpredictable rain", "summary": "Paddy crops drying up due to delayed monsoon and lack of irrigation channels.", "category": "Agriculture", "severity": 4, "district": "Palamu", "stage": "offered", "university": "CUJ_RANCHI"},
    {"title": "Frequent Power Cuts", "summary": "Rural areas face 14-hour power cuts hindering daily life and small businesses.", "category": "Energy", "severity": 4, "district": "Gumla", "stage": "pending", "university": "BIT_MESRA"},
    {"title": "Broken Bridge Access", "summary": "Panchayat main bridge broken after floods, disconnecting 3 villages from the block office.", "category": "Infrastructure", "severity": 5, "district": "Lohardaga", "stage": "pending", "university": "NIT_JSR"},
    {"title": "Open Defecation Issues", "summary": "Community toilets broken, leading to open defecation and hygiene issues near the market.", "category": "Sanitation", "severity": 3, "district": "Deoghar", "stage": "pending", "university": "BIT_MESRA"},
    {"title": "Pension Scheme Delays", "summary": "Elderly citizens not receiving pension for 6 months despite repeated applications.", "category": "Governance", "severity": 4, "district": "Ranchi", "stage": "pending", "university": "XLRI_JSR"},
    {"title": "Forest Fire Incidents", "summary": "Frequent forest fires destroying valuable timber and wildlife habitat in Saranda.", "category": "Environment", "severity": 5, "district": "West Singhbhum", "stage": "pending", "university": "IIT_ISM"},
    {"title": "Malnutrition among children", "summary": "Anganwadi centers lack proper nutritional supplies and growth monitoring.", "category": "Health", "severity": 4, "district": "Pakur", "stage": "pending", "university": "RANCHI_UNIV"},
    {"title": "Solar Pump Malfunctions", "summary": "Solar irrigation pumps broken for months, affecting paddy and vegetable farming.", "category": "Energy", "severity": 3, "district": "Dumka", "stage": "pending", "university": "CUJ_RANCHI"},
    {"title": "Lack of Cold Storage", "summary": "Farmers throwing away tomatoes due to lack of cold storage facilities at the mandi.", "category": "Agriculture", "severity": 4, "district": "Hazaribagh", "stage": "pending", "university": "NIT_JSR"},
]

MILESTONE_PLAN = [
    (1, "M1: Feasibility Study & Field Survey", "VERIFIED", -30),
    (2, "M2: Prototype Design & Lab Testing", "SUBMITTED", 15),
    (3, "M3: Field Validation & Handover", "PENDING", 60),
]

STAGE_STATUS = {
    "pending": ("PENDING_TRIAGE", "PENDING_OFFICER_REVIEW", "PENDING_APPROVAL"),
    "offered": ("ROUTED", "ROUTED", "OFFERED"),
    "accepted": ("ROUTED", "ACCEPTED", "ACCEPTED"),
}


async def seed(session) -> None:
    now = datetime.now(timezone.utc)

    universities: dict[str, University] = {}
    for data in UNIVERSITIES:
        existing = (await session.execute(select(University).where(University.short_code == data["short_code"]))).scalars().first()
        if existing:
            # Reconcile drift (e.g. rows pre-created by init_db.sql with older emails)
            # so the documented demo sign-ins always resolve to this workspace.
            if existing.nodal_contact_email != data["nodal_contact_email"]:
                existing.nodal_contact_email = data["nodal_contact_email"]
            universities[data["short_code"]] = existing
            continue
        university = University(**data, capability_embedding=fake_embedding())
        session.add(university)
        await session.flush()
        universities[data["short_code"]] = university
    print(f"Universities: {len(universities)} available")

    for data in OFFICERS:
        existing = (await session.execute(select(Officer).where(Officer.email == data["email"]))).scalars().first()
        if existing:
            continue
        session.add(Officer(name=data["name"], department=data["department"], district=data["district"], role=data["role"], email=data["email"], password_hash=get_password_hash(data["password"])))
    print(f"Officers: {len(OFFICERS)} ensured")

    industries: dict[str, Industry] = {}
    for data in INDUSTRIES:
        existing = (await session.execute(select(Industry).where(Industry.contact_email == data["contact_email"]))).scalars().first()
        if existing:
            industries[data["contact_email"]] = existing
            continue
        industry = Industry(**data)
        session.add(industry)
        await session.flush()
        industries[data["contact_email"]] = industry
    print(f"Industries: {len(industries)} available")

    already_seeded = (await session.execute(
        select(Submission.submission_id).where(Submission.tracking_token == f"{DEMO_TOKEN_PREFIX}01")
    )).scalars().first()
    if already_seeded:
        print("Demo challenges already seeded; skipping challenge pipeline.")
        await session.commit()
        return

    for index, challenge in enumerate(CHALLENGES, start=1):
        token = f"{DEMO_TOKEN_PREFIX}{index:02d}"
        submission_status, problem_status, assignment_status = STAGE_STATUS[challenge["stage"]]

        citizen = Citizen(phone_encrypted=b"demo_encrypted_phone", language_pref="hi")
        session.add(citizen)
        await session.flush()

        submission = Submission(
            citizen_id=citizen.citizen_id,
            raw_text=challenge["summary"],
            geo_district=challenge["district"],
            tracking_token=token,
            status=submission_status,
            created_at=now - timedelta(days=len(CHALLENGES) - index + 5),
        )
        session.add(submission)
        await session.flush()

        problem = Problem(
            submission_id=submission.submission_id,
            title=challenge["title"],
            summary=challenge["summary"],
            category=challenge["category"],
            severity_score=challenge["severity"],
            confidence_score=0.85,
            summary_embedding=fake_embedding(),
            status=problem_status,
        )
        session.add(problem)
        await session.flush()

        university = universities[challenge["university"]]
        assignment = RouteAssignment(
            problem_id=problem.problem_id,
            university_id=university.university_id,
            rank_order=1,
            match_score=0.9 if challenge["stage"] != "pending" else 0.72,
            score_breakdown={"semantic": 0.9, "theme": 0.85, "capacity": 0.8, "geo": 0.95},
            sla_deadline=now + timedelta(days=7),
            status=assignment_status,
            responded_at=now - timedelta(days=2) if challenge["stage"] == "accepted" else None,
        )
        session.add(assignment)
        await session.flush()

        if challenge["stage"] == "accepted":
            team_info = challenge["team"]
            team = ProjectTeam(
                assignment_id=assignment.assignment_id,
                problem_id=problem.problem_id,
                university_id=university.university_id,
                faculty_mentor_name=team_info["mentor"],
                student_lead_name=team_info["lead"],
                proposal_title=team_info["proposal"],
                status="IN_PROGRESS",
            )
            session.add(team)
            await session.flush()
            for num, title, status_value, due_offset in MILESTONE_PLAN:
                session.add(Milestone(team_id=team.team_id, milestone_num=num, title=title, status=status_value, due_date=now + timedelta(days=due_offset)))

        for pledge_email, amount in challenge.get("pledges", []):
            industry = industries.get(pledge_email)
            if industry:
                session.add(FundingLink(problem_id=problem.problem_id, industry_id=industry.industry_id, pledged_amount_inr=amount, status="PLEDGED"))

        session.add(AuditLog(entity_type="submission", entity_id=str(submission.submission_id), action="SUBMITTED", actor_id="citizen", actor_role="citizen", after_snapshot={"status": submission_status}))
        if challenge["stage"] != "pending":
            session.add(AuditLog(entity_type="problem", entity_id=str(problem.problem_id), action="OFFICER_APPROVE", actor_id="officer@nitivayu.gov.in", actor_role="officer", after_snapshot={"status": problem_status}))
        if challenge["stage"] == "accepted":
            session.add(AuditLog(entity_type="problem", entity_id=str(problem.problem_id), action="UNIVERSITY_ACCEPT", actor_id=university.nodal_contact_email, actor_role="university", after_snapshot={"status": "ACCEPTED"}))

    await session.commit()
    print(f"Seeded {len(CHALLENGES)} demo challenges across all pipeline stages.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed(session)
    print("\nSeed completed. Demo sign-ins (any password):")
    print("  Officer/Admin : officer@nitivayu.gov.in  |  admin@nitivayu.in")
    print("  University    : iic.head@bitmesra.ac.in  |  iic.coord@nitjsr.ac.in")
    print("  CSR Industry  : csr@tatasteel.com")
    print(f"  Track tokens  : {DEMO_TOKEN_PREFIX}01 .. {DEMO_TOKEN_PREFIX}{len(CHALLENGES):02d}")


if __name__ == "__main__":
    asyncio.run(main())
