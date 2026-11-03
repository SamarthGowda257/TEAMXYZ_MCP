// Hospital content for the CareLine website. CareLine Hospitals is fictional (hackathon demo);
// all names, numbers and stories below are invented for the demo and labelled as such in the footer.

export const HOSPITAL = {
  name: "CareLine Hospitals",
  tagline: "Multi-speciality hospital · Marathahalli, Bengaluru",
  address: "42 Outer Ring Road, Marathahalli, Bengaluru 560037",
  phone: "080 4000 1234",
  phoneHref: "tel:+918040001234",
  emergency: "108",
  ambulance: "080 4000 1108",
  email: "care@careline.test",
  founded: 2009,
};

export const STATS = [
  { value: "350", label: "Beds, including 60 critical-care beds" },
  { value: "45", label: "Senior specialists across 14 departments" },
  { value: "24×7", label: "Emergency, trauma, pharmacy and lab" },
  { value: "17", label: "Years caring for East Bengaluru" },
];

export type Centre = { key: string; name: string; dept: string; icon: string; summary: string; treats: string[] };
export const CENTRES: Centre[] = [
  { key: "heart", name: "Heart Institute", dept: "Cardiology", icon: "HeartPulse",
    summary: "Round-the-clock cath lab, non-invasive cardiology and a dedicated cardiac ICU for heart attacks, rhythm problems and heart failure.",
    treats: ["Angiography and angioplasty", "Pacemaker clinic", "Echo, TMT and Holter", "Hypertension clinic"] },
  { key: "neuro", name: "Brain & Spine Centre", dept: "Neurology", icon: "Brain",
    summary: "Stroke-ready emergency pathway, epilepsy care and spine services led by neurologists and neurosurgeons together.",
    treats: ["Stroke thrombolysis", "Headache and migraine clinic", "Epilepsy and EEG", "Memory clinic"] },
  { key: "ortho", name: "Bone & Joint Centre", dept: "Orthopaedics", icon: "Bone",
    summary: "Joint replacement, arthroscopy and sports injury care, with physiotherapy on the same floor from day one.",
    treats: ["Knee and hip replacement", "Arthroscopy", "Fracture and trauma care", "Spine clinic"] },
  { key: "mother", name: "Mother & Child", dept: "Gynaecology & Obstetrics", icon: "Baby",
    summary: "Antenatal care, painless delivery, a level III NICU and paediatricians available round the clock.",
    treats: ["Antenatal packages", "High-risk pregnancy", "Level III NICU", "Child vaccination clinic"] },
  { key: "gastro", name: "Digestive & Liver Care", dept: "Gastroenterology", icon: "Microscope",
    summary: "Advanced endoscopy suite and liver clinic for acidity, ulcers, fatty liver, IBS and GI bleeding.",
    treats: ["Endoscopy and colonoscopy", "Fatty liver clinic", "IBD care", "Nutrition counselling"] },
  { key: "kidney", name: "Kidney & Urology", dept: "Nephrology", icon: "Droplets",
    summary: "Twelve-station dialysis unit, kidney stone management and chronic kidney disease programmes.",
    treats: ["Haemodialysis", "CKD programme", "Kidney stone clinic", "Diabetic kidney care"] },
];

export const FACILITIES = [
  { icon: "Ambulance", title: "24×7 emergency & trauma", text: "A 20-bed emergency department with triage in under 5 minutes, two resuscitation bays and an ambulance fleet with ventilators." },
  { icon: "ScanLine", title: "Advanced imaging", text: "Two 3 Tesla MRI scanners, two 128-slice CT scanners, digital X-ray, mammography and DEXA under one roof." },
  { icon: "BedDouble", title: "Critical care", text: "60 ICU beds across medical, surgical, cardiac and neonatal intensive care, staffed by intensivists day and night." },
  { icon: "FlaskConical", title: "24-hour laboratory", text: "Automated lab with most blood reports ready the same day and secure online access to every result." },
  { icon: "Pill", title: "Pharmacy", text: "Open 24 hours on the ground floor, with home delivery within 5 km for prescriptions above ₹500." },
  { icon: "Accessibility", title: "Senior citizen desk", text: "Wheelchair help at entrance B, priority billing, early-morning slots and updates to a family member if you wish." },
];

export const PACKAGES = [
  { code: "PKG-BASIC", name: "Basic Health Check", price: 2499, tests: "32 tests", items: ["Complete blood count", "Blood sugar and HbA1c", "Lipid profile", "Kidney and liver function", "Physician consultation"] },
  { code: "PKG-EXEC", name: "Executive Health Check", price: 6999, tests: "68 tests", items: ["Everything in Basic", "ECG and treadmill test", "Chest X-ray and ultrasound abdomen", "Thyroid profile and vitamin D", "Dietitian consultation"] },
  { code: "PKG-SENIOR", name: "Senior Citizen Health Check", price: 4999, tests: "54 tests", items: ["Heart, kidney and liver screening", "Bone density (DEXA)", "Eye and hearing check", "Fall-risk assessment", "Geriatric physician review"] },
];

export const STORIES = [
  { name: "Shanthamma K", place: "Jayanagar · 67", text: "My son lives abroad, so I worried about managing visits alone. The assistant books my heart check-ups in Kannada, a wheelchair is waiting at the gate, and Ravi gets every update on his phone.", dept: "Heart Institute" },
  { name: "Arjun Mehta", place: "Whitefield · 34", text: "Dr. Iyer was fully booked for the week, so I joined the waitlist. Two days later a slot opened, I got a text, tapped accept and was in that same morning.", dept: "Cardiology" },
  { name: "Priya Nair", place: "Koramangala · 29", text: "I used to call the lab three times for one report. Now I ask on chat, it tells me if it's ready and emails it. The results with normal ranges are in my portal.", dept: "Endocrinology" },
];

export const TIPS = [
  { tag: "Heart health", title: "Chest pain that comes with walking? Don't wait it out", text: "Pain or pressure that starts with exertion and eases with rest can be angina. Get an ECG and a cardiology review within days, not months." },
  { tag: "Diabetes", title: "HbA1c: the one number to know every three months", text: "It shows your average sugar over three months. Most adults with diabetes aim for below 7 percent; ask your doctor what your target is." },
  { tag: "Seniors", title: "Five ways to prevent falls at home", text: "Good lighting at night, grab bars in the bathroom, no loose rugs, the right glasses and a yearly medicine review cut fall risk sharply." },
];

export const VISITOR_INFO = [
  { title: "Visiting hours", text: "Wards: 11 AM to 1 PM and 5 PM to 7 PM. ICU: 5 PM to 6 PM. One attendant pass per patient." },
  { title: "Parking", text: "Free for patients for 3 hours in Basement 2. Valet at the main entrance. Drop-off bay at entrance B for wheelchairs." },
  { title: "What to bring", text: "Photo ID, insurance card, your booking ID, old reports and the medicines you take. Arrive 15 minutes early." },
  { title: "Getting here", text: "Next to the Innovative Multiplex on Outer Ring Road. 10 minutes from Marathahalli bridge; BMTC stop: Kalamandir." },
];

export const MILESTONES = [
  { year: "2009", text: "Opened as a 120-bed hospital on Outer Ring Road" },
  { year: "2014", text: "Heart Institute and 24-hour cath lab started" },
  { year: "2018", text: "Expanded to 350 beds with a level III NICU" },
  { year: "2023", text: "Second MRI and CT, 12-station dialysis unit" },
  { year: "2026", text: "AI front desk on chat and phone, powered by Talkdesk" },
];

// Stock photographs (Unsplash licence), used as atmosphere for this fictional hospital.
// Swap any URL for the team's own photos (put files in frontend/public/img/ and use "/img/name.jpg").
const U = (id: string, w = 1400) => `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${w}&q=75`;
export const IMAGES = {
  hero: U("1519494026892-80bbd2d6fd0d", 1600),          // doctor in a bright hospital corridor
  team: U("1582750433449-648ed127bb54"),               // clinicians talking
  consult: U("1576091160550-2173dba999ef"),            // doctor with stethoscope and tablet
  building: U("1586773860418-d37222d8fce3"),           // hospital exterior
  ward: U("1516549655169-df83a0774514"),               // hospital room
  lab: U("1579154204601-01588f351e67"),                // laboratory
  scan: U("1559757175-5700dde675bc"),                  // MRI / imaging
  care: U("1631815588090-d4bfec5b1ccb"),               // nurse with patient
};
export const CENTRE_IMAGES: Record<string, string> = {
  heart: U("1628348068343-c6a848d2b6dd", 900),
  neuro: U("1559757175-5700dde675bc", 900),
  ortho: U("1530026405186-ed1f139313f8", 900),
  mother: U("1555252333-9f8e92e65df9", 900),
  gastro: U("1579154204601-01588f351e67", 900),
  kidney: U("1631217868264-e5b90bb7e133", 900),
};
