# This module fetches domain data from SEMrush through the API.
#
# This API typically has daily limits as well as total monthy credits/limits
# which can be configured on 'config.py' along with the API key.
#
# This module can check available API units through the API to confirm
# that there are still credits remaining to make a request.

import config
import requests, json, time
from urllib.parse import urlparse

class domains():
	def __init__(self,domains):
		self.apiProgress = 0
		self.apiStatus = ''
		self.apiRequests = []
		self.apiNextRequest = -1

		self.reportHeaders = []
		self.reportData = {}
		self.APIdisconnect = False
		self.totalErrors = 0

		for thisDomain in domains:
			parsedURL = urlparse(thisDomain)
			if '://' not in thisDomain:
				parsedURL = urlparse('https://' + thisDomain)
			if parsedURL[1] not in self.apiRequests:
				self.apiRequests.append(parsedURL[1])
	def processNext(self):
		nextID = self.apiNextRequest + 1
		totalRequests = len(self.apiRequests)
		if nextID < totalRequests and not self.APIdisconnect:
			self.apiProgress = (nextID / totalRequests) * 100
			self.apiStatus = self.apiRequests[nextID]
			self.getDomainData(self.apiRequests[nextID])
			self.apiNextRequest = nextID
			return True;
		else:
			return False
	def getDomainData(self,domain):
		apiEndpoint = 'https://api.semrush.com/analytics/v1'
		headers = {'content-type':"application/json"}
		params = {
			'key':config.apiConfig['semrush']['apiKey'],
			'type':'backlinks_overview',
			'database':'us',
			'target_type':'domain',
			'target':domain
		}
		try:
			HTTPrequest = requests.get(apiEndpoint,headers = headers,params = params)
			rows = HTTPrequest.text.split("\r\n")
			results = [thisRow.split(";") for thisRow in rows]
			self.reportHeaders = results.pop(0)
			if(results != []):
				self.reportData[domain] = results[0]
		except requests.exceptions.SSLError:
			self.totalErrors = self.totalErrors + 1
			if(self.totalErrors > 50):
				self.APIdisconnect = True
		except requests.exceptions.ConnectionError:
			self.APIdisconnect = True
class info():
	def checkAPILimits(self):
		apiEndpoint = 'http://www.semrush.com/users/countapiunits.html'
		headers = {'content-type':"application/json"}
		params = {
			'key':config.apiConfig['semrush']['apiKey']
		}
		try:
			HTTPrequest = requests.get(apiEndpoint,headers = headers,params = params)
			return int(HTTPrequest.text)
		except:
			return -1