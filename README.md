# Google App Engine for Self-Serve API Access and Data Processing

This Google App Engine app allows multiple users to access third-party APIs to request data, process content, and export results to Google Drive, Google Sheets, and BigQuery while enforcing API limits and quotas.

This app uses Flask to render front-end templates where users can make requests and view report data, accept request for new reports, and respond to Google Cloud Task workers to actually execute the API request and data processing for each requested report.

Users are authenticated with their Google Account with Google Sign-In. Each user is allowed to make a specified number of daily and monthly requests to an API. This helps conserve credits for any billed APIs or those with specific request limits.

Users can view the API data and any additional data that was processed by the back end when it has been completed. Data is also exported to Google Drive, Google Sheets, and BigQuery and is shared with the user that made the initial request.

## Configuring

You'll need to create a service worker for your Google App Engine app and add the appropriate credentials to the `credentials.json` file. You'll also need to add any relevant API keys and the API daily and monthly limits to the `config.py` file.

## Report Data

Each report exports a simple table of report data that can be displayed in the app itself or processed and exported in Google Sheets, BigQuery, or any other third-party tools that can connect to those.

### Front End

The front end included in this app consists of simple Jinja templates with an AJAX request that updates progress.

### Google Suite

You'll need to create a service worker as well as an actual 'recipient' account in order to access Google Drive and Google Sheet files. The service worker will need to share the file with the recipient account and then transfer ownership to that account. The user that requested the report will be sent a Google Drive sharing request.

### Included APIs and Data Processors

- Ngrammer - This breaks long-form text into ngrams and counts their occurances
- SEMrush Domain Authority - Request historical domain authority data from SEMrush (this can be expanded for other SEMrush endpoints)
- Sentiment Analysis - Examine positive and negative sentiment within long-form content via the Google Cloud Natural Language API
- Schema Search - Search with a custom Google Search Engine for pages that contain schema and structured data

Each of these reports utilizes slightly different configurations to access data, process it, and share it with the user so they should be useful templates for many common REST and GraphQL endpoints or other data that's accessible through Python.

## App Configuration, User Flow, and Integration

This app utilizes several Google services to host the app, track report request, process actual API requests, store report data, and show the data to the user.

### App Configuration and Google Services

![App and Data Flow](https://github.com/myawesomebike/API-Self-Service-App/raw/master/static/app-config.jpg)

### Example of the front end interface

![Tool Example](https://github.com/myawesomebike/API-Self-Service-App/raw/master/static/tool-example.png)