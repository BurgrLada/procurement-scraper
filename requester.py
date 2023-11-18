import requests
import xml.etree.ElementTree as ET
import csv

# how many submissions to get
NO_OF_SUBMISSIONS = 500

# defining the api-endpoint
# API_ENDPOINT = f"https://api.vvz.nipez.cz/api/submissions/search?page=1&limit={NO_OF_SUBMISSIONS}&form=vz&workflowPlace=UVEREJNENO_VVZ&data.druhFormulare=F03&order%5Bdata.datumUverejneniVvz%5D=DESC"

# the prefix is necessary (in this format) for XML search (find function) to work
def getXMLAttr(attr):
    return "{https://www.vvz.nipez.cz/zvz_xml/schemas/vvz/v1.0.0}" + attr


def getSearchResults(page, limit):
    return f"https://api.vvz.nipez.cz/api/submissions/search?page={page}&limit={limit}&form=vz&workflowPlace=UVEREJNENO_VVZ&data.druhFormulare=F03&order%5Bdata.datumUverejneniVvz%5D=DESC"


allSubmissions = []
submissionRemaining = NO_OF_SUBMISSIONS
page = 1
# get all search results (250 is max per request)
while submissionRemaining > 0:
    limit = min(250, submissionRemaining)
    searchRes = requests.get(url=getSearchResults(page, limit))
    allSubmissions.extend(searchRes.json())
    submissionRemaining -= limit
    page += 1

results = []
notCZK = 0
noEstimate = 0
xmlError = 0
parsed = 0

with open('results.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["název", "CPV", "počet soutěžících",
                    "výsledná cena", "očekávaná cena"])

    # iterate all results
    for submission in allSubmissions:
        parsed += 1
        id = submission['submissionVersion'].split('/')[-1]
        SUBMISSION_FIRST_URL = f'https://api.vvz.nipez.cz/api/submission_attachments?limit=50&submissionVersion={id}'

        firstRes = requests.get(url=SUBMISSION_FIRST_URL)
        publicId = firstRes.json()[0]["publicId"]

        SUBMISSION_SECOND_URL = f'https://api.vvz.nipez.cz/download/submission_attachments/public/{publicId}'
        secondRes = requests.get(url=SUBMISSION_SECOND_URL)

        xmlRoot = ET.fromstring(secondRes.content)

        # TODO Add delay to not overload the server

        try:
            try:
                title = xmlRoot[0].find(getXMLAttr("OBJECT_CONTRACT")).find(
                    getXMLAttr("TITLE")).find(getXMLAttr("P")).text
            except:
                raise Exception("no title")

            try:
                cpv = xmlRoot[0].find(getXMLAttr("OBJECT_CONTRACT")).find(
                    getXMLAttr("CPV_MAIN")).find(getXMLAttr("CPV_CODE")).attrib["CODE"]
            except:
                raise Exception("no cpv")

            try:
                tenderResults = xmlRoot[0].find(getXMLAttr("AWARD_CONTRACT")).find(
                    getXMLAttr("AWARDED_CONTRACT"))
            except:
                raise Exception("no tender results")

            try:
                values = tenderResults.find(getXMLAttr("VALUES"))
            except:
                raise Exception("no values")

            try:
                estimatedVal = values.find(getXMLAttr("VAL_ESTIMATED_TOTAL"))
                if estimatedVal is None:
                    raise Exception()
            except:
                raise Exception("no estimated value")

            try:
                realVal = values.find(getXMLAttr("VAL_TOTAL"))
                if realVal is None:
                    raise Exception()
            except:
                raise Exception("no real value")

            if estimatedVal is None:
                print("NO ESTIMATED VALUE")
                noEstimate += 1
                continue

            try:
                realCurr = realVal.attrib["CURRENCY"]
                estimatedCurr = estimatedVal.attrib["CURRENCY"]
            except:
                raise Exception("no currency attribute")

            if (realCurr != "CZK" or estimatedCurr != "CZK"):
                notCZK += 1
                raise Exception("currency error")

            noOfCompetitors = tenderResults.find(getXMLAttr("TENDERS")).find(
                getXMLAttr("NB_TENDERS_RECEIVED")).text

            results.append(
                {"title": title, "cpv": cpv, "real": realVal.text, "estimated": estimatedVal.text, "competitors": noOfCompetitors})
            writer.writerow([title, cpv, noOfCompetitors,
                            realVal.text, estimatedVal.text])
        except Exception as err:
            xmlError += 1
            print("ERROR IN XML", err, '(', SUBMISSION_SECOND_URL, ')')

# print(results)
print("celkem zpracováno", parsed)
print("ne v CZK", notCZK)
print("bez odhadu ceny", noEstimate)
print("chyb v parsování XML", xmlError)
# notes:
# get all 100 000 ids
# get param submissionVersion
# go to its endpoint (i.e. "/api/submission_versions/7bc9c387-a901-4ad7-a0c2-58768758546a") at api https://api.vvz.nipez.cz/api/submission_attachments?limit=50&submissionVersion=7bc9c387-a901-4ad7-a0c2-58768758546a
# get publicId param and use it at API https://api.vvz.nipez.cz/download/submission_attachments/public/6RYwKzRTMV84Xza7bdo4avFupJhpEdaS
# compare <VAL_ESTIMATED_TOTAL CURRENCY="CZK">1380000</VAL_ESTIMATED_TOTAL> and <VAL_TOTAL CURRENCY="CZK">1321969</VAL_TOTAL>


# extracting data in json format


# print(data)
