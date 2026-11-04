# WellNest Hospitals, Bengaluru — Comprehensive Master Operating Compendium & Institutional Guide
**Confidential Institutional Reference | Hospital Ownership & Administrative Manual**
**Location:** 42 Outer Ring Road, Marathahalli, Bengaluru, Karnataka 560037
**Landmark:** Adjacent to Innovative Multiplex | **Plot Area:** 3.8 Acres | **Built-up Area:** 420,000 sq. ft.
**Licensing & Accreditations:** NABH (National Accreditation Board for Hospitals), NABL (ISO 15189:2022 Lab Accreditation), AERB (Atomic Energy Regulatory Board), CDSCO (Pharmacy License), Fire & Bio-Medical Waste Clearance (KSPCB).

> **Status in this repo (added 4 Nov 2026):** reference content source for the website's `/policies`, `/about` and FAQ
> pages. Where this document disagrees with the live database or `app/kb.py`, **the live data wins** — see
> `docs/FRONTEND_REDESIGN_PROMPT.md` §12. Do not copy this file into `data/hospital/` as-is: the RAG loader needs
> plain speakable sentences, not tables.

---

## 1. Executive Hospital Profile & Capacities

| Operational Metric | Institutional Capacity / Specification |
| :--- | :--- |
| **Total Licensed Bed Strength** | **250 Inpatient Beds** (including 45 Intensive Care Beds and 15 Daycare Surgery Beds) |
| **Daily OPD Footfall Capacity** | 1,200 to 1,500 Outpatients per day across 32 Consultation Chambers |
| **Operating Theatres** | 6 Ultra-Clean Modular Operating Theatres with Class 10,000 Laminar Airflow + 1 Cardiac Cath Lab |
| **Diagnostic Imaging** | 2 High-Field 3.0T MRI Scanners, 2 128-Slice Dual-Energy CT Scanners, 4 Digital X-Ray, 6 High-Res 4D USG |
| **Emergency Bay** | 12 Dedicated Resuscitation & Triage Beds, 2 Negative-Pressure Isolation Bays, 1 Minor OT |
| **Workforce** | 45 Senior Consultants, 60 Duty Medical Officers/Registrars, 280 Registered Nurses, 140 Allied Paramedics |
| **Helpline Numbers** | Front Desk: `080 4000 1234` · Emergency Trauma Line: `080 4000 108` · Insurance Desk: `080 4000 1250` |
| **AI Virtual Reception DID** | **`+1 218 443 7744`** (Global Voice Trunk connected to Talkdesk Autopilot & Render Backend) |
| **Digital Web Presence** | Patient Portal & Staff Console: `https://teamxyz-mcp.onrender.com` |

---

## 2. Campus Master Layout, Gates & Floor-by-Floor Directory

### Campus Access & Entrance Gates
- **Gate 1 (West Wing — 24/7 Emergency & Trauma Access):** Dedicated entry for ambulances, emergency drop-offs, and the 24/7 Emergency Department (Entrance B). Zero-grade ramp, 24/7 porter station, direct pneumatic tube connection to the blood bank.
- **Gate 2 (North Wing — Main Hospital Entrance & OPD Atrium):** Primary entrance for outpatient clinics, diagnostic imaging, visitor lobby and valet drop-off. Automated revolving doors, central concierge reception, wheelchair dispatch hub, coffee kiosk.
- **Gate 3 (East Wing — Service & Logistics / Parking Entry):** Inbound ramp for multi-level basement parking (P1 & P2), bio-medical waste vehicle bay, liquid oxygen tank farm (10,000 L cryogenic storage), pharmacy bulk deliveries.
- **Gate 4 (South Wing — Staff Entry & Mortuary Exit):** Biometric staff turnstiles, auditorium access, private mortuary dispatch bay.

### Floor-by-Floor Directory

```
[ Floor 5 ] === Surgical Complex (6 Modular OTs, Recovery PACU, Cath Lab, CSSD Sterile Supply)
[ Floor 4 ] === Specialty Inpatient Wards, Orthopaedics, Nephrology & 20-Bed Dialysis Center, Endocrinology
[ Floor 3 ] === Cardiology, Neurology, Gastroenterology, Pulmonology OPD & Endoscopy Suite
[ Floor 2 ] === Women & Child Center (OBG, Paediatrics), Dermatology, ENT, Ophthalmology, Daycare Surgery
[ Floor 1 ] === Executive Health Checkup Lounge, Blood Bank, Multifaith Prayer Room, Administration, TPA Billing
[ Ground  ] === Main Atrium, Central Reception, 24/7 ER (Entrance B), 24/7 Pharmacy, Cafeteria, ATM Hub
[Basement 1] === Central Diagnostic Imaging (3T MRI, 128-Slice CT, X-Ray), NABL Pathology Labs, Records Room
[Basement 2] === Multi-Level Patient Parking (P1/P2 - 280 Cars, 450 Two-Wheelers, 8 EV Fast Chargers)
```

---

## 3. The 14 Clinical Specialties & Medical Faculty Directory

> **Note:** the live `doctors` table is the authority for who consults, on which days, at what fee. This list is
> background for the website's department pages only.

Every doctor is verified on the Karnataka Medical Council (KMC) registry and maintains regular OPD chambers and operative schedules.

### 1. Cardiology (Floor 3 — OPD Suite 310-314)
*Scope: Interventional cardiology, coronary angiography, angioplasty, pacemaker implantation, heart failure clinic, 2D Echo, TMT, Holter.*
- **Dr. Rajesh Iyer** (MBBS, MD, DM Cardiology) | 24 Yrs | English, Tamil, Hindi | **₹1,200** | OPD-310 | Mon, Wed, Fri (10:00–13:00) | *Chief Interventional Cardiologist (heavily booked — priority waitlist active)*
- **Dr. Kavya Reddy** (MBBS, MD, DM Cardiology) | 15 Yrs | English, Telugu, Kannada | **₹1,200** | OPD-311 | Tue, Thu, Sat (14:00–17:00) | *Heart Failure & Women's Heart Specialist*
- **Dr. Suresh Menon** (MBBS, DNB Cardiology) | 11 Yrs | English, Malayalam, Hindi | **₹1,000** | OPD-312 | Mon, Tue, Thu, Fri (16:00–19:00) | *Preventive Cardiology & Echo Specialist*
- **Dr. Farzana Begum** (MBBS, MD Med, DM) | 8 Yrs | English, Hindi, Urdu, Kannada | **₹900** | OPD-313 | Wed, Sat (09:00–12:00) | *Hypertension & Dyslipidemia Consultant*
- **Dr. Imran Qureshi** (MBBS, MD, DM Cardiology) | 30 Yrs | English, Hindi, Urdu | **₹1,800** | OPD-314 | Tue, Fri (10:00–12:00) | *Emeritus Interventionalist & Complex TAVR Specialist*

### 2. Orthopaedics & Joint Replacement (Floor 4 — OPD Suite 402-405)
*Scope: Robotic total knee/hip replacement, arthroscopic ACL repair, complex trauma, spine decompression, sports medicine.*
- **Dr. Kiran Shetty** (MBBS, MS Ortho) | 19 Yrs | English, Kannada, Tulu | **₹1,000** | OPD-402 | Mon–Fri (09:00–13:00) | *Joint Replacement & Arthroscopy Consultant*
- **Dr. Vikram Rathore** (MBBS, MS Ortho, MCh) | 27 Yrs | English, Hindi, Marathi | **₹1,500** | OPD-403 | Tue, Thu, Sat (14:00–18:00) | *Complex Pelvic Trauma & Revision Joint Surgeon*
- **Dr. Ananya Kulkarni** (MBBS, DNB Ortho) | 7 Yrs | English, Marathi, Kannada | **₹800** | OPD-404 | Mon, Wed, Fri (15:00–19:00) | *Pediatric Ortho & Sports Injuries*
- **Dr. Aditya Verma** (MBBS, MS, Fellowship Spine) | 13 Yrs | English, Hindi | **₹1,300** | OPD-405 | Mon, Wed, Fri (09:00–12:00) | *Minimally Invasive Spine & Disc Surgery*

### 3. Neurology & Stroke Care (Floor 3 — OPD Suite 320-322)
*Scope: Acute ischemic stroke thrombolysis, epilepsy clinic, Parkinson's disease, neuromuscular disorders, EEG, EMG, nerve conduction.*
- **Dr. Harish Gowda** (MBBS, MD, DM Neurology) | 21 Yrs | English, Kannada | **₹1,400** | OPD-320 | Mon, Wed, Fri (09:30–13:00) | *Head of Stroke Unit & Epilepsy Specialist*
- **Dr. Sunita Banerjee** (MBBS, MD, DM Neurology) | 13 Yrs | English, Bengali, Hindi | **₹1,300** | OPD-321 | Tue, Thu (14:00–18:00) | *Movement Disorders & Multiple Sclerosis*
- **Dr. Arvind Pillai** (MBBS, DNB Neurology) | 6 Yrs | English, Malayalam, Tamil | **₹1,000** | OPD-322 | Saturday (09:00–14:00) | *Headache, Migraine & Neuropathy Clinic*

### 4. General & Internal Medicine (Ground Floor — OPD Suite 101-105)
*Scope: Tropical fevers (dengue, malaria, typhoid), infectious diseases, uncontrolled diabetes, hypertension, adult immunizations.*
- **Dr. Anil Kumar** (MBBS, MD Medicine) | 18 Yrs | English, Kannada, Hindi | **₹600** | OPD-101 | Mon–Sat (09:00–13:00) | *Senior Physician & Fever Clinic Lead*
- **Dr. Sneha Rao** (MBBS, MD Medicine) | 10 Yrs | English, Kannada, Telugu | **₹600** | OPD-102 | Mon, Wed, Fri (14:00–18:00) | *Lifestyle Disorders & Metabolic Clinic*
- **Dr. Mohammed Irfan** (MBBS, DNB Family Med) | 9 Yrs | English, Hindi, Urdu, Kannada | **₹500** | OPD-103 | Tue, Thu, Sat (14:00–19:00) | *Family Physician & Preventative Health*
- **Dr. Deepa Krishnan** (MBBS, MD Medicine) | 14 Yrs | English, Tamil, Kannada | **₹600** | OPD-104 | Mon–Fri (17:00–20:00) | *Evening Clinic & Chronic Disease Management*
- **Dr. Bhavana Shenoy** (MBBS, MD Geriatrics) | 15 Yrs | English, Kannada, Konkani, Tulu | **₹700** | OPD-105 | Mon, Tue, Thu, Fri (09:00–12:00) | *Chief Geriatrician (Senior Citizen Wellness Clinic)*

### 5. Paediatrics & Child Health (Floor 1 — OPD Suite 120-122)
*Scope: Well-baby clinic, national immunization schedule, childhood asthma, growth monitoring, NICU/PICU step-down.*
- **Dr. Lakshmi Nair** (MBBS, MD Paediatrics) | 16 Yrs | English, Malayalam, Kannada | **₹700** | OPD-120 | Mon–Sat (09:00–13:00) | *Head of Paediatrics & Neonatal Care*
- **Dr. Rohit Agarwal** (MBBS, DCH, DNB Paed) | 12 Yrs | English, Hindi | **₹700** | OPD-121 | Mon, Wed, Fri (15:00–19:00) | *Paediatric Pulmonology & Allergy*
- **Dr. Shalini Hegde** (MBBS, MD Paediatrics) | 5 Yrs | English, Kannada, Konkani | **₹600** | OPD-122 | Tue, Thu, Sat (14:00–18:00) | *Developmental Paediatrics & Nutrition*

### 6. Obstetrics & Gynaecology (Floor 1 — OPD Suite 130-132)
*Scope: High-risk pregnancy, painless normal delivery, Caesarean section, laparoscopic hysterectomy, PCOS, infertility management.*
- **Dr. Nandini Rao** (MBBS, MS OBG) | 22 Yrs | English, Kannada, Telugu | **₹1,000** | OPD-130 | Mon, Wed, Fri, Sat (09:30–13:30) | *High-Risk Obstetrics & Advanced Laparoscopy*
- **Dr. Priyanka Desai** (MBBS, DGO, DNB OBG) | 11 Yrs | English, Hindi, Gujarati, Marathi | **₹900** | OPD-131 | Tue, Thu (14:00–18:00) | *Adolescent Health, PCOD & Infertility*
- **Dr. Mary Thomas** (MBBS, MS OBG) | 17 Yrs | English, Malayalam, Tamil | **₹1,000** | OPD-132 | Mon–Fri (16:00–19:00) | *Menopause Clinic & Uro-gynaecology*

### 7. Dermatology, Cosmetology & Trichology (Floor 2 — OPD Suite 205-207)
*Scope: Psoriasis, eczema, acne vulgaris, hair loss (PRP therapy), skin allergies, vitiligo, laser therapy.*
- **Dr. Priya Mehta** (MBBS, MD Derm) | 12 Yrs | English, Hindi, Gujarati | **₹800** | OPD-205 | Mon, Tue, Thu, Sat (09:30–13:00) | *Clinical Dermatology & Laser Specialist*
- **Dr. Farhan Ali** (MBBS, DVD, DNB Derm) | 9 Yrs | English, Hindi, Urdu | **₹800** | OPD-206 | Tue, Wed, Fri (14:00–17:00) | *Trichology & Hair Restoration Specialist*
- **Dr. Ritu Saxena** (MBBS, MD Derm) | 6 Yrs | English, Hindi | **₹700** | OPD-207 | Mon, Wed, Fri (17:00–20:00) | *Pediatric Dermatology & Allergy Testing*

### 8. ENT / Otorhinolaryngology (Floor 2 — OPD Suite 215-216)
*Scope: Micro-ear surgery, endoscopic sinus surgery (FESS), tonsillectomy, vertigo clinic, audiometry, voice analysis.*
- **Dr. Venkatesh Murthy** (MBBS, MS ENT) | 23 Yrs | English, Kannada, Telugu | **₹800** | OPD-215 | Tue, Thu, Sat (10:00–14:00) | *Senior ENT Surgeon & Otology/Implant Specialist*
- **Dr. Aisha Khan** (MBBS, DLO, DNB ENT) | 8 Yrs | English, Hindi, Urdu | **₹700** | OPD-216 | Mon, Wed, Fri (14:00–18:00) | *Rhinology, Sinusitis & Vertigo Clinic*

### 9. Ophthalmology & Eye Institute (Floor 2 — OPD Suite 220-222)
*Scope: Phacoemulsification cataract surgery, diabetic retinopathy, glaucoma screening, Lasik evaluation, refractions.*
- **Dr. Sanjay Kapoor** (MBBS, MS Ophthal) | 20 Yrs | English, Hindi, Punjabi | **₹800** | OPD-220 | Mon–Fri (09:00–13:00) | *Cataract & Refractive Surgeon*
- **Dr. Revathi Subramanian** (MBBS, DNB Ophthal) | 10 Yrs | English, Tamil, Kannada | **₹700** | OPD-221 | Tue, Thu, Sat (14:00–18:00) | *Glaucoma & Medical Retina Specialist*
- **Dr. Abhishek Jain** (MBBS, DO) | 4 Yrs | English, Hindi, Marathi | **₹600** | OPD-222 | Mon, Wed, Fri (16:00–19:00) | *Comprehensive Ophthalmology & Refraction*

### 10. Gastroenterology & Hepatology (Floor 3 — OPD Suite 330-332)
*Scope: Diagnostic/therapeutic upper GI endoscopy, colonoscopy, ERCP, fatty liver, jaundice, inflammatory bowel disease.*
- **Dr. Naveen Chandra** (MBBS, MD, DM Gastro) | 19 Yrs | English, Kannada, Hindi | **₹1,300** | OPD-330 | Mon, Wed, Fri (10:00–14:00) | *Lead Gastroenterologist & Interventional Endoscopist*
- **Dr. Pooja Sharma** (MBBS, MD, DNB Gastro) | 9 Yrs | English, Hindi, Punjabi | **₹1,200** | OPD-331 | Tue, Thu, Sat (14:00–18:00) | *Luminal Gastroenterology & Motility Specialist*
- **Dr. Thomas George** (MBBS, MD, DM) | 26 Yrs | English, Malayalam | **₹1,500** | OPD-332 | Tue, Thu (09:00–12:00) | *Hepatologist (Liver Cirrhosis & Post-Transplant Care)*

### 11. Pulmonology & Sleep Medicine (Floor 3 — OPD Suite 340-342)
*Scope: Bronchoscopy, PFT (spirometry), sleep apnea (polysomnography), chronic cough, COPD, asthma, allergic bronchitis.*
- **Dr. Ramesh Babu** (MBBS, MD Pulm) | 17 Yrs | English, Telugu, Kannada | **₹1,000** | OPD-340 | Mon–Fri (09:00–12:00) | *Senior Pulmonologist & Interventional Bronchoscopist*
- **Dr. Shweta Patil** (MBBS, DNB Resp) | 7 Yrs | English, Marathi, Kannada, Hindi | **₹900** | OPD-341 | Tue, Thu, Sat (15:00–19:00) | *Allergy, Asthma & Sleep Apnea Specialist*
- **Dr. Gopal Krishna** (MBBS, MD, DTCD) | 29 Yrs | English, Kannada, Tamil | **₹1,100** | OPD-342 | Mon, Wed, Fri (14:00–17:00) | *Interstitial Lung Disease & Tuberculosis Lead*

### 12. Nephrology & Hemodialysis (Floor 4 — OPD Suite 410-412)
*Scope: Acute & chronic kidney disease, diabetic nephropathy, hemodialysis, peritoneal dialysis, renal biopsy, transplant evaluation.*
- **Dr. Arun Prakash** (MBBS, MD, DM Nephro) | 20 Yrs | English, Tamil, Kannada | **₹1,300** | OPD-410 | Mon, Wed, Fri (09:30–13:00) | *Head of Nephrology & Dialysis Unit*
- **Dr. Meenakshi Sundaram** (MBBS, MD, DNB Nephro) | 12 Yrs | English, Tamil | **₹1,200** | OPD-411 | Tue, Thu, Sat (14:00–17:30) | *Glomerular Diseases & Peritoneal Dialysis*
- **Dr. Sameer Joshi** (MBBS, MD Med, DM) | 8 Yrs | English, Marathi, Hindi | **₹1,000** | OPD-412 | Tue, Fri (09:00–12:00) | *Hypertensive Kidney Disease & Interventional Access*

### 13. Endocrinology & Diabetology (Floor 4 — OPD Suite 420-422)
*Scope: Type 1 & 2 diabetes, insulin pump therapy, thyroid nodules, Hashimoto's, pituitary, adrenal, osteoporosis.*
- **Dr. Divya Bhat** (MBBS, MD, DM Endo) | 13 Yrs | English, Kannada, Konkani | **₹1,200** | OPD-420 | Mon–Fri (10:00–13:00) | *Head of Endocrinology & Pediatric Hormone Disorders*
- **Dr. Karthik Raman** (MBBS, DNB Endo) | 9 Yrs | English, Tamil, Telugu | **₹1,100** | OPD-421 | Mon, Wed, Fri, Sat (15:00–19:00) | *Metabolic Syndrome, Obesity & Thyroid Lead*
- **Dr. Neha Gupta** (MBBS, MD Med, DM) | 5 Yrs | English, Hindi, Bengali | **₹900** | OPD-422 | Tue, Thu (17:00–20:00) | *Gestational Diabetes & Bone Health*

### 14. Radiodiagnosis & Interventional Radiology (Basement 1 — Suites RAD-01/02)
- **Dr. Prakash Rao** (MBBS, MD Radiology) | 25 Yrs | English, Kannada, Telugu | RAD-01 | Mon–Sat (09:00–13:00) | *Chief Radiologist (Advanced Neuro & Musculoskeletal MRI)*
- **Dr. Sarah D'Souza** (MBBS, DNB Radiology) | 11 Yrs | English, Konkani, Kannada | RAD-02 | Mon–Fri (14:00–18:00) | *Cross-Sectional Imaging (CT Coronary & Body Scans)*

---

## 4. Surgical Suites, Operating Theatres & Cath Lab Complex

Located on **Floor 5**, accessible only via sterile airlock corridors and staff scrub-in bays.

### Operating Theatre Infrastructure
1. **OT 1 (Cardiac & Vascular):** Dedicated heart-lung bypass machine (Stockert S5), Maquet operative table, continuous blood gas analysis.
2. **OT 2 (Robotic & Laparoscopy Suite):** 4-arm robotic surgical system, 4K Stryker laparoscopic towers, CO2 insufflators.
3. **OT 3 (Orthopaedic & Spine):** Class 100 laminar airflow with vertical HEPA filtration, radiolucent carbon-fiber table, Siemens C-Arm fluoroscope.
4. **OT 4 (Neuro & Micro-Surgery):** Zeiss Kinevo 900 operative neuro-microscope, intraoperative neuromonitoring (IONM), ultrasonic aspirator (CUSA).
5. **OT 5 (General, Gastro & Daycare Surgery):** High-definition Olympus endoscopy towers, harmonic scalpel, argon plasma coagulator.
6. **OT 6 (Obstetrics & Emergency C-Section):** Direct elevator connectivity to labour delivery suites on Floor 1, dedicated neonatal resuscitation cribs (Panda Warmer).

### Cardiac Cath Lab (Suite C-01)
- **Equipment:** Philips Azurion 7 Biplane Flat-Panel Digital Cath Lab.
- **Procedures:** Primary percutaneous coronary intervention (door-to-balloon SLA < 60 minutes), electrophysiology studies, permanent pacemaker implantation (single/dual chamber), peripheral vascular angioplasty.
- **On-Call Team:** Available 24/7/365 with a mandatory 20-minute mobilization SLA for acute ST-elevation myocardial infarction (STEMI).

---

## 5. Diagnostic Imaging & Advanced Radiology Institute

Housed in **Basement 1** with lead-shielded walls compliant with AERB safety standards.

| Procedure Code | Examination Name | Machine / Modality | Price (INR) | Duration | Fasting Prep | Patient Preparation & Safety Instructions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `MRI-BRAIN` | **MRI Brain (Plain)** | GE 3.0T Signa Pioneer | **₹8,500** | 45 min | Nil | Strict screening for cardiac pacemakers, metallic implants, aneurysmal clips. Earplugs provided. Arrive 30 mins early. |
| `MRI-SPINE` | **MRI Lumbar / Cervical Spine** | GE 3.0T Signa Pioneer | **₹9,500** | 45 min | Nil | Wear metal-free hospital gown. Inform staff if prone to claustrophobia. |
| `MRI-KNEE` | **MRI Knee Joint** | GE 3.0T Signa Pioneer | **₹7,500** | 30 min | Nil | High-resolution cartilage and meniscus sequences. No fasting required. |
| `CT-HEAD` | **CT Head (Brain)** | 128-Slice Philips Ingenuity | **₹3,500** | 15 min | Nil | Non-contrast acute hemorrhage protocol. Bring previous head injury/scan records. |
| `CT-CHEST` | **High-Res CT Chest (HRCT)** | 128-Slice Philips Ingenuity | **₹5,500** | 15 min | 4 Hours | Fasting required if IV contrast is administered. **Creatinine test result mandatory** (< 1.2 mg/dL). |
| `CT-ABD` | **CT Abdomen & Pelvis (CECT)** | 128-Slice Philips Ingenuity | **₹6,500** | 20 min | 4 Hours | Oral contrast provided at radiology counter 1 hour prior to scan. Fasting required. |
| `USG-ABD` | **Ultrasound Whole Abdomen** | Samsung RS85 High-End | **₹1,600** | 20 min | 6 Hours | Strict 6-hour fasting. Drink 1 litre of plain water 1 hour prior; **do not void (full bladder mandatory)**. |
| `USG-PELVIS` | **Ultrasound Pelvis (KUB/Gyne)** | Samsung RS85 High-End | **₹1,500** | 20 min | Nil | Drink 4–5 glasses of water 45 mins prior to scan. Full bladder required. |
| `XRAY-CHEST` | **Digital X-Ray Chest (PA View)** | Shimadzu 500mA Digital | **₹450** | 10 min | Nil | Remove all necklaces, metal chains and underwire brassieres. Instant digital capture. |
| `XRAY-KNEE` | **Digital X-Ray Knee (AP/Lat)** | Shimadzu 500mA Digital | **₹500** | 10 min | Nil | Weight-bearing views taken as per orthopedic requisition. |

---

## 6. 24/7 NABL Accredited Central Pathology & Diagnostic Laboratories

Housed in **Basement 1**, operating 24 hours a day with automated barcoded track systems (Sysmex, Roche Cobas, bioMérieux analyzers).

| Test Panel | Clinical Scope | Reporting Turnaround (SLA) | Routine Sample Type | Specimen Instructions |
| :--- | :--- | :--- | :--- | :--- |
| **Complete Blood Count (CBC)** | Hemoglobin, TLC, DLC, platelet count, RBC indices, ESR | **2 to 3 Hours** | 2 mL EDTA whole blood | Non-fasting. Urgent stat delivery available in 45 mins for dengue/trauma. |
| **Lipid Profile** | Total cholesterol, triglycerides, HDL, LDL, VLDL | **4 Hours** | 3 mL plain serum | **10 to 12 hours strict overnight fasting.** Water is permitted. |
| **HbA1c & Fasting Glucose** | Glycated hemoglobin (3-month control) + blood glucose | **3 Hours** | Fluoride / EDTA blood | 8-hour fasting for glucose; HbA1c can be drawn non-fasting. |
| **Liver Function Test (LFT)** | Bilirubin (total/direct), SGOT, SGPT, alkaline phosphatase, protein | **4 Hours** | 3 mL plain serum | 4-hour fasting recommended. Avoid alcohol 24 hours prior. |
| **Kidney Function Test (KFT)** | Blood urea, serum creatinine, uric acid, sodium, potassium | **3 to 4 Hours** | 3 mL plain serum | Mandatory before all contrast CT scans or nephrotoxic drug regimens. |
| **Thyroid Profile (T3, T4, TSH)** | Total T3, free T4, ultrasensitive TSH | **4 Hours** | 3 mL plain serum | Fasting morning sample preferred before the morning thyroid hormone dose. |
| **Urine Routine & Microscopic** | Protein, glucose, pus cells, RBCs, crystals, casts | **2 Hours** | 20 mL clean catch midstream | Clean catch midstream urine in the sterile container provided by the lab. |
| **Blood Culture & Sensitivity** | Aerobic & anaerobic bacterial isolation, antibiotic susceptibility | **48 to 72 Hours** | Paired BACTEC blood bottles | Automated BACTEC FX monitoring; preliminary alert at 24 hours if positive. |
| **Biopsy & Histopathology** | Surgical tissue excision, frozen sections, IHC staining | **3 to 5 Working Days** | Formalin-fixed tissue | Processed by Senior Consultant Pathologist Dr. Rekha Joshi. |

---

## 7. 24/7 Emergency & Level-1 Trauma Centre (Gate 1)

Located on the **Ground Floor, West Wing (Entrance B)** with zero-stair direct ambulance docking.

### Emergency Triage Protocol (Manchester Triage System)
- **Red (Priority 1 — Immediate Resuscitation):** Cardiac arrest, polytrauma with hemorrhagic shock, massive stroke within window, airway obstruction. **SLA: 0 minutes (immediate doctor bedside).**
- **Yellow (Priority 2 — Very Urgent):** Chest discomfort with stable vitals, acute asthma with SpO2 90–94%, severe open fractures, acute abdominal pain. **SLA: < 15 minutes.**
- **Green (Priority 3 — Standard / Non-Urgent):** Mild lacerations, closed limb sprains, low-grade fevers, mild viral gastroenteritis. **SLA: < 45 minutes.**

### Emergency Fleet & Mobile ICU
- **3 Advanced Cardiac Life Support (ACLS) Ambulances:** Hamilton transport ventilators, Zoll biphasic defibrillators, syringe infusion pumps, automated chest compressors, onboard cellular ECG telemetry.
- **1 Basic Life Support (BLS) Patient Transfer Van:** For non-critical patient discharges and inter-facility transit.
- **Dispatch Hotline:** `080 4000 108` for immediate Marathahalli/Whitefield/Bellandur emergency dispatch.

---

## 8. Critical Care Units (ICU, CCU, NICU, PICU)

Housed on **Floor 3 and Floor 4**, with individual glass-partitioned cubicles to minimize nosocomial infections.

### Critical Care Breakdown (45 Beds Total)
1. **Medical & Surgical ICU (MICU/SICU — 20 Beds, Floor 3):** 1:1 nurse-to-patient ratio for ventilated patients. Multi-channel invasive arterial monitoring, continuous renal replacement therapy (CRRT), bedside fiberoptic bronchoscopy.
2. **Coronary Care Unit (CCU — 10 Beds, Floor 3):** Dedicated acute post-angioplasty and cardiogenic shock unit. Bedside telemetry linked to the central nursing station.
3. **Neonatal Intensive Care Unit (NICU Level III — 10 Beds, Floor 2):** High-frequency oscillatory ventilators (HFOV), LED phototherapy, total parenteral nutrition compounding, neonatal transport incubators.
4. **Pediatric Intensive Care Unit (PICU — 5 Beds, Floor 2):** Specialized care for critically ill children and post-pediatric surgery recovery.

### Critical Care Visiting Policy (Strict Infection Control)
- **Hours:** Strictly **5:00 PM to 6:00 PM daily**.
- **Rules:** Exactly **1 adult family member** allowed inside the cubicle. Hand hygiene and sterile shoe covers mandatory. Children under 12 strictly prohibited.

---

## 9. Inpatient Wards, Rooms & Daily Room Tariffs

All inpatient admissions include 24-hour nursing supervision, duty doctor rounds, housekeeping and basic room amenities.

| Accommodation Type | Room Description & Amenities | Daily Tariff (INR) | Attendant Policy |
| :--- | :--- | :--- | :--- |
| **General Multi-Bed Ward** | 6-bed partition room, central air-conditioning, privacy curtains, shared bathroom. | **₹2,200 / day** | 1 attendant pass (common waiting lounge access, bedside chair). |
| **Twin-Sharing (Semi-Private)** | 2 beds per room separated by soundproof curtain, television, individual storage, attached bath. | **₹4,500 / day** | 1 attendant pass with overnight reclining lounger. |
| **Single Deluxe Private Room** | Private air-conditioned room, motorized hospital bed, flat-screen TV, sofa-cum-bed, private attached bathroom, refrigerator, high-speed Wi-Fi. | **₹7,800 / day** | 1 attendant pass with dedicated overnight sleeper sofa. |
| **Executive Presidential Suite** | Two-room suite (patient bedroom + private visitors' living lounge), kitchenette with microwave, 2 LED TVs, executive desk, dining table, luxury bath amenities. | **₹16,500 / day** | Up to 2 attendants permitted; luxury visitor amenities included. |
| **ICU / CCU Bed** | Full invasive multi-parameter hemodynamic monitoring, motorized high-dependency bed, 1:1 dedicated nursing care. | **₹11,500 / day** | No overnight bedside attendant; waiting lounge access provided. |

---

## 10. Pharmacy Operations, 24/7 Dispensary & Drug Formulary

WellNest operates two licensed dispensaries compliant with the Karnataka State Drugs Control Department and CDSCO guidelines:
1. **Central Outpatient & Emergency Pharmacy (Ground Floor, adjacent to Gate 1):** Open **24 hours a day, 365 days a year**.
2. **Inpatient Floor Satellite Dispensary (Floor 4):** Serves OT and ward medication cassettes.

### Key Formulary & Pharmacy Guidelines
- **Stock Availability:** Over 1,200 essential molecules stocked across cardiology, endocrinology, pulmonology, orthopaedics and emergency critical care.
- **Chronic Disease Refill Coordination:**
  - Automated tracking for 30-day maintenance supplies of antihypertensives (telmisartan, amlodipine), statins (atorvastatin, rosuvastatin), oral hypoglycemics (metformin, glimepiride, dapagliflozin) and inhalers (Budecort, Foracort).
  - Patients/caregivers receive a refill alert **4 days prior to expiration** via WhatsApp/SMS.
- **Home Delivery Service:** Free prescription delivery within a 5 km radius (Marathahalli, Kadubeesanahalli, Munnekollal, Brookefield) for medicine orders exceeding ₹500. Pharmacy desk: `080 4000 1240`.
- **Statutory Prescription Laws (Drugs & Cosmetics Act):**
  - **Schedule H & H1 drugs (antibiotics, psychotropics, strong NSAIDs):** Strictly prohibited from dispensing without a valid physical or authenticated e-prescription signed by a registered medical practitioner within the past 6 months. Over-the-counter dispensing is legally barred.

---

## 11. Mobility, Wheelchairs, Stretchers & Two-Way Porter Escort System

WellNest maintains an institutional mobility fleet to ensure barrier-free access for elderly, injured and differently-abled patients.

### Fleet Inventory & Station Locations
- **Wheelchair Fleet:** 40 heavy-duty chrome folding wheelchairs with swing-away footrests and safety seatbelts.
- **Stretcher Fleet:** 12 mobile hydraulic trauma stretchers with IV poles and oxygen cylinder brackets.
- **Main Dispatch Stations:**
  - **Porter Station Alpha (Gate 1 — Emergency Bay):** 15 wheelchairs, 8 stretchers (immediate 24/7 dispatch).
  - **Porter Station Beta (Gate 2 — Main OPD Atrium):** 20 wheelchairs, 4 stretchers (active 7:30 AM to 8:30 PM).
  - **Porter Station Gamma (Basement P1 Elevator Lobby):** 5 wheelchairs for direct car-to-lift transit.

### Institutional Mobility Rules & Closed-Loop Protocol
1. **100% Complimentary On-Campus Service:** Wheelchair equipment, transfers and dedicated porter assistance across all floors, diagnostic wings and clinics are completely **free (₹0 fee)**.
2. **Two-Way Closed-Loop Escort:**
   - **Inbound Leg:** When a wheelchair is booked (token `AS-XXXXX`), the assigned porter meets the patient at the designated entrance (Gate 1 or Gate 2) and escorts them directly to their consultation chamber.
   - **Outbound Leg (Return Trip):** The clinic nurse on Floor 2, 3 or 4 pages the porter desk once the doctor's visit is complete, and a porter escorts the patient back down to their parked car or taxi at Gate 2.
3. **Dispatch SLA:** 15-minute advance lead time required for scheduled arrivals.
4. **Off-Campus Security Deposit Rule:** Wheelchairs are strictly prohibited from leaving hospital grounds (e.g. to hotels or private homes). If an emergency exception is granted by the Hospital Superintendent, a **₹1,000 refundable security deposit** and a formal security gate pass are mandatory.

---

## 12. Parking Infrastructure, EV Stations & Traffic Flow

The hospital operates a high-capacity, multi-level subterranean parking complex managed via automated FASTag and licence plate recognition (ANPR) systems.

### Parking Capacity & Allocation
- **Basement Level P1:** 120 four-wheeler bays (reserved for OPD patients and senior citizens) + 200 two-wheeler bays.
- **Basement Level P2:** 160 four-wheeler bays (inpatient visitors and staff) + 250 two-wheeler bays.
- **Disabled Accessible Parking:** 12 dedicated extra-wide bays within 15 metres of the primary elevator lobbies on P1.

### Tariff Structure
- **OPD Patients (valid consultation slip):** **Free for the first 3 hours** upon barcode scanning at the billing counter. Thereafter ₹20 per hour.
- **Inpatient Attendants:** 1 vehicle pass issued at admission allowing unlimited 24-hour entry/exit at a subsidized flat rate of **₹100 per day**.
- **General Visitors:** ₹30 for the first 2 hours; ₹20 for each subsequent hour.
- **Valet Parking Service:** Available exclusively at **Gate 2 (Main Atrium)** from 8:00 AM to 8:00 PM for a convenience surcharge of **₹50** (plus applicable parking fee).

### Electric Vehicle (EV) Fast Charging Hub (Basement P1)
- **4 Type-2 AC Chargers (7.4 kW / 22 kW):** Subsidized charging at ₹14 per kWh.
- **4 DC Dual-Gun Fast Chargers (60 kW CCS-2):** Charges 20% to 80% in approximately 35 minutes; ₹19 per kWh.

---

## 13. Dining, Cafeteria & Patient Family Amenities

Located on the **Ground Floor, South Wing**, catering to patient attendants, visitors and hospital staff.

### WellNest Cafeteria ("The Courtyard Bistro")
- **Operating Hours:** Open daily from **7:00 AM to 10:00 PM**.
- **Cuisine & Standards:** 100% vegetarian certified kitchen adhering to FSSAI hygiene standards. Serves South Indian, North Indian, fresh fruit juices and clinical diabetic-friendly meal platters.
- **Sample Pricing:** Idli-Vada combo ₹60 · Sprouts salad ₹70 · Mini thali (lunch/dinner) ₹120 · Fresh tender coconut ₹50.
- **Inpatient Dietetics:** Customized therapeutic meals (salt-restricted, diabetic, renal, liquid pureed) prepared under the supervision of Chief Clinical Nutritionist Ms. Suman Hegde and delivered to the ward bedside via temperature-controlled meal trolleys.

### Additional Campus Amenities
- **Coffee Kiosk:** Main Atrium (Gate 2 Lobby) — open 7:00 AM to 11:00 PM.
- **24/7 ATM Hub:** Main Reception Corridor.
- **Multifaith Prayer & Meditation Room:** Floor 1, East Wing — quiet room open 24/7 for families of all faiths.
- **Mother & Child Nursing / Lactation Room:** Floor 1 (adjacent to Paediatric OPD 120) — private, soundproof nursing lounge with diaper-changing stations.

---

## 14. Insurance, TPA Desk & Cashless Billing Operations

WellNest operates a dedicated **Institutional TPA & Corporate Insurance Centre** on the **Ground Floor, Wing B (Counters 12–16)**, open Monday to Saturday from 8:00 AM to 7:00 PM, with 24/7 emergency coverage via duty billing managers.

### Direct Cashless Empanelled Insurers & TPAs
- **Retail & Group Health Insurers:** Star Health & Allied Insurance, HDFC ERGO General Insurance, Care Health Insurance (Religare), ICICI Lombard, Niva Bupa Health Insurance, Bajaj Allianz, Tata AIG, SBI General Insurance.
- **Third-Party Administrators (TPAs):** Medi Assist TPA, Vidal Health TPA, Heritage Health, Paramount TPA, FHPL (Family Health Plan), Raksha TPA, MDIndia Healthcare.
- **Government Schemes:** Ayushman Bharat (PM-JAY) and Karnataka Arogya Sanjeevini (subject to scheme portal empanelment for emergency cardiac and trauma admissions).

### The Cashless Claim Reality & Regulatory Rules (IRDAI Compliance)
1. **Pre-Authorization is an Estimate, Not a Payout Guarantee:** An insurance eligibility check by phone or chat confirms hospital network empanelment only. Final cashless authorization is issued strictly by the insurer's medical audit team after reviewing clinical notes, investigations and physician admission summaries.
2. **Mandatory Documentation for the Cashless Desk:**
   - Original physical health insurance card / e-card with policy number.
   - Government photo identification (Aadhaar card or passport of the patient).
   - Attending consultant's written requisition / admission advice note.
3. **Turnaround Time for Pre-Auth:**
   - **Emergency Admissions:** Initial emergency pre-auth decision within **1 to 2 hours** of document upload.
   - **Planned Daycare / Inpatient Surgeries:** Requisitions must be submitted at least **48 hours in advance**.
4. **Mandatory Consumables Exclusion Disclosure:**
   - Under standard IRDAI regulations, non-medical consumables are **non-payable by insurers**.
   - These include hospital admission file charges (₹250), PPE/sanitization kits, disposable bedsheets, thermometers, gloves and surgical contrast syringes (~₹600–₹850).
   - **These charges must be settled out-of-pocket** by the patient/attendant before final discharge.
5. **Section 80D Income Tax Certificates:** Every payment receipt issued for consultations, lab diagnostics or hospitalizations carries the hospital's registered PAN and GSTIN, making it valid for income tax deduction under Section 80D.

---

## 15. Institutional Terms of Conditions, Patient Rights & Legal Compliance

### 1. OPD Consultations & Appointment Rules
- **Follow-up Review Policy:** Every paid OPD consultation fee includes **1 complimentary follow-up review within 7 calendar days** for the same medical complaint. Visits on day 8 onwards are billed as fresh consultations.
- **Reporting Time & Vital Signs Triage:** All outpatients must report to the respective floor reception **15 minutes prior to their scheduled slot** for mandatory vital signs recording (blood pressure, pulse, SpO2, body temperature, weight) by floor nurses.
- **15-Minute Late Arrival Grace Period:** Scheduled slots are held for exactly 15 minutes past the appointment time. Patients arriving more than 15 minutes late have their booking converted to an end-of-clinic walk-in, to protect subsequent patients from compounding delays.

### 2. Cancellation & Refund Policy
- **Free Cancellation Window:** Patients may cancel or reschedule with **zero financial penalty up to 2 hours** prior to the scheduled slot.
- **Late Cancellation & No-Show Deduction:** Cancellations within 2 hours of the slot, or failure to appear, incur a **₹150 administrative slot re-allocation deduction**. The remaining balance is refunded.
- **Refund Settlement SLA:** Digital refunds for prepaid UPI, card or net-banking transactions are processed automatically back to the source account within **3 to 5 banking days**.

### 3. Patient Data Privacy & Digital Health Proxy (DPDP Act 2023 & DISHA)
- **Confidentiality of Diagnostic Records:** In compliance with Section 1.3.4 of the National Medical Commission (NMC) Code of Medical Ethics and India's Digital Personal Data Protection (DPDP) Act 2023, lab reports and biopsy findings are confidential medical records released strictly to the verified patient's registered mobile number and email on file.
- **Caregiver Proxy Scope:** Linking a caregiver (such as an adult son or daughter for an elderly parent) authorizes the caregiver to receive **operational alerts only** (appointment tokens, clinic room updates, porter tokens, doctor delay alerts). Caregivers do **not** receive sensitive medical reports or physician clinical notes over digital channels without an explicit, physically signed Medical Power of Attorney or OTP authentication from the patient's registered mobile.

### 4. Telemedicine & Prescription Refill Guidelines
- **Schedule H Drug Regulations:** Antibiotics, sleep aids and psychotropic medications **cannot** be refilled or prescribed over voice/chat channels without a formal video or in-person evaluation, per the Telemedicine Practice Guidelines issued by the Ministry of Health and Family Welfare.

### 5. Patient Grievance Redressal & Quality Escalations
- **Patient Rights Charter:** Patients have the right to transparent billing, dignified clinical care and second medical opinions.
- **Formal Grievance Tracking:** Any billing dispute or clinical service dissatisfaction logged via the Support Agent generates a traceable grievance code (`GRV-XXXXX`).
- **Executive Resolution SLA:** A senior Patient Relations Manager investigates and contacts the aggrieved patient within **15 minutes for clinical/urgent handoffs** and within **24 hours for administrative billing audits**. Contact: `grievance@wellnest.test` or `080 4000 1290`.

---
*Manual compiled for WellNest Hospitals Bengaluru on behalf of the Hospital Administration (TeamXYZ, Talkdesk AI Hackday). All patient data referenced in this repository is invented.*
