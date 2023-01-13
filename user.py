# These functions handle user authentication, BigQuery initilization for databases,
# Google Drive integration, Google Sheets creation, and sharing files to the Google Suite
# user making the request.
#
# Google Suite users are authenticated with Google Sign-In which then adds 'X-Goog-Authenticated-User'
# headers. This app uses provided user ID to track requests and user email for file sharing/access.

import config
import datetime
import time
from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import datastore
from google.cloud import bigquery


def getUserData():
    userID = request.headers.get('X-Goog-Authenticated-User-ID')
    user = request.headers.get('X-Goog-Authenticated-User-Email')
    if user != None:
        user = user.split(':')[1]
    else:
        userID = -1
        user = ''

    return [userID,user]

class user:
	def __init__(self,fromID = -1):
		self.ID = request.headers.get('X-Goog-Authenticated-User-ID')
		self.name = request.headers.get('X-Goog-Authenticated-User-Email')
		if self.name != None:
			self.name = str(self.name.split(':')[1])
			self.ID = str(self.ID.split(':')[1])
			self.client = bigquery.Client()
		else:
			if fromID != -1:
				self.ID = fromID
			else:
				self.ID = 'None'
			self.name = ''
	def setupUserDataset(self):
		bq = bigquery.Client()
		from google.cloud.exceptions import NotFound
		try:
			bq.get_dataset(self.ID)
		except NotFound:
			dataset_ref = bq.dataset(self.ID)
			dataset = bigquery.Dataset(dataset_ref)
			dataset.location = "US"
			dataset = bq.create_dataset(dataset)

			access_entries = dataset.access_entries
			access_entries.append(bigquery.AccessEnty('READER', 'groupByEmai',self.name))
			dataset.access_entries = access_entries
			dataset = bq.update_dataset(dataset,['access_entries'])
	def addTable(self,table_name):
		if self.ID != -1:
			self.setupUserDataset()
			bq = bigquery.Client()
			dataset_ref = bq.dataset(self.ID)
			schema = [
				bigquery.SchemaField('id', 'STRING', mode = 'REQUIRED'),
				bigquery.SchemaField('data', 'STRING', mode = 'REQUIRED')
			]
			table_ref = dataset_ref.table(table_name)
			table = bigquery.Table(table_ref, schema = schema)
			table = bq.create_table(table)
			table.table_id == table_name
	def addData(self,table_id,data):
		if self.ID != -1 and data != []:
			bq = bigquery.Client()
			dataset_ref = bq.dataset(self.ID)
			table_ref = dataset_ref.table(table_id)
			table = bq.get_table(table_ref)

			errors = bq.insert_rows(table,data)
	def getData(self,table_id):
		bq = bigquery.Client()
		dataset_ref = bq.dataset(self.ID)
		table_ref = dataset_ref.table(table_id)
		table = bq.get_table(table_ref)

		sql = "SELECT * FROM `{0}.{1}.{2}`".format(config.apiConfig['tasks']['project-id'],self.ID,table_id)
		request = bq.query(sql)
		data = request.result()
		return data

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