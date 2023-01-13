# Basic ngram extractor that breaks long-form content apart by punctuation and commonly-used english stop words.

import re

class document():
	def __init__(self,contentName,content,categories = []):
		self.name = contentName
		self.content = content
		self.categories = categories
		self.terms = {}
		self.ngrams = {}
		self.categoryIDs = []
		self.totalTerms = 0
class ngram():
	ngram = ''
	contentIDs = []
	instances = 0
	def __init__(self,ngram,contentID):
		self.ngram = ngram
		self.contentIDs = [contentID]
		self.instances = 1
	def addInstance(self,contentID):
		self.instances = self.instances + 1
		if contentID not in self.contentIDs:
			self.contentIDs.append(contentID)
class ngrammer():
	stopwords = ["a","about","above","after","again","against","all","am","an","and","any","are","as","at","be","because","been","before","being","below","between", "both", "but", "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has", "have", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "it", "it's", "its", "itself", "let's", "me", "more", "most", "my", "myself", "nor", "of", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "she'd", "she'll", "she's", "should", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "we'd", "we'll", "we're", "we've", "were", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "would", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves" ]
	wordboundaries = [' ','.',',','!','?','(',')','[',']','{','}','-','_','@','#','$','%','^','&','*','|','\\',"/","<",">","\n","\r\n"]
	def __init__(self,requestData):
		self.apiProgress = 0
		self.apiStatus = ''
		self.apiRequests = []
		self.apiNextRequest = -1
		self.documents = {}
		self.ngrams = {}

		self.apiRequests = requestData.split('\n')
	def processNext(self):
		nextID = self.apiNextRequest + 1
		totalRequests = len(self.apiRequests)
		if nextID < totalRequests:
			rawContent = self.apiRequests[nextID].strip()
			if rawContent != '':
				docID = len(self.documents)
				self.documents[docID] = document(rawContent[:75] + (rawContent[75:] and '...'),rawContent)
				self.apiProgress = (nextID / totalRequests) * 100
				self.apiStatus = self.documents[docID].name
				docNgrams = self.getNgrams(self.documents[docID].content,4)
				for thisGram in docNgrams:
					self.addNgram(thisGram,docID)
			self.apiNextRequest = nextID
			return True;
		else:
			return False

	def getNgrams(self,content,maxSize = 5):
		
		#splitWords = re.split('\.|\!|\?|\(|\)|\[|\]|\{|\}|\-|\_ \'|\' | |\,|\"|\@|\#|\$|\%|\^|\&|\*|\;|\<|\>|\n|\r\n',content)
		regex = "+|\\".join(self.wordboundaries)
		splitWords = re.split(regex,content)
		
		ngrams = []
		for thisGram in splitWords:
			if thisGram != '':
				ngrams.append(thisGram.lower())
		wordCount = len(ngrams)	
		output = []	
		if(wordCount > 1):
			for strLen in range(1,maxSize):
				for start in range(wordCount - strLen + 1):
					if(ngrams[start] not in self.stopwords and ngrams[(start + strLen - 1)] not in self.stopwords):
						thisGram = " ".join(ngrams[start:(start + strLen)]).strip()
						if(thisGram != '' and thisGram not in self.stopwords):
							output.append(thisGram)
		return output
	def addNgram(self,newNgram,contentID):
		ngramIndex = -1
		for index,thisNgram in self.ngrams.items():
			if(thisNgram.ngram == newNgram):
				ngramIndex = index
				break
		if(ngramIndex == -1):
			self.ngrams[len(self.ngrams.items())] = ngram(newNgram,contentID)
		else:
			self.ngrams[ngramIndex].addInstance(contentID)