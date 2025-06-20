import httpx
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Union
import os
from pydantic import BaseModel
from datetime import datetime
import logging
import re
from urllib.parse import urljoin

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'scraper_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)

# HTTP Request/Response logging
def log_http_request(method: str, url: str, **kwargs):
    """Log HTTP request details"""
    logger.info(f"🌐 HTTP REQUEST: {method} {url}")
    if kwargs.get('data'):
        # Safely log form data without exposing sensitive info
        safe_data = {k: '***' if 'password' in k.lower() else v for k, v in kwargs['data'].items()}
        logger.info(f"📤 REQUEST_DATA: {safe_data}")
    if kwargs.get('headers'):
        safe_headers = {k: v for k, v in kwargs['headers'].items() if 'authorization' not in k.lower()}
        logger.info(f"📤 REQUEST_HEADERS: {safe_headers}")

def log_http_response(response: httpx.Response):
    """Log HTTP response details"""
    logger.info(f"🌐 HTTP RESPONSE: {response.status_code} {response.reason_phrase}")
    logger.info(f"📥 RESPONSE_URL: {response.url}")
    logger.info(f"📥 RESPONSE_SIZE: {len(response.content)} bytes")
    logger.info(f"📥 RESPONSE_HEADERS: {dict(response.headers)}")
    if response.headers.get('content-type', '').startswith('text/html'):
        logger.info(f"📥 RESPONSE_PREVIEW: {response.text[:100]}...")

# Enhanced HTTP client wrapper
class LoggedHTTPClient:
    def __init__(self):
        self.client = httpx.Client(follow_redirects=True, timeout=30.0)
    
    def get(self, url: str, **kwargs):
        log_http_request("GET", url, **kwargs)
        response = self.client.get(url, **kwargs)
        log_http_response(response)
        return response
    
    def post(self, url: str, **kwargs):
        log_http_request("POST", url, **kwargs)
        response = self.client.post(url, **kwargs)
        log_http_response(response)
        return response
    
    @property
    def cookies(self):
        return self.client.cookies

class LabCourseMarks(BaseModel):
    subject_code: str
    subject_name: str
    ca1_marks: Optional[float]  # CA1 (Max: 25)
    ca2_marks: Optional[float]  # CA2 (Max: 25)
    total_marks: Optional[float]  # Total (Max: 50)
    conv_total: Optional[float]  # Converted Total (Max: 60)

class TheoryCourseMarks(BaseModel):
    subject_code: str
    subject_name: str
    t1_marks: Optional[float]  # Test 1 (Max: 30)
    t2_marks: Optional[float]  # Test 2 (Max: 30)
    rt_marks: Optional[float]  # Retest (Max: 30)
    rt1_marks: Optional[float]  # Retest 1 (Max: 30)
    rt2_marks: Optional[float]  # Retest 2 (Max: 30)
    test_total: Optional[float]  # Total of tests (Max: 30)
    ap_marks: Optional[float]  # Assignment/Project (Max: 8)
    mpt_marks: Optional[float]  # Tutorial (Max: 12)
    total_marks: Optional[float]  # Total (Max: 50)
    conv_total: Optional[float]  # Converted Total (Max: 40)

class CAMarksScraper:
    BASE_URL = "https://ecampus.psgtech.ac.in/studzone"
    LOGIN_URL = f"{BASE_URL}"
    CA_MARKS_URL = f"{BASE_URL}/ContinuousAssessment/CAMarksView"
    
    def __init__(self):
        """Initialize scraper with logged HTTP client and empty session"""
        self.client = LoggedHTTPClient()
        self.session_cookies = None
        self._load_config()
    
    def _load_config(self):
        """Load credentials from config file"""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.credentials = config["credentials"]
                self.server_config = config["server"]
        except (FileNotFoundError, KeyError) as e:
            raise Exception("Invalid config.json file") from e

    def _get_csrf_token(self, html_content: str) -> str:
        """Extract CSRF token from login page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        csrf_input = soup.find('input', {'name': '__RequestVerificationToken'})
        if not csrf_input:
            raise Exception("Could not find CSRF token")
        return csrf_input.get('value', '')

    def login(self):
        """Authenticate with the portal"""
        logger.info("Starting login process...")
        
        # Get login page and CSRF token
        response = self.client.get(self.LOGIN_URL)
        logger.info(f"Got login page, status: {response.status_code}")
        csrf_token = self._get_csrf_token(response.text)
        logger.info(f"Extracted CSRF token: {csrf_token[:20]}...")

        # Prepare login data
        login_data = {
            "rollno": self.credentials["roll_number"].upper(),
            "password": self.credentials["password"],
            "__RequestVerificationToken": csrf_token,
            "chkterms": "on"  # Fixed: actual field name is "chkterms", not "terms"
        }
        
        logger.info(f"Attempting login with roll number: {self.credentials['roll_number']}")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        # Attempt login
        response = self.client.post(
            self.LOGIN_URL,
            data=login_data,
            headers=headers
        )
        
        logger.info(f"Login POST response: {response.status_code}, URL: {response.url}")

        # Enhanced login success/failure detection
        current_url = str(response.url)
        response_text = response.text.lower()
        
        print(f"[DEBUG] After login attempt:")
        print(f"[DEBUG] Status code: {response.status_code}")
        print(f"[DEBUG] Final URL: {current_url}")
        print(f"[DEBUG] Response length: {len(response.text)} chars")
        
        # Check for successful login - redirect to Home/Menu page
        if "/studzone/Home/Menu" in current_url:
            print(f"[DEBUG] SUCCESS: Redirected to Home/Menu page")
            logger.info("Login successful!")
            self.session_cookies = self.client.cookies
            self.session_active = True
            return
        
        # Additional success indicators in the response content
        success_indicators = [
            "main menu", "profile", "logout", "welcome", 
            "continuous assessment", "ca marks", "breadcrumb"
        ]
        
        failure_indicators = [
            "student login", "rollno", "password", "forgot password",
            "invalid", "incorrect", "error", "login failed",
            "terms & conditions", "staff", "parent"
        ]
        
        success_count = sum(1 for indicator in success_indicators if indicator in response_text)
        failure_count = sum(1 for indicator in failure_indicators if indicator in response_text)
        
        print(f"[DEBUG] Success indicators found: {success_count}")
        print(f"[DEBUG] Failure indicators found: {failure_count}")
        
        # If we're still on login page or have failure indicators, login failed
        if ("/studzone" in current_url and "/Home/Menu" not in current_url) or failure_count > success_count:
            print(f"[DEBUG] FAILURE: Still on login page or failure indicators detected")
            print(f"[DEBUG] Response snippet: {response_text[:500]}...")
            logger.error(f"Login failed. Response URL: {response.url}")
            logger.error(f"Response text snippet: {response.text[:500]}...")
            raise Exception("Login failed. Check your credentials.")
        
        # Final check: if we have more success indicators than failure ones
        if success_count > failure_count:
            print(f"[DEBUG] SUCCESS: More success indicators than failure indicators")
            logger.info("Login successful!")
            self.session_cookies = self.client.cookies
            self.session_active = True
            return
        
        print(f"[DEBUG] UNCLEAR: Unable to determine login status clearly")
        logger.error(f"Login status unclear. Response URL: {response.url}")
        raise Exception("Login failed. Check your credentials.")

    def get_ca_marks(self) -> dict[str, Union[List[LabCourseMarks], List[TheoryCourseMarks]]]:
        """Fetch CA marks from the portal for both lab and theory courses"""
        if not self.session_cookies:
            self.login()

        response = self.client.get(self.CA_MARKS_URL)
        
        if "Login" in response.text:
            # Session expired, try logging in again
            self.login()
            response = self.client.get(self.CA_MARKS_URL)

        return self._parse_marks_tables(response.text)

    def _parse_marks_tables(self, html_content: str) -> dict[str, Union[List[LabCourseMarks], List[TheoryCourseMarks]]]:
        """Parse both lab and theory marks tables from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table', {'class': 'table'})
        
        result = {
            'lab_courses': [],
            'theory_courses': []
        }

        for table in tables:
            # Check table structure to determine if it's lab or theory
            headers = table.find_all('th')
            if any('LT1' in header.text for header in headers):
                # This is a lab course table
                result['lab_courses'].extend(self._parse_lab_table(table))
            elif any('T1' in header.text for header in headers):
                # This is a theory course table
                result['theory_courses'].extend(self._parse_theory_table(table))

        return result

    def _parse_lab_table(self, table: BeautifulSoup) -> List[LabCourseMarks]:
        """Parse the lab courses marks table"""
        marks_list = []
        rows = table.find_all('tr')[2:]  # Skip header rows

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 6:  # Ensure row has all required columns
                continue

            def parse_mark(mark_text: str) -> Optional[float]:
                mark_text = mark_text.strip()
                try:
                    return float(mark_text) if mark_text and mark_text != '*' else None
                except ValueError:
                    return None

            marks = LabCourseMarks(
                subject_code=cols[0].text.strip(),
                subject_name=cols[1].text.strip(),
                ca1_marks=parse_mark(cols[2].text),
                ca2_marks=parse_mark(cols[3].text),
                total_marks=parse_mark(cols[4].text),
                conv_total=parse_mark(cols[5].text)
            )
            marks_list.append(marks)

        return marks_list

    def _parse_theory_table(self, table: BeautifulSoup) -> List[TheoryCourseMarks]:
        """Parse the theory courses marks table"""
        marks_list = []
        rows = table.find_all('tr')[2:]  # Skip header rows

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 12:  # Ensure row has all required columns
                continue

            def parse_mark(mark_text: str) -> Optional[float]:
                mark_text = mark_text.strip()
                try:
                    return float(mark_text) if mark_text and mark_text != '*' else None
                except ValueError:
                    return None

            marks = TheoryCourseMarks(
                subject_code=cols[0].text.strip(),
                subject_name=cols[1].text.strip(),
                t1_marks=parse_mark(cols[2].text),
                t2_marks=parse_mark(cols[3].text),
                rt_marks=parse_mark(cols[4].text),
                rt1_marks=parse_mark(cols[5].text),
                rt2_marks=parse_mark(cols[6].text),
                test_total=parse_mark(cols[7].text),
                ap_marks=parse_mark(cols[8].text),
                mpt_marks=parse_mark(cols[9].text),  # Tutorial marks
                total_marks=parse_mark(cols[10].text),
                conv_total=parse_mark(cols[11].text)
            )
            marks_list.append(marks)

        return marks_list

    def close(self):
        """Close the HTTP client"""
        self.client.client.close() 