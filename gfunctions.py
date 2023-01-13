# These functions connect to Google Drive and Google Sheets as well as manage
# user requests and quotas via the service worker.
#
# Service worker account is authenticated from the 'credentials.json' file.
#
# The service worker account will create and own the Google Sheet so it will need to be
# shared with an actual Google User account for access and then ownership can be transfered.
#
# User quotas for maximum daily and monthly requests are defined in the 'config.py' file.
#
# The addUserRequest function tracks user requests in Google Datastore and are checked against
# the defined quotas when making a new request.

import config
import datetime
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import datastore
from google.cloud import bigquery

class gInterface:
	def __init__(self):
		self.credentials = service_account.Credentials.from_service_account_file('credentials.json')
		self.datastore = datastore.Client()
	def startDrive(self):
		self.drive = build('drive', 'v3', credentials = self.credentials)
		self.sheets = build('sheets', 'v4', credentials = self.credentials)

	def createSheet(self,name):
		spreadsheet = {'properties': {'title': name}}
		spreadsheet = self.sheets.spreadsheets().create(body = spreadsheet,fields = 'spreadsheetId').execute()
		sheetID = spreadsheet.get('spreadsheetId')
		return sheetID

	def addDataToSheet(self,sheetID,dataRange,data):
		body = {'values':data}
		self.sheets.spreadsheets().values().update(spreadsheetId = sheetID,range = dataRange,valueInputOption = "RAW",body = body).execute()

	def shareFileWithUser(self,fileID,userEmail,message = ''):
		if userEmail != '':
			permissions = self.drive.permissions().create(
				fileId = fileID,
				transferOwnership = False,
				sendNotificationEmail = True,
				emailMessage = message,
				body = {
					'type':'user',
					'role':'writer',
					'emailAddress': userEmail
				}
			).execute()

			self.drive.files().update(fileId = fileID,body = {'permissionIds': [permissions['id']]}).execute()

	def transferToUser(self,fileID,userEmail):
		if userEmail != '':
			permissions = self.drive.permissions().create(
				fileId = fileID,
				transferOwnership = True,
				body = {
					'type':'user',
					'role':'owner',
					'emailAddress': userEmail
				}
			).execute()

			self.drive.files().update(fileId = fileID,body = {'permissionIds': [permissions['id']]}).execute()
	def addUserRequest(self,userID,apiName,requests):
		sessionRecord = datastore.Entity(key = self.datastore.key(str(userID)))
		sessionRecord.update({'timestamp':time.time(),'api':apiName,'requests':requests})
		self.datastore.put(sessionRecord)

	def checkUserRequests(self,userID,apiName,beginTime = 0, endTime = 2000000000):
		userRecord = self.datastore.query(kind = str(userID))
		userData = userRecord.fetch()

		totalRequests = 0
		for thisRow in userData:
			if 'api' in thisRow:
				if thisRow['api'] == apiName:
					if thisRow['timestamp'] > beginTime and thisRow['timestamp'] < endTime:
						totalRequests = totalRequests + thisRow['requests']
		
		return totalRequests
	def getQuotas(self,userID,apiName):
		quotas = {}

		now = datetime.datetime.today()
		endMonth = now.month
		endYear = now.year
		if endMonth == 12:
			endMonth = 1
			endYear = endYear + 1
		startTime = datetime.datetime.timestamp(datetime.datetime(year = now.year, month = now.month, day = 1))
		endTime = datetime.datetime.timestamp(datetime.datetime(year = endYear, month = endMonth, day = 1))
		quotas['userMonth'] = self.checkUserRequests(userID,apiName,startTime,endTime)
		quotas['userTotal'] = config.apiConfig[apiName]['user-monthly-limit']

		startTime = datetime.datetime.timestamp(datetime.datetime(year = now.year, month = now.month, day = now.day))
		endTime = datetime.datetime.timestamp(datetime.datetime(year = now.year, month = now.month, day = now.day + 1))
		quotas['apiToday'] = self.checkUserRequests(apiName,apiName,startTime,endTime)
		quotas['apiTotal'] = config.apiConfig[apiName]['api-daily-limit']

		availableUserRequests = quotas['userTotal'] - quotas['userMonth']
		availableAPIRequests = quotas['apiTotal'] - quotas['apiToday']

		if availableAPIRequests > 0 and availableUserRequests > 0:
			if availableAPIRequests > availableUserRequests:
				quotas['maxAvailable'] = availableUserRequests
			else:
				quotas['maxAvailable'] = availableAPIRequests
		else:
			quotas['maxAvailable'] = 0

		return quotas
