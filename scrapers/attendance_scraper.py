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
        logging.FileHandler(f'attendance_scraper_{datetime.now().strftime("%Y%m%d")}.log')
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

class SubjectAttendance(BaseModel):
    course_code: str
    total_hours: int
    exempted_hours: int
    absent_hours: int
    present_hours: int
    attendance_percentage: float
    exemption_percentage: float
    exemption_med_percentage: float
    attendance_from: str
    attendance_to: str
    available_bunks: Optional[int] = None  # Calculated field

class AttendanceScraper:
    BASE_URL = "https://ecampus.psgtech.ac.in/studzone"
    LOGIN_URL = f"{BASE_URL}"
    ATTENDANCE_URL = f"{BASE_URL}/Attendance/StudentPercentage"
    
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

    def get_attendance_data(self) -> List[SubjectAttendance]:
        """Fetch attendance data from the portal"""
        if not self.session_cookies:
            self.login()

        response = self.client.get(self.ATTENDANCE_URL)
        
        if "Login" in response.text:
            # Session expired, try logging in again
            self.login()
            response = self.client.get(self.ATTENDANCE_URL)

        return self._parse_attendance_table(response.text)

    def _parse_attendance_table(self, html_content: str) -> List[SubjectAttendance]:
        """Parse the attendance table from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the main attendance table
        table = soup.find('table', {'id': 'example'})
        if not table:
            logger.error("Could not find attendance table with id 'example'")
            return []

        attendance_list = []
        tbody = table.find('tbody')
        if not tbody:
            logger.error("Could not find tbody in attendance table")
            return []

        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} attendance rows")

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10:  # Ensure row has all required columns
                logger.warning(f"Row has only {len(cols)} columns, expected 10")
                continue

            try:
                def safe_int(text: str) -> int:
                    """Safely convert text to int"""
                    text = text.strip()
                    try:
                        return int(text) if text and text != '*' else 0
                    except ValueError:
                        return 0

                def safe_float(text: str) -> float:
                    """Safely convert text to float"""
                    text = text.strip()
                    try:
                        return float(text) if text and text != '*' else 0.0
                    except ValueError:
                        return 0.0

                course_code = cols[0].text.strip()
                total_hours = safe_int(cols[1].text)
                exempted_hours = safe_int(cols[2].text)
                absent_hours = safe_int(cols[3].text)
                present_hours = safe_int(cols[4].text)
                attendance_percentage = safe_float(cols[5].text)
                exemption_percentage = safe_float(cols[6].text)
                exemption_med_percentage = safe_float(cols[7].text)
                attendance_from = cols[8].text.strip()
                attendance_to = cols[9].text.strip()

                # Calculate available bunks using the Bunker API formula
                available_bunks = self._calculate_available_bunks(
                    total_hours, present_hours, absent_hours
                )

                attendance = SubjectAttendance(
                    course_code=course_code,
                    total_hours=total_hours,
                    exempted_hours=exempted_hours,
                    absent_hours=absent_hours,
                    present_hours=present_hours,
                    attendance_percentage=attendance_percentage,
                    exemption_percentage=exemption_percentage,
                    exemption_med_percentage=exemption_med_percentage,
                    attendance_from=attendance_from,
                    attendance_to=attendance_to,
                    available_bunks=available_bunks
                )
                attendance_list.append(attendance)
                
                logger.debug(f"Parsed attendance for {course_code}: {present_hours}/{total_hours} ({attendance_percentage}%)")

            except Exception as e:
                logger.error(f"Error parsing attendance row: {e}")
                continue

        logger.info(f"Successfully parsed {len(attendance_list)} attendance records")
        return attendance_list

    def _calculate_available_bunks(self, total_hours: int, present_hours: int, 
                                 absent_hours: int, min_attendance: float = 75.0) -> int:
        """
        Calculate how many more classes can be safely skipped while maintaining minimum attendance
        
        Formula from Bunker API:
        available_bunks = floor((present_hours - (min_attendance_ratio * total_hours)) / min_attendance_ratio)
        where min_attendance_ratio = min_attendance / 100
        """
        if total_hours == 0:
            return 0
            
        min_attendance_ratio = min_attendance / 100
        
        # Calculate the minimum required present hours
        min_required_present = min_attendance_ratio * total_hours
        
        # If already below minimum, return 0
        if present_hours < min_required_present:
            return 0
        
        # Calculate how many more classes can be bunked
        # Formula: available_bunks = (present_hours - min_attendance_ratio * (total_hours + bunks)) / (1 - min_attendance_ratio)
        # Simplified: available_bunks = (present_hours - min_attendance_ratio * total_hours) / min_attendance_ratio
        available_bunks = int((present_hours - min_required_present) / min_attendance_ratio)
        
        return max(0, available_bunks)

    def find_subject_attendance(self, attendance_list: List[SubjectAttendance], 
                              search_term: str) -> Optional[SubjectAttendance]:
        """Find a subject by course code"""
        search_term = search_term.upper().strip()
        for attendance in attendance_list:
            if search_term == attendance.course_code.upper():
                return attendance
        return None

    def close(self):
        """Close the HTTP client"""
        self.client.client.close() 