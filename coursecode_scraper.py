import httpx
import json
from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import List
from datetime import datetime, timedelta
import logging

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'coursecode_scraper_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Logging helpers
def log_http_request(method: str, url: str, **kwargs):
    logger.info(f"🌐 HTTP REQUEST: {method} {url}")
    if kwargs.get("data"):
        safe_data = {k: '***' if 'password' in k.lower() else v for k, v in kwargs['data'].items()}
        logger.info(f"📤 DATA: {safe_data}")
    if kwargs.get("headers"):
        logger.info(f"📤 HEADERS: {kwargs['headers']}")

def log_http_response(response: httpx.Response):
    logger.info(f"🌐 HTTP RESPONSE: {response.status_code} - {response.url}")
    logger.info(f"📥 LENGTH: {len(response.content)} bytes")
    if 'text/html' in response.headers.get("content-type", ""):
        logger.debug(f"📥 BODY PREVIEW: {response.text[:100]}...")

# HTTP Client with logging
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

    def close(self):
        self.client.close()

# Pydantic model for course info
class CourseInfo(BaseModel):
    course_code: str
    course_name: str

# Scraper for course codes
class CourseCodeScraper:
    BASE_URL = "https://ecampus.psgtech.ac.in/studzone"
    LOGIN_URL = f"{BASE_URL}"
    COURSE_PAGE_URL = f"{BASE_URL}/Attendance/courseplan"

    def __init__(self):
        self.client = LoggedHTTPClient()
        self.session_cookies = None
        self.cache = None
        self.last_fetch = None
        self.cache_duration = timedelta(minutes=30)
        self._load_config()

    def _load_config(self):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.credentials = config["credentials"]
        except Exception as e:
            raise Exception("Invalid or missing config.json") from e

    def _get_csrf_token(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        token = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token:
            raise Exception("CSRF token not found")
        return token.get("value", "")

    def login(self):
        logger.info("🔐 Logging in...")
        resp = self.client.get(self.LOGIN_URL)
        token = self._get_csrf_token(resp.text)
        data = {
            "rollno": self.credentials["roll_number"].upper(),
            "password": self.credentials["password"],
            "__RequestVerificationToken": token,
            "chkterms": "on"
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0"
        }
        resp = self.client.post(self.LOGIN_URL, data=data, headers=headers)
        if "/Home/Menu" in str(resp.url) or "logout" in resp.text.lower():
            self.session_cookies = self.client.cookies
            logger.info("✅ Login successful")
        else:
            logger.error("❌ Login failed")
            raise Exception("Login failed")

    def is_cache_valid(self) -> bool:
        return self.cache and self.last_fetch and (datetime.now() - self.last_fetch < self.cache_duration)

    def fetch_course_list(self) -> List[CourseInfo]:
        if self.is_cache_valid():
            logger.info("🔁 Returning cached course list")
            return self.cache

        if not self.session_cookies:
            self.login()

        logger.info("📥 Fetching course registration page...")
        resp = self.client.get(self.COURSE_PAGE_URL)
        if "Login" in resp.text:
            logger.warning("Session expired. Re-logging in.")
            self.login()
            resp = self.client.get(self.COURSE_PAGE_URL)

        course_list = self._parse_course_page(resp.text)
        self.cache = course_list
        self.last_fetch = datetime.now()
        return course_list

    def _parse_course_page(self, html: str) -> List[CourseInfo]:
        soup = BeautifulSoup(html, "html.parser")
        card_divs = soup.find_all("div", class_="card")

        if not card_divs:
            logger.error("No course cards found")
            return []

        course_dict = {}
        for card in card_divs:
            text_items = [t.strip() for t in card.stripped_strings]
            if len(text_items) >= 2:
                course_code = text_items[0]
                course_name = text_items[1]
                course_dict[course_code] = course_name  # Deduplicated

        logger.info(f"✅ Parsed {len(course_dict)} unique courses from card view")
        return [CourseInfo(course_code=k, course_name=v) for k, v in course_dict.items()]

    def close(self):
        self.client.close()

# Example usage
if __name__ == "__main__":
    scraper = CourseCodeScraper()
    try:
        course_list = scraper.fetch_course_list()
        course_dict = {course.course_code: course.course_name for course in course_list}
        print(json.dumps(course_dict, indent=2))  # Pretty-print as JSON
    finally:
        scraper.close()
