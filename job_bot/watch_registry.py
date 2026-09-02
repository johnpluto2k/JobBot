"""Verified public job-board endpoints for the companies John tracks.

Every entry here was probed live on 2026-09-02 and returned real postings.
Tokens are NOT guessable reliably, so this file is curated data, not inference.
Companies absent from this file have no usable public feed (Taleo, iCIMS,
SuccessFactors, Phenom People, Avature, or a bespoke site) and stay on the
manual next_check_due nudge instead.

How each entry was verified
---------------------------
Greenhouse       GET  https://boards-api.greenhouse.io/v1/boards/{token}/jobs
Ashby            POST https://jobs.ashbyhq.com/api/non-user-graphql
                      ?op=ApiJobBoardWithTeams  (data.jobBoard non-null)
SmartRecruiters  GET  https://api.smartrecruiters.com/v1/companies/{token}/postings
                      (accepted only when totalFound > 0 -- this endpoint
                       returns HTTP 200 with totalFound == 0 for ANY token)
Workday          POST https://{host}/wday/cxs/{tenant}/{site}/jobs
                      body {"appliedFacets":{},"limit":20,"offset":0,"searchText":""}
                      200 = tenant + site + wdN all correct
                      404 = tenant correct, site slug wrong
                      422 = tenant does not exist

Every candidate hit was additionally opened and the returned job titles read,
so squatted / same-word-different-company boards were thrown out (see the
exclusion notes near the bottom of this file).

Trailing counts are open roles observed at verification time. Workday reports
`total`, which it caps at 2000, so "2000" means "2000 or more".
"""

# name must match companies.name exactly as stored in the tracker.
GREENHOUSE = {
    "Stripe": "stripe",                                       # 592 open roles when verified
    "Databricks": "databricks",                               # 865
    "Accenture Federal Services": "accenturefederalservices", # 641
    "Datadog": "datadog",                                     # 444
    "Brex": "brex",                                           # 292
    "Affirm": "affirm",                                       # 199
    "Block": "block",                                         # 196
    "Coinbase": "coinbase",                                   # 190
    "Forvis Mazars": "forvismazars",                          # 190 (EU board: DE/FR roles, no US)
    "Appian": "appian",                                       # 163
    "Airbnb": "airbnb",                                       # 163
    "Robinhood": "robinhood",                                 # 131
    "Diligent": "diligentcorporation",                        # 114 (NOT "diligent" -- see exclusions)
    "Gusto": "gusto",                                         # 94
    "OneTrust": "onetrust",                                   # 85
    "Charles River Associates": "charlesriverassociates",     # 77
    "Chime": "chime",                                         # 63
    "SoFi": "sofi",                                           # 62
    "Mercury": "mercury",                                     # 54
    "ID.me": "idme",                                          # 52
    "Thoughtworks": "thoughtworks",                           # 43
    "LogicGate": "logicgate",                                 # 14
    "Virtru": "virtru",                                       # 14
    "Pilot": "pilothq",                                       # 12
    "Expel": "expel",                                         # 6
    "Hyperproof": "hyperproof",                               # 5
    "2U": "2u",                                               # 2
}

ASHBY = {
    "Snowflake": "snowflake",        # 381
    "Ramp": "ramp",                  # 138
    "Vanta": "vanta",                # 109
    "Plaid": "plaid",                # 102
    "Drata": "drata",                # 44
    "Numeric": "numeric",            # 21
    "Secureframe": "secureframe",    # 14 (several Washington D.C. roles)
}

SMARTRECRUITERS = {
    "ServiceNow": "ServiceNow",                               # 574
    "Experian": "Experian",                                   # 458
    "Northwestern Mutual": "NorthwesternMutual",              # 69 (tech/field roles; corporate roles are on the Workday feed below)
    "Accenture Federal Services": "AccentureFederalServices", # 23 (separate feed from their Greenhouse board)
    "CACI International": "caci",                             # 14 (intel/linguist roles; the bulk is on the Workday feed below)
    "Castro & Company": "CastroCompany",                      # 7 (DMV federal-audit shop: Staff/Senior Auditor, Audit Manager)
}

# name -> (host, tenant, site)
WORKDAY = {
    # --- Big 4 / accounting / advisory ---
    # US slug, not Global_Experienced_Careers (4301). The global board is mostly
    # Mumbai/Bengaluru postings - a live pass through it returned 150 roles and 0
    # survived the DMV location filter, so it is pure noise for this watcher.
    "PwC": ("pwc.wd3.myworkdayjobs.com", "pwc", "US_Experienced_Careers"),              # 472
    "RSM": ("rsm.wd1.myworkdayjobs.com", "rsm", "RsmCareers"),                          # 771 (39 match "Washington")
    "Baker Tilly": ("bakertilly.wd5.myworkdayjobs.com", "bakertilly", "BTCareers"),     # 427 (164 match "audit")
    "Andersen": ("andersen.wd12.myworkdayjobs.com", "andersen", "Andersen_External_Career_Site"),  # 255
    "Crowe": ("crowe.wd12.myworkdayjobs.com", "crowe", "External_Careers"),             # 217 (44 match "Washington")
    "EisnerAmper": ("eisneramper.wd1.myworkdayjobs.com", "eisneramper", "Eisneramper_External"),   # 165
    "Plante Moran": ("plantemoran.wd1.myworkdayjobs.com", "plantemoran", "pmexternalcareers"),     # 135

    # --- Consulting / strategy ---
    "Accenture": ("accenture.wd103.myworkdayjobs.com", "accenture", "AccentureCareers"),  # 2000 (capped)
    "Oliver Wyman": ("mmc.wd1.myworkdayjobs.com", "mmc", "Mmc"),                        # 1923 on the parent Marsh McLennan board; 425 match "Oliver Wyman"
    "Guidehouse": ("guidehouse.wd1.myworkdayjobs.com", "guidehouse", "External"),       # 794 (124 match "Washington")
    "Huron Consulting": ("huron.wd1.myworkdayjobs.com", "huron", "HuronCareers"),       # 274
    "Ankura": ("ankura.wd5.myworkdayjobs.com", "ankura", "Ankura"),                     # 47

    # --- Govcon / federal (DMV core) ---
    "Northrop Grumman": ("ngc.wd1.myworkdayjobs.com", "ngc", "Northrop_Grumman_External_Site"),  # 3692
    "Amentum": ("pae.wd1.myworkdayjobs.com", "pae", "Amentum_Careers"),                 # 2682 (tenant is the legacy "pae")
    "Booz Allen Hamilton": ("bah.wd1.myworkdayjobs.com", "bah", "Bah_Jobs"),            # 2000 (capped)
    "Leidos": ("leidos.wd5.myworkdayjobs.com", "leidos", "External"),                   # 2000 (capped)
    "CACI International": ("caci.wd1.myworkdayjobs.com", "caci", "External"),           # 1764
    "General Dynamics IT": ("gdit.wd5.myworkdayjobs.com", "gdit", "External_Career_Site"),  # 1173
    "ICF": ("icf.wd5.myworkdayjobs.com", "icf", "ICFExternal_Career_Site"),             # 387

    # --- Financial services / DMV employers ---
    "Capital One": ("capitalone.wd12.myworkdayjobs.com", "capitalone", "Capital_One"),  # 1866
    "Wells Fargo": ("wf.wd1.myworkdayjobs.com", "wf", "WellsFargoJobs"),                # 1687
    "Citi": ("citi.wd5.myworkdayjobs.com", "citi", "2"),                                # 2000 (capped)
    "Raymond James": ("raymondjames.wd1.myworkdayjobs.com", "raymondjames", "RaymondjamesCareers"),  # 347
    "GEICO": ("geico.wd1.myworkdayjobs.com", "geico", "External"),                      # 282
    "BlackRock": ("blackrock.wd1.myworkdayjobs.com", "blackrock", "Blackrock_Professional"),  # 275
    "USAA": ("usaa.wd1.myworkdayjobs.com", "usaa", "USAAJOBSWD"),                       # 176
    "T. Rowe Price": ("troweprice.wd5.myworkdayjobs.com", "troweprice", "Troweprice"),  # 125
    "Freddie Mac": ("freddiemac.wd5.myworkdayjobs.com", "freddiemac", "External"),      # 90
    "Northwestern Mutual": ("northwesternmutual.wd5.myworkdayjobs.com", "northwesternmutual", "CORPORATE-CAREERS"),  # 86
    "Fannie Mae": ("fanniemae.wd1.myworkdayjobs.com", "fanniemae", "FanniemaeCareers"), # 57
    "Cerity Partners": ("ceritypartners.wd12.myworkdayjobs.com", "ceritypartners", "CeritypartnersCareers"),  # 55
    "American Bankers Association": ("aba.wd1.myworkdayjobs.com", "aba", "Aba"),        # 5 (all "US DC Main Office")

    # --- Data / analytics / fintech infrastructure ---
    "IQVIA": ("iqvia.wd1.myworkdayjobs.com", "iqvia", "Iqvia"),                         # 1903
    "Danaher": ("danaher.wd1.myworkdayjobs.com", "danaher", "DanaherJobs"),             # 1327
    "Gartner": ("gartner.wd5.myworkdayjobs.com", "gartner", "EXT"),                     # 744
    "FIS": ("fis.wd5.myworkdayjobs.com", "fis", "SearchJobs"),                          # 418
    "CoStar Group": ("costar.wd1.myworkdayjobs.com", "costar", "CostarCareers"),        # 403
    "Fiserv": ("fiserv.wd5.myworkdayjobs.com", "fiserv", "EXT"),                        # 370
    "S&P Global": ("spgi.wd5.myworkdayjobs.com", "spgi", "Spgi_Careers"),               # 314
    "TransUnion": ("transunion.wd5.myworkdayjobs.com", "transunion", "Transunion"),     # 236
    "Morningstar": ("morningstar.wd5.myworkdayjobs.com", "morningstar", "Morningstar"), # 214
    "Equifax": ("equifax.wd5.myworkdayjobs.com", "equifax", "External"),                # 193
    "Blackbaud": ("blackbaud.wd1.myworkdayjobs.com", "blackbaud", "ExternalCareers"),   # 90
    "PayPal": ("paypal.wd1.myworkdayjobs.com", "paypal", "jobs"),                       # 29

    # --- Big tech / other ---
    "NVIDIA": ("nvidia.wd5.myworkdayjobs.com", "nvidia", "NvidiaExternalCareerSite"),   # 2000 (capped)
    "Salesforce": ("salesforce.wd12.myworkdayjobs.com", "salesforce", "External_Career_Site"),  # 1481
    "Cisco": ("cisco.wd5.myworkdayjobs.com", "cisco", "Cisco_Careers"),                 # 1270
    "Adobe": ("adobe.wd5.myworkdayjobs.com", "adobe", "external_experienced"),          # 733
    "Uline": ("uline.wd1.myworkdayjobs.com", "uline", "Uline_Careers"),                 # 424
    "Workday": ("workday.wd5.myworkdayjobs.com", "workday", "Workday"),                 # 371
    "Insulet": ("insulet.wd5.myworkdayjobs.com", "insulet", "InsuletCareers"),          # 175
}

# ---------------------------------------------------------------------------
# Probed, real, and deliberately EXCLUDED -- recorded so nobody re-adds them.
#
#   Greenhouse "cornerstone"  -> Cornerstone Child Development Center (not Cornerstone Research)
#   Greenhouse "oliver"       -> OLIVER Agency (not Oliver Wyman)
#   Greenhouse "costar"       -> Co-Star, the astrology app (not CoStar Group)
#   Greenhouse "diligent"     -> Diligent Services, a construction firm (not Diligent the GRC vendor)
#   Greenhouse "general"      -> a board literally named "General Interest" (not General Dynamics IT)
#   Greenhouse "cherry"       -> a board named "Cherry" with 0 postings (not Cherry Bekaert)
#   Ashby      "moss"         -> Moss, a Berlin fintech (not Moss Adams)
#   SmartRec.  "Palantir"     -> profile named Palantir but posts C#/QA contract roles; not
#                                Palantir Technologies, which has no public feed
#   SmartRec.  "GEICO"        -> 1 posting from a local GEICO agent office; corporate GEICO is
#                                the Workday entry above
#   SmartRec.  "Uber"         -> 1 posting titled "Test UAT"
#   SmartRec.  "mazars"       -> profile "MAZARS", French-language roles only
#   Workday    bdo.wd3/Bdo    -> real, 295 roles, but it is BDO Canada; 0 hits for "Washington"
#   Workday    roberthalf.wd1/RoberthalfCareers -> Robert Half's own board; Protiviti roles
#                                are not posted there
#   Workday    mitre.wd5/MITRE, alvarezandmarsal.wd1/alvarezandmarsalp, dell.wd1/External
#                             -> tenant and site both valid, but the feed returns total == 0
#
# Companies with NO public feed on any of the four platforms (every candidate
# Workday tenant returned 422, every board token 404'd): Deloitte, EY, KPMG,
# Grant Thornton (only grantthorntonaus.wd105 exists, Australia-only),
# Protiviti, CohnReznick, Cherry Bekaert, BDO (US), SAIC, Peraton, MITRE,
# Maximus, Noblis, LMI, Palantir, Cvent, Marriott International, Under Armour,
# Aledade, Arcadia, EAB, Dell Technologies, Alvarez & Marsal, Dun & Bradstreet,
# Berkeley Research Group.
# ---------------------------------------------------------------------------


def all_entries() -> list[dict]:
    """[{name, platform, token|host/tenant/site}] for every verified company."""
    out = []
    for n, t in GREENHOUSE.items():
        out.append({"name": n, "platform": "Greenhouse", "token": t})
    for n, t in ASHBY.items():
        out.append({"name": n, "platform": "Ashby", "token": t})
    for n, t in SMARTRECRUITERS.items():
        out.append({"name": n, "platform": "SmartRecruiters", "token": t})
    for n, (h, te, s) in WORKDAY.items():
        out.append({"name": n, "platform": "Workday", "host": h, "tenant": te, "site": s})
    return out
