#!/usr/bin/env python3

from ebaysdk.finding import Connection as Finding
from ebaysdk.shopping import Connection as Shopping
from ebaysdk.exception import ConnectionError

import json, re, datetime, os, requests

request = {
        "keywords": "",
        "categoryId": "9355",
        "itemFilter": [
            {"name": "LocatedIn", "value": "US"}
        ],
        "paginationInput": {
            "entriesPerPage": 100,
            "pageNumber": 1
        },
    }

# DateTime object in the response make json.dumps failed. I Modified the default encoder to handle the type datetime. 
json.JSONEncoder.default = lambda self,obj: (obj.isoformat() if isinstance(obj, datetime.datetime) else obj.__dict__)

def getResponseFromQuery(query, pageNum):
    """ Execute a request to the eBay API using a search query and the page number.
        The response returned contains informations about each ad on the page.

    Attributes:
        query (str): The eBay search query.
        pageNum (int): The page number to make the request. Pages have 100 entries per page.

    Returns:
        ebaysdk.response.Response corresponding to the query passed and the page number."""

    try:
        request["paginationInput"]["pageNumber"] = pageNum
        request["keywords"] = query
        api = Finding(config_file="ebaysdk/ebay.yaml", siteid="EBAY-US")
        return api.execute("findItemsAdvanced", request)
    except ConnectionError as e:
            print(e)
            print("Request to the ebay API has failed.")



def getResponseFromItemId(itemId):
    """ Execute a request to the eBay API using an itemId.
        The response returned contains informations about the ad.

    Attributes:
        itemId (str): The id of the eBay ad.

    Returns:
        ebaysdk.response.Response corresponding to the itemId."""

    try:
        api = Shopping(config_file="ebaysdk/ebay.yaml", siteid="EBAY-US")
        response = api.execute("GetSingleItem", {"ItemID": itemId})
        return response
    except ConnectionError as e:
            print(e)
            print(e.response.dict())


def responseToList(response):
    """ Format the response into a list of dictionaries.
        Each dictionary contains data about the item in each ad 
        from the eBay response.

    Attributes:
        response (ebaysdk.response.Response): The response from the ebay API.

    Returns:
        list of dictionnaries corresponding to the query passed and the page number.
        If the response is from the search API returns the response as a dictionnary else."""

    responseList = []
    if hasattr(response.reply, "searchResult"):
        for item in response.reply.searchResult.item:
            try:
                responseList.append(item.__dict__)
            except Exception as e:
                print(e)
                print("FormatResponse failed for a response.")
    return responseList



def printResponse(response):
    """ Print the response obtained from the eBay API in a readable way.

    Args:
        response (ebaysdk.response.Response): The response from the ebay API."""

    print(json.dumps(json.loads(response.json()), indent=4 ))



def printListOfDictionaries(responseList):
    """ Print the a list of dictionaries, or a dictionary in a readable way.
    
    Attributes:
        response (list, dict): a list containing dictionaries, or a dictionary."""
    

    if type(responseList) == list:
        for item in responseList:
            print(json.dumps(item, indent=4))
    elif type(responseList) == dict:
        print(json.dumps(responseList, indent=4))
    else:
        raise Exception("Argument passed should be of type dictionary or list")



def getValue(dictionary, key):
    """ Gets the value of corresponding to a key in a mutlidimensional dictionary.

    Attributes:
        dictionary (dict): a dictionary.
        key (str): the key corresponding to the value to return.    
        
    Returns: 
        the value corresponding to the key if the key is in the dictionary, return None otherwise."""

    value = None
    if key not in dictionary:
        for i in dictionary.keys():
            if type(dictionary[i]) != str and type(dictionary[i]) != list: 
                if value == None:
                    value = getValue(dictionary[i].__dict__, key)
        return value
    else:
        return dictionary[key]



def formatActiveAds(responseList):
    """ Formats a list of dictionaries obtained from a request to the eBay api.
        format is of the form: { itemId: endTime }. Used to get the final infos on ads
        when they end.

    Attributes:
        responseList (list): a list containing dictionaries. 

    Returns:
        A list of dictionaries of the form: { itemId: endTime }."""

    for i in range(len(responseList)):
        itemId = responseList[i]["itemId"]
        endTime = getValue(responseList[i], "endTime")
        responseList[i] = {itemId: endTime}
    return responseList



def formatFinishedAds(responseList):
    """ Formats a list of dictionaries obtained from a request to the eBay api.
        format is of the form: { itemId: {data about the item} }.

    Attributes:
        responseList (list): a list containing dictionaries. 

    Returns:
        A list of dictionaries of the form: { itemId: {data about the item} }."""

    for i in range(len(responseList)):
        itemId = responseList[i]["ItemID"]
        responseList[i] = {itemId: responseList[i]}
    return responseList



def writeAdsToFile(responseList, path):
    """ Write to a file (.json) the ads that are not in the file. 
        Uses the itemId from the response obtained from the eBay API,
        to check if an ad is already present in the file.
        
    Attributes:
        responseList (list): a list containing dictionaries.
        path (str): the of a json file to write the new data to.
        
    Returns:
        an integer corresponding to the number of new ads added to the file."""  

    # Check if the itemId is in the .json file and remove the item from 
    # responseList if ItemId was found.
    with open(path, mode="r", encoding="utf-8") as adsFile:
        ads = json.loads(adsFile.read())

        for item in list(responseList):
            itemId = list(item)[0]
            if itemId in ads: responseList.remove(item)
        

    with open(path, mode="r+", encoding="utf-8") as adsFile:
        ads = adsFile.read()
        isEmptyFile = len(json.loads(ads)) == 0

        # Remove the last 2 characters of the file. (\n and } for .json files)
        adsFile.seek(adsFile.tell() - 1, os.SEEK_SET)
        adsFile.write("")

        # Append the new ads to the end of the .json file.
        for item in responseList:
            if not isEmptyFile:
                adsFile.write("," + json.dumps(item, indent=4)[1:-2])
            else: 
                isEmptyFile = False
                adsFile.write(json.dumps(item, indent=4)[1:-2])
        adsFile.write("\n}")
    
    return len(responseList)



def writeDataFinishedAds(path1, path2):
    """ Get the data from ads that ended. Uses the itemId of af an ad to make a request to the eBay API.
        Uses the endTime attribute of an ad to verify if the ad has ended. 
        Removes the ads from path1 that have ended.
        
    Attributes:
        path1 (str): the path of a json file where the itemId and endTime of an ad are stored.
        path2 (str): the path of a json file to store the final data from ads once they have ended."""  

    
    # Get the ads in path1.
    with open(path1, mode="r", encoding="utf-8") as file1:
        ads = json.loads(file1.read())
        responseList = []

        for itemId in list(ads):
            hasPassed = isDatePassed(ads[itemId])
            if hasPassed: 
                # Remove the ads that have ended.
                ads.pop(itemId)

                # Get the response from the ItemId if the ad has ended and is still an ad.
                response = getResponseFromItemId(itemId)
                if response is not None:
                    responseDict = response.dict()["Item"]
                    responseList.append(responseDict)
                    

    # Write the ads that have ended to path2.
    formatedResponse = formatFinishedAds(responseList)
    totalAds = writeAdsToFile(formatedResponse, path2)
    
    # Remove the ads that have ended in path1.
    with open(path1, mode="w", encoding="utf-8") as file1:
        json.dump(ads, file1, indent=4)

    print("%d new ad(s) added to %s" % (totalAds, path2))
    return totalAds


def isDatePassed(date):
    """ Returns if the string date has passed or not.
    
    Attributes:
        date (str): the date to compare to the present date.
    
    Returns:
        True if the date has passed. False otherwise."""

    try:
        endTime = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
        return datetime.datetime.now() >= endTime
    except Exception as e:
        print(e)
        print("Date parsing has failed.")



def getDataOnItem(query, filename):
    """ Creates a JSON file containing data from the items corresponding to the query passed.
        Get the data from the eBay API on an item using a query.
        The data is updated everytime the function is called. Tracks
        the end time of each ad in order to know when to get the final
        data from each ads. 
        
        Attributes:
            query (str): The eBay search query.
            filename (str): The name of the file (json) to store the data to."""

    path1 = "Active/active" + filename + ".json"
    path2 = "Final/" + filename + ".json"
    if not os.path.isfile(path1):
        with open(path1, mode="w") as file1:
            file1.write("{\n\n}")
    if not os.path.isfile(path2):
        with open(path2, mode="w") as file2:
            file2.write("{\n\n}")

    totalAds = 0
    for i in range(10):  
        response = getResponseFromQuery(query, i)
        responseList = responseToList(response)
        formatedResponse = formatActiveAds(responseList)
        totalAds += writeAdsToFile(formatedResponse, path1)
    
    clearDuplicates("Active")
    
    print("%d new ad(s) added to %s" % (totalAds, path1))
    totalAds = writeDataFinishedAds(path1, path2)   
    return totalAds if totalAds else 0



def clearDuplicates(directory):
    files = os.listdir(directory)
    itemIds = {}
    duplicateIds = []

    # Get the ItemIds in all the files in the directory
    for f in files:
        if re.match("(.*?).json", f):
            with open(directory + "/" + f, mode="r") as file:
                responseList = json.load(file)
                for i in responseList:
                    if i not in itemIds: itemIds[i] = responseList[i]
                    else: duplicateIds.append(i)

    # Remove the duplicates in every files in the directory
    for f in files:
        if re.match("(.*?).json", f):
            responseList = None 
            with open(directory + "/" + f, mode="r") as file:
                responseList = json.load(file)
                for i in duplicateIds:
                    if i in responseList: del responseList[i]
            with open(directory + "/" + f, mode="w") as file:
                json.dump(responseList, file, indent=4)

    duplicateDict = None

    # Create a duplicates.json file in the directory if it does not exist.
    if not os.path.exists(directory + "duplicates.json"):
        with open(directory + "/duplicates.json", "w") as duplicate:
            duplicate.write("{\n}")

    # Ad all the duplicates to the duplicates.json file
    with open(directory + "/duplicates.json", "r") as duplicate:
        duplicateDict = json.load(duplicate)
        for i in duplicateIds:
            duplicateDict[i] = itemIds[i]
    with open(directory + "/duplicates.json", "w") as duplicate:
        json.dump(duplicateDict, duplicate, indent=4)

     

if __name__ == "__main__":
    os.chdir("/Users/jeanmer/Desktop/Python/Ebay")

    added = []
    added.append(getDataOnItem("Iphone 7s", "IPhone7s"))
    added.append(getDataOnItem("Iphone 10", "IPhone10"))
    added.append(getDataOnItem("Iphone 8", "IPhone8"))
    added.append(getDataOnItem("Iphone SE", "IPhoneSE"))
    added.append(getDataOnItem("Iphone 7", "IPhone7"))
    added.append(getDataOnItem("Iphone X", "IPhoneX"))
    added.append(getDataOnItem("Iphone Xr", "IPhoneXr"))
    from Count import printInfo
    printInfo(added)





