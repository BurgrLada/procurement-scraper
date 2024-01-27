import requests
import xml.etree.ElementTree as ET
import csv
from time import sleep

# TODO: F06?

# how many submissions to get
NO_OF_SUBMISSIONS = 100000

# the prefix is necessary (in this format) for XML search (find function) to work
def getXMLAttr(attr):
    return "{https://www.vvz.nipez.cz/zvz_xml/schemas/vvz/v1.0.0}" + attr


def getSearchResultsUrl(page, limit):
    return f"https://api.vvz.nipez.cz/api/submissions/search?page={page}&limit={limit}&form=vz&workflowPlace=UVEREJNENO_VVZ&data.druhFormulare=F03&order%5Bdata.datumUverejneniVvz%5D=DESC"

# 50ms delay to not to overload the server
# sleep(0.05)

currSubmissions = []
submissionRemaining = NO_OF_SUBMISSIONS
page = 1


# Uncomment result variable to print all the results (in larger quantities = memory issues)
# results = []
notCZK = 0
noEstimate = 0
xmlError = 0
parsed = 0

with open('results.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["název zakázky", "zadavatel", "druh", "CPV", "počet soutěžících",
                    "výsledná cena", "očekávaná cena"])

    # get all search results (250 is max per request)
    while submissionRemaining > 0:
        limit = min(250, submissionRemaining)
        searchRes = requests.get(url=getSearchResultsUrl(page, limit)).json()

        # reached the end of the results
        if 'code' in searchRes and searchRes['code'] == "BAD_REQUEST":
            print("no more results", searchRes)
            break

        currSubmissions = searchRes
        submissionRemaining -= limit
        page += 1

        # iterate all results
        for submission in currSubmissions:
            parsed += 1
            id = submission['submissionVersion'].split('/')[-1]
            SUBMISSION_FIRST_URL = f'https://api.vvz.nipez.cz/api/submission_attachments?limit=50&submissionVersion={id}'

            firstRes = requests.get(url=SUBMISSION_FIRST_URL)
            publicId = firstRes.json()[0]["publicId"]

            SUBMISSION_SECOND_URL = f'https://api.vvz.nipez.cz/download/submission_attachments/public/{publicId}'
            secondRes = requests.get(url=SUBMISSION_SECOND_URL)

            xmlRoot = ET.fromstring(secondRes.content)

            try:
                # název zakázky
                try:
                    title = xmlRoot[0].find(getXMLAttr("OBJECT_CONTRACT")).find(
                        getXMLAttr("TITLE")).find(getXMLAttr("P")).text
                except:
                    raise Exception("no title")

                # zadavatel
                try:
                    contractOwner = xmlRoot[0].find(getXMLAttr("CONTRACTING_BODY")).find(
                        getXMLAttr("ADDRESS_CONTRACTING_BODY")).find(getXMLAttr("OFFICIALNAME")).text
                except:
                    raise Exception("no contract owner")

                # druh zakázky
                try:
                    kind = ""
                    xmlKind = xmlRoot[0].find(getXMLAttr("OBJECT_CONTRACT")).find(
                        getXMLAttr("TYPE_CONTRACT")).attrib["CTYPE"]
                    if xmlKind == "SUPPLIES":
                        kind = "Dodávky"
                    elif xmlKind == "SERVICES":
                        kind = "Služby"
                    elif xmlKind == "WORKS":
                        kind = "Stavební práce"
                    else:
                        raise Exception()
                except:
                    raise Exception("no kind")

                # CPV
                try:
                    cpv = xmlRoot[0].find(getXMLAttr("OBJECT_CONTRACT")).find(
                        getXMLAttr("CPV_MAIN")).find(getXMLAttr("CPV_CODE")).attrib["CODE"]
                except:
                    raise Exception("no cpv")

                # výsledek soutěže
                try:
                    tenderResults = xmlRoot[0].find(getXMLAttr("AWARD_CONTRACT")).find(
                        getXMLAttr("AWARDED_CONTRACT"))
                except:
                    raise Exception("no tender results")
                
                # počet soutěžících
                noOfCompetitors = tenderResults.find(getXMLAttr("TENDERS")).find(
                    getXMLAttr("NB_TENDERS_RECEIVED")).text

                # ceny
                try:
                    values = tenderResults.find(getXMLAttr("VALUES"))
                except:
                    raise Exception("no values")

                # očekávaná cena
                try:
                    estimatedVal = values.find(getXMLAttr("VAL_ESTIMATED_TOTAL"))
                    if estimatedVal is None:
                        raise Exception()
                except:
                    noEstimate += 1
                    raise Exception("no estimated value")

                # výsledná cena
                try:
                    realVal = values.find(getXMLAttr("VAL_TOTAL"))
                    if realVal is None:
                        raise Exception()
                except:
                    raise Exception("no real value")

                if estimatedVal is None:
                    noEstimate += 1
                    raise Exception("no estimated value")

                try:
                    realCurr = realVal.attrib["CURRENCY"]
                    estimatedCurr = estimatedVal.attrib["CURRENCY"]
                except:
                    raise Exception("no currency attribute")

                if (realCurr != "CZK" or estimatedCurr != "CZK"):
                    notCZK += 1
                    raise Exception("currency error")

                # results.append(
                #     {"title": title, "contractOwner": contractOwner, "kind": kind, "cpv": cpv, "real": realVal.text, "estimated": estimatedVal.text, "competitors": noOfCompetitors})
                writer.writerow([title, contractOwner, kind, cpv, noOfCompetitors,
                                realVal.text, estimatedVal.text])
            except Exception as err:
                xmlError += 1
                # print("ERROR IN XML", err, '(', SUBMISSION_SECOND_URL, ')')

# print(results)
print("celkem zpracováno", parsed)
print("ne v CZK", notCZK)
print("bez odhadu ceny", noEstimate)
print("celkem chyb v parsování XML (nejčasttěji chybějící cena, nevyhodnocená zakázka atp.)", xmlError)

