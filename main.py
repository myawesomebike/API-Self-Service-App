#!/usr/bin/env python3

# This Google App Engine app handles user requests for third-party APIs.
#
# Users are authenticated via Google Suite - this app only tracks their user IDs
#
# The app can be can be configured with daily and monthly API request limits to ensure
# that multiple users can access a third-party API without exceeding predefined limits.
#
# The app routes below handle front end rendering from templates, the API endpoints for tool
# requests, and the Cloud Tasks request URls that actually call third-party APIs and process data.
#
# The front end is updated every 2500ms while the Cloud Tasks are waiting and running.
#
# Report data is shown to users when ready as well as exported to Google Drive, Google Sheets, and BigQuery.
#
# Users can view reports at a later time or process data further from exported CSVs, Google Sheets, or BigQuery.

import config
import datetime
import time
import json
import math
import ngrammer
import semrushapi
import sentimentapi
import schemasearch
import gfunctions
import reports
import user
from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from urllib.parse import urlparse
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

app = Flask(__name__)

# All - Report Status
@app.route('/report_status', methods = ['POST'])
def report_status():
    reportID = request.form['id']
    r = reports.report(int(reportID))
    redirectURL = ''
    if r.status == 2:
        redirectURL = '/' + r.taskType + '?id=' + str(r.reportID)
    returnData = {}
    returnData['id'] = r.reportID
    returnData['status'] = r.status
    returnData['msg'] = r.statusMsg
    returnData['progress'] = r.progress
    returnData['redirect'] = redirectURL
    return jsonify(returnData)

# Ngrams - Cloud Task Handler
@app.route('/process_ngrams', methods = ['POST'])
def process_ngrams():
    returnData = {}
    returnData['status'] = -1
    if request.data != '':
        r = reports.report(int(request.data))
        r.status = 1
        r.statusMsg = 'Starting ngrammer'
        r.saveReport()

        n = ngrammer.ngrammer(r.taskRequest['content'])

        while n.processNext():
            if n.apiProgress != r.progress:
                r.progress = n.apiProgress
                r.statusMsg = 'Ngramming ' + n.apiStatus
                r.saveReport()

        r.progress = 99
        r.statusMsg = 'Saving data'
        r.saveReport()

        ngrams = []
        for index,thisNgram in n.ngrams.items():
            ngrams.append([n.ngrams[index].ngram,n.ngrams[index].instances])

        u = user.user(r.userID)
        tableName = 'ngrams' + str(r.reportID)
        u.addTable(tableName)
        u.addData(tableName,ngrams)

        r.reportData['bq'] = "https://console.cloud.google.com/bigquery?project={0}&pli=1&p={0}&d={1}&t={2}&page=table".format(config.apiConfig['tasks']['project-id'],r.userID,tableName)
        
        sheetName = 'Self Serve - ngrams - ' + datetime.datetime.today().strftime('%Y-%m-%d')
        g = user.gInterface()
        g.startDrive()
        sheetID = g.createSheet(sheetName)

        dataRange = "Sheet1!A:B"
        data = [['ngram','Instances']]
        data.extend(ngrams)
        g.addDataToSheet(sheetID,dataRange,data)

        g.transferToUser(sheetID,'***_ACCOUNT_EMAIL_***@gmail.com')
        g.shareFileWithUser(sheetID,u.name,"Here's your ngrams.")

        r.reportData['gdrive'] = 'https://docs.google.com/spreadsheets/d/' + sheetID
        
        r.status = 2
        r.progress = -1
        r.statusMsg = 'Done processing ngrams'
        r.saveReport()

        returnData['status'] = 2

    return jsonify(returnData)

# Ngrams - New Request
@app.route('/get_ngrams', methods = ['POST'])
def get_ngrams():
    requestData = request.form['content']
    returnData = {}
    returnData['id'] = -1
    if requestData != '':
        u = user.user()
        r = reports.report()
        r.statusMsg = 'Waiting to process ngrams'
        r.newReport('ngrams',u.ID,{'content':requestData})
        r.addToQueue()
        returnData['id'] = r.reportID
        returnData['status'] = r.status
        returnData['msg'] = r.statusMsg
        returnData['progress'] = -1
    return jsonify(returnData)

# Ngrams - Front End
@app.route('/ngrams')
def ngrams():
    reportID = request.args.get('id')
    ngrams = []
    download = {}
    u = user.user()
    if reportID != None:
        r = reports.report(reportID)
        ngrams = u.getData('ngrams' + r.reportID)
        download = r.reportData
    return render_template('ngrams.html', user = u.name, download = download, ngrams = ngrams)

# Domain Authority - Cloud Task Handler
@app.route('/process_domainauthority', methods = ['POST'])
def process_domainauthority():
    returnData = {}
    returnData['status'] = -1
    reportCost = 40

    r = reports.report(int(request.data))
    u = user.user(r.userID)
    g = gfunctions.gInterface()
    quotas = g.getQuotas(u.ID,'semrush')

    semInfo = semrushapi.info()
    availableCredits = semInfo.checkAPILimits()

    parsedDomains = []
    domainData = []
    gsheetData = []
    domainReports = math.floor(quotas['maxAvailable'] / reportCost)

    if (availableCredits / reportCost) < domainReports:
        domainReports = math.floor(availableCredits / reportCost)
    if domainReports > 0:
        r.status = 1
        r.statusMsg = 'Starting Domain Authority'
        r.saveReport()

        rawDomains = r.taskRequest['content']
        domains = rawDomains.split('\n')
        sem = semrushapi.domains(domains)
        if len(sem.apiRequests) > domainReports:
            sem.apiRequests = sem.apiRequests[:domainReports]

        while sem.processNext():
            if sem.apiProgress != r.progress:
                r.progress = sem.apiProgress
                r.statusMsg = 'Getting domain authority for ' + sem.apiStatus
                r.saveReport()

        r.progress = 99
        r.statusMsg = 'Saving data'
        r.saveReport()

        for URL,thisDomain in sem.reportData.items():
            scores = {'score':sem.reportData[URL][5],'trust':sem.reportData[URL][6]}
            domainData.append([URL,json.dumps(scores)])
            gsheetData.append([URL,sem.reportData[URL][5],sem.reportData[URL][6]])

        usedCredits = availableCredits - semInfo.checkAPILimits()
        g.addUserRequest(u.ID,'semrush',usedCredits)
        g.addUserRequest('semrush','semrush',usedCredits)

        tableName = 'domainauthority' + str(r.reportID)
        u.addTable(tableName)
        u.addData(tableName,domainData)
        r.reportData['bq'] = "https://console.cloud.google.com/bigquery?project={0}&pli=1&p={0}&d={1}&t={2}&page=table".format(config.apiConfig['tasks']['project-id'],r.userID,tableName)
        
        sheetName = 'Self Serve - Domain Authority - ' + datetime.datetime.today().strftime('%Y-%m-%d')
        g = user.gInterface()
        g.startDrive()
        sheetID = g.createSheet(sheetName)

        dataRange = "Sheet1!A:C"
        data = [['Domain','Score','Trust Score']]
        data.extend(gsheetData)
        g.addDataToSheet(sheetID,dataRange,data)

        g.transferToUser(sheetID,'***_ACCOUNT_EMAIL_***@gmail.com')
        g.shareFileWithUser(sheetID,u.name,"Here's your domain authority data.")
        r.reportData['gdrive'] = 'https://docs.google.com/spreadsheets/d/' + sheetID
        
        r.status = 2
        r.progress = -1
        r.statusMsg = 'Done getting domain authority'
        r.saveReport()
        returnData['status'] = 2
    else:
        r.status = 3
        r.progress = 0
        r.statusMsg = 'Out of daily credits'
        r.saveReport()
        returnData['status'] = 3

    return jsonify(returnData)

# Domain Authority - New Request
@app.route('/get_domain_authority', methods = ['POST'])
def get_domain_authority():
    requestData = request.form['content']
    returnData = {}
    returnData['id'] = -1
    if requestData != '':
        u = user.user()
        r = reports.report()
        r.statusMsg = 'Waiting to get domain authority'
        r.newReport('domainauthority',u.ID,{'content':requestData})
        r.addToQueue()
        returnData['id'] = r.reportID
        returnData['status'] = r.status
        returnData['msg'] = r.statusMsg
        returnData['progress'] = -1
    return jsonify(returnData)

# Domain Authority - Front End
@app.route('/domainauthority')
def domainAuthority():
    reportID = request.args.get('id')
    domainData = []
    download = {}
    u = user.user()
    if reportID != None:
        r = reports.report(reportID)
        download = r.reportData
        bqData = u.getData('domainauthority' + r.reportID)
        for thisDomain in bqData:
            domainData.append([thisDomain[0],json.loads(thisDomain[1])])
    g = user.gInterface()
    quotas = g.getQuotas(u.ID,'semrush')

    return render_template('domainauthority.html',user = u.name,download = download,domainData = domainData,quotas = quotas)

# Sentiment Analysis - Cloud Task Handler
@app.route('/process_sentiment', methods = ['POST'])
def process_sentiment():
    returnData = {}
    returnData['status'] = -1

    r = reports.report(int(request.data))
    u = user.user(r.userID)
    g = gfunctions.gInterface()
    quotas = g.getQuotas(u.ID,'semrush')

    sentimentData = []
    gsheetData = []
    if quotas['maxAvailable'] > 0:
        r.status = 1
        r.statusMsg = 'Starting Sentiment Analysis'
        r.saveReport()

        rawText = r.taskRequest['content']
        strings = rawText.split('\n')
        if strings != []:
            sentiment = sentimentapi.sentiment(strings)

        stringID = 0
        while sentiment.processNext():
            if sentiment.apiProgress != r.progress:
                r.progress = sentiment.apiProgress
                r.statusMsg = 'Getting sentiment...'
                r.saveReport()
            g.addUserRequest(u.ID,'sentiment',1)
            g.addUserRequest('sentiment','sentiment',1)

        r.progress = 99
        r.statusMsg = 'Saving data'
        r.saveReport()

        stringID = 0
        for string,thisString in sentiment.reportData.items():
            data = {'string':string,'score':sentiment.reportData[string][0],'magnitude':sentiment.reportData[string][1]}
            sentimentData.append([stringID,json.dumps(data)])
            stringID = stringID + 1
            gsheetData.append([string,sentiment.reportData[string][0],sentiment.reportData[string][1]])

        tableName = 'sentiment' + str(r.reportID)
        u.addTable(tableName)
        u.addData(tableName,sentimentData)
        returnData['status'] = 2

        r.reportData['bq'] = "https://console.cloud.google.com/bigquery?project={0}&pli=1&p={0}&d={1}&t={2}&page=table".format(config.apiConfig['tasks']['project-id'],r.userID,tableName)
        
        sheetName = 'Self Serve - Sentiment - ' + datetime.datetime.today().strftime('%Y-%m-%d')
        g = user.gInterface()
        g.startDrive()
        sheetID = g.createSheet(sheetName)

        dataRange = "Sheet1!A:C"
        data = [['Text','Score','Magnitude']]
        data.extend(gsheetData)
        g.addDataToSheet(sheetID,dataRange,data)

        g.transferToUser(sheetID,'***_ACCOUNT_EMAIL_***@gmail.com')
        g.shareFileWithUser(sheetID,u.name,"Here's your sentiment data.")

        r.reportData['gdrive'] = 'https://docs.google.com/spreadsheets/d/' + sheetID
        
        r.status = 2
        r.progress = -1
        r.statusMsg = 'Done getting sentiment'
        r.saveReport()
        returnData['status'] = 2
    else:
        r.status = 3
        r.progress = 0
        r.statusMsg = 'Out of daily credits'
        r.saveReport()
        returnData['status'] = 3
    
    return jsonify(returnData)

# Sentiment Analysis - New Request
@app.route('/get_sentiment', methods = ['POST'])
def get_sentiment():
    requestData = request.form['content']
    returnData = {}
    returnData['id'] = -1
    if requestData != '':
        u = user.user()
        r = reports.report()
        r.statusMsg = 'Waiting to get sentiment'
        r.newReport('sentiment',u.ID,{'content':requestData})
        r.addToQueue()
        returnData['id'] = r.reportID
        returnData['status'] = r.status
        returnData['msg'] = r.statusMsg
        returnData['progress'] = -1
    return jsonify(returnData)

# Sentiment Analysis - Front End
@app.route('/sentiment')
def sentiment():
    reportID = request.args.get('id')
    sentimentData = []
    download = {}
    u = user.user()
    if reportID != None:
        r = reports.report(reportID)
        download = r.reportData
        bqData = u.getData('sentiment' + r.reportID)
        for thisString in bqData:
            sentimentData.append([json.loads(thisString[1])])
    g = user.gInterface()
    quotas = g.getQuotas(u.ID,'sentiment')

    return render_template('sentimentanalysis.html',user = u.name,download = download,sentimentData = sentimentData,quotas = quotas)

@app.route('/search-schema', methods = ['POST'])
def searchSchema():
    apiName = 'schemasearch'
    u = user.user()
    g = gfunctions.gInterface()
    quotas = g.getQuotas(u.ID,apiName)

    schemaData = []
    if quotas['maxAvailable'] > 0:
        query = request.form['query']
        if query != []:
            schemaData = []
            schema = schemasearch.schemaSearch()
            schema.findSchema(query)

            for thisRow in schema.reportData:
                schemaData.append([thisRow['url'],thisRow['title'],thisRow['description'],', '.join(thisRow['schemas'])])

            g.addUserRequest(u.ID,apiName,schema.pages)
            g.addUserRequest(apiName,apiName,schema.pages)
    
    return render_template('schemasearch.html',user = u.name,schemaData = schemaData,quotas = quotas)

@app.route('/schemasearch')
def schemaSearch():
    u = user.user()
    g = gfunctions.gInterface()
    quotas = g.getQuotas(u.ID,'schemasearch')

    return render_template('schemasearch.html',user = u.name,schemaData = [],quotas = quotas)

@app.route('/')
def root():
    u = user.user()
        
    return render_template('index.html',user = u.name, ngrams = ngrams)

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
    #app.run(host='127.0.0.1', port=8080, debug=True, threaded = True)
# [START gae_python37_render_template]
