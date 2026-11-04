# Knowledge base (RAG) contents

Generated from `app/kb.py` and the database. Live view with embedding status: `/api/ops/kb?token=<DASHBOARD_TOKEN>` (`&kind=policy`, `&full=true`).

**111 passages.** Each is one speakable answer returned by `get_hospital_info` (and `suggest_department` for departments).

## Hospital information (8)

| Ref | Title | Text |
|---|---|---|
| `kb:info:address` | Address | WellNest Hospitals, 42 Outer Ring Road, Marathahalli, Bengaluru 560037. Landmark: next to Innovative Multiplex… |
| `kb:info:hours` | Hours | Outpatient clinics run Monday to Saturday, 8 AM to 8 PM. Emergency and pharmacy are open 24 hours, all days. S… |
| `kb:info:parking` | Parking | Free parking for patients in Basement 2 for 3 hours. Valet at the main entrance. Wheelchairs are available at … |
| `kb:info:visiting` | Visiting | Ward visiting hours are 11 AM to 1 PM and 5 PM to 7 PM. One attendant pass per patient. ICU visits 5 PM to 6 P… |
| `kb:info:emergency` | Emergency | Our emergency department is open 24 hours on the ground floor, entrance B. For a life-threatening emergency ca… |
| `kb:info:facilities` | Facilities | 14 specialities, 2 MRI and 2 CT scanners, 24 hour lab, pharmacy, cafeteria, ATM, prayer room, wheelchair help … |
| `kb:info:pharmacy` | Pharmacy | The pharmacy on the ground floor is open 24 hours. Home delivery within 5 km for orders above 500 rupees. |
| `kb:info:contact` | Contact | Front desk: 080 4000 1234. Email: care@wellnest.test. TPA and insurance desk: 080 4000 1250, 9 AM to 6 PM, Mon… |

## Departments (14)

| Ref | Title | Text |
|---|---|---|
| `kb:dept:CARD` | Cardiology | Cardiology (3rd floor): Heart and blood vessel care: chest pain review, BP, ECG, echo, TMT. Common reasons to … |
| `kb:dept:ORTH` | Orthopaedics | Orthopaedics (4th floor): Bones, joints, spine, sports injuries and fractures. Common reasons to visit: knee p… |
| `kb:dept:NEUR` | Neurology | Neurology (3rd floor): Headache, seizures, stroke follow-up, nerve problems. Common reasons to visit: headache… |
| `kb:dept:GMED` | General Medicine | General Medicine (Ground floor): Fever, infections, diabetes, BP and general check-ups. Common reasons to visi… |
| `kb:dept:PAED` | Paediatrics | Paediatrics (1st floor): Children's health, vaccinations and growth. Common reasons to visit: child, baby, inf… |
| `kb:dept:GYNO` | Gynaecology & Obstetrics | Gynaecology & Obstetrics (1st floor): Women's health, pregnancy and antenatal care. Common reasons to visit: p… |
| `kb:dept:DERM` | Dermatology | Dermatology (2nd floor): Skin, hair and nail problems. Common reasons to visit: skin, rash, itching, acne, pim… |
| `kb:dept:ENT` | ENT | ENT (2nd floor): Ear, nose and throat. Common reasons to visit: ear pain, ear discharge, hearing loss, ringing… |
| `kb:dept:OPHT` | Ophthalmology | Ophthalmology (2nd floor): Eye check-ups, cataract and vision. Common reasons to visit: eyes, blurred vision, … |
| `kb:dept:GAST` | Gastroenterology | Gastroenterology (3rd floor): Stomach, liver and digestion; endoscopy. Common reasons to visit: stomach pain, … |
| `kb:dept:PULM` | Pulmonology | Pulmonology (3rd floor): Lungs, asthma, breathing and sleep problems. Common reasons to visit: cough that does… |
| `kb:dept:NEPH` | Nephrology | Nephrology (4th floor): Kidney care and dialysis. Common reasons to visit: kidney, urine problems, burning uri… |
| `kb:dept:ENDO` | Endocrinology | Endocrinology (4th floor): Diabetes, thyroid and hormones. Common reasons to visit: diabetes, high sugar, thyr… |
| `kb:dept:RADI` | Radiology | Radiology (Basement 1): MRI, CT, X-ray and ultrasound. Common reasons to visit: MRI, CT scan, X-ray, ultrasoun… |

## Tests and procedures (35)

| Ref | Title | Text |
|---|---|---|
| `kb:proc:MRI-BRAIN` | MRI Brain | MRI Brain: Remove all metal. Tell us about pacemakers or implants. Arrive 30 minutes early. Insurance pre-auth… |
| `kb:proc:MRI-SPINE` | MRI Spine | MRI Spine: Remove all metal. Wear loose clothes. Arrive 30 minutes early. Insurance pre-authorisation is usual… |
| `kb:proc:MRI-KNEE` | MRI Knee | MRI Knee: Remove all metal. No fasting needed. Arrive 30 minutes early. Insurance pre-authorisation is usually… |
| `kb:proc:CT-HEAD` | CT Head | CT Head: Bring previous scans if any. Arrive 20 minutes early. Insurance pre-authorisation is usually needed. |
| `kb:proc:CT-CHEST` | CT Chest | CT Chest: 4 hours fasting if contrast is planned. Bring kidney function report. Fasting: 4 hours. Insurance pr… |
| `kb:proc:CT-ABD` | CT Abdomen | CT Abdomen: 4 hours fasting. Bring kidney function report. Fasting: 4 hours. Insurance pre-authorisation is us… |
| `kb:proc:XRAY-CHEST` | X-Ray Chest | X-Ray Chest: Remove jewellery. No preparation needed. |
| `kb:proc:XRAY-KNEE` | X-Ray Knee | X-Ray Knee: No preparation needed. |
| `kb:proc:USG-ABD` | Ultrasound Abdomen | Ultrasound Abdomen: 6 hours fasting. Drink water and come with a full bladder. Fasting: 6 hours. |
| `kb:proc:USG-PELVIS` | Ultrasound Pelvis | Ultrasound Pelvis: Come with a full bladder. |
| `kb:proc:ECHO` | Echocardiogram (2D Echo) | Echocardiogram (2D Echo): No preparation needed. |
| `kb:proc:ECG` | ECG | ECG: No preparation needed. |
| `kb:proc:TMT` | Treadmill Test (TMT) | Treadmill Test (TMT): Light meal 2 hours before. Wear walking shoes. Fasting: 2 hours. |
| `kb:proc:MAMMO` | Mammography | Mammography: Avoid deodorant or powder on the day. |
| `kb:proc:DEXA` | DEXA Bone Density | DEXA Bone Density: Avoid calcium tablets for 24 hours. |
| `kb:proc:ENDOSCOPY` | Upper GI Endoscopy | Upper GI Endoscopy: 8 hours fasting. Come with an attendant. Fasting: 8 hours. Insurance pre-authorisation is … |
| `kb:proc:COLONOSCOPY` | Colonoscopy | Colonoscopy: Bowel preparation the day before. Come with an attendant. Fasting: 12 hours. Insurance pre-author… |
| `kb:proc:PFT` | Pulmonary Function Test | Pulmonary Function Test: Avoid inhalers for 4 hours if your doctor agrees. |
| `kb:proc:LAB-CBC` | Complete Blood Count | Complete Blood Count: No fasting needed. |
| `kb:proc:LAB-LIPID` | Lipid Profile | Lipid Profile: 12 hours fasting. Water is fine. Fasting: 12 hours. |
| `kb:proc:LAB-HBA1C` | HbA1c | HbA1c: No fasting needed. |
| `kb:proc:LAB-THYROID` | Thyroid Profile (T3, T4, TSH) | Thyroid Profile (T3, T4, TSH): Morning sample preferred. |
| `kb:proc:LAB-LFT` | Liver Function Test | Liver Function Test: 8 hours fasting. Fasting: 8 hours. |
| `kb:proc:LAB-KFT` | Kidney Function Test | Kidney Function Test: No fasting needed. |
| `kb:proc:LAB-VITD` | Vitamin D | Vitamin D: No fasting needed. |
| `kb:proc:LAB-B12` | Vitamin B12 | Vitamin B12: No fasting needed. |
| `kb:proc:LAB-URINE` | Urine Routine | Urine Routine: Early morning sample in the container from the lab. |
| `kb:proc:LAB-FBS` | Fasting Blood Sugar | Fasting Blood Sugar: 10 hours fasting. Fasting: 10 hours. |
| `kb:proc:LAB-CRP` | C-Reactive Protein | C-Reactive Protein: No fasting needed. |
| `kb:proc:LAB-DENGUE` | Dengue NS1 and IgM | Dengue NS1 and IgM: No fasting needed. |
| `kb:proc:PKG-BASIC` | Basic Health Check | Basic Health Check: 12 hours fasting. Allow 2 to 3 hours. Fasting: 12 hours. |
| `kb:proc:PKG-EXEC` | Executive Health Check | Executive Health Check: 12 hours fasting. Allow half a day. Fasting: 12 hours. |
| `kb:proc:PKG-SENIOR` | Senior Citizen Health Check | Senior Citizen Health Check: 12 hours fasting. An attendant is welcome. Fasting: 12 hours. |
| `kb:proc:PKG-CARDIAC` | Cardiac Health Check | Cardiac Health Check: 12 hours fasting. Wear walking shoes for TMT. Fasting: 12 hours. |
| `kb:proc:PKG-WOMEN` | Women's Wellness Check | Women's Wellness Check: 12 hours fasting. Fasting: 12 hours. |

## Insurers (10)

| Ref | Title | Text |
|---|---|---|
| `kb:ins:STAR` | Star Health | We accept Star Health (cashless and reimbursement). Pre-authorisation is needed for MRI, CT and endoscopy. Doc… |
| `kb:ins:HDFCERGO` | HDFC ERGO | We accept HDFC ERGO (cashless and reimbursement). Pre-authorisation is needed for MRI, CT and endoscopy. Docum… |
| `kb:ins:ICICILOM` | ICICI Lombard | We accept ICICI Lombard (cashless). Pre-authorisation is needed for MRI, CT and endoscopy. Documents: E-card, … |
| `kb:ins:NIVA` | Niva Bupa | We accept Niva Bupa (cashless). Pre-authorisation is needed for MRI, CT and endoscopy. Documents: Health card,… |
| `kb:ins:CARE` | Care Health | We accept Care Health (cashless and reimbursement). Pre-authorisation is needed for MRI, CT and endoscopy. Doc… |
| `kb:ins:ABHI` | Aditya Birla Health | We accept Aditya Birla Health (cashless). Pre-authorisation is needed for MRI, CT and endoscopy. Documents: E-… |
| `kb:ins:TATAAIG` | Tata AIG | We accept Tata AIG (cashless and reimbursement). Pre-authorisation is needed for MRI, CT and endoscopy. Docume… |
| `kb:ins:BAJAJ` | Bajaj Allianz | We accept Bajaj Allianz (reimbursement only). Pre-authorisation is needed for MRI, CT and endoscopy. Documents… |
| `kb:ins:CGHS` | CGHS | We accept CGHS (cashless). Pre-authorisation is needed for MRI, CT and endoscopy. Documents: CGHS card, referr… |
| `kb:ins:ECHS` | ECHS | We accept ECHS (cashless). Pre-authorisation is needed for MRI, CT and endoscopy. Documents: ECHS card, referr… |

## FAQs (28)

| Ref | Title | Text |
|---|---|---|
| `kb:faq:food` | Food and cafeteria | The cafeteria on the ground floor is open 7 AM to 10 PM and serves vegetarian meals. Ward patients get meals f… |
| `kb:faq:wifi` | Wi-Fi and internet | Free guest Wi-Fi (wifi internet) called WellNest-Guest is available in all waiting areas. Ask the front desk f… |
| `kb:faq:documents` | What to bring | Please bring a photo ID, your insurance card, your booking ID, old reports and the medicines you take. Arrive … |
| `kb:faq:attendant` | Attendant pass | Each admitted patient gets one attendant pass. The attendant can stay overnight in the ward. Ward visiting hou… |
| `kb:faq:icu` | ICU visiting hours | ICU visiting hours are 5 PM to 6 PM, one visitor at a time. Children under 12 are not allowed in the ICU. Doct… |
| `kb:faq:children` | Children visiting | Children under 12 may visit general wards with an adult during visiting hours, but not the ICU. |
| `kb:faq:payment` | Payment methods | We accept UPI, debit and credit cards, net banking and cash. You can also pay a bill online from the payment l… |
| `kb:faq:cashless` | Cashless insurance | For cashless treatment, show your insurance card and photo ID at the TPA desk on the ground floor. Planned pro… |
| `kb:faq:reports` | Lab reports | Most blood reports are ready the same day. Your report is in the patient portal under Lab reports, and we can … |
| `kb:faq:records` | Medical records | To get copies of your medical records or a discharge summary, ask at the medical records desk on the 1st floor… |
| `kb:faq:second_opinion` | Second opinion | You can book a second-opinion consultation with any of our specialists. Bring your earlier reports and scans; … |
| `kb:faq:cancel_policy` | Cancelling or changing a booking | You can cancel or reschedule a booking free of charge on chat, by phone or in the patient portal. If your doct… |
| `kb:faq:waitlist` | Waitlist | If the doctor you want is full, join the waitlist. When a slot opens we send you an offer by SMS and email; th… |
| `kb:faq:senior` | Senior citizen help | Our senior citizen desk at entrance B offers wheelchair help, priority billing, early-morning slots and update… |
| `kb:faq:wheelchair` | Wheelchairs and accessibility | Wheelchairs are free at the main entrance and entrance B. All floors have lifts and accessible toilets. Ask at… |
| `kb:faq:languages` | Languages | Our staff and doctors speak English, Kannada, Hindi, Tamil, Telugu and Malayalam. Ask for a doctor who speaks … |
| `kb:faq:packages` | Health check packages | Basic Health Check: 2,499 rupees, 32 tests. Executive Health Check: 6,999 rupees, 68 tests. Senior Citizen Hea… |
| `kb:faq:home_collection` | Home sample collection | We collect blood samples at home within 10 km, 7 AM to 11 AM, for a fee of 200 rupees. Book it on chat or by p… |
| `kb:faq:teleconsult` | Video consultation | Follow-up visits can be done by video for most departments. Ask for a video consultation when you book; the li… |
| `kb:faq:ambulance` | Ambulance | For an emergency call 108. Our own ambulance service is on 080 4000 1108, 24 hours, with ventilator-equipped a… |
| `kb:faq:blood_bank` | Blood bank | The blood bank on the ground floor is open 24 hours. Voluntary donors are welcome from 9 AM to 5 PM. |
| `kb:faq:lost_found` | Lost and found | Lost something? Ask at the security desk at the main entrance or call the front desk on 080 4000 1234. |
| `kb:faq:feedback` | Complaints and feedback | We want to hear from you. Tell us on chat, write to care@wellnest.test, or ask for the patient relations offic… |
| `kb:faq:prayer` | Prayer room | A quiet prayer and meditation room is on the 1st floor, open all day for patients and families. |
| `kb:faq:atm` | ATM | There is an ATM next to the pharmacy on the ground floor. |
| `kb:faq:discharge` | Discharge | Discharge usually happens before 12 noon. The billing team prepares your final bill and the doctor gives a dis… |
| `kb:faq:getting_here` | Getting here | We are next to the Innovative Multiplex on Outer Ring Road, 10 minutes from Marathahalli bridge. Nearest BMTC … |
| `kb:faq:emergency_signs` | Emergency warning signs | Chest pain or pressure, trouble breathing, a face drooping or slurred speech, sudden weakness on one side, fai… |

## Policies (demo wording, replace with the real ones) (16)

| Ref | Title | Text |
|---|---|---|
| `kb:policy:visitors` | Visitor policy | Visitors are welcome during ward visiting hours, 11 AM to 1 PM and 5 PM to 7 PM, two at a time per patient. Pl… |
| `kb:policy:cancellation` | Cancellation and refund policy | You can cancel or reschedule an outpatient booking free of charge until the appointment time. Prepaid consulta… |
| `kb:policy:payment_deposit` | Admission deposit and billing policy | Planned admissions need an advance deposit, which depends on the procedure and room type; the billing desk giv… |
| `kb:policy:privacy` | Patient privacy and records policy | Your medical information is shared only with you, people you authorise in writing, and your treating team. Rep… |
| `kb:policy:consent` | Consent policy | Procedures and surgeries need your written informed consent after the doctor explains the benefits and risks. … |
| `kb:policy:patient_rights` | Patient rights | You have the right to respectful care, to know your diagnosis and treatment options in a language you understa… |
| `kb:policy:complaints` | Complaint and grievance policy | Raise a complaint on chat, by phone, by email to care@wellnest.test, or with the patient relations officer at … |
| `kb:policy:smoking` | No smoking and no alcohol | The whole campus is no smoking, no tobacco and no alcohol, including the parking areas. |
| `kb:policy:valuables` | Valuables policy | Please do not bring jewellery or large amounts of cash. The hospital is not responsible for valuables left in … |
| `kb:policy:outside_food` | Outside food policy | Outside food for patients needs the nurse's or dietitian's approval. Visitors may use the cafeteria on the gro… |
| `kb:policy:photography` | Photography and mobile phones | Please do not take photos or videos of other patients or staff. Mobile phones should be on silent in wards and… |
| `kb:policy:discharge_policy` | Discharge policy | Discharge usually happens before 12 noon after the doctor's review. You receive a discharge summary, medicine … |
| `kb:policy:children_policy` | Children and minors policy | Patients under 18 must be accompanied by a parent or guardian, who gives consent for treatment. Children under… |
| `kb:policy:emergency_policy` | Emergency care policy | Emergency treatment is never delayed for payment or paperwork. Call 108 or come to emergency entrance B, open … |
| `kb:policy:medicine_policy` | Medicine and prescription policy | Prescription refills are approved only by a doctor. The pharmacy needs a valid prescription for prescription-o… |
| `kb:policy:appointment_policy` | Appointment and late arrival policy | Please arrive 15 minutes before your appointment. If you are more than 15 minutes late, the doctor may see you… |
