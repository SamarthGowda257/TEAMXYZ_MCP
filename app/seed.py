"""Deterministic demo dataset for WellNest Hospitals, Bengaluru (all people and data are fictional).

Generated relative to "today" so the demo always has upcoming slots.
Run:  python -m app.seed --reset      (drops and rebuilds everything)
"""

import random
import sys
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, text

from . import config, db
from .security import hash_password

SEED = 20261104

DEPARTMENTS = [
    ("CARD", "Cardiology", "3rd floor", "Heart and blood vessel care: chest pain review, BP, ECG, echo, TMT."),
    ("ORTH", "Orthopaedics", "4th floor", "Bones, joints, spine, sports injuries and fractures."),
    ("NEUR", "Neurology", "3rd floor", "Headache, seizures, stroke follow-up, nerve problems."),
    ("GMED", "General Medicine", "Ground floor", "Fever, infections, diabetes, BP and general check-ups."),
    ("PAED", "Paediatrics", "1st floor", "Children's health, vaccinations and growth."),
    ("GYNO", "Gynaecology & Obstetrics", "1st floor", "Women's health, pregnancy and antenatal care."),
    ("DERM", "Dermatology", "2nd floor", "Skin, hair and nail problems."),
    ("ENT", "ENT", "2nd floor", "Ear, nose and throat."),
    ("OPHT", "Ophthalmology", "2nd floor", "Eye check-ups, cataract and vision."),
    ("GAST", "Gastroenterology", "3rd floor", "Stomach, liver and digestion; endoscopy."),
    ("PULM", "Pulmonology", "3rd floor", "Lungs, asthma, breathing and sleep problems."),
    ("NEPH", "Nephrology", "4th floor", "Kidney care and dialysis."),
    ("ENDO", "Endocrinology", "4th floor", "Diabetes, thyroid and hormones."),
    ("RADI", "Radiology", "Basement 1", "MRI, CT, X-ray and ultrasound."),
]

# name, gender, dept, qualification, exp, languages, fee, room, ISO days, start, end, slot minutes
DOCTORS = [
    ("Dr. Rajesh Iyer", "male", "CARD", "MBBS, MD, DM (Cardiology)", 24, "English,Tamil,Hindi", 1200, "OPD-310", "1,3,5", "10:00", "13:00", 15),
    ("Dr. Kavya Reddy", "female", "CARD", "MBBS, MD, DM (Cardiology)", 15, "English,Telugu,Kannada", 1200, "OPD-311", "2,4,6", "14:00", "17:00", 15),
    ("Dr. Suresh Menon", "male", "CARD", "MBBS, DNB (Cardiology)", 11, "English,Malayalam,Hindi", 1000, "OPD-312", "1,2,4,5", "16:00", "19:00", 15),
    ("Dr. Farzana Begum", "female", "CARD", "MBBS, MD (Medicine), DM", 8, "English,Hindi,Urdu,Kannada", 900, "OPD-313", "3,6", "09:00", "12:00", 15),
    ("Dr. Kiran Shetty", "male", "ORTH", "MBBS, MS (Ortho)", 19, "English,Kannada,Tulu", 1000, "OPD-402", "1,2,3,4,5", "09:00", "13:00", 15),
    ("Dr. Vikram Rathore", "male", "ORTH", "MBBS, MS (Ortho), MCh", 27, "English,Hindi,Marathi", 1500, "OPD-403", "2,4,6", "14:00", "18:00", 20),
    ("Dr. Ananya Kulkarni", "female", "ORTH", "MBBS, DNB (Ortho)", 7, "English,Marathi,Kannada", 800, "OPD-404", "1,3,5", "15:00", "19:00", 15),
    ("Dr. Harish Gowda", "male", "NEUR", "MBBS, MD, DM (Neurology)", 21, "English,Kannada", 1400, "OPD-320", "1,3,5", "09:30", "13:00", 20),
    ("Dr. Sunita Banerjee", "female", "NEUR", "MBBS, MD, DM (Neurology)", 13, "English,Bengali,Hindi", 1300, "OPD-321", "2,4", "14:00", "18:00", 20),
    ("Dr. Arvind Pillai", "male", "NEUR", "MBBS, DNB (Neurology)", 6, "English,Malayalam,Tamil", 1000, "OPD-322", "6", "09:00", "14:00", 20),
    ("Dr. Anil Kumar", "male", "GMED", "MBBS, MD (Medicine)", 18, "English,Kannada,Hindi", 600, "OPD-101", "1,2,3,4,5,6", "09:00", "13:00", 15),
    ("Dr. Sneha Rao", "female", "GMED", "MBBS, MD (Medicine)", 10, "English,Kannada,Telugu", 600, "OPD-102", "1,3,5", "14:00", "18:00", 15),
    ("Dr. Mohammed Irfan", "male", "GMED", "MBBS, DNB (Family Medicine)", 9, "English,Hindi,Urdu,Kannada", 500, "OPD-103", "2,4,6", "14:00", "19:00", 15),
    ("Dr. Deepa Krishnan", "female", "GMED", "MBBS, MD (Medicine)", 14, "English,Tamil,Kannada", 600, "OPD-104", "1,2,3,4,5", "17:00", "20:00", 15),
    ("Dr. Lakshmi Nair", "female", "PAED", "MBBS, MD (Paediatrics)", 16, "English,Malayalam,Kannada", 700, "OPD-120", "1,2,3,4,5,6", "09:00", "13:00", 15),
    ("Dr. Rohit Agarwal", "male", "PAED", "MBBS, DCH, DNB (Paediatrics)", 12, "English,Hindi", 700, "OPD-121", "1,3,5", "15:00", "19:00", 15),
    ("Dr. Shalini Hegde", "female", "PAED", "MBBS, MD (Paediatrics)", 5, "English,Kannada,Konkani", 600, "OPD-122", "2,4,6", "14:00", "18:00", 15),
    ("Dr. Nandini Rao", "female", "GYNO", "MBBS, MS (OBG)", 22, "English,Kannada,Telugu", 1000, "OPD-130", "1,3,5,6", "09:30", "13:30", 15),
    ("Dr. Priyanka Desai", "female", "GYNO", "MBBS, DGO, DNB (OBG)", 11, "English,Hindi,Gujarati,Marathi", 900, "OPD-131", "2,4", "14:00", "18:00", 15),
    ("Dr. Mary Thomas", "female", "GYNO", "MBBS, MS (OBG)", 17, "English,Malayalam,Tamil", 1000, "OPD-132", "1,2,3,4,5", "16:00", "19:00", 15),
    ("Dr. Priya Mehta", "female", "DERM", "MBBS, MD (Dermatology)", 12, "English,Hindi,Gujarati", 800, "OPD-205", "1,2,4,6", "09:30", "13:00", 15),
    ("Dr. Farhan Ali", "male", "DERM", "MBBS, DVD, DNB (Dermatology)", 9, "English,Hindi,Urdu", 800, "OPD-206", "2,3,5", "14:00", "17:00", 15),
    ("Dr. Ritu Saxena", "female", "DERM", "MBBS, MD (Dermatology)", 6, "English,Hindi", 700, "OPD-207", "1,3,5", "17:00", "20:00", 15),
    ("Dr. Venkatesh Murthy", "male", "ENT", "MBBS, MS (ENT)", 23, "English,Kannada,Telugu", 800, "OPD-215", "2,4,6", "10:00", "14:00", 15),
    ("Dr. Aisha Khan", "female", "ENT", "MBBS, DLO, DNB (ENT)", 8, "English,Hindi,Urdu", 700, "OPD-216", "1,3,5", "14:00", "18:00", 15),
    ("Dr. Sanjay Kapoor", "male", "OPHT", "MBBS, MS (Ophthalmology)", 20, "English,Hindi,Punjabi", 800, "OPD-220", "1,2,3,4,5", "09:00", "13:00", 15),
    ("Dr. Revathi Subramanian", "female", "OPHT", "MBBS, DNB (Ophthalmology)", 10, "English,Tamil,Kannada", 700, "OPD-221", "2,4,6", "14:00", "18:00", 15),
    ("Dr. Abhishek Jain", "male", "OPHT", "MBBS, DO", 4, "English,Hindi,Marathi", 600, "OPD-222", "1,3,5", "16:00", "19:00", 15),
    ("Dr. Naveen Chandra", "male", "GAST", "MBBS, MD, DM (Gastro)", 19, "English,Kannada,Hindi", 1300, "OPD-330", "1,3,5", "10:00", "14:00", 20),
    ("Dr. Pooja Sharma", "female", "GAST", "MBBS, MD, DNB (Gastro)", 9, "English,Hindi,Punjabi", 1200, "OPD-331", "2,4,6", "14:00", "18:00", 20),
    ("Dr. Thomas George", "male", "GAST", "MBBS, MD (Medicine), DM", 26, "English,Malayalam", 1500, "OPD-332", "2,4", "09:00", "12:00", 20),
    ("Dr. Ramesh Babu", "male", "PULM", "MBBS, MD (Pulmonology)", 17, "English,Telugu,Kannada", 1000, "OPD-340", "1,2,3,4,5", "09:00", "12:00", 15),
    ("Dr. Shweta Patil", "female", "PULM", "MBBS, DNB (Respiratory)", 7, "English,Marathi,Kannada,Hindi", 900, "OPD-341", "2,4,6", "15:00", "19:00", 15),
    ("Dr. Gopal Krishna", "male", "PULM", "MBBS, MD, DTCD", 29, "English,Kannada,Tamil", 1100, "OPD-342", "1,3,5", "14:00", "17:00", 15),
    ("Dr. Arun Prakash", "male", "NEPH", "MBBS, MD, DM (Nephrology)", 20, "English,Tamil,Kannada", 1300, "OPD-410", "1,3,5", "09:30", "13:00", 20),
    ("Dr. Meenakshi Sundaram", "female", "NEPH", "MBBS, MD, DNB (Nephrology)", 12, "English,Tamil", 1200, "OPD-411", "2,4,6", "14:00", "17:30", 20),
    ("Dr. Sameer Joshi", "male", "NEPH", "MBBS, MD (Medicine), DM", 8, "English,Marathi,Hindi", 1000, "OPD-412", "2,5", "09:00", "12:00", 20),
    ("Dr. Divya Bhat", "female", "ENDO", "MBBS, MD, DM (Endocrinology)", 13, "English,Kannada,Konkani", 1200, "OPD-420", "1,2,3,4,5", "10:00", "13:00", 15),
    ("Dr. Karthik Raman", "male", "ENDO", "MBBS, DNB (Endocrinology)", 9, "English,Tamil,Telugu", 1100, "OPD-421", "1,3,5,6", "15:00", "19:00", 15),
    ("Dr. Neha Gupta", "female", "ENDO", "MBBS, MD (Medicine), DM", 5, "English,Hindi,Bengali", 900, "OPD-422", "2,4", "17:00", "20:00", 15),
    ("Dr. Prakash Rao", "male", "RADI", "MBBS, MD (Radiology)", 25, "English,Kannada,Telugu", 900, "RAD-01", "1,2,3,4,5,6", "09:00", "13:00", 20),
    ("Dr. Sarah D'Souza", "female", "RADI", "MBBS, DNB (Radiology)", 11, "English,Konkani,Kannada", 900, "RAD-02", "1,2,3,4,5", "14:00", "18:00", 20),
    ("Dr. Imran Qureshi", "male", "CARD", "MBBS, MD, DM (Cardiology)", 30, "English,Hindi,Urdu", 1800, "OPD-314", "2,5", "10:00", "12:00", 20),
    ("Dr. Bhavana Shenoy", "female", "GMED", "MBBS, MD (Geriatrics)", 15, "English,Kannada,Konkani,Tulu", 700, "OPD-105", "1,2,4,5", "09:00", "12:00", 15),
    ("Dr. Aditya Verma", "male", "ORTH", "MBBS, MS, Fellowship (Spine)", 13, "English,Hindi", 1300, "OPD-405", "1,3,5", "09:00", "12:00", 20),
]

# code, name, category, dept, price, minutes, preauth, fasting hours, instructions
PROCEDURES = [
    ("MRI-BRAIN", "MRI Brain", "MRI", "RADI", 8500, 45, True, 0, "Remove all metal. Tell us about pacemakers or implants. Arrive 30 minutes early."),
    ("MRI-SPINE", "MRI Spine", "MRI", "RADI", 9500, 45, True, 0, "Remove all metal. Wear loose clothes. Arrive 30 minutes early."),
    ("MRI-KNEE", "MRI Knee", "MRI", "RADI", 7500, 30, True, 0, "Remove all metal. No fasting needed. Arrive 30 minutes early."),
    ("CT-HEAD", "CT Head", "CT", "RADI", 3500, 15, True, 0, "Bring previous scans if any. Arrive 20 minutes early."),
    ("CT-CHEST", "CT Chest", "CT", "RADI", 5500, 15, True, 4, "4 hours fasting if contrast is planned. Bring kidney function report."),
    ("CT-ABD", "CT Abdomen", "CT", "RADI", 6500, 20, True, 4, "4 hours fasting. Bring kidney function report."),
    ("XRAY-CHEST", "X-Ray Chest", "XRAY", "RADI", 450, 10, False, 0, "Remove jewellery. No preparation needed."),
    ("XRAY-KNEE", "X-Ray Knee", "XRAY", "RADI", 500, 10, False, 0, "No preparation needed."),
    ("USG-ABD", "Ultrasound Abdomen", "USG", "RADI", 1600, 20, False, 6, "6 hours fasting. Drink water and come with a full bladder."),
    ("USG-PELVIS", "Ultrasound Pelvis", "USG", "RADI", 1500, 20, False, 0, "Come with a full bladder."),
    ("ECHO", "Echocardiogram (2D Echo)", "CARDIO", "CARD", 2200, 30, False, 0, "No preparation needed."),
    ("ECG", "ECG", "CARDIO", "CARD", 300, 10, False, 0, "No preparation needed."),
    ("TMT", "Treadmill Test (TMT)", "CARDIO", "CARD", 2000, 45, False, 2, "Light meal 2 hours before. Wear walking shoes."),
    ("MAMMO", "Mammography", "XRAY", "RADI", 2500, 20, False, 0, "Avoid deodorant or powder on the day."),
    ("DEXA", "DEXA Bone Density", "XRAY", "RADI", 2800, 20, False, 0, "Avoid calcium tablets for 24 hours."),
    ("ENDOSCOPY", "Upper GI Endoscopy", "ENDO", "GAST", 4500, 30, True, 8, "8 hours fasting. Come with an attendant."),
    ("COLONOSCOPY", "Colonoscopy", "ENDO", "GAST", 7500, 45, True, 12, "Bowel preparation the day before. Come with an attendant."),
    ("PFT", "Pulmonary Function Test", "CARDIO", "PULM", 1200, 30, False, 0, "Avoid inhalers for 4 hours if your doctor agrees."),
    ("LAB-CBC", "Complete Blood Count", "LAB", "GMED", 350, 10, False, 0, "No fasting needed."),
    ("LAB-LIPID", "Lipid Profile", "LAB", "GMED", 650, 10, False, 12, "12 hours fasting. Water is fine."),
    ("LAB-HBA1C", "HbA1c", "LAB", "ENDO", 550, 10, False, 0, "No fasting needed."),
    ("LAB-THYROID", "Thyroid Profile (T3, T4, TSH)", "LAB", "ENDO", 700, 10, False, 0, "Morning sample preferred."),
    ("LAB-LFT", "Liver Function Test", "LAB", "GAST", 750, 10, False, 8, "8 hours fasting."),
    ("LAB-KFT", "Kidney Function Test", "LAB", "NEPH", 800, 10, False, 0, "No fasting needed."),
    ("LAB-VITD", "Vitamin D", "LAB", "ENDO", 1400, 10, False, 0, "No fasting needed."),
    ("LAB-B12", "Vitamin B12", "LAB", "GMED", 1100, 10, False, 0, "No fasting needed."),
    ("LAB-URINE", "Urine Routine", "LAB", "GMED", 250, 10, False, 0, "Early morning sample in the container from the lab."),
    ("LAB-FBS", "Fasting Blood Sugar", "LAB", "ENDO", 150, 10, False, 10, "10 hours fasting."),
    ("LAB-CRP", "C-Reactive Protein", "LAB", "GMED", 600, 10, False, 0, "No fasting needed."),
    ("LAB-DENGUE", "Dengue NS1 and IgM", "LAB", "GMED", 1200, 10, False, 0, "No fasting needed."),
    ("PKG-BASIC", "Basic Health Check", "PKG", "GMED", 2499, 120, False, 12, "12 hours fasting. Allow 2 to 3 hours."),
    ("PKG-EXEC", "Executive Health Check", "PKG", "GMED", 6999, 240, False, 12, "12 hours fasting. Allow half a day."),
    ("PKG-SENIOR", "Senior Citizen Health Check", "PKG", "GMED", 4999, 180, False, 12, "12 hours fasting. An attendant is welcome."),
    ("PKG-CARDIAC", "Cardiac Health Check", "PKG", "CARD", 5999, 180, False, 12, "12 hours fasting. Wear walking shoes for TMT."),
    ("PKG-WOMEN", "Women's Wellness Check", "PKG", "GYNO", 4499, 180, False, 12, "12 hours fasting."),
]

RESOURCES = [("MRI Scanner 1", "MRI"), ("MRI Scanner 2", "MRI"), ("CT Scanner 1", "CT"), ("CT Scanner 2", "CT"),
             ("X-Ray Room 1", "XRAY"), ("X-Ray Room 2", "XRAY"), ("Ultrasound Room 1", "USG"),
             ("Ultrasound Room 2", "USG"), ("Sample Collection", "LAB"), ("Cardiac Lab", "CARDIO"),
             ("Endoscopy Suite", "ENDO"), ("Health Check Lounge", "PKG")]

INSURERS = [
    ("STAR", "Star Health", "both", "Star Health in-house TPA", "Policy card, photo ID, doctor's advice, pre-authorisation form for planned procedures"),
    ("HDFCERGO", "HDFC ERGO", "both", "HDFC ERGO in-house", "E-card, photo ID, doctor's advice"),
    ("ICICILOM", "ICICI Lombard", "cashless", "ICICI Lombard in-house", "E-card, photo ID, KYC, doctor's advice"),
    ("NIVA", "Niva Bupa", "cashless", "Niva Bupa in-house", "Health card, photo ID, doctor's advice"),
    ("CARE", "Care Health", "both", "Care Health in-house", "Policy number, photo ID, doctor's advice"),
    ("ABHI", "Aditya Birla Health", "cashless", "Aditya Birla in-house", "E-card, photo ID"),
    ("TATAAIG", "Tata AIG", "both", "Medi Assist", "E-card, photo ID, doctor's advice"),
    ("BAJAJ", "Bajaj Allianz", "reimbursement", "Health Administration Team", "Original bills, discharge summary, claim form"),
    ("CGHS", "CGHS", "cashless", "CGHS Bengaluru", "CGHS card, referral letter"),
    ("ECHS", "ECHS", "cashless", "ECHS Polyclinic", "ECHS card, referral from polyclinic"),
]

HOSPITAL_INFO = {
    "address": "WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru 560037. Landmark: next to Innovative Multiplex.",
    "hours": "Outpatient clinics run Monday to Saturday, 8 AM to 8 PM. Emergency and pharmacy are open 24 hours, all days. Sunday outpatient is closed.",
    "parking": "Free parking for patients in Basement 2 for 3 hours. Valet at the main entrance. Wheelchairs are available at the entrance.",
    "visiting": "Ward visiting hours are 11 AM to 1 PM and 5 PM to 7 PM. One attendant pass per patient. ICU visits 5 PM to 6 PM only.",
    "emergency": "Our emergency department is open 24 hours on the ground floor, entrance B. For a life-threatening emergency call 108 right away.",
    "facilities": "14 specialities, 2 MRI and 2 CT scanners, 24 hour lab, pharmacy, cafeteria, ATM, prayer room, wheelchair help and a senior citizen desk.",
    "pharmacy": "The pharmacy on the ground floor is open 24 hours. Home delivery within 5 km for orders above 500 rupees.",
    "contact": "Front desk: 080 4000 1234. Email: care@wellnest.test. TPA and insurance desk: 080 4000 1250, 9 AM to 6 PM, Monday to Saturday.",
}

FIRST_M = ["Aarav", "Rohan", "Vikram", "Karthik", "Manoj", "Suresh", "Rahul", "Naveen", "Prakash", "Arun", "Sachin",
           "Ganesh", "Ravi", "Ajay", "Nikhil", "Siddharth", "Varun", "Imran", "Joseph", "Harsha", "Mahesh", "Deepak",
           "Pradeep", "Kiran", "Abdul", "Sandeep", "Vinod", "Yash", "Tejas", "Anand", "Raghav", "Srinivas", "Murali"]
FIRST_F = ["Diya", "Ananya", "Isha", "Pooja", "Divya", "Nisha", "Sneha", "Kavitha", "Meghana", "Shruti", "Lakshmi",
           "Anjali", "Bhavya", "Rekha", "Sushma", "Fathima", "Asha", "Deepika", "Swati", "Neha", "Radha", "Gayathri",
           "Pallavi", "Harini", "Sowmya", "Nandita", "Ritu", "Sana", "Priyanka", "Vidya", "Usha", "Kamala", "Savitri"]
LAST = ["Sharma", "Reddy", "Gowda", "Iyer", "Nair", "Patel", "Rao", "Kumar", "Shetty", "Joshi", "Hegde", "Menon",
        "Pillai", "Das", "Mukherjee", "Singh", "Khan", "Fernandes", "Naidu", "Kulkarni", "Bhat", "Acharya",
        "Chatterjee", "Pai", "Prasad", "Murthy", "Kamath", "Varghese", "Choudhary", "Srinivasan", "Ali", "Thomas"]
LOCALITIES = ["Marathahalli", "Whitefield", "Indiranagar", "Koramangala", "HSR Layout", "Jayanagar", "BTM Layout",
              "Bellandur", "Electronic City", "Hebbal", "Yelahanka", "Malleshwaram", "Basavanagudi", "KR Puram",
              "Banashankari", "JP Nagar", "Rajajinagar", "Sarjapur Road", "Hennur", "Kadugodi"]
REASONS = {
    "CARD": ["Chest discomfort review", "BP follow-up", "Palpitations", "ECG review", "Post-angioplasty follow-up"],
    "ORTH": ["Knee pain", "Back pain", "Shoulder pain", "Fracture follow-up", "Sports injury"],
    "NEUR": ["Migraine", "Dizziness", "Numbness in hands", "Seizure follow-up", "Memory concerns"],
    "GMED": ["Fever and cold", "Diabetes review", "Routine check-up", "Fatigue", "Cough"],
    "PAED": ["Vaccination", "Fever", "Growth check", "Cough and cold", "Stomach upset"],
    "GYNO": ["Antenatal visit", "Irregular periods", "Routine check-up", "PCOS follow-up", "Post-natal check"],
    "DERM": ["Skin rash", "Acne", "Hair fall", "Eczema", "Pigmentation"],
    "ENT": ["Ear pain", "Sinus problem", "Throat infection", "Hearing check", "Nose block"],
    "OPHT": ["Vision check", "Red eye", "Cataract review", "Spectacle power", "Diabetic eye check"],
    "GAST": ["Acidity", "Abdominal pain", "Liver function review", "Constipation", "Endoscopy review"],
    "PULM": ["Asthma review", "Breathlessness on exertion", "Chronic cough", "Snoring", "Post-COVID follow-up"],
    "NEPH": ["Kidney function review", "Swelling of feet", "High creatinine", "Dialysis review", "Kidney stone follow-up"],
    "ENDO": ["Thyroid follow-up", "Diabetes review", "Weight management", "Vitamin D deficiency", "PCOS hormones"],
    "RADI": ["Scan review", "Report discussion", "Ultrasound review", "X-ray review", "MRI report review"],
}
MEDICINES = ["Atorvastatin 10 mg", "Metformin 500 mg", "Amlodipine 5 mg", "Levothyroxine 50 mcg", "Pantoprazole 40 mg",
             "Paracetamol 650 mg", "Telmisartan 40 mg", "Vitamin D3 60000 IU", "Cetirizine 10 mg", "Montelukast 10 mg",
             "Aspirin 75 mg", "Glimepiride 1 mg", "Calcium + D3", "Salbutamol inhaler", "Rosuvastatin 10 mg"]

LAB_TESTS = {
    "Complete Blood Count": ("Blood counts are within the normal range.", {"Haemoglobin": ("13.6 g/dL", "12-16"), "WBC": ("7,200 /uL", "4,000-11,000"), "Platelets": ("2.6 lakh /uL", "1.5-4.5 lakh")}),
    "Lipid Profile": ("Cholesterol is slightly above the target; your doctor will review it.", {"Total cholesterol": ("212 mg/dL", "<200"), "LDL": ("138 mg/dL", "<100"), "HDL": ("44 mg/dL", ">40"), "Triglycerides": ("160 mg/dL", "<150")}),
    "HbA1c": ("Average sugar over 3 months is in the controlled range.", {"HbA1c": ("6.4 %", "<5.7 normal, 5.7-6.4 prediabetes")}),
    "Thyroid Profile (T3, T4, TSH)": ("Thyroid values are within the normal range.", {"T3": ("1.2 ng/mL", "0.8-2.0"), "T4": ("8.1 ug/dL", "5.1-14.1"), "TSH": ("2.9 uIU/mL", "0.27-4.2")}),
    "Liver Function Test": ("Liver tests are within the normal range.", {"SGOT": ("28 U/L", "<40"), "SGPT": ("31 U/L", "<41"), "Bilirubin": ("0.8 mg/dL", "0.3-1.2")}),
    "Kidney Function Test": ("Kidney tests are within the normal range.", {"Creatinine": ("0.9 mg/dL", "0.6-1.3"), "Urea": ("26 mg/dL", "15-40")}),
    "Vitamin D": ("Vitamin D is low; your doctor may suggest supplements.", {"25-OH Vitamin D": ("18 ng/mL", "30-100")}),
    "Vitamin B12": ("Vitamin B12 is within the normal range.", {"Vitamin B12": ("420 pg/mL", "200-900")}),
    "Urine Routine": ("Urine test shows no abnormality.", {"Protein": ("Nil", "Nil"), "Sugar": ("Nil", "Nil"), "Pus cells": ("1-2 /hpf", "0-5")}),
    "X-Ray Chest Report": ("The radiologist's report is ready to view.", None),
    "Ultrasound Abdomen Report": ("The radiologist's report is ready to view.", None),
    "MRI Knee Report": ("The radiologist's report is ready to view.", None),
    "ECG Report": ("ECG report is ready; your doctor will explain it at your visit.", None),
}

# Hospital pharmacy list (prices per pack). code, brand, generic, strength, pack, schedule, chronic, stock, price,
# restock in hours (None = in stock), cold chain, in-stock alternative code
PHARMACY = [
    ("DOLO650", "Dolo 650", "Paracetamol", "650 mg", "strip of 15 tablets", "OTC", False, 240, 32, None, False, None),
    ("CROCIN", "Crocin Advance", "Paracetamol", "500 mg", "strip of 15 tablets", "OTC", False, 150, 25, None, False, None),
    ("GELUSIL", "Gelusil MPS", "Antacid gel", "200 ml", "bottle", "OTC", False, 40, 120, None, False, None),
    ("DIGENE", "Digene Gel", "Antacid gel", "200 ml", "bottle", "OTC", False, 0, 135, 20, False, "GELUSIL"),
    ("UPRISED3", "Uprise D3 60K", "Vitamin D3 (cholecalciferol)", "60000 IU", "strip of 4 capsules", "OTC", False, 90, 130, None, False, None),
    ("NEUROBION", "Neurobion Forte", "Vitamin B complex with B12", "", "strip of 30 tablets", "OTC", False, 80, 45, None, False, None),
    ("ELECTRAL", "Electral ORS", "Oral rehydration salts", "21.8 g", "pack of 5 sachets", "OTC", False, 120, 110, None, False, None),
    ("STREPSILS", "Strepsils", "Cough and throat lozenges", "", "strip of 8 lozenges", "OTC", False, 100, 40, None, False, None),
    ("CETZINE", "Cetzine", "Cetirizine", "10 mg", "strip of 10 tablets", "OTC", False, 110, 35, None, False, None),
    ("BANDAGE", "Sterile Gauze Bandage", "Sterile bandage roll", "10 cm", "roll", "OTC", False, 60, 60, None, False, None),
    ("GLYCOMET", "Glycomet 500 SR", "Metformin", "500 mg SR", "strip of 10 tablets", "H", True, 200, 48, None, False, None),
    ("AMARYL", "Amaryl 1", "Glimepiride", "1 mg", "strip of 30 tablets", "H", True, 70, 110, None, False, None),
    ("TELMA40", "Telma 40", "Telmisartan", "40 mg", "strip of 15 tablets", "H", True, 0, 110, 24, False, "TELMICIPLA"),
    ("TELMICIPLA", "Telmisartan 40 (Cipla)", "Telmisartan", "40 mg", "strip of 15 tablets", "H", True, 120, 75, None, False, None),
    ("AMLONG5", "Amlong 5", "Amlodipine", "5 mg", "strip of 15 tablets", "H", True, 150, 38, None, False, None),
    ("ATORVA10", "Atorva 10", "Atorvastatin", "10 mg", "strip of 15 tablets", "H", True, 130, 95, None, False, None),
    ("ROSUVAS10", "Rosuvas 10", "Rosuvastatin", "10 mg", "strip of 15 tablets", "H", True, 90, 160, None, False, None),
    ("THYRONORM", "Thyronorm 50", "Levothyroxine", "50 mcg", "bottle of 100 tablets", "H", True, 60, 180, None, False, None),
    ("ECOSPRINAV", "Ecosprin-AV 75", "Aspirin + Atorvastatin", "75/10 mg", "strip of 15 capsules", "H", True, 0, 58, 26, False, "ASPATORSUN"),
    ("ASPATORSUN", "Aspirin + Atorvastatin 75/10 (Sun Pharma)", "Aspirin + Atorvastatin", "75/10 mg", "strip of 15 capsules", "H", True, 80, 42, None, False, None),
    ("PAN40", "Pan 40", "Pantoprazole", "40 mg", "strip of 15 tablets", "H", False, 140, 150, None, False, None),
    ("MONTAIRLC", "Montair LC", "Montelukast + Levocetirizine", "10/5 mg", "strip of 10 tablets", "H", False, 75, 210, None, False, None),
    ("ASTHALIN", "Asthalin Inhaler", "Salbutamol", "100 mcg", "inhaler (200 doses)", "H", True, 50, 150, None, False, None),
    ("BUDECORT", "Budecort 200 Inhaler", "Budesonide", "200 mcg", "inhaler (200 doses)", "H", True, 40, 480, None, False, None),
    ("FORACORT", "Foracort 200 Inhaler", "Formoterol + Budesonide", "6/200 mcg", "inhaler (120 doses)", "H", True, 35, 560, None, False, None),
    ("AUGMENTIN", "Augmentin 625 Duo", "Amoxicillin + Clavulanic acid", "625 mg", "strip of 6 tablets", "H1", False, 90, 220, None, False, None),
    ("AZITHRAL", "Azithral 500", "Azithromycin", "500 mg", "strip of 3 tablets", "H1", False, 120, 120, None, False, None),
    ("LANTUS", "Lantus SoloStar", "Insulin glargine", "100 IU/ml", "1 pen (3 ml)", "H", True, 30, 780, None, True, None),
    ("MIXTARD", "Human Mixtard 30/70", "Human insulin (biphasic isophane)", "40 IU/ml", "1 vial (10 ml)", "H", True, 25, 180, None, True, None),
    ("ZOLFRESH", "Zolfresh 10", "Zolpidem", "10 mg", "strip of 10 tablets", "X", False, 20, 95, None, False, None),
    ("ALPRAX", "Alprax 0.25", "Alprazolam", "0.25 mg", "strip of 15 tablets", "X", False, 20, 40, None, False, None),
    ("CLONOTRIL", "Clonotril 0.5", "Clonazepam", "0.5 mg", "strip of 10 tablets", "X", False, 15, 55, None, False, None),
]
# Starting HealthCredits (1 credit = 1 rupee) by persona key; Priya's 400 shows the split payment.
WALLETS = {"shanthamma": 3500, "rahul": 1800, "arjun": 1000, "priya": 400, "meera": 500}


def _pharmacy_rows(now: datetime) -> list[dict]:
    return [dict(medicine_code=c, brand_name=b, generic_name=g, strength=st, pack=pk, schedule_class=sch, chronic=ch,
                 stock_qty=q, unit_price_inr=pr, restock_eta=(now + timedelta(hours=h)).replace(minute=0, second=0) if h else None,
                 cold_chain=cold, alternative_code=alt, updated_at=now)
            for c, b, g, st, pk, sch, ch, q, pr, h, cold, alt in PHARMACY]


def _persona_rx(T: date) -> list[dict]:
    """Maintenance medicines for the demo: Rahul's diabetes and BP prescriptions (refill due in 4 days),
    Shanthamma's Metformin (refill due in 4 days). Dr. Anil Kumar = 11, Dr. Sneha Rao = 12, Dr. Rajesh Iyer = 1."""
    return [dict(patient_id=4, doctor_id=11, medicine_name="Metformin 500 mg SR", dosage="Twice daily after meals",
                 start_date=T - timedelta(days=20), end_date=T + timedelta(days=4)),
            dict(patient_id=4, doctor_id=12, medicine_name="Telmisartan 40 mg", dosage="Once daily in the morning",
                 start_date=T - timedelta(days=26), end_date=T + timedelta(days=4)),
            dict(patient_id=1, doctor_id=1, medicine_name="Metformin 500 mg SR", dosage="Once daily after dinner",
                 start_date=T - timedelta(days=26), end_date=T + timedelta(days=4))]


def ensure_extras() -> dict:
    """Repeat-safe additions for a database seeded before these features: pharmacy list, wallets, demo
    prescriptions, and the real demo emails from DEMO_PERSONA_EMAILS. Runs at every start."""
    done = {}
    T, NOW = config.today(), config.now()
    with db.engine.begin() as c:
        if not c.execute(select(func.count()).select_from(db.pharmacy_inventory)).scalar():
            c.execute(db.pharmacy_inventory.insert(), _pharmacy_rows(NOW))
            done["pharmacy"] = len(PHARMACY)
        for i, p in enumerate(PERSONAS):
            pid = i + 1
            if not c.execute(select(db.patients.c.id).where(db.patients.c.id == pid, db.patients.c.phone == p["phone"])).first():
                continue
            if not c.execute(select(db.health_credit_wallets.c.patient_id).where(db.health_credit_wallets.c.patient_id == pid)).first():
                c.execute(db.health_credit_wallets.insert().values(patient_id=pid, balance=WALLETS.get(p["key"], 0), updated_at=NOW))
                done["wallets"] = done.get("wallets", 0) + 1
            real = config.DEMO_PERSONA_EMAILS.get(p["key"])
            if real:
                c.execute(db.patients.update().where(db.patients.c.id == pid).values(email=real, web_email=real.lower()))
        for rx in _persona_rx(T):
            if not c.execute(select(db.prescriptions.c.id).where(db.prescriptions.c.patient_id == rx["patient_id"],
                                                                 db.prescriptions.c.medicine_name == rx["medicine_name"])).first():
                c.execute(db.prescriptions.insert().values(**rx))
                done["prescriptions"] = done.get("prescriptions", 0) + 1
    return done


# Demo personas (fixed, created first). Emails come from DEMO_PERSONA_EMAILS when set.
PERSONAS = [
    dict(key="shanthamma", name="Shanthamma K", phone="+919845000001", dob=date(1959, 3, 4), gender="female",
         language="Kannada", pref="morning", insurer="STAR", caregiver=("Ravi K", "son", "+919845000011", "ravi.k.caregiver@example.com"),
         consent=True, mobility="Uses a walking stick; needs wheelchair help at the entrance", locality="Jayanagar"),
    dict(key="arjun", name="Arjun Mehta", phone="+919845000002", dob=date(1992, 6, 15), gender="male",
         language="English", pref="morning", insurer="HDFCERGO", caregiver=None, consent=False, mobility=None, locality="Whitefield"),
    dict(key="priya", name="Priya Nair", phone="+919845000003", dob=date(1997, 1, 20), gender="female",
         language="English", pref="afternoon", insurer="NIVA", caregiver=None, consent=False, mobility=None, locality="Koramangala"),
    dict(key="rahul", name="Rahul Verma", phone="+919845000004", dob=date(1981, 9, 10), gender="male",
         language="Hindi", pref="evening", insurer=None, caregiver=None, consent=False, mobility=None, locality="Marathahalli"),
    dict(key="meera", name="Meera Joshi", phone="+919845000005", dob=date(2018, 5, 12), gender="female",
         language="English", pref="morning", insurer="ICICILOM", caregiver=("Sanjay Joshi", "father", "+919845000015", "sanjay.joshi@example.com"),
         consent=True, mobility=None, locality="HSR Layout"),
]


def doctor_slots(start: str, end: str, minutes: int) -> list[str]:
    s = datetime.combine(date.today(), time.fromisoformat(start))
    e = datetime.combine(date.today(), time.fromisoformat(end))
    out = []
    while s + timedelta(minutes=minutes) <= e:
        out.append(s.strftime("%H:%M"))
        s += timedelta(minutes=minutes)
    return out


def persona_email(key: str, default: str) -> str:
    return config.DEMO_PERSONA_EMAILS.get(key) or default


def migrate_brand() -> None:
    """One-time, repeat-safe rename of data written before the CareLine -> WellNest rename."""
    with db.engine.begin() as c:
        c.execute(text("UPDATE appointments SET booking_code = 'WN-' || substr(booking_code, 4) WHERE booking_code LIKE 'CL-%'"))
        c.execute(text("UPDATE hospital_info SET content = replace(replace(replace(content, 'CareLine', 'WellNest'), 'careline', 'wellnest'), 'CARELINE', 'WELLNEST') "
                       "WHERE lower(content) LIKE '%careline%'"))
        c.execute(text("UPDATE interaction_notes SET summary = replace(summary, 'CareLine', 'WellNest') WHERE summary LIKE '%CareLine%'"))


def is_seeded() -> bool:
    try:
        with db.engine.connect() as c:
            return (c.execute(select(func.count()).select_from(db.doctors)).scalar() or 0) > 0
    except Exception:
        return False


def reset(verbose: bool = True) -> dict:
    db.drop_schema()
    db.create_schema()
    return seed(verbose)


def seed(verbose: bool = False) -> dict:
    rnd = random.Random(SEED)
    t0 = datetime.now()
    T = config.today()
    NOW = config.now()
    rows: dict[str, list] = {}

    # ---------------- reference
    rows["departments"] = [dict(id=i + 1, code=c, name=n, floor=f, description=d) for i, (c, n, f, d) in enumerate(DEPARTMENTS)]
    dept_id = {c: i + 1 for i, (c, *_r) in enumerate(DEPARTMENTS)}
    rows["doctors"] = []
    for i, (n, g, dp, q, x, langs, fee, room, days, s, e, sm) in enumerate(DOCTORS):
        rows["doctors"].append(dict(id=i + 1, code=f"DOC-{i + 1:03d}", name=n, gender=g, department_id=dept_id[dp],
                                    qualification=q, experience_years=x, languages=langs, fee_inr=fee, room=room,
                                    consult_days=days, start_time=s, end_time=e, slot_minutes=sm,
                                    bio=f"{n.split(' ', 1)[1]} has {x} years of experience in {DEPARTMENTS[dept_id[dp] - 1][1]}."))
    rows["procedures"] = [dict(id=i + 1, code=c, name=n, category=cat, department_id=dept_id[dp], price_inr=p,
                               duration_minutes=m, preauth_required=pa, fasting_hours=fh, instructions=ins)
                          for i, (c, n, cat, dp, p, m, pa, fh, ins) in enumerate(PROCEDURES)]
    rows["resources"] = [dict(id=i + 1, name=n, category=c) for i, (n, c) in enumerate(RESOURCES)]
    rows["insurers"] = [dict(id=i + 1, code=c, name=n, mode=m, tpa_name=t, documents=d,
                             notes="Pre-authorisation is needed for MRI, CT and endoscopy.")
                        for i, (c, n, m, t, d) in enumerate(INSURERS)]
    ins_id = {c: i + 1 for i, (c, *_r) in enumerate(INSURERS)}
    cov = []
    for ins in rows["insurers"]:
        generous = ins["code"] in ("STAR", "HDFCERGO", "NIVA", "CGHS", "ECHS")
        for p in rows["procedures"]:
            if p["category"] == "PKG":
                c, cp = ("partial", 50) if generous else ("no", 0)
            elif p["category"] in ("MRI", "CT", "ENDO"):
                c, cp = ("yes", 0) if generous else ("partial", rnd.choice([10, 20, 30]))
            else:
                c, cp = rnd.choice([("yes", 0), ("yes", 0), ("partial", 10), ("partial", 20)])
            cov.append(dict(insurer_id=ins["id"], procedure_id=p["id"], department_id=None, coverage=c, copay_percent=cp,
                            cap_inr=(12000 if p["category"] in ("MRI", "CT") else None),
                            preauth_required=p["preauth_required"], preauth_turnaround_hours=24 if generous else 48))
        for d in rows["departments"]:
            if d["code"] == "DERM":
                c, cp = "partial", 50
            else:
                c, cp = ("yes", 10) if generous else ("partial", 20)
            cov.append(dict(insurer_id=ins["id"], procedure_id=None, department_id=d["id"], coverage=c, copay_percent=cp,
                            cap_inr=None, preauth_required=False, preauth_turnaround_hours=24))
    rows["coverage_rules"] = cov
    rows["hospital_info"] = [dict(topic=k, content=v) for k, v in HOSPITAL_INFO.items()]

    # ---------------- patients
    pats = []
    demo_hash = hash_password(config.DEMO_PASSWORD)
    for i, p in enumerate(PERSONAS):
        cg = p["caregiver"]
        email = persona_email(p["key"], f"{p['key']}.demo@example.com")
        pats.append(dict(id=i + 1, patient_code=f"PT-{100001 + i}", full_name=p["name"], phone=p["phone"],
                         date_of_birth=p["dob"], gender=p["gender"], email=email, address=f"{p['locality']}, Bengaluru",
                         preferred_language=p["language"], preferred_time=p["pref"],
                         insurer_id=ins_id.get(p["insurer"]) if p["insurer"] else None,
                         policy_number=f"POL{rnd.randint(10_000_000, 99_999_999)}" if p["insurer"] else None,
                         caregiver_name=cg[0] if cg else None, caregiver_relation=cg[1] if cg else None,
                         caregiver_phone=cg[2] if cg else None, caregiver_email=cg[3] if cg else None,
                         caregiver_consent=p["consent"], mobility_needs=p["mobility"], is_guest=False,
                         password_hash=demo_hash, web_email=email.lower(), created_at=NOW - timedelta(days=400)))
    used_phones = {p["phone"] for p in pats}
    n_pat = 600
    for i in range(len(pats), n_pat):
        r = rnd.random()
        if r < 0.15:
            age = rnd.randint(0, 14)
        elif r < 0.37:
            age = rnd.randint(60, 92)
        else:
            age = rnd.randint(18, 59)
        g = rnd.choice(["male", "female"])
        first = rnd.choice(FIRST_M if g == "male" else FIRST_F)
        last = rnd.choice(LAST)
        while True:
            ph = f"+9198{rnd.randint(10_000_000, 99_999_999)}"
            if ph not in used_phones and not ph.startswith("+91984500"):
                used_phones.add(ph)
                break
        dob = T - timedelta(days=age * 365 + rnd.randint(0, 364))
        insured = rnd.random() < 0.7
        child = age < 15
        cg_name = f"{rnd.choice(FIRST_M + FIRST_F)} {last}" if child or (age >= 70 and rnd.random() < 0.6) else None
        pats.append(dict(id=i + 1, patient_code=f"PT-{100001 + i}", full_name=f"{first} {last}", phone=ph,
                         date_of_birth=dob, gender=g, email=f"{first.lower()}.{last.lower()}.{i}@example.com",
                         address=f"{rnd.choice(LOCALITIES)}, Bengaluru",
                         preferred_language=rnd.choice(["English", "English", "Kannada", "Hindi", "Tamil", "Telugu", "Malayalam"]),
                         preferred_time=rnd.choice(["any", "any", "morning", "afternoon", "evening"]),
                         insurer_id=rnd.randint(1, len(INSURERS)) if insured else None,
                         policy_number=f"POL{rnd.randint(10_000_000, 99_999_999)}" if insured else None,
                         caregiver_name=cg_name, caregiver_relation=("parent" if child else "child") if cg_name else None,
                         caregiver_phone=f"+9197{rnd.randint(10_000_000, 99_999_999)}" if cg_name else None,
                         caregiver_email=f"caregiver.{i}@example.com" if cg_name else None,
                         caregiver_consent=bool(cg_name) and rnd.random() < 0.8,
                         mobility_needs=rnd.choice([None, None, None, "Wheelchair at entrance", "Walker"]) if age >= 70 else None,
                         is_guest=False, password_hash=None, web_email=None,
                         created_at=NOW - timedelta(days=rnd.randint(10, 900))))
    rows["patients"] = pats
    ages = {p["id"]: (T - p["date_of_birth"]).days // 365 for p in pats}
    pool_child = [p["id"] for p in pats[5:] if ages[p["id"]] < 15]
    pool_adult = [p["id"] for p in pats[5:] if ages[p["id"]] >= 15]
    pool_women = [p["id"] for p in pats[5:] if 18 <= ages[p["id"]] <= 55 and p["gender"] == "female"]

    # ---------------- appointments
    appts, codes = [], set()

    def new_code(prefix):
        while True:
            c = f"{prefix}-{rnd.randint(10000, 99999)}"
            if c not in codes:
                codes.add(c)
                return c

    def add_appt(**kw):
        a = dict(id=len(appts) + 1, booking_code=new_code("WN"), procedure_id=None, resource_id=None, reason=None,
                 idempotency_key=None, cancelled_at=None, cancel_reason=None, doctor_id=None)
        a.update(kw)
        a.setdefault("updated_at", a["created_at"])
        appts.append(a)
        return a

    taken = set()   # (doctor_id, date, time) for active bookings
    iyer, kavya = 1, 2
    persona_slots = {}
    # Persona bookings first so they never collide with random ones.
    def next_consult(doc_idx, start_offset):
        d = DOCTORS[doc_idx - 1]
        days = {int(x) for x in d[8].split(",")}
        for k in range(start_offset, start_offset + 14):
            dd = T + timedelta(days=k)
            if dd.isoweekday() in days:
                return dd
    s_day = next_consult(iyer, 1)
    persona_slots["shanthamma"] = add_appt(patient_id=1, doctor_id=iyer, appt_date=s_day, appt_time="10:30", status="booked",
                                           reason="BP and chest discomfort review", channel="web", created_at=NOW - timedelta(days=5))
    persona_slots["shanthamma"]["booking_code"] = "WN-48213"
    codes.add("WN-48213")
    taken.add((iyer, s_day, "10:30"))
    m_day = next_consult(15, 2)  # Dr. Lakshmi Nair, paediatrics
    add_appt(patient_id=5, doctor_id=15, appt_date=m_day, appt_time="10:00", status="booked", reason="Vaccination",
             channel="chat", created_at=NOW - timedelta(days=3))
    taken.add((15, m_day, "10:00"))

    window_past, window_future = 28, 14
    for di, d in enumerate(DOCTORS):
        doc_id = di + 1
        days = {int(x) for x in d[8].split(",")}
        grid = doctor_slots(d[9], d[10], d[11])
        dept = d[2]
        for k in range(-window_past, window_future + 1):
            dd = T + timedelta(days=k)
            if dd.isoweekday() not in days or dd.isoweekday() == 7:
                continue
            for hh in grid:
                if (doc_id, dd, hh) in taken:
                    continue
                if k < 0 or (k == 0 and hh < NOW.strftime("%H:%M")):
                    occ = 0.6
                else:
                    occ = max(0.22, 0.62 - 0.03 * k) + (0.08 if hh < "12:00" else 0) + (0.06 if dd.isoweekday() == 1 else 0)
                # Dr. Rajesh Iyer is fully booked for the coming week (waitlist demo)
                if doc_id == iyer and 0 <= k <= 7:
                    occ = 1.0
                if rnd.random() >= occ:
                    continue
                pool = pool_child if dept == "PAED" else pool_women if dept == "GYNO" else pool_adult
                pid = rnd.choice(pool)
                created = datetime.combine(dd, time(9)) - timedelta(days=rnd.randint(1, 20), minutes=rnd.randint(0, 600))
                if created >= datetime.combine(T, time(0)):   # never stamp seeded bookings as made today
                    created = NOW - timedelta(days=rnd.randint(1, 12), minutes=rnd.randint(0, 600))
                past = k < 0 or (k == 0 and hh < NOW.strftime("%H:%M"))
                if past:
                    r = rnd.random()
                    status = "completed" if r < 0.85 else ("no_show" if r < 0.91 else "cancelled")
                else:
                    # (no cancelled holes in Dr. Iyer's fully booked week, so the waitlist demo holds)
                    status = "cancelled" if rnd.random() < 0.05 and not (doc_id == iyer and k <= 7) else "booked"
                ch = rnd.choices(["web", "voice", "chat", "staff"], [35, 30, 30, 5])[0]
                a = add_appt(patient_id=pid, doctor_id=doc_id, appt_date=dd, appt_time=hh, status=status,
                             reason=rnd.choice(REASONS[dept]), channel=ch, created_at=created)
                if status == "cancelled":
                    a["cancelled_at"] = created + timedelta(days=1)
                    a["cancel_reason"] = rnd.choice(["Feeling better", "Travel", "Clash with work", "Booked elsewhere"])
                else:
                    taken.add((doc_id, dd, hh))
    # Past persona visits (history + memory)
    def past_visit(pid, doc_id, days_ago, hh, reason):
        dd = T - timedelta(days=days_ago)
        while (doc_id, dd, hh) in taken:
            dd -= timedelta(days=7)
        taken.add((doc_id, dd, hh))
        return add_appt(patient_id=pid, doctor_id=doc_id, appt_date=dd, appt_time=hh, status="completed", reason=reason,
                        channel="voice", created_at=datetime.combine(dd, time(8)) - timedelta(days=3))
    s_ortho = past_visit(1, 5, 9, "09:15", "Knee pain")
    p_endo = past_visit(3, 38, 12, "10:15", "Thyroid follow-up")
    r_gmed = past_visit(4, 11, 20, "11:00", "Fever and fatigue")
    # Procedure bookings (resource slots)
    proc_by_code = {p["code"]: p for p in rows["procedures"]}
    res_by_cat = {}
    for r in rows["resources"]:
        res_by_cat.setdefault(r["category"], []).append(r["id"])
    taken_res = set()
    for _ in range(260):
        p = rnd.choice(rows["procedures"])
        k = rnd.randint(-20, 10)
        dd = T + timedelta(days=k)
        if dd.isoweekday() == 7:
            continue
        hh = f"{rnd.randint(8, 19):02d}:{rnd.choice(['00', '30'])}"
        rid = rnd.choice(res_by_cat[p["category"]])
        if (rid, dd, hh) in taken_res:
            continue
        taken_res.add((rid, dd, hh))
        past = k < 0
        add_appt(patient_id=rnd.choice(pool_adult), procedure_id=p["id"], resource_id=rid, appt_date=dd, appt_time=hh,
                 status="completed" if past else "booked", reason=p["name"], channel=rnd.choice(["web", "chat", "voice"]),
                 created_at=datetime.combine(dd, time(8)) - timedelta(days=rnd.randint(1, 10)))
    # Shanthamma's MRI Knee (done 2 days ago, report pending)
    mri = proc_by_code["MRI-KNEE"]
    mri_day = T - timedelta(days=2) if (T - timedelta(days=2)).isoweekday() != 7 else T - timedelta(days=3)
    s_mri = add_appt(patient_id=1, procedure_id=mri["id"], resource_id=res_by_cat["MRI"][0], appt_date=mri_day,
                     appt_time="09:30", status="completed", reason="MRI Knee", channel="voice",
                     created_at=datetime.combine(mri_day, time(8)) - timedelta(days=4))
    rows["appointments"] = appts

    # ---------------- lab reports, prescriptions, bills
    labs, rx, bills = [], [], []
    lab_codes, bill_codes = set(), set()

    def code(prefix, used):
        while True:
            c = f"{prefix}-{rnd.randint(10000, 99999)}"
            if c not in used:
                used.add(c)
                return c
    test_names = [t for t in LAB_TESTS if LAB_TESTS[t][1]]
    for a in appts:
        if a["status"] != "completed" or a["patient_id"] <= 5:
            continue
        if rnd.random() < 0.4:
            tn = rnd.choice(test_names)
            ordered = datetime.combine(a["appt_date"], time.fromisoformat(a["appt_time"]))
            days_since = (T - a["appt_date"]).days
            if days_since <= 2 and rnd.random() < 0.5:
                st, ready, exp = "pending", None, ordered + timedelta(hours=rnd.randint(24, 60))
            else:
                ready = ordered + timedelta(hours=rnd.randint(6, 36))
                st, exp = ("collected" if rnd.random() < 0.55 else "ready"), None
            summ, res = LAB_TESTS[tn]
            labs.append(dict(report_code=code("LR", lab_codes), patient_id=a["patient_id"], appointment_id=a["id"],
                             doctor_id=a["doctor_id"], test_name=tn, status=st, ordered_at=ordered, expected_at=exp,
                             ready_at=ready, summary=summ if st != "pending" else None,
                             results={k: {"value": v[0], "range": v[1]} for k, v in res.items()} if st != "pending" else None))
        if a["doctor_id"] and rnd.random() < 0.35:
            rx.append(dict(patient_id=a["patient_id"], doctor_id=a["doctor_id"], medicine_name=rnd.choice(MEDICINES),
                           dosage=rnd.choice(["Once daily after breakfast", "Twice daily after food", "At bedtime"]),
                           start_date=a["appt_date"], end_date=a["appt_date"] + timedelta(days=rnd.choice([30, 60, 90]))))
        if rnd.random() < 0.7:
            amount = rows["doctors"][a["doctor_id"] - 1]["fee_inr"] if a["doctor_id"] else rows["procedures"][a["procedure_id"] - 1]["price_inr"]
            pinfo = pats[a["patient_id"] - 1]
            ins_paid = int(amount * 0.8) if pinfo["insurer_id"] and amount > 2000 else 0
            st = rnd.choices(["paid", "due", "partially_paid"], [85, 10, 5])[0]
            bills.append(dict(bill_code=code("BL", bill_codes), patient_id=a["patient_id"], appointment_id=a["id"],
                              description=("Consultation" if a["doctor_id"] else rows["procedures"][a["procedure_id"] - 1]["name"]),
                              amount_inr=amount, insurer_paid_inr=ins_paid, status=st,
                              due_date=a["appt_date"] + timedelta(days=15),
                              created_at=datetime.combine(a["appt_date"], time(18))))
    # persona records
    labs.append(dict(report_code="LR-20931", patient_id=3, appointment_id=p_endo["id"], doctor_id=38,
                     test_name="Thyroid Profile (T3, T4, TSH)", status="ready",
                     ordered_at=datetime.combine(p_endo["appt_date"], time(10, 30)), expected_at=None,
                     ready_at=NOW - timedelta(days=1, hours=3), summary=LAB_TESTS["Thyroid Profile (T3, T4, TSH)"][0],
                     results={k: {"value": v[0], "range": v[1]} for k, v in LAB_TESTS["Thyroid Profile (T3, T4, TSH)"][1].items()}))
    labs.append(dict(report_code="LR-20932", patient_id=3, appointment_id=p_endo["id"], doctor_id=38,
                     test_name="Vitamin D", status="collected", ordered_at=datetime.combine(p_endo["appt_date"], time(10, 30)),
                     expected_at=None, ready_at=datetime.combine(p_endo["appt_date"], time(20)),
                     summary=LAB_TESTS["Vitamin D"][0],
                     results={k: {"value": v[0], "range": v[1]} for k, v in LAB_TESTS["Vitamin D"][1].items()}))
    labs.append(dict(report_code="LR-20940", patient_id=1, appointment_id=s_mri["id"], doctor_id=41, test_name="MRI Knee Report",
                     status="pending", ordered_at=datetime.combine(mri_day, time(9, 30)),
                     expected_at=datetime.combine(T, time(18)) + timedelta(days=1), ready_at=None, summary=None, results=None))
    labs.append(dict(report_code="LR-20941", patient_id=1, appointment_id=s_ortho["id"], doctor_id=5, test_name="X-Ray Knee Report",
                     status="collected", ordered_at=datetime.combine(s_ortho["appt_date"], time(9, 30)), expected_at=None,
                     ready_at=datetime.combine(s_ortho["appt_date"], time(15)), summary="The radiologist's report is ready to view.",
                     results=None))
    bills.append(dict(bill_code="BL-55012", patient_id=4, appointment_id=r_gmed["id"], description="Consultation and blood tests",
                      amount_inr=2350, insurer_paid_inr=0, status="due", due_date=T + timedelta(days=3),
                      created_at=datetime.combine(r_gmed["appt_date"], time(18))))
    bills.append(dict(bill_code="BL-55013", patient_id=1, appointment_id=s_mri["id"], description="MRI Knee",
                      amount_inr=7500, insurer_paid_inr=7500, status="paid", due_date=mri_day + timedelta(days=15),
                      created_at=datetime.combine(mri_day, time(18))))
    rx.append(dict(patient_id=1, doctor_id=1, medicine_name="Amlodipine 5 mg", dosage="Once daily after breakfast",
                   start_date=T - timedelta(days=60), end_date=T + timedelta(days=30)))
    rx.append(dict(patient_id=3, doctor_id=38, medicine_name="Vitamin D3 60000 IU", dosage="Once a week for 8 weeks",
                   start_date=p_endo["appt_date"], end_date=p_endo["appt_date"] + timedelta(days=56)))
    rows["lab_reports"], rows["prescriptions"], rows["bills"] = labs, rx, bills

    # ---------------- waitlist (Arjun is first in line for Dr. Rajesh Iyer)
    wl, wl_codes = [], set()
    wl.append(dict(code="WL-3392", patient_id=2, department_id=dept_id["CARD"], doctor_id=iyer, date_from=T,
                   date_to=T + timedelta(days=7), time_preference="any", urgent=False, status="waiting",
                   created_at=NOW - timedelta(days=2)))
    wl_codes.add("WL-3392")
    popular = [3, 5, 8, 11, 15, 18, 21, 26, 29, 38]
    for _ in range(39):
        doc = rnd.choice(popular)
        wl.append(dict(code=code("WL", wl_codes), patient_id=rnd.choice(pool_adult[:200]),
                       department_id=rows["doctors"][doc - 1]["department_id"], doctor_id=doc,
                       date_from=T + timedelta(days=rnd.randint(0, 2)), date_to=T + timedelta(days=rnd.randint(3, 9)),
                       time_preference=rnd.choice(["any", "morning", "afternoon"]), urgent=rnd.random() < 0.08,
                       status="waiting", created_at=NOW - timedelta(hours=rnd.randint(2, 120))))
    rows["waitlist"] = wl

    # ---------------- memory, support, feedback
    topics = [("Asked about MRI Knee preparation; told no fasting is needed and to remove metal.", "mri,preparation"),
              ("Asked whether Star Health covers cardiology consultation; explained 10 percent co-pay.", "insurance,coverage"),
              ("Rescheduled dermatology visit to the next Saturday.", "reschedule,dermatology"),
              ("Asked for parking details; told Basement 2 is free for 3 hours.", "parking"),
              ("Asked when the blood test report will be ready; told by evening.", "lab report"),
              ("Wanted a Kannada-speaking doctor for knee pain; booked Dr. Kiran Shetty.", "booking,orthopaedics,language"),
              ("Asked about visiting hours for a relative in the ward.", "visiting"),
              ("Requested a payment link for an outstanding bill.", "billing"),
              ("Asked about the senior citizen health check package and price.", "health check,senior")]
    notes = []
    for _ in range(800):
        pid = rnd.choice(pats[5:])["id"]
        s, tp = rnd.choice(topics)
        notes.append(dict(patient_id=pid, phone=pats[pid - 1]["phone"], channel=rnd.choice(["chat", "voice"]), summary=s,
                          topics=tp, outcome=rnd.choice(["resolved", "resolved", "booked", "informed"]),
                          created_at=NOW - timedelta(days=rnd.randint(1, 90), minutes=rnd.randint(0, 900))))
    notes += [
        dict(patient_id=3, phone="+919845000003", channel="chat", summary="Asked whether her MRI report from last month could be emailed; told it is in the portal under Lab reports.",
             topics="mri,report,email", outcome="informed", created_at=NOW - timedelta(days=6, hours=2)),
        dict(patient_id=3, phone="+919845000003", channel="voice", summary="Asked when the thyroid test result will be ready; told within 24 hours.",
             topics="thyroid,lab report", outcome="informed", created_at=NOW - timedelta(days=2, hours=5)),
        dict(patient_id=1, phone="+919845000001", channel="voice", summary="Son Ravi asked for wheelchair help for her cardiology visit; noted on file.",
             topics="wheelchair,caregiver,cardiology", outcome="resolved", created_at=NOW - timedelta(days=5, hours=1)),
        dict(patient_id=1, phone="+919845000001", channel="voice", summary="Asked when the MRI Knee report will be ready; told it is expected tomorrow evening.",
             topics="mri,report", outcome="informed", created_at=NOW - timedelta(days=1, hours=4)),
    ]
    rows["interaction_notes"] = notes
    res = []
    for a in appts:
        if a["created_at"] >= NOW - timedelta(days=10):
            res.append(dict(patient_id=a["patient_id"], actor="agent" if a["channel"] in ("chat", "voice") else "web",
                            action="book_appointment", ref=a["booking_code"], ok=True, channel=a["channel"],
                            summary=f"Booked {a['reason'] or 'visit'} for {a['appt_date'].isoformat()} {a['appt_time']}",
                            created_at=a["created_at"]))
            if a["status"] == "cancelled" and a["cancelled_at"]:
                res.append(dict(patient_id=a["patient_id"], actor="agent", action="cancel_appointment", ref=a["booking_code"],
                                ok=True, channel=a["channel"], summary=f"Cancelled: {a['cancel_reason']}",
                                created_at=min(a["cancelled_at"], NOW)))
    rows["resolutions"] = res
    ho, cb, fb = [], [], []
    ho_codes, cb_codes = set(), set()
    for _ in range(60):
        pid = rnd.choice(pats[5:])["id"]
        pr = "urgent" if rnd.random() < 0.2 else "normal"
        ho.append(dict(handoff_code=code("HO", ho_codes), patient_id=pid, phone=pats[pid - 1]["phone"], priority=pr,
                       reason_code="emergency" if pr == "urgent" else rnd.choice(["complaint", "complex", "requested_human"]),
                       summary="Caller reported severe symptoms; advised to call 108." if pr == "urgent" else rnd.choice(
                           ["Billing dispute about an old bill.", "Wants to speak to a person about surgery costs.",
                            "Complex insurance claim question."]),
                       status="closed", assigned_to=rnd.choice(["Anita (front desk)", "Joseph (TPA desk)", "Nurse Rekha"]),
                       created_at=NOW - timedelta(days=rnd.randint(1, 30))))
    for _ in range(40):
        pid = rnd.choice(pats[5:])["id"]
        cb.append(dict(callback_code=code("CB", cb_codes), patient_id=pid, phone=pats[pid - 1]["phone"],
                       preferred_time=rnd.choice(["Tomorrow morning", "After 6 PM", "Any time"]),
                       reason=rnd.choice(["Surgery cost estimate", "Insurance claim help", "Report explanation"]),
                       status=rnd.choice(["done", "done", "queued"]), created_at=NOW - timedelta(days=rnd.randint(0, 14))))
    done = [a for a in appts if a["status"] == "completed"]
    for a in rnd.sample(done, min(500, len(done))):
        fb.append(dict(patient_id=a["patient_id"], appointment_id=a["id"], rating=rnd.choices([5, 4, 3, 2, 1], [55, 30, 9, 4, 2])[0],
                       comment=rnd.choice([None, "Doctor explained everything clearly.", "Short waiting time.",
                                           "Booking on chat was quick.", "Parking was difficult.", None]),
                       created_at=datetime.combine(a["appt_date"], time(19))))
    rows["handoffs"], rows["callbacks"], rows["feedback"] = ho, cb, fb

    # ---------------- write
    order = ["departments", "doctors", "procedures", "resources", "insurers", "coverage_rules", "hospital_info", "patients",
             "appointments", "lab_reports", "prescriptions", "bills", "waitlist", "interaction_notes", "resolutions",
             "handoffs", "callbacks", "feedback"]
    with db.engine.begin() as c:
        for name in order:
            data = rows[name]
            tbl = db.md.tables[name]
            for i in range(0, len(data), 2000):
                c.execute(tbl.insert(), data[i:i + 2000])
        if db.IS_POSTGRES:
            for name in db.md.tables:
                if "id" in db.md.tables[name].c:
                    c.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                                   f"COALESCE((SELECT MAX(id) FROM {name}), 0) + 1, false)"))
    counts = {k: len(v) for k, v in rows.items()}
    counts.update(ensure_extras())
    counts["seconds"] = round((datetime.now() - t0).total_seconds(), 1)
    if verbose:
        print(counts)
    return counts


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset()
    else:
        db.create_schema()
        if not is_seeded():
            seed(verbose=True)
        else:
            print("Already seeded. Use --reset to rebuild.")
