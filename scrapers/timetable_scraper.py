import httpx
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Union
import os
from pydantic import BaseModel
from datetime import datetime, time, timedelta
import logging
import re
from urllib.parse import urljoin

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'timetable_scraper_{datetime.now().strftime("%Y%m%d")}.log')
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

class TimeTableEntry(BaseModel):
    day: str  # Monday, Tuesday, etc.
    period: int  # 1-8
    start_time: time  # e.g., 08:00
    end_time: time  # e.g., 08:50
    course_code: str  # e.g., 19CS401
    course_name: str  # e.g., Operating Systems
    faculty: str  # Professor name
    room: str  # Room number/name

class TimeTableScraper:
    BASE_URL = "https://ecampus.psgtech.ac.in/studzone"
    LOGIN_URL = f"{BASE_URL}"
    TIMETABLE_URL = f"{BASE_URL}/Attendance/TimeTable"
    
    # Standard time slots for periods (adjusted for PSG Tech schedule with breaks)
    PERIOD_TIMES = {
        1: (time(8, 30), time(9, 20)),
        2: (time(9, 20), time(10, 10)),
        # Break: 10:10 to 10:30
        3: (time(10, 30), time(11, 20)),
        4: (time(11, 20), time(12, 10)),
        # Lunch Break: 12:10 to 13:40
        5: (time(13, 40), time(14, 30)),
        6: (time(14, 30), time(15, 20)),
        # Break: 15:20 to 15:30
        7: (time(15, 30), time(16, 20)),
        8: (time(16, 20), time(17, 10))
    }
    
    # Define break times that should be excluded from class scheduling
    BREAK_TIMES = [
        (time(10, 10), time(10, 30)),  # Morning break
        (time(12, 10), time(13, 40)),  # Lunch break  
        (time(15, 20), time(15, 30))   # Afternoon break
    ]
    
    DAYS_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    def __init__(self):
        """Initialize scraper with logged HTTP client and empty session"""
        self.client = LoggedHTTPClient()
        self.session_cookies = None
        self.timetable_cache = None
        self.last_fetch = None
        self.cache_duration = timedelta(minutes=30)  # Cache for 30 minutes
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

    def is_cache_valid(self) -> bool:
        """Check if cached timetable data is still valid"""
        if not self.timetable_cache or not self.last_fetch:
            return False
        return datetime.now() - self.last_fetch < self.cache_duration

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
            "chkterms": "on"
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

    def get_timetable_data(self) -> List[TimeTableEntry]:
        """Fetch timetable data from the portal"""
        # Check cache first
        if self.is_cache_valid():
            logger.info("Returning cached timetable data")
            return self.timetable_cache

        if not self.session_cookies:
            self.login()

        response = self.client.get(self.TIMETABLE_URL)
        
        if "Login" in response.text:
            # Session expired, try logging in again
            self.login()
            response = self.client.get(self.TIMETABLE_URL)

        timetable_entries = self._parse_timetable_table(response.text)
        
        # Update cache
        self.timetable_cache = timetable_entries
        self.last_fetch = datetime.now()
        
        return timetable_entries

    def _parse_timetable_table(self, html_content: str) -> List[TimeTableEntry]:
        """Parse the timetable table from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the main timetable table
        table = soup.find('table', {'class': 'table table-bordered timetable-table'}) or soup.find('table', {'class': 'table'}) or soup.find('table')
        if not table:
            logger.error("Could not find timetable table")
            return []

        timetable_entries = []
        
        # Find tbody with the actual schedule data
        tbody = table.find('tbody')
        if not tbody:
            logger.error("Could not find tbody in timetable table")
            return []

        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} timetable rows")

        # Parse each day row
        for row_idx, row in enumerate(rows):
            try:
                # First element should be the day name in a <th> tag
                day_header = row.find('th')
                if not day_header:
                    logger.warning(f"Row {row_idx} has no day header, skipping")
                    continue
                
                day = day_header.text.strip()
                logger.debug(f"Processing day: {day}")
                
                # Find all td elements (period cells)
                period_cells = row.find_all('td')
                if not period_cells:
                    logger.warning(f"Row {row_idx} has no period cells, skipping")
                    continue

                current_period = 1
                
                for cell in period_cells:
                    # Check if cell has content or is empty/dash
                    cell_text = cell.get_text(strip=True)
                    
                    if cell_text == '-' or not cell_text:
                        # Empty cell, advance period based on colspan
                        colspan = int(cell.get('colspan', 1))
                        current_period += colspan
                        continue
                    
                    # Parse the cell content
                    course_info = self._parse_timetable_cell(cell)
                    if course_info:
                        # Handle colspan for lab sessions
                        colspan = int(cell.get('colspan', 1))
                        
                        # Get period times
                        start_time, end_time = self.PERIOD_TIMES.get(current_period, (time(8, 0), time(8, 50)))
                        
                        # If colspan > 1, extend end time
                        if colspan > 1 and (current_period + colspan - 1) in self.PERIOD_TIMES:
                            _, end_time = self.PERIOD_TIMES[current_period + colspan - 1]
                        
                        entry = TimeTableEntry(
                            day=day,
                            period=current_period,
                            start_time=start_time,
                            end_time=end_time,
                            course_code=course_info.get('course_code', ''),
                            course_name=course_info.get('course_name', ''),
                            faculty=course_info.get('faculty', ''),
                            room=course_info.get('room', '')
                        )
                        timetable_entries.append(entry)
                        
                        logger.debug(f"Parsed: {day} Period {current_period}-{current_period + colspan - 1} - {entry.course_code} ({entry.course_name})")
                    
                    # Advance period based on colspan
                    colspan = int(cell.get('colspan', 1))
                    current_period += colspan

            except Exception as e:
                logger.error(f"Error parsing timetable row {row_idx}: {e}")
                continue

        logger.info(f"Successfully parsed {len(timetable_entries)} timetable entries")
        return timetable_entries

    def _parse_timetable_cell(self, cell) -> Optional[Dict[str, str]]:
        """Parse individual timetable cell to extract course details"""
        try:
            # Look for tooltip wrapper div
            tooltip_wrapper = cell.find('div', {'class': 'tooltip-wrapper'})
            if not tooltip_wrapper:
                return None
            
            # Extract course code from <b> tag
            course_code_elem = tooltip_wrapper.find('b')
            course_code = course_code_elem.text.strip() if course_code_elem else ''
            
            # Extract course name from tooltip-text span
            course_name_elem = tooltip_wrapper.find('span', {'class': 'tooltip-text'})
            course_name = course_name_elem.text.strip() if course_name_elem else ''
            
            # Extract class/section info (text before the <b> tag)
            class_info = ''
            for text in tooltip_wrapper.stripped_strings:
                if course_code_elem and text == course_code_elem.text.strip():
                    break
                class_info += text + ' '
            class_info = class_info.strip()
            
            if course_code or course_name:
                return {
                    'course_code': course_code,
                    'course_name': course_name,
                    'faculty': '',  # Not available in this format
                    'room': '',     # Not available in this format
                    'class_info': class_info
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing cell content: {e}")
            return None

    def _parse_cell_content(self, cell_text: str) -> Optional[Dict[str, str]]:
        """Parse individual cell content to extract course details"""
        if not cell_text or cell_text.strip() == '':
            return None
            
        lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
        
        if not lines:
            return None
        
        # Initialize with defaults
        course_info = {
            'course_code': '',
            'course_name': '',
            'faculty': '',
            'room': ''
        }
        
        # Try to extract course code (usually starts with numbers/letters pattern)
        course_code_pattern = r'\b[A-Z]*\d{2}[A-Z]*\d+\b'
        
        for line in lines:
            # Look for course code
            code_match = re.search(course_code_pattern, line)
            if code_match and not course_info['course_code']:
                course_info['course_code'] = code_match.group()
                # Remove course code from line for further processing
                line = line.replace(course_info['course_code'], '').strip()
            
            # Look for room number (usually contains numbers and might have letters)
            room_pattern = r'\b[A-Z]*\d+[A-Z]*\b'
            room_match = re.search(room_pattern, line)
            if room_match and len(room_match.group()) <= 6:  # Reasonable room number length
                course_info['room'] = room_match.group()
                line = line.replace(course_info['room'], '').strip()
            
            # Remaining text could be course name or faculty
            if line and not course_info['course_name']:
                # If it looks like a person's name (has title or multiple words), it's faculty
                if any(title in line.lower() for title in ['dr.', 'prof.', 'mr.', 'ms.', 'mrs.']):
                    course_info['faculty'] = line
                elif len(line.split()) >= 2:  # Multiple words might be course name
                    course_info['course_name'] = line
                else:
                    course_info['course_name'] = line
        
        # If we have at least a course code or course name, return the info
        if course_info['course_code'] or course_info['course_name']:
            return course_info
        
        return None

    def is_break_time(self, check_time: Optional[time] = None) -> bool:
        """Check if the given time falls within any break period"""
        if not check_time:
            check_time = datetime.now().time()
        
        for break_start, break_end in self.BREAK_TIMES:
            if break_start <= check_time <= break_end:
                return True
        return False

    def get_current_period(self, current_time: Optional[datetime] = None) -> int:
        """Determine current period number based on time"""
        if not current_time:
            current_time = datetime.now()
        
        current_time_only = current_time.time()
        
        # Check if it's break time first
        if self.is_break_time(current_time_only):
            return -1  # Special value for break time
        
        for period, (start_time, end_time) in self.PERIOD_TIMES.items():
            if start_time <= current_time_only <= end_time:
                return period
        
        return 0  # No current period

    def find_timetable_entries(self, timetable_list: List[TimeTableEntry], 
                             day: Optional[str] = None, 
                             course_code: Optional[str] = None) -> List[TimeTableEntry]:
        """Find timetable entries by day and/or course code"""
        filtered_entries = timetable_list
        
        if day:
            day = day.lower()
            filtered_entries = [entry for entry in filtered_entries 
                              if entry.day.lower() == day]
        
        if course_code:
            course_code = course_code.upper()
            filtered_entries = [entry for entry in filtered_entries 
                              if entry.course_code.upper() == course_code]
        
        return filtered_entries

    def close(self):
        """Close the HTTP client"""
        self.client.client.close() 