# github_client.py
"""
Simplified GitHub client for repository operations
"""
import os
import requests
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ai-code-mate-demo"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        
        self.current_owner = os.getenv("GITHUB_OWNER")
        self.current_repo = os.getenv("GITHUB_REPO")
    
    def switch_repo(self, owner: str, repo: str):
        """Switch to a different repository"""
        self.current_owner = owner
        self.current_repo = repo
        return f"Switched to repository: {owner}/{repo}"
    
    def get_current_repo(self) -> str:
        """Get current repository identifier"""
        return f"{self.current_owner}/{self.current_repo}"
    
    def search_code(self, query: str, path: str = "") -> Dict:
        """Search for code in the current repository"""
        # First try to find files by name using the repository contents API
        filename_results = self._search_files_by_name(query, path)
        
        # Then try GitHub's code search API for content
        content_results = self._search_code_content(query, path)
        
        # Combine results
        combined_results = {
            "filename_matches": filename_results,
            "content_matches": content_results,
            "total_count": len(filename_results) + len(content_results.get("items", []))
        }
        
        return combined_results
    
    def _search_files_by_name(self, query: str, path: str = "") -> List[Dict]:
        """Search for files by name using repository contents API"""
        try:
            # Get all files in the repository
            tree_data = self.get_file_tree("")
            if "error" in tree_data:
                return []
            
            files = tree_data.get("tree", [])
            matches = []
            
            for file_info in files:
                if file_info.get("type") == "blob":  # It's a file
                    file_path = file_info.get("path", "")
                    file_name = file_path.split("/")[-1]  # Get just the filename
                    
                    # Check if query matches filename (case-insensitive)
                    if query.lower() in file_name.lower():
                        # If path filter is specified, check if file is in that path
                        if not path or path in file_path:
                            matches.append({
                                "path": file_path,
                                "name": file_name,
                                "type": "filename_match",
                                "url": f"https://github.com/{self.current_owner}/{self.current_repo}/blob/main/{file_path}"
                            })
            
            return matches
            
        except Exception as e:
            return []
    
    def _search_code_content(self, query: str, path: str = "") -> Dict:
        """Search for code content using GitHub's search API"""
        search_query = f"{query} repo:{self.current_owner}/{self.current_repo}"
        if path:
            search_query += f" path:{path}"
        
        url = f"{self.base_url}/search/code"
        params = {"q": search_query}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Content search failed: {str(e)}"}
    
    def get_file_contents(self, path: str) -> str:
        """Get the contents of a specific file"""
        url = f"{self.base_url}/repos/{self.current_owner}/{self.current_repo}/contents/{path}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            file_data = response.json()
            
            if file_data.get("type") == "file":
                import base64
                content = base64.b64decode(file_data["content"]).decode("utf-8", errors="replace")
                return content
            else:
                return f"Path {path} is not a file"
                
        except requests.exceptions.RequestException as e:
            return f"Error fetching file {path}: {str(e)}"
    
    def list_files(self, path: str = ".") -> List[Dict]:
        """List files in a directory"""
        url = f"{self.base_url}/repos/{self.current_owner}/{self.current_repo}/contents/{path}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return [{"error": f"Failed to list files: {str(e)}"}]

    def list_repos_for_owner(self, owner: Optional[str] = None) -> List[str]:
        """List repositories for a user/org owner. Returns repo names."""
        owner_to_use = owner or self.current_owner
        if not owner_to_use:
            return []
        headers = self.headers
        repos: List[str] = []
        # Try user endpoint
        urls = [
            f"{self.base_url}/users/{owner_to_use}/repos?per_page=100",
            f"{self.base_url}/orgs/{owner_to_use}/repos?per_page=100",
        ]
        for url in urls:
            try:
                r = requests.get(url, headers=headers, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    repos.extend([item.get("name", "") for item in data if item.get("name")])
                    break
            except requests.exceptions.RequestException:
                continue
        # De-duplicate while preserving order
        seen = set()
        unique = []
        for name in repos:
            if name not in seen:
                seen.add(name)
                unique.append(name)
        return unique
    
    def get_repo_info(self) -> Dict:
        """Get information about the current repository"""
        url = f"{self.base_url}/repos/{self.current_owner}/{self.current_repo}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to get repo info: {str(e)}"}
    
    def get_file_tree(self, path: str = "") -> Dict:
        """Get the file tree structure"""
        url = f"{self.base_url}/repos/{self.current_owner}/{self.current_repo}/git/trees/main"
        if path:
            url += f"?recursive=1"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to get file tree: {str(e)}"}
    
    def list_all_files(self) -> List[str]:
        """List all files in the repository for debugging"""
        try:
            tree_data = self.get_file_tree("")
            if "error" in tree_data:
                return []
            
            files = tree_data.get("tree", [])
            file_paths = []
            
            for file_info in files:
                if file_info.get("type") == "blob":  # It's a file
                    file_paths.append(file_info.get("path", ""))
            
            return file_paths
            
        except Exception as e:
            return []
