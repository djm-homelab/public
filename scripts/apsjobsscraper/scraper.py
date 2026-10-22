
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import shutil

import requests

BASE_URL = "https://www.apsjobs.gov.au"
SEARCH_URL = f"{BASE_URL}/s/job-search"
AURA_URL = f"{BASE_URL}/s/sfsites/aura"

# Copied from the browser request. These may need refreshing if
# Salesforce changes its deployed framework version.
AURA_CONTEXT = {
    "mode": "PROD",
    "fwuid": "SGRNczhXdnNHNDNKUWhIdXFhdFJlUWtVMjdnTGFERUU2S3FfSVdrcU92bkExNS4zLjE2MDEw",
    "app": "siteforce:communityApp",
    "loaded": {
        "APPLICATION@markup://siteforce:communityApp":
            "1893_tc0hDgV9c96ds91w6tiHCw"
    },
    "dn": [],
    "globals": {},
    "uad": True,
}
# {"actions":[{"id":"122;a","descriptor":"aura://ApexActionController/ACTION$execute","callingDescriptor":"UNKNOWN","params":{"namespace":"","classname":"aps_jobSearchController","method":"retrieveJobListings","params":{"filter":"{\"searchString\":null,\"salaryFrom\":null,\"salaryTo\":null,\"closingDate\":null,\"positionInitiative\":null,\"classification\":[\"Executive Level 1\",\"Executive Level 2\"],\"securityClearance\":null,\"officeArrangement\":null,\"duration\":null,\"department\":null,\"category\":[\"Info/Comm Tech (ICT)\",\"Policy\",\"Other Management\"],\"opportunityType\":[\"Full-Time\"],\"employmentStatus\":[\"Ongoing\"],\"state\":null,\"sortBy\":null,\"offset\":30,\"offsetIsLimit\":false,\"lastVisitedId\":null,\"daysInPast\":null,\"name\":null,\"type\":null,\"notificationsEnabled\":null,\"savedSearchId\":null}&requested=Thu Oct 22 2026 06:18:18 GMT+1100 (Australian Eastern Daylight Time)"},"cacheable":false,"isContinuation":false}}]}
#
DEFAULT_FILTERS = {
    "searchString": None,
    "salaryFrom": None,
    "salaryTo": None,
    "closingDate": None,
    "positionInitiative": None,
    "classification": ["Executive Level 1", "Executive Level 2"],
    "securityClearance": None,
    "officeArrangement": None,
    "duration": None,
    "department": None,
    "category": ["Info Comm Tech (ICT)","Policy","Other Management"],
    "opportunityType": ["Full-Time"],
    "employmentStatus": ["Ongoing"],
    "state": None,
    "sortBy": None,
    "offset": 0,
    "offsetIsLimit": False,
    "lastVisitedId": None,
    "daysInPast": None,
    "name": None,
    "type": None,
    "notificationsEnabled": None,
    "savedSearchId": None,
}


def js_date_now():
    """Produce the date format used in the captured Aura request."""
    now = datetime.now(ZoneInfo("Australia/Sydney"))
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    day = now.day
    offset = now.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}"
    zone_name = (
        "Australian Eastern Daylight Time"
        if now.dst().total_seconds() != 0
        else "Australian Eastern Standard Time"
    )
    return (
        f"{weekdays[now.weekday()]} {months[now.month - 1]} "
        f"{day} {now.year} {now.strftime('%H:%M:%S')} "
        f"GMT{offset.replace(':', '')} ({zone_name})"
    )


def retrieve_jobs(offset=0, filters=None):
    return_list = []
    # Establish a fresh public-site session instead of hardcoding
    # browser cookies copied from DevTools.
    #
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Origin": BASE_URL,
        "Referer": SEARCH_URL,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-SFDC-LDS-Endpoints":
            "ApexActionController.execute:aps_jobSearchController.retrieveJobListings",
    })

    session.get(SEARCH_URL, timeout=90).raise_for_status()

    page_size = 15
    num_results = 10000

    active_filters = DEFAULT_FILTERS.copy()

    if filters:
        active_filters.update(filters)

    #create loop here to request next page of results.
    # offset+pagesize
    # 0 15  1000
    while( (offset + page_size) < num_results ):
        active_filters["offset"] = offset

        # The filter is JSON encoded inside a string, with a separate
        # requested timestamp appended to that string.
        #
        filter_value = (
            json.dumps(active_filters, separators=(",", ":"))
            + "&requested="
            + js_date_now()
        )

        message = {
            "actions": [{
                "id": "111;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "",
                    "classname": "aps_jobSearchController",
                    "method": "retrieveJobListings",
                    "params": {"filter": filter_value},
                    "cacheable": False,
                    "isContinuation": False,
                },
            }]
        }

        response = session.post(
            AURA_URL,
            params={"r": "6", "aura.ApexAction.execute": "1"},
            data={
                "message": json.dumps(message, separators=(",", ":")),
                "aura.context": json.dumps(
                    AURA_CONTEXT, separators=(",", ":")
                ),
                "aura.pageURI": "/s/job-search",
                "aura.token": "null",
            },
            timeout=60,
        )
        response.raise_for_status()

        # Preserve the unmodified response body for debugging.
        Path(f"apsjobs-offset-{offset}.raw").write_bytes(response.content)

        body = response.text.lstrip()
        if body.startswith("while(1);"):
            body = body[len("while(1);"):].lstrip()

        result = json.loads(body)

        Path(f"apsjobs-offset-{offset}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        for action in result.get("actions", []):
            if action.get("state") != "SUCCESS":
                print("Aura action:", action.get("state"))
                print(json.dumps(action.get("error"), indent=2))
                continue

            value = action.get("returnValue")
            print("Return value type:", type(value).__name__)
            print(json.dumps(value, indent=2, ensure_ascii=False)[:500])

            num_results = action.get("returnValue").get("returnValue").get("jobListingCount")
            print(type(action.get("returnValue").get("returnValue").get("jobListings")).__name__)
            for joblisting in action.get("returnValue").get("returnValue").get("jobListings"):
                return_list.append(joblisting)

        offset+= page_size
        print(f"offset={offset}")
        print(f"page size={page_size}")
        print(f"number of results={num_results}")

       # joblistings=action.get("returnValue").get("returnValue").get("jobListings");
       # print("break here\n\n\n")
       # print(joblistings);

    return return_list

def formatJobHtml(job):
    fields_to_keep = [
        "departmentName",
        "departmentURL" ,
        "jobClassification",
        "jobName" 	 ,
        "jobSalaryFrom",
        "applicationURL",
        "jobLocation" ,
        "jobPostedDate",
        "jobCloseDate" ,
        "departmentDescription",
        "jobDescription"	,
        "jobDuties" 	,
        "jobEligibilityRequirements" 	,
        "jobCategory" 	,
        "jobContact" 	,
        "jobContactPhone"  	,
        "jobNotes" 	,
        "jobStatus" ,
        "jobType" ,
        "officeArrangement"
    ]

    returnstring = ""
    classification = job.get("jobClassification")
    title = job.get("jobName")
    department = job.get("departmentName")
    returnstring += f"<details> \n <summary>{classification} - {department} - {title}</summary> \n"
    returnstring += "<ul> \n <table> \n <tr>\n <th>Field</th>\n <th>Data</th> \n</tr>\n"

    for field in fields_to_keep:
        if "URL" in field:
            returnstring+= f"<tr>\n <td>{field}</td>\n <td><a href='{job.get(field)}'> {job.get(field)}</a> </td> \n</tr>\n"
        elif "jobName" in field:
            returnstring+= f"<tr>\n <td>{field}</td>\n <td><a href='https://www.apsjobs.gov.au/s/job-details?Id={job.get("jobId")}'> {job.get(field)}</a> </td> \n</tr>\n"
        elif "jobSalaryFrom" in field:
            if job.get('jobSalaryFrom') == None or job.get('jobSalaryTo') == None: continue
            salFrom=int(float(job.get('jobSalaryFrom')))
            salTo=int(float(job.get('jobSalaryTo')))
            returnstring += f"<tr>\n <td>Salary</td>\n <td> ${salFrom:,d} to ${salTo:,d}</td> \n</tr>\n"
        else:
            returnstring+= f"<tr>\n <td>{field}</td>\n <td>{job.get(field)}</td> \n</tr>\n"

    #for item in job.items():
    #    returnstring+= f"<tr>\n <td>{item[0]}</td>\n <td>{item[1]}</td> \n</tr>\n"

    returnstring +=(f"</table></ul></details>")

    return returnstring



if __name__ == "__main__":
    #set filters here
    filters = None
    jobs_dict = {}

    closing_soon = retrieve_jobs(filters = {"sortBy": "Closing Date (Closest First)"})
    jobs = retrieve_jobs(filters=filters)
    remaining_jobs=[]

    filepath = Path("apsjobs-complete.json")
    htmlfilepath=Path(f"apsjobs-completelist-{js_date_now()}.html")
    current_date = date.today()

    with htmlfilepath.open(mode="a", encoding="utf-8") as htmlfile:
        htmlfile.write("<style> table, th, td {border: 1px solid black; border-collapse: collapse;} </style>")
        htmlfile.write("<H1> New Jobs Today </H1>")

        for job in jobs:
            title= job.get("jobName")
            postedDate = date.fromisoformat(job.get("jobPostedDate"))
            if (("Section 26") in title) or ("Temporary" in title) or ("26" in title):
                continue
            print(f"current date: {current_date}, posted date: {postedDate}")
            if postedDate == current_date:
                htmlfile.write(formatJobHtml(job))
            else:
                remaining_jobs.append(job)



        htmlfile.write("<H1> Jobs Closing Soon (Next 7 days) </H1>")

        for job in closing_soon:
            current_date = date.today()
            close_date = date.fromisoformat(job.get("jobCloseDate"))
            if close_date > (current_date + timedelta(days=7)):
                continue
            htmlfile.write(formatJobHtml(job))

        htmlfile.write("<H1> All jobs meeting criteria</H1>")
        for job in remaining_jobs:
            title= job.get("jobName")
            if (("Section 26") in title) or ("Temporary" in title) or ("26" in title):
                continue

            htmlfile.write("<style> table, th, td {border: 1px solid black; border-collapse: collapse;} </style>")
            htmlfile.write(formatJobHtml(job))

        indexfilepath=Path("index.html")
        shutil.copy(htmlfilepath,indexfilepath)


#        with filepath.open(mode="a", encoding="utf-8") as file:
#            file.write(json.dumps(job,indent=2,ensure_ascii=False))
