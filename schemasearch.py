# This module uses a custom Google Search Engine to search for sites that contain structured data.
#
# The search engine type (cx) and apiKey are defined in 'config.py'

import config
import requests, json, time

class schemaSearch():
	def __init__(self):
		self.pagemapIgnore = ['cse_thumbnail','metatags','cse_image']
		self.reportData = []
		self.APIdisconnect = False
		self.totalErrors = 0
		self.pages = 0
	def findSchema(self,search):
		search = search.strip()

		if search != '':
			startIndex = 1
			while True:
				if not self.APIdisconnect:
					searchData = self.apiRequest(search,startIndex)
					if searchData != None:
						self.pages = self.pages + 1
						startIndex = searchData
					else:
						break
				else:
					break

	def apiRequest(self,search,startIndex = 1):
		apiEndpoint = 'https://www.googleapis.com/customsearch/v1'

		returnData = []
		params = {
			'cx':config.apiConfig['schemasearch']['cx'],
			'key':config.apiConfig['schemasearch']['apiKey'],
			'start':startIndex,
			'q':'search'
		}
		try:
			HTTPrequest = requests.get(apiEndpoint,params = params)
			schemaData = json.loads(HTTPrequest.text)

			for thisResult in schemaData['items']:
				urlData = {}
				urlData['url'] = thisResult['link']
				urlData['title'] = thisResult['title']
				urlData['description'] = thisResult['snippet']
				urlSchemas = []
				for thisSchema,items in thisResult['pagemap'].items():
					if thisSchema not in self.pagemapIgnore:
						urlSchemas.append(thisSchema)
				urlData['schemas'] = urlSchemas
				self.reportData.append(urlData)
			if schemaData['queries']['nextPage'] != []:
				return schemaData['queries']['nextPage'][0]['startIndex']
			else:
				return None
		except:
			self.totalErrors = self.totalErrors + 1
			if(self.totalErrors > 50):
				self.APIdisconnect = True
			return None