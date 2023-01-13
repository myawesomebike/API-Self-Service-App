// [START gae_python37_log]
'use strict';

window.addEventListener('load', function () {

  console.log("JS Loaded");

});
// [END gae_python37_log]

var t;
var reportID = -1

// shortcut to get front end elements
function ge(obj) {
	if(document.getElementById(obj)) { return document.getElementById(obj); }
}
// Basic AJAX request handler for report updates
function reportStatus() {
	var xmlhttp = new XMLHttpRequest();
	xmlhttp.onreadystatechange = function() {
		server(xmlhttp.responseText);
	}
	var src = encodeURI('/report_status');
	xmlhttp.open("POST",src,true);
	xmlhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
	xmlhttp.send('id=' + reportID);

}
// API request handler for new tool/API request
function toolRequest(endpoint,dataSource,destination) {
	var xmlhttp = new XMLHttpRequest();
	xmlhttp.onreadystatechange = function() {
		server(xmlhttp.responseText);
	}
	var requestData = document.getElementById(dataSource).value;
	var src = encodeURI('/' + endpoint);
	xmlhttp.open("POST",src,true);
	xmlhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
	xmlhttp.send('content=' + requestData);
}
// Respond handler that updates request progress, final report data, and any redirects to a new URL
function server(response) {
	var data = '';
	try {
		if(response != '') {
			data = JSON.parse(response);
		}
	}
	catch (e) {
	}

	if(data != '') {
		if('msg' in data) {
			ge('statusblock').style.display = 'block';
			ge('reportstatus').innerHTML = data['msg'];
			ge('reportprogress').value = data['progress'];
			if(data['progress'] == -1) { ge('reportprogress').removeAttribute("value"); }
		}
		else {
			ge('statusblock').style.display = 'none';
		}
		if('status' in data) {
			if(data['status'] == 0 && reportID == -1) {
				reportID = data['id']
				t = setInterval(reportStatus,2500);
			}
			if(data['status'] != 0 && data['status'] != 1) {
				clearInterval(t);
			}
		}
		if('redirect' in data) {
			if(data['redirect'] != '') {
				window.location.replace(data['redirect']);
			}
		}
	}
}