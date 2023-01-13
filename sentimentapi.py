# This module uses Google Cloud Natural Language to evaluate the sentiment of long-form text.
#
# API requests will be attempted several times before backing off when encountering an error.

import time
import gfunctions

from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types

class sentiment():
	def __init__(self,strings):
		self.apiProgress = 0
		self.apiStatus = ''
		self.apiRequests = []
		self.apiNextRequest = -1

		self.reportHeaders = []
		self.reportData = {}
		self.APIdisconnect = False
		self.totalErrors = 0

		g = gfunctions.gInterface()
		self.client = language.LanguageServiceClient(credentials = g.credentials)

		for thisString in strings:
			if thisString not in self.apiRequests:
				self.apiRequests.append(thisString)
	
	def processNext(self):
		nextID = self.apiNextRequest + 1
		totalRequests = len(self.apiRequests)
		if nextID < totalRequests and not self.APIdisconnect:
			self.apiProgress = (nextID / totalRequests) * 100
			self.apiStatus = self.apiRequests[nextID]
			self.checkSentiment(self.apiRequests[nextID])
			self.apiNextRequest = nextID
			return True;
		else:
			return False
	def checkSentiment(self,string):
		string.strip()
		document = types.Document(
			content = string,
			language = "en",
			type = enums.Document.Type.PLAIN_TEXT)
		
		sentiment = None
		retries = 0
		while retries < 5:
			try:
				sentimentData = self.client.analyze_sentiment(document = document).document_sentiment
				self.reportData[string] = [sentimentData.score,sentimentData.magnitude]
				break
			except:
				time.sleep(1)
				retries = retries + 1
				self.totalErrors = self.totalErrors + 1
				if(self.totalErrors > 20):
					self.APIdisconnect = True
