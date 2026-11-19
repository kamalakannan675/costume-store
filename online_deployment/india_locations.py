"""
COSTUME STORE — Indian Administrative Location & Postal PIN Code Dataset
Comprehensive mapping of all 28 States and 8 Union Territories of India
with their administrative districts and postal PIN codes.
"""
import os
import re
import json

INDIA_STATES_AND_DISTRICTS = {
    "Andhra Pradesh": [
        "Alluri Sitharama Raju",
        "Anakapalli",
        "Ananthapuramu",
        "Annamayya",
        "Bapatla",
        "Chittoor",
        "Dr. B.R. Ambedkar Konaseema",
        "East Godavari",
        "Eluru",
        "Guntur",
        "Kakinada",
        "Krishna",
        "Kurnool",
        "Nandyal",
        "NTR",
        "Palnadu",
        "Parvathipuram Manyam",
        "Prakasam",
        "Srikakulam",
        "Sri Potti Sriramulu Nellore",
        "Sri Sathya Sai",
        "Tirupati",
        "Visakhapatnam",
        "Vizianagaram",
        "West Godavari",
        "YSR Kadapa"
    ],
    "Arunachal Pradesh": [
        "Anjaw",
        "Changlang",
        "Dibang Valley",
        "East Kameng",
        "East Siang",
        "Kamle",
        "Kra Daadi",
        "Kurung Kumey",
        "Lepa Rada",
        "Lohit",
        "Longding",
        "Lower Dibang Valley",
        "Lower Siang",
        "Lower Subansiri",
        "Namsai",
        "Pakke Kessang",
        "Papum Pare",
        "Shi Yomi",
        "Siang",
        "Tawang",
        "Tirap",
        "Upper Siang",
        "Upper Subansiri",
        "West Kameng",
        "West Siang"
    ],
    "Assam": [
        "Baksa",
        "Barpeta",
        "Biswanath",
        "Bongaigaon",
        "Cachar",
        "Charaideo",
        "Chirang",
        "Darrang",
        "Dhemaji",
        "Dhubri",
        "Dibrugarh",
        "Dima Hasao",
        "Goalpara",
        "Golaghat",
        "Hailakandi",
        "Hojai",
        "Jorhat",
        "Kamrup",
        "Kamrup Metropolitan (Guwahati)",
        "Karbi Anglong",
        "Karimganj",
        "Kokrajhar",
        "Lakhimpur",
        "Majuli",
        "Morigaon",
        "Nagaon",
        "Nalbari",
        "Sivasagar",
        "Sonitpur",
        "South Salmara-Mankachar",
        "Tinsukia",
        "Udalguri",
        "West Karbi Anglong"
    ],
    "Bihar": [
        "Araria",
        "Arwal",
        "Aurangabad",
        "Banka",
        "Begusarai",
        "Bhagalpur",
        "Bhojpur",
        "Buxar",
        "Darbhanga",
        "East Champaran (Motihari)",
        "Gaya",
        "Gopalganj",
        "Jamui",
        "Jehanabad",
        "Kaimur (Bhabua)",
        "Katihar",
        "Khagaria",
        "Kishanganj",
        "Lakhisarai",
        "Madhepura",
        "Madhubani",
        "Munger",
        "Muzaffarpur",
        "Nalanda (Bihar Sharif)",
        "Nawada",
        "Patna",
        "Purnia",
        "Rohtas (Sasaram)",
        "Saharsa",
        "Samastipur",
        "Saran (Chhapra)",
        "Sheikhpura",
        "Sheohar",
        "Sitamarhi",
        "Siwan",
        "Supaul",
        "Vaishali (Hajipur)",
        "West Champaran (Bettiah)"
    ],
    "Chhattisgarh": [
        "Balod",
        "Baloda Bazar",
        "Balrampur",
        "Bastar (Jagdalpur)",
        "Bemetara",
        "Bijapur",
        "Bilaspur",
        "Dantewada",
        "Dhamtari",
        "Durg",
        "Gariaband",
        "Gaurela-Pendra-Marwahi",
        "Janjgir-Champa",
        "Jashpur",
        "Kabirdham (Kawardha)",
        "Kanker",
        "Khairagarh-Chhuikhadan-Gandai",
        "Kondagaon",
        "Korba",
        "Koriya",
        "Mahasamund",
        "Manendragarh-Chirmiri-Bharatpur",
        "Mohla-Manpur-Ambagarh Chowki",
        "Mungeli",
        "Narayanpur",
        "Raigarh",
        "Raipur",
        "Rajnandgaon",
        "Sakti",
        "Sarangarh-Bilaigarh",
        "Sukma",
        "Surajpur",
        "Surguja (Ambikapur)"
    ],
    "Goa": [
        "North Goa (Panaji)",
        "South Goa (Madgaon)"
    ],
    "Gujarat": [
        "Ahmedabad",
        "Amreli",
        "Anand",
        "Aravalli",
        "Banaskantha (Palanpur)",
        "Bharuch",
        "Bhavnagar",
        "Botad",
        "Chhota Udaipur",
        "Dahod",
        "Dang (Ahwa)",
        "Devbhumi Dwarka",
        "Gandhinagar",
        "Gir Somnath",
        "Jamnagar",
        "Junagadh",
        "Kheda (Nadiad)",
        "Kutch (Bhuj)",
        "Mahisagar",
        "Mehsana",
        "Morbi",
        "Narmada (Rajpipla)",
        "Navsari",
        "Panchmahal (Godhra)",
        "Patan",
        "Porbandar",
        "Rajkot",
        "Sabarkantha (Himmatnagar)",
        "Surat",
        "Surendranagar",
        "Tapi (Vyara)",
        "Vadodara",
        "Valsad"
    ],
    "Haryana": [
        "Ambala",
        "Bhiwani",
        "Charkhi Dadri",
        "Faridabad",
        "Fatehabad",
        "Gurugram",
        "Hisar",
        "Jhajjar",
        "Jind",
        "Kaithal",
        "Karnal",
        "Kurukshetra",
        "Mahendragarh (Narnaul)",
        "Nuh",
        "Palwal",
        "Panchkula",
        "Panipat",
        "Rewari",
        "Rohtak",
        "Sirsa",
        "Sonipat",
        "Yamunanagar"
    ],
    "Himachal Pradesh": [
        "Bilaspur",
        "Chamba",
        "Hamirpur",
        "Kangra (Dharamshala)",
        "Kinnaur",
        "Kullu",
        "Lahaul and Spiti",
        "Mandi",
        "Shimla",
        "Sirmaur (Nahan)",
        "Solan",
        "Una"
    ],
    "Jharkhand": [
        "Bokaro",
        "Chatra",
        "Deoghar",
        "Dhanbad",
        "Dumka",
        "East Singhbhum (Jamshedpur)",
        "Garhwa",
        "Giridih",
        "Godda",
        "Gumla",
        "Hazaribagh",
        "Jamtara",
        "Khunti",
        "Koderma",
        "Latehar",
        "Lohardaga",
        "Pakur",
        "Palamu (Daltonganj)",
        "Ramgarh",
        "Ranchi",
        "Sahebganj",
        "Seraikela Kharsawan",
        "Simdega",
        "West Singhbhum (Chaibasa)"
    ],
    "Karnataka": [
        "Bagalkote",
        "Ballari (Bellary)",
        "Belagavi (Belgaum)",
        "Bengaluru Rural",
        "Bengaluru Urban",
        "Bidar",
        "Chamarajanagar",
        "Chikkaballapura",
        "Chikkamagaluru",
        "Chitradurga",
        "Dakshina Kannada (Mangaluru)",
        "Davanagere",
        "Dharwad (Hubballi)",
        "Gadag",
        "Hassan",
        "Haveri",
        "Kalaburagi (Gulbarga)",
        "Kodagu (Madikeri)",
        "Kolar",
        "Koppal",
        "Mandya",
        "Mysuru (Mysore)",
        "Raichur",
        "Ramanagara",
        "Shivamogga (Shimoga)",
        "Tumakuru (Tumkur)",
        "Udupi",
        "Uttara Kannada (Karwar)",
        "Vijayanagara",
        "Vijayapura (Bijapur)",
        "Yadgir"
    ],
    "Kerala": [
        "Alappuzha",
        "Ernakulam (Kochi)",
        "Idukki",
        "Kannur",
        "Kasaragod",
        "Kollam",
        "Kottayam",
        "Kozhikode",
        "Malappuram",
        "Palakkad",
        "Pathanamthitta",
        "Thiruvananthapuram",
        "Thrissur",
        "Wayanad"
    ],
    "Madhya Pradesh": [
        "Agar Malwa",
        "Alirajpur",
        "Anuppur",
        "Ashoknagar",
        "Balaghat",
        "Barwani",
        "Betul",
        "Bhind",
        "Bhopal",
        "Burhanpur",
        "Chhatarpur",
        "Chhindwara",
        "Damoh",
        "Datia",
        "Dewas",
        "Dhar",
        "Dindori",
        "Guna",
        "Gwalior",
        "Harda",
        "Hoshangabad (Narmadapuram)",
        "Indore",
        "Jabalpur",
        "Jhabua",
        "Katni",
        "Khandwa",
        "Khargone",
        "Maihar",
        "Mandla",
        "Mandsaur",
        "Morena",
        "Mauganj",
        "Narsinghpur",
        "Neemuch",
        "Niwari",
        "Panna",
        "Raisen",
        "Rajgarh",
        "Ratlam",
        "Rewa",
        "Sagar",
        "Satna",
        "Sehore",
        "Seoni",
        "Shahdol",
        "Shajapur",
        "Sheopur",
        "Shivpuri",
        "Sidhi",
        "Singrauli",
        "Tikamgarh",
        "Ujjain",
        "Umaria",
        "Vidisha"
    ],
    "Maharashtra": [
        "Ahmednagar (Ahilyanagar)",
        "Akola",
        "Amravati",
        "Chhatrapati Sambhajinagar (Aurangabad)",
        "Beed",
        "Bhandara",
        "Buldhana",
        "Chandrapur",
        "Dhule",
        "Gadchiroli",
        "Gondia",
        "Hingoli",
        "Jalgaon",
        "Jalna",
        "Kolhapur",
        "Latur",
        "Mumbai City",
        "Mumbai Suburban",
        "Nagpur",
        "Nanded",
        "Nandurbar",
        "Nashik",
        "Dharashiv (Osmanabad)",
        "Palghar",
        "Parbhani",
        "Pune",
        "Raigad (Alibag)",
        "Ratnagiri",
        "Sangli",
        "Satara",
        "Sindhudurg",
        "Solapur",
        "Thane",
        "Wardha",
        "Washim",
        "Yavatmal"
    ],
    "Manipur": [
        "Bishnupur",
        "Chandel",
        "Churachandpur",
        "Imphal East",
        "Imphal West",
        "Jiribam",
        "Kakching",
        "Kamjong",
        "Kangpokpi",
        "Noney",
        "Pherzawl",
        "Senapati",
        "Tamenglong",
        "Tengnoupal",
        "Thoubal",
        "Ukhrul"
    ],
    "Meghalaya": [
        "East Garo Hills",
        "East Jaintia Hills",
        "East Khasi Hills (Shillong)",
        "Eastern West Khasi Hills",
        "North Garo Hills",
        "Ri-Bhoi",
        "South Garo Hills",
        "South West Garo Hills",
        "South West Khasi Hills",
        "West Garo Hills (Tura)",
        "West Jaintia Hills (Jowai)",
        "West Khasi Hills (Nongstoin)"
    ],
    "Mizoram": [
        "Aizawl",
        "Champhai",
        "Hnahthial",
        "Khawzawl",
        "Kolasib",
        "Lawngtlai",
        "Lunglei",
        "Mamit",
        "Saitual",
        "Serchhip",
        "Siaha"
    ],
    "Nagaland": [
        "Chümoukedima",
        "Dimapur",
        "Kiphire",
        "Kohima",
        "Longleng",
        "Mokokchung",
        "Mon",
        "Niuland",
        "Noklak",
        "Peren",
        "Phek",
        "Shamator",
        "Tseminyü",
        "Tuensang",
        "Wokha",
        "Zünheboto"
    ],
    "Odisha": [
        "Angul",
        "Balangir",
        "Balasore (Baleswar)",
        "Bargarh",
        "Bhadrak",
        "Boudh",
        "Cuttack",
        "Deogarh",
        "Dhenkanal",
        "Gajapati",
        "Ganjam (Chhatrapur)",
        "Jagatsinghpur",
        "Jajpur",
        "Jharsuguda",
        "Kalahandi",
        "Kandhamal",
        "Kendrapara",
        "Kendujhar (Keonjhar)",
        "Khordha (Bhubaneswar)",
        "Koraput",
        "Malkangiri",
        "Mayurbhanj (Baripada)",
        "Nabarangpur",
        "Nayagarh",
        "Nuapada",
        "Puri",
        "Rayagada",
        "Sambalpur",
        "Subarnapur (Sonepur)",
        "Sundargarh"
    ],
    "Punjab": [
        "Amritsar",
        "Barnala",
        "Bathinda",
        "Faridkot",
        "Fatehgarh Sahib",
        "Fazilka",
        "Ferozepur",
        "Gurdaspur",
        "Hoshiarpur",
        "Jalandhar",
        "Kapurthala",
        "Ludhiana",
        "Malerkotla",
        "Mansa",
        "Moga",
        "Muktsar",
        "Pathankot",
        "Patiala",
        "Rupnagar (Ropar)",
        "Sahibzada Ajit Singh Nagar (Mohali)",
        "Sangrur",
        "Shahid Bhagat Singh Nagar (Nawanshahr)",
        "Tarn Taran"
    ],
    "Rajasthan": [
        "Ajmer",
        "Alwar",
        "Anupgarh",
        "Balotra",
        "Banswara",
        "Baran",
        "Barmer",
        "Beawar",
        "Bharatpur",
        "Bhilwara",
        "Bikaner",
        "Bundi",
        "Chittorgarh",
        "Churu",
        "Dausa",
        "Deeg",
        "Dholpur",
        "Didwana-Kuchaman",
        "Dudu",
        "Dungarpur",
        "Gangapur City",
        "Hanumangarh",
        "Jaipur",
        "Jaipur Rural",
        "Jaisalmer",
        "Jalore",
        "Jhalawar",
        "Jhunjhunu",
        "Jodhpur",
        "Jodhpur Rural",
        "Karauli",
        "Kekri",
        "Khairthal-Tijara",
        "Kota",
        "Kotputli-Behror",
        "Nagaur",
        "Neem Ka Thana",
        "Pali",
        "Phalodi",
        "Pratapgarh",
        "Rajsamand",
        "Salumbar",
        "Sanchore",
        "Sawai Madhopur",
        "Shahpura",
        "Sikar",
        "Sirohi",
        "Sri Ganganagar",
        "Tonk",
        "Udaipur"
    ],
    "Sikkim": [
        "Gangtok",
        "Gyalshing",
        "Mangan",
        "Namchi",
        "Pakyong",
        "Soreng"
    ],
    "Tamil Nadu": [
        "Ariyalur",
        "Chengalpattu",
        "Chennai",
        "Coimbatore",
        "Cuddalore",
        "Dharmapuri",
        "Dindigul",
        "Erode",
        "Kallakurichi",
        "Kanchipuram",
        "Kanyakumari (Nagercoil)",
        "Karur",
        "Krishnagiri",
        "Madurai",
        "Mayiladuthurai",
        "Nagapattinam",
        "Namakkal",
        "Nilgiris (Udhagamandalam)",
        "Perambalur",
        "Pudukkottai",
        "Ramanathapuram",
        "Ranipet",
        "Salem",
        "Sivaganga",
        "Tenkasi",
        "Thanjavur",
        "Theni",
        "Thoothukudi",
        "Tiruchirappalli",
        "Tirunelveli",
        "Tirupathur",
        "Tiruppur",
        "Tiruvallur",
        "Tiruvannamalai",
        "Tiruvarur",
        "Vellore",
        "Viluppuram",
        "Virudhunagar"
    ],
    "Telangana": [
        "Adilabad",
        "Bhadradri Kothagudem",
        "Hanumakonda",
        "Hyderabad",
        "Jagtial",
        "Jangaon",
        "Jayashankar Bhupalpally",
        "Jogulamba Gadwal",
        "Kamareddy",
        "Karimnagar",
        "Khammam",
        "Kumuram Bheem Asifabad",
        "Mahabubabad",
        "Mahabubnagar",
        "Mancherial",
        "Medak",
        "Medchal-Malkajgiri",
        "Mulugu",
        "Nagarkurnool",
        "Nalgonda",
        "Narayanpet",
        "Nirmal",
        "Nizamabad",
        "Peddapalli",
        "Rajanna Sircilla",
        "Rangareddy",
        "Sangareddy",
        "Siddipet",
        "Suryapet",
        "Vikarabad",
        "Wanaparthy",
        "Warangal",
        "Yadadri Bhuvanagiri"
    ],
    "Tripura": [
        "Dhalai",
        "Gomati",
        "Khowai",
        "North Tripura",
        "Sepahijala",
        "South Tripura",
        "Unakoti",
        "West Tripura (Agartala)"
    ],
    "Uttar Pradesh": [
        "Agra",
        "Aligarh",
        "Ambedkar Nagar",
        "Amethi",
        "Amroha",
        "Auraiya",
        "Ayodhya (Faizabad)",
        "Azamgarh",
        "Baghpat",
        "Bahraich",
        "Ballia",
        "Balrampur",
        "Banda",
        "Barabanki",
        "Bareilly",
        "Basti",
        "Bhadohi",
        "Bijnor",
        "Budaun",
        "Bulandshahr",
        "Chandauli",
        "Chitrakoot",
        "Deoria",
        "Etah",
        "Etawah",
        "Farrukhabad",
        "Fatehpur",
        "Firozabad",
        "Gautam Buddha Nagar (Noida)",
        "Ghaziabad",
        "Ghazipur",
        "Gonda",
        "Gorakhpur",
        "Hamirpur",
        "Hapur",
        "Hardoi",
        "Hathras",
        "Jalaun (Orai)",
        "Jaunpur",
        "Jhansi",
        "Kannauj",
        "Kanpur Dehat",
        "Kanpur Nagar",
        "Kasganj",
        "Kaushambi",
        "Kheri (Lakhimpur)",
        "Kushinagar",
        "Lalitpur",
        "Lucknow",
        "Maharajganj",
        "Mahoba",
        "Mainpuri",
        "Mathura",
        "Mau",
        "Meerut",
        "Mirzapur",
        "Moradabad",
        "Muzaffarnagar",
        "Pilibhit",
        "Pratapgarh",
        "Prayagraj (Allahabad)",
        "Raebareli",
        "Rampur",
        "Saharanpur",
        "Sambhal",
        "Sant Kabir Nagar",
        "Shahjahanpur",
        "Shamli",
        "Shravasti",
        "Siddharthnagar",
        "Sitapur",
        "Sonbhadra",
        "Sultanpur",
        "Unnao",
        "Varanasi"
    ],
    "Uttarakhand": [
        "Almora",
        "Bageshwar",
        "Chamoli",
        "Champawat",
        "Dehradun",
        "Haridwar",
        "Nainital",
        "Pauri Garhwal",
        "Pithoragarh",
        "Rudraprayag",
        "Tehri Garhwal",
        "Udham Singh Nagar",
        "Uttarkashi"
    ],
    "West Bengal": [
        "Alipurduar",
        "Bankura",
        "Birbhum (Suri)",
        "Cooch Behar",
        "Dakshin Dinajpur (Balurghat)",
        "Darjeeling",
        "Hooghly (Chinsurah)",
        "Howrah",
        "Jalpaiguri",
        "Jhargram",
        "Kalimpong",
        "Kolkata",
        "Malda",
        "Murshidabad (Baharampur)",
        "Nadia (Krishnanagar)",
        "North 24 Parganas (Barasat)",
        "Paschim Bardhaman (Asansol)",
        "Paschim Medinipur (Midnapore)",
        "Purba Bardhaman (Bardhaman)",
        "Purba Medinipur (Tamluk)",
        "Purulia",
        "South 24 Parganas (Alipore)",
        "Uttar Dinajpur (Raiganj)"
    ],
    "Andaman and Nicobar Islands": [
        "Nicobar",
        "North and Middle Andaman",
        "South Andaman (Port Blair)"
    ],
    "Chandigarh": [
        "Chandigarh"
    ],
    "Dadra and Nagar Haveli and Daman and Diu": [
        "Daman",
        "Diu",
        "Dadra and Nagar Haveli (Silvassa)"
    ],
    "Delhi": [
        "Central Delhi",
        "East Delhi",
        "New Delhi",
        "North Delhi",
        "North East Delhi",
        "North West Delhi",
        "Shahdara",
        "South Delhi",
        "South East Delhi",
        "South West Delhi",
        "West Delhi"
    ],
    "Jammu and Kashmir": [
        "Anantnag",
        "Bandipora",
        "Baramulla",
        "Budgam",
        "Doda",
        "Ganderbal",
        "Jammu",
        "Kathua",
        "Kishtwar",
        "Kulgam",
        "Kupwara",
        "Poonch",
        "Pulwama",
        "Rajouri",
        "Ramban",
        "Reasi",
        "Samba",
        "Shopian",
        "Srinagar",
        "Udhampur"
    ],
    "Ladakh": [
        "Kargil",
        "Leh"
    ],
    "Lakshadweep": [
        "Lakshadweep (Kavaratti)"
    ],
    "Puducherry": [
        "Karaikal",
        "Mahe",
        "Puducherry",
        "Yanam"
    ]
}

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_JSON_PATH = os.path.join(_BASE_DIR, 'static', 'js', 'india_locations.json')

def _load_district_pincodes():
    """Loads authoritative postal PIN codes from the bundled India Post dataset."""
    if os.path.exists(_JSON_PATH):
        try:
            with open(_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('pincodes', {})
        except Exception:
            pass
    return {}

DISTRICT_PINCODES = _load_district_pincodes()


def get_all_states():
    """Returns sorted list of all Indian States and Union Territories."""
    return sorted(list(INDIA_STATES_AND_DISTRICTS.keys()))


def get_districts_for_state(state):
    """Returns sorted list of districts for a given state, or empty list if state is invalid."""
    if not state or not isinstance(state, str):
        return []
    state_norm = state.strip()
    for s_name, districts in INDIA_STATES_AND_DISTRICTS.items():
        if s_name.lower() == state_norm.lower():
            return sorted(list(districts))
    return []


def is_valid_state(state):
    """Verifies whether state exists in official Indian States/UTs dataset."""
    if not state or not isinstance(state, str):
        return False
    state_norm = state.strip().lower()
    return any(s.lower() == state_norm for s in INDIA_STATES_AND_DISTRICTS.keys())


def is_valid_district(state, district):
    """Verifies whether district is a valid administrative subdivision of the given state."""
    districts = get_districts_for_state(state)
    if not districts or not district or not isinstance(district, str):
        return False
    dist_norm = district.strip().lower()
    return any(d.lower() == dist_norm or dist_norm in d.lower() or d.lower() in dist_norm for d in districts)


def get_pincodes_for_district(state, district):
    """Returns sorted list of 6-digit postal PIN codes for a given state and district."""
    if not state or not district:
        return []
    state_norm = state.strip()
    district_norm = district.strip()
    # Direct match
    key = f"{state_norm}|{district_norm}"
    if key in DISTRICT_PINCODES:
        return DISTRICT_PINCODES[key]
    # Case-insensitive direct lookup
    for k, v in DISTRICT_PINCODES.items():
        s, d = k.split("|", 1)
        if s.lower() == state_norm.lower() and d.lower() == district_norm.lower():
            return v
    # Substring / alias lookup (e.g. 'Bengaluru' matching both 'Bengaluru Urban' and 'Bengaluru Rural')
    all_matched = []
    for k, v in DISTRICT_PINCODES.items():
        s, d = k.split("|", 1)
        if s.lower() == state_norm.lower() and (district_norm.lower() in d.lower() or d.lower() in district_norm.lower()):
            all_matched.extend(v)
    if all_matched:
        return sorted(list(set(all_matched)))
    return []


def is_valid_pincode(pincode, state=None, district=None):
    """
    Validates a 6-digit Indian postal PIN code.
    If state and district are provided, validates that the PIN code corresponds to that district.
    If only state is provided, validates that the PIN code belongs to that state.
    """
    if not pincode:
        return False
    pin_str = str(pincode).strip()
    if not re.match(r'^[1-9][0-9]{5}$', pin_str):
        return False
    if state and district:
        valid_pins = get_pincodes_for_district(state, district)
        if valid_pins:
            return pin_str in valid_pins
        return False
    elif state:
        districts = get_districts_for_state(state)
        for d in districts:
            if pin_str in get_pincodes_for_district(state, d):
                return True
        return False
    return True


def normalize_full_name(name):
    """Normalizes customer full name by trimming and collapsing whitespace."""
    if not name or not isinstance(name, str):
        return ""
    name = name.strip()
    return re.sub(r'\s+', ' ', name)


def validate_full_name(name):
    """
    Validates customer full name.
    Accepts legitimate English first names, middle names, and surnames.
    Allows spaces, hyphens, periods, and apostrophes.
    Rejects numbers, emojis, unsupported symbols, keyboard mashing, repeated characters,
    and vowelless or unnatural consonant sequences.
    """
    if not name or not isinstance(name, str):
        return False, "Full Name is required."
    
    clean_name = normalize_full_name(name)
    
    if len(clean_name) < 2:
        return False, "Full Name must be at least 2 characters long."
    if len(clean_name) > 100:
        return False, "Full Name cannot exceed 100 characters."
    
    # Check for invalid characters (only letters, spaces, hyphens, apostrophes, and periods allowed)
    if not re.match(r"^[A-Za-z\s.'-]+$", clean_name):
        if re.search(r'[0-9]', clean_name):
            return False, "Full Name must contain English letters only (numbers are not permitted)."
        return False, "Full Name must contain English letters only (numbers, emojis, and symbols are not permitted)."
    
    # Must start with a letter and end with a letter or period (e.g. initials like 'A. P. J.')
    if not re.match(r'^[A-Za-z]', clean_name) or not re.search(r'[A-Za-z.]$', clean_name):
        return False, "Full Name must start with an English letter."
    
    # Check for invalid consecutive punctuation (e.g. '--', "''", '..')
    if re.search(r"[-'.]{2,}", clean_name):
        return False, "Full Name contains invalid punctuation sequences."
    
    # Reject excessive repeated characters (3 or more of the same letter in a row)
    if re.search(r'([A-Za-z])\1{2,}', clean_name, re.IGNORECASE):
        return False, "Full Name contains invalid repeated characters."
    
    lower_compact = re.sub(r'[^a-z]', '', clean_name.lower())
    
    # Keyboard mash sequence detection (forward and reverse sequences >= 4)
    keyboard_patterns = [
        'qwerty', 'wertyu', 'ertyui', 'rtyuio', 'tyuiop',
        'asdfgh', 'sdfghj', 'dfghjk', 'fghjkl',
        'zxcvbn', 'xcvbnm',
        'qwer', 'wert', 'erty', 'rtyu', 'tyui', 'yuio', 'uiop',
        'asdf', 'sdfg', 'dfgh', 'fghj', 'ghjk', 'hjkl',
        'zxcv', 'xcvb', 'cvbn', 'vbnm',
        'rewq', 'trew', 'ytre', 'uytr', 'iuyt', 'poiuy',
        'fdsa', 'gfdsa', 'lkjh', 'kjhg', 'jhgf', 'hgfd',
        'vcxz', 'bvcx', 'nbvc', 'mnbv'
    ]
    for pat in keyboard_patterns:
        if pat in lower_compact:
            return False, "Full Name appears to contain random keyboard patterns or meaningless keystrokes."
    
    # Repetitive 2-char pattern check (e.g. 'asdfasdf', 'ababab')
    if len(lower_compact) >= 6:
        for i in range(len(lower_compact) - 5):
            sub = lower_compact[i:i+4]
            if lower_compact.count(sub) >= 2:
                return False, "Full Name contains repetitive meaningless keystroke patterns."
    
    # Token-level validation
    tokens = re.split(r'[\s.\'-]+', clean_name)
    tokens = [t for t in tokens if t]
    
    for t in tokens:
        t_lower = t.lower()
        # Words of length >= 3 must have at least one vowel
        if len(t) >= 3 and not any(c in 'aeiouy' for c in t_lower):
            return False, "Each name word must contain valid vowel patterns."
        # No consonant clusters >= 5
        if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', t_lower):
            return False, "Full Name contains unnatural consonant sequences."
    
    # Global vowel ratio check for names >= 5 letters
    letters = [c for c in lower_compact if c.isalpha()]
    if len(letters) >= 5:
        vowels = [c for c in letters if c in 'aeiouy']
        if len(vowels) / len(letters) < 0.15:
            return False, "Full Name lacks a realistic vowel-to-consonant structure."
    
    return True, ""


def validate_email_address(email):
    """
    Validates customer registration email syntax and structure.
    Enforces valid local and domain parts, top-level domain structure,
    and rejects consecutive dots, malformed formatting, and keyboard mashing.
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    
    email = email.strip()
    
    if not email:
        return False, "Email address is required."
    
    if len(email) > 254:
        return False, "Email address exceeds maximum length of 254 characters."
    
    # Disallow consecutive dots
    if '..' in email:
        return False, "Email address cannot contain consecutive periods."
    
    # Must contain exactly one '@'
    parts = email.split('@')
    if len(parts) != 2:
        return False, "Please provide a valid email address with a single '@' symbol."
    
    local, domain = parts[0], parts[1]
    
    if not local or not domain:
        return False, "Please provide a complete email address with both user and domain parts."
    
    # Local part checks
    if len(local) > 64:
        return False, "The email local part cannot exceed 64 characters."
    
    if local.startswith('.') or local.endswith('.'):
        return False, "The email local part cannot begin or end with a period."
    
    if not re.match(r"^[a-zA-Z0-9._%+-]+$", local):
        return False, "The email local part contains invalid characters."
    
    # Keyboard mash check on local part
    local_lower = re.sub(r'[^a-z]', '', local.lower())
    mash_patterns = ['asdfasdf', 'qwertyuiop', 'zxcvbnm', 'fagcvcbgjfcgtgj', 'fgcnvcbcgjfctgj']
    for p in mash_patterns:
        if p in local_lower:
            return False, "The email local part appears to contain random keyboard patterns."
    
    # Domain part checks
    if '.' not in domain:
        return False, "Email domain must include a valid top-level domain (e.g. .com, .in)."
    
    domain_labels = domain.split('.')
    if any(not lbl for lbl in domain_labels):
        return False, "Email domain contains empty domain labels."
    
    tld = domain_labels[-1]
    if len(tld) < 2 or len(tld) > 24 or not tld.isalpha():
        return False, "Email top-level domain must contain at least 2 alphabetic characters."
    
    # Validate each label in domain
    for lbl in domain_labels:
        if len(lbl) > 63:
            return False, "Email domain label exceeds maximum length of 63 characters."
        if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$', lbl):
            return False, "Email domain labels can only contain letters, numbers, and hyphens."
    
    # Reject meaningless / vowelless second-level domains (e.g. 'cdf.cv')
    sld = domain_labels[-2].lower()
    if len(sld) >= 3 and not any(c in 'aeiouy' for c in sld):
        return False, "Email domain does not appear to be a valid or recognized domain."
    
    for p in ['asdf', 'qwerty', 'zxcv']:
        if p in sld:
            return False, "Email domain appears to be random keyboard keystrokes."
    
    return True, ""


def validate_street_address(addr):
    """
    Validates Indian street address (Flat/House, Building, Street, Area).
    Rejects empty, too short, too long, repeated characters, and keyboard-mashing gibberish.
    """
    if not addr or not isinstance(addr, str):
        return False, "Street address is required."
    addr = addr.strip()
    if len(addr) < 10:
        return False, "Address is too short. It must be at least 10 characters long with meaningful street details."
    if len(addr) > 250:
        return False, "Address cannot exceed 250 characters."

    # Must contain alphanumeric characters
    if not re.search(r'[A-Za-z0-9]', addr):
        return False, "Address must contain alphanumeric information (house/flat number and street name)."

    # Allowed characters: letters, numbers, spaces, and standard address punctuation
    if re.search(r"[^A-Za-z0-9\s,./#\-&():']", addr):
        return False, "Address contains invalid special characters."

    # Reject repeated identical characters (e.g. 'aaaaa', '11111')
    if re.search(r'(.)\1{3,}', addr):
        return False, "Address contains invalid repetitive characters or repeated patterns."

    # Keyboard mash sequence detection
    mash_patterns = [
        r'asdf', r'hjkl', r'qwerty', r'zxcv', r'12345', r'67890',
        r'qwer', r'wert', r'erty', r'rtyu', r'tyui', r'yuio', r'uiop',
        r'dfgh', r'fghj', r'ghjk', r'hjkl', r'zxcvb', r'xcvbn'
    ]
    lower_addr = addr.lower()
    for pat in mash_patterns:
        if re.search(pat, lower_addr):
            return False, "Address appears to contain random keystrokes or meaningless characters."

    # Must contain word boundaries / separated tokens (at least 2 distinct words)
    tokens = [t for t in re.split(r'[\s,./#\-]+', addr) if t]
    if len(tokens) < 2:
        return False, "Please include complete street details such as house/flat number, street name, and area."

    for t in tokens:
        if len(t) >= 3 and len(set(t.lower())) == 1:
            return False, "Address contains invalid repeated character tokens."
        # Check for keyboard mash words (words longer than 5 letters without vowels)
        if len(t) > 5 and not any(v in t.lower() for v in 'aeiouy'):
            return False, "Address contains unrecognized or meaningless word sequences."
        # Consecutive consonant clusters >= 5
        if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', t.lower()):
            return False, "Address contains meaningless consonant sequences."

    # Vowel ratio check across letters to block keyboard mash
    letters = [c.lower() for c in addr if c.isalpha()]
    if letters:
        vowels = [c for c in letters if c in 'aeiouy']
        if len(letters) >= 8 and (len(vowels) / len(letters)) < 0.15:
            return False, "Address appears to be random or meaningless characters."

    return True, ""
