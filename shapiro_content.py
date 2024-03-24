from shapiro_util import get_logger
import requests
import json
import base64
from abc import ABC
import os
import logging
from typing import List
from datetime import datetime


log = get_logger("SHAPIRO_CONTENT")

class ContentAdaptor(ABC):
    """Abstract base class for content adaptors. A content adaptor retrieves model data from a 
    storage medium (e.g. file system, webdav repo, remote version control repo, ...) based on the
    notion of a path tothe content (e.g. directory hierarchy)."""

    def get_content(self, filepath:str) -> str:
        """Retrieve the string content of the file at the specified path."""
        pass
    
    def is_file(self, filepath:str) -> bool:
        """Returns true if the file at the specified path exists, false otherwise."""
        pass
    
    def get_changed_files(self, dirpath:str, since=None) -> List[str]:
        """Returns the list of filepaths that have changed in between the current time and the time specified in the since.
        If since is none, then returns all files."""
        pass

class GitHubException(Exception):
    """This exception is raised by the adaptor if anything in the interaction with the GutHub API goes wrong."""
    
    def __init__(self, msg):
        super().__init__(msg)

class GitHubAdaptor(ContentAdaptor):
    """Allows Shapiro to retrieve schemas from a GitHub repo directly."""
    
    FILE_RETRIEVE_URL = 'https://api.github.com/repos/{user}/{repo}/contents/{path}?ref={branch}'
    BRANCH_RETRIEVE_URL = 'https://api.github.com/repos/{user}/{repo}'
    TREE_RETRIEVE_URL = 'https://api.github.com/repos/{user}/{repo}/contents/{path}?ref={branch}'
    COMMITS_URL = 'https://api.github.com/repos/{user}/{repo}/commits?sha={branch_hash}&path={path}'
    BRANCH_HASH_URL = 'https://api.github.com/repos/{user}/{repo}/git/refs'
     
    BASE64 = 'base64'
    MSG = 'message'
    DEF_BRANCH = 'default_branch'
    
    def __init__(self, user:str, repo:str, token:str, branch:str=None):
        self.user = user
        self.repo = repo
        self.token = token
        self.branch = branch
        if self.branch is None or self.branch == '':
            self.branch = self.get_default_branch()
        self.branch_hash = self.get_branch_hash()
        log.info("Initialized GitHubAdaptor (user '{}', repo '{}', branch '{}', branch hash '{}', token '{}')".format(self.user, self.repo, self.branch, self.branch_hash, self.token))
        
    def get_auth(self):
        auth = None
        if self.token is not None:
            auth = {"Authorization": "Bearer "+self.token}
        return auth        
        
    def get_default_branch(self):
        url = self.BRANCH_RETRIEVE_URL.format(user=self.user, repo=self.repo)
        log.info("GitHubAdaptor: Retrieving default branch for repo '{}'".format(self.repo))
        response = requests.get(url, headers = self.get_auth())
        data = response.json()
        if response.status_code != 200:
            # GitHub responded with an error, so seomthing isn't right with the request
            log.error("Error retrieving default branch from GitHub for repo '{}': {}. Rate limits are {}.".format(self.repo, data[self.MSG], response.headers['x-ratelimit-limit']))
            raise GitHubException("Error retrieving default branch from GitHub:" + json.dumps(data, indent=5))
        if self.DEF_BRANCH in data.keys():
            log.info("GitHubAdaptor: default branch '{}' found.".format(data[self.DEF_BRANCH]))
            return data[self.DEF_BRANCH]
        log.info("GitHubAdaptor: no default branch found")
        return None
    
    def get_branch_hash(self):
        url = self.BRANCH_HASH_URL.format(user=self.user, repo=self.repo)
        response = requests.get(url, headers= self.get_auth())
        data = response.json()
        if response.status_code != 200:
            # GitHub responded with an error, so seomthing isn't right with the request
            log.error("Error retrieving branch hash from GitHub for repo '{}': {}".format(self.repo, json.dumps(data, indent=5)))
            raise GitHubException("Error retrieving branch hash from GitHub:" + json.dumps(data, indent=5))
        for d in data:
            if d['ref'] == 'refs/heads/'+self.branch:
                return d['object']['sha']
        log.error("Could not find branch hash from GitHub for repo '{}': {}".format(self.repo, json.dumps(data, indent=5)))
        raise GitHubException("Could not find branch hash for branch '{}'from GitHub: {}".format(self.branch, json.dumps(data, indent=5)))
            
    def trim(self, filepath:str) -> str:
        if filepath.startswith('./'):
            filepath = filepath[2:len(filepath)]
        if filepath.endswith('/'):
            filepath = filepath[0:len(filepath)-1]
        return filepath
        
    def get_content(self, filepath:str) -> str:
        filepath = self.trim(filepath)
        url = self.FILE_RETRIEVE_URL.format(user=self.user, repo=self.repo, path=filepath, branch=self.branch)
        response = requests.get(url, headers= self.get_auth())
        log.info("Loading '{}' from GitHub.".format(filepath))
        data = response.json()
        if response.status_code != 200:
            # GitHub responded with an error, so seomthing isn't right (e.g. file not found, branch not found, etc.)
            log.error("Error retrieving '{}' from GitHub: {}".format(filepath, json.dumps(data, indent=5)))
            raise GitHubException("Error retrieving '{}' from GitHub: {}".format(filepath, json.dumps(data, indent=5)))
        if data['encoding'] == self.BASE64:
            log.info('Decoding content for "{}" from GitHub'.format(filepath))
            return base64.b64decode(data['content'])
        else:
            log.error("Error decoding content from Github (unknown endocing): {}".format(data['encoding']))
            raise GitHubException('Received data from GitHub in unknown encoding "{}" - expected base64.'.format(data['encoding']))

    def is_file(self, filepath:str) -> bool:
        """Return true if the filepath points to a file."""
        filepath = self.trim(filepath)
        log.info("Checking if '{}' is file on GitHub.".format(filepath))
        try:
            self.get_content(filepath)
            return True
        except:
            return False
        
    def has_changed(self, filepath:str, since=None) -> bool:
        filepath = self.trim(filepath)
        if since is None:
            return True
        else:
            url = self.COMMITS_URL.format(user=self.user, repo=self.repo, branch_hash=self.branch_hash, path=filepath)
        response = requests.get(url, headers = self.get_auth())
        data = response.json()
        if response.status_code != 200:
            # GitHub responded with an error, so seomthing isn't right (e.g. file not found, branch not found, etc.)
            log.error("Error determining changed files for '{}' from GitHub: {}".format(filepath, json.dumps(data, indent=5)))
            raise GitHubException("Error determining changed files for '{}' from GitHub: {}".format(filepath, json.dumps(data, indent=5)))
        if len(data) < 1:
            raise GitHubException('Could not receive commit information to determine whether "{}" has changed.'.format(filepath))
        timestamp = data[0]['commit']['author']['date'] # date of the most recent commit
        return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ') > since 
                 
    def get_changed_files(self, dirpath:str, since=None) -> List[str]:
        """Returns the list of filepaths that have changed in between the current time and the time specified in since."""
        dirpath = self.trim(dirpath)
        result = []
        url = self.TREE_RETRIEVE_URL.format(user=self.user, repo=self.repo, path=dirpath, branch=self.branch)
        response = requests.get(url, headers=self.get_auth())
        data = response.json()
        if response.status_code != 200:
            # GitHub responded with an error message, so seomthing isn't right (e.g. file not found, branch not found, etc.)
            log.error("Error getting changed files for '{}' from GitHub: {}".format(dirpath, json.dumps(data, indent=5)))
            raise GitHubException("Error getting changed files for '{}' from GitHub: {}".format(dirpath, json.dumps(data, indent=5)))
        for d in data:
            if d['type'] == 'file' and self.has_changed(dirpath+'/'+d['name'], since) is True:
                result.append(dirpath+'/'+d['name'])
            if d['type'] == 'dir':
                result += self.get_changed_files(dirpath+'/'+d['name'], since)
        return result

                
class FileSystemAdaptor(ContentAdaptor):
    
    def __init__(self):
        log.info("Initializing FileSystemAdaptor")
    
    def get_content(self, filepath:str) -> str:
        log.info("FileSystemAdaptor retrieving file '{}'".format(filepath))
        f = open(filepath, "r")
        content = f.read()
        f.close()
        return content
        
    def is_file(self, filepath:str) -> str:
        log.info("Checkging if '{}' is file".format(filepath))
        return os.path.isfile(filepath)
    
    def get_changed_files(self, dirpath:str, since=None) -> List[str]:
        """Returns the list of filepaths that have changed in between the current time and the time specified in since.
        If since is none, then returns all files."""
        result = []        
        for dir in os.walk(dirpath):
            path = dir[0].replace("\\", "/").replace(os.path.sep, "/")
            for filename in dir[2]:
                if path.endswith("/"):
                    full_name = path + filename
                else:
                    full_name = path + "/" + filename
                mod_time = datetime.fromtimestamp(os.stat(full_name).st_mtime)
                if since is None or since < mod_time:
                    result.append(full_name)
        return result
