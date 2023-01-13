# These functions manage individual user requests or "reports".
#
# User requests are created and added to a Datastore and a new Cloud Task is created.
#
# Each request is stored in a Datastore bucket and can be recalled by
# user ID and report ID.
#
# Report data is stored in a Google Cloud Store JSON blob and are recalled by a report ID.
#
# Reports can be saved incrementally as they load or process more data.
#
# Cloud Task requests are added for any reports or backend processes.
# Tasks can be scheduled for the next available worker or scheduled for a later time.

import gfunctions
import config
import datetime
import time
import json
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from google.cloud import datastore
from google.cloud import storage


class report:
	def __init__(self, reportID = -1):
		self.reportID = reportID
		self.userID = -1
		self.taskType = ''
		self.status = -1
		self.statusMsg = ''
		self.progress = 0
		self.taskRequest = {}
		self.reportData = {}
		self.G = gfunctions.gInterface()

		if reportID != -1:
			self.loadReport()

	def saveReport(self):
		if self.reportID != -1:
			reportName = 'report_' + str(self.reportID)
			blobClient = storage.Client()
			blobBucket = blobClient.get_bucket('request_blobs')
			blob = blobBucket.blob(reportName)
			blob.upload_from_string(json.dumps(self.taskRequest))

			sessionRecord = datastore.Entity(key = self.G.datastore.key(reportName))
			sessionRecord.update({
				'userID':self.userID,
				'taskType':self.taskType,
				'status':self.status,
				'statusMsg':self.statusMsg,
				'progress':self.progress,
				'data':self.reportData,
				'timestamp':time.time()
				})
			self.G.datastore.put(sessionRecord)

	def loadReport(self):
		if self.reportID != -1:
			reportName = 'report_' + str(self.reportID)
			blobClient = storage.Client()
			blobBucket = blobClient.get_bucket('request_blobs')
			blob = blobBucket.blob(reportName)
			blobJson = blob.download_as_string()

			reportIndex = self.G.datastore.query(kind = reportName)
			reportIndex.order = ['-timestamp']
			reportData = list(reportIndex.fetch())
			reportData = reportData[0]
			self.userID = reportData['userID']
			self.taskType = reportData['taskType']
			self.status = reportData['status']
			self.statusMsg = reportData['statusMsg']
			self.progress = reportData['progress']
			self.reportData = reportData['data']
			self.taskRequest = json.loads(blobJson)

	def newReport(self,reportType = '',userID = -1, request = {}):
		if reportType != '':
			self.taskType = reportType
			self.userID = userID
			self.taskRequest = request

			reportIndex = self.G.datastore.query(kind = 'all_reports')
			reportData = reportIndex.fetch()
			self.reportID = len(list(reportData))
			self.saveReport()

			allReports = datastore.Entity(key = self.G.datastore.key('all_reports'))
			allReports.update({'reportID':self.reportID,'userID':self.userID,'type':self.taskType,'timestamp':time.time()})
			self.G.datastore.put(allReports)

	def addToQueue(self):
	    tasks = tasks_v2.CloudTasksClient()
	    in_seconds = None

	    parent = tasks.queue_path(config.apiConfig['tasks']['project-id'],config.apiConfig['tasks']['project-location'],self.taskType)

	    task = {
	        'app_engine_http_request': {
	            'http_method': 'POST',
	            'relative_uri': '/process_' + self.taskType
	        }
	    }
	    if self.reportID != -1:
	        requestBody = str(self.reportID).encode()
	        task['app_engine_http_request']['body'] = requestBody

	    if in_seconds is not None:
	        d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)

	        timestamp = timestamp_pb2.Timestamp()
	        timestamp.FromDatetime(d)

	        task['schedule_time'] = timestamp

	    response = tasks.create_task(parent, task)
	    self.status = 0
	    self.saveReport()