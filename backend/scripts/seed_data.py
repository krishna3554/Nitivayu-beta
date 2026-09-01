import asyncio
import os
import bcrypt
import json
import asyncpg
from datetime import datetime, timezone
import random

DB_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://nitivayu_user:nitivayu_secure_password@localhost:5432/nitivayu_db"
).replace("+asyncpg", "")

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

UNIVERSITIES = [
    {
        "name": "Birla Institute of Technology (BIT), Mesra",
        "short_code": "BIT_MESRA",
        "iic_code": "IIC-JH-BIT-01",
        "district": "Ranchi",
        "geo_lat": 23.4123,
        "geo_lng": 85.4399,
        "domain_specializations": ["Water Purification", "Remote Sensing & GIS", "Solid Waste Management", "Renewable Energy", "Environmental Engineering"],
        "active_capacity": 15,
        "nodal_contact_email": "iic.head@bitmesra.ac.in"
    },
    {
        "name": "National Institute of Technology (NIT), Jamshedpur",
        "short_code": "NIT_JSR",
        "iic_code": "IIC-JH-NIT-02",
        "district": "East Singhbhum",
        "geo_lat": 22.7766,
        "geo_lng": 86.1444,
        "domain_specializations": ["Industrial Effluent Treatment", "Metallurgical Innovation", "Civil Infrastructure", "IoT Sensor Networks"],
        "active_capacity": 12,
        "nodal_contact_email": "iic.coord@nitjsr.ac.in"
    },
    {
        "name": "Indian Institute of Technology (IIT-ISM), Dhanbad",
        "short_code": "IIT_ISM",
        "iic_code": "IIC-JH-ISM-03",
        "district": "Dhanbad",
        "geo_lat": 23.8143,
        "geo_lng": 86.4412,
        "domain_specializations": ["Mine Dust Suppression", "Heavy Metal Soil Remediation", "Clean Coal Technology", "Geotechnical Engineering"],
        "active_capacity": 15,
        "nodal_contact_email": "dean.rnd@iitism.ac.in"
    },
    {
        "name": "Central University of Jharkhand (CUJ)",
        "short_code": "CUJ_RANCHI",
        "iic_code": "IIC-JH-CUJ-04",
        "district": "Ranchi (Brambe)",
        "geo_lat": 23.3644,
        "geo_lng": 85.1581,
        "domain_specializations": ["Tribal Livelihoods", "Solar Microgrids", "Indigenous Forest Produce Processing", "Rural Healthcare Tech"],
        "active_capacity": 10,
        "nodal_contact_email": "iic@cuj.ac.in"
    },
    {
        "name": "Ranchi University",
        "short_code": "RANCHI_UNIV",
        "iic_code": "IIC-JH-RU-05",
        "district": "Ranchi",
        "geo_lat": 23.3700,
        "geo_lng": 85.3250,
        "domain_specializations": ["Community Health Monitoring", "Primary Education Technologies", "Botanical Herb Formulations", "Groundwater Surveying"],
        "active_capacity": 8,
        "nodal_contact_email": "research@ranchiuniversity.ac.in"
    },
    {
        "name": "XLRI Xavier School of Management",
        "short_code": "XLRI_JSR",
        "iic_code": "IIC-JH-XLRI-06",
        "district": "East Singhbhum",
        "geo_lat": 22.8028,
        "geo_lng": 86.1854,
        "domain_specializations": ["Dokra Artisan Supply Chains", "Rural Self-Help Group Economics", "CSR Policy Evaluation", "Public Administration Logistics"],
        "active_capacity": 10,
        "nodal_contact_email": "social.innovation@xlri.ac.in"
    }
]

CHALLENGES = [
    {"title": "Water Contamination in Garhwa", "summary": "Garhwa block ke handpump mein fluoride aur peela rang aa raha hai, baccho ke daant kharab ho rahe hain.", "category": "Water", "severity": 5, "district": "Garhwa"},
    {"title": "Industrial Pollution at Adityapur", "summary": "Adityapur industrial area toxic effluent is being discharged into Subarnarekha River.", "category": "Environment", "severity": 5, "district": "East Singhbhum"},
    {"title": "Coal Mining Dust in Jharia", "summary": "झरिया कोयला ढुलाई से भारी धूल प्रदूषण और बच्चों में अस्थमा बढ़ रहा है।", "category": "Environment", "severity": 4, "district": "Dhanbad"},
    {"title": "Exploitation of Tribal Handicrafts", "summary": "Khunti Dokra and Lac artisans getting exploited by middlemen, need direct catalog linkage.", "category": "Livelihood", "severity": 3, "district": "Khunti"},
    {"title": "Poor School Infrastructure in Torpa", "summary": "तोरपा आवासीय विद्यालय में बरसात की वजह से छत टपक रही है और बिजली बैकअप नहीं है।", "category": "Education", "severity": 4, "district": "Khunti"},
    {"title": "Lack of Primary Healthcare", "summary": "No functioning PHC in block, villagers rely on quacks.", "category": "Health", "severity": 5, "district": "Simdega"},
    {"title": "Crop Failure due to unpredictable rain", "summary": "Paddy crops drying up due to delayed monsoon and lack of irrigation.", "category": "Agriculture", "severity": 4, "district": "Palamu"},
    {"title": "Frequent Power Cuts", "summary": "Rural areas face 14-hour power cuts hindering daily life.", "category": "Energy", "severity": 4, "district": "Gumla"},
    {"title": "Broken Bridge Access", "summary": "Panchayat main bridge broken after floods, disconnecting 3 villages.", "category": "Infrastructure", "severity": 5, "district": "Lohardaga"},
    {"title": "Open Defecation Issues", "summary": "Community toilets broken, leading to open defecation and hygiene issues.", "category": "Sanitation", "severity": 3, "district": "Deoghar"},
    {"title": "Pension Scheme Delays", "summary": "Elderly citizens not receiving pension for 6 months.", "category": "Governance", "severity": 4, "district": "Ranchi"},
    {"title": "Forest Fire Incidents", "summary": "Frequent forest fires destroying valuable timber and wildlife.", "category": "Environment", "severity": 5, "district": "West Singhbhum"},
    {"title": "Malnutrition among children", "summary": "Anganwadi centers lack proper nutritional supplies.", "category": "Health", "severity": 4, "district": "Pakur"},
    {"title": "Solar Pump Malfunctions", "summary": "Solar irrigation pumps broken, affecting farming.", "category": "Energy", "severity": 3, "district": "Dumka"},
    {"title": "Lack of Cold Storage", "summary": "Farmers throwing away tomatoes due to lack of cold storage facilities.", "category": "Agriculture", "severity": 4, "district": "Hazaribagh"}
]

OFFICERS = [
    {"name": "Anil Kumar", "department": "District Administration", "district": "Ranchi", "role": "district_officer", "email": "anil.kumar@jharkhand.gov.in", "password": "password123"},
    {"name": "Sunita Devi", "department": "Urban Development", "district": "Statewide", "role": "senior_officer", "email": "sunita.devi@jharkhand.gov.in", "password": "password123"},
    {"name": "Ramesh Singh", "department": "IT & E-Governance", "district": "Statewide", "role": "state_admin", "email": "admin@nitivayu.in", "password": "admin"}
]

INDUSTRIES = [
    {"name": "Tata Steel", "sector": "Steel", "csr_focus_areas": ["Healthcare", "Education", "Livelihood", "Environment"], "csr_budget_inr": 500000000.00, "contact_person": "J. Irani", "contact_email": "csr@tatasteel.com"},
    {"name": "Central Coalfields Limited (CCL)", "sector": "Mining", "csr_focus_areas": ["Environment", "Infrastructure", "Health"], "csr_budget_inr": 300000000.00, "contact_person": "R. Sharma", "contact_email": "csr@ccl.gov.in"},
    {"name": "Bharat Coking Coal Limited (BCCL)", "sector": "Mining", "csr_focus_areas": ["Environment", "Education", "Sanitation"], "csr_budget_inr": 250000000.00, "contact_person": "K. Singh", "contact_email": "csr@bccl.gov.in"},
    {"name": "Vedanta Resources", "sector": "Mining", "csr_focus_areas": ["Livelihood", "Health", "Education"], "csr_budget_inr": 400000000.00, "contact_person": "M. Agarwal", "contact_email": "csr@vedanta.com"}
]

async def generate_fake_embedding():
    # Return a 384-d random vector as a string array for pgvector
    vec = [random.uniform(-1, 1) for _ in range(384)]
    return f"[{','.join(map(str, vec))}]"

async def main():
    print(f"Connecting to {DB_URL}...")
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Failed to connect to database. Ensure it is running. Error: {e}")
        return

    print("Seeding universities...")
    for u in UNIVERSITIES:
        await conn.execute(
            '''
            INSERT INTO universities (name, short_code, iic_code, district, geo_lat, geo_lng, domain_specializations, active_capacity, nodal_contact_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (short_code) DO NOTHING
            ''',
            u['name'], u['short_code'], u['iic_code'], u['district'], u['geo_lat'], u['geo_lng'], u['domain_specializations'], u['active_capacity'], u['nodal_contact_email']
        )
    
    print("Seeding officers...")
    for o in OFFICERS:
        pwd_hash = get_password_hash(o['password'])
        await conn.execute(
            '''
            INSERT INTO officers (name, department, district, role, email, password_hash)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (email) DO NOTHING
            ''',
            o['name'], o['department'], o['district'], o['role'], o['email'], pwd_hash
        )

    print("Seeding industries...")
    for i in INDUSTRIES:
        await conn.execute(
            '''
            INSERT INTO industries (name, sector, csr_focus_areas, csr_budget_inr, contact_person, contact_email)
            VALUES ($1, $2, $3, $4, $5, $6)
            ''',
            i['name'], i['sector'], i['csr_focus_areas'], i['csr_budget_inr'], i['contact_person'], i['contact_email']
        )

    print("Seeding challenges (submissions and problems)...")
    for c in CHALLENGES:
        citizen_id = await conn.fetchval(
            '''
            INSERT INTO citizens (phone_encrypted, language_pref)
            VALUES ($1, $2)
            RETURNING citizen_id
            ''',
            b'fake_encrypted_phone', 'hi'
        )

        submission_id = await conn.fetchval(
            '''
            INSERT INTO submissions (citizen_id, raw_text, geo_district, status)
            VALUES ($1, $2, $3, 'ROUTED')
            RETURNING submission_id
            ''',
            citizen_id, c['summary'], c['district']
        )

        embedding_str = await generate_fake_embedding()
        await conn.execute(
            '''
            INSERT INTO problems (submission_id, title, summary, category, severity_score, summary_embedding, status)
            VALUES ($1, $2, $3, $4, $5, $6::vector, 'PENDING_OFFICER_REVIEW')
            ''',
            submission_id, c['title'], c['summary'], c['category'], c['severity'], embedding_str
        )

    print("Seeding completed successfully!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
