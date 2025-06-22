"""
TechMCP Server

Main MCP server for PSG Tech e-campus portal integration.
Provides tools for fetching CA marks, assignments, and tutorials.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from fastmcp import FastMCP

# Import our modular components
from scrapers import CAMarksScraper, AttendanceScraper, TimeTableScraper, CourseCodeScraper
from tools.marks_tools import register_marks_tools
from tools.attendance_tools import register_attendance_tools
from tools.timetable_tools import register_timetable_tools
from tools.coursecode_tools import register_coursecode_tools # NEW: Import coursecode tools

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'techMCP_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
logger.info("Initializing TechMCP server...")
mcp = FastMCP("TechMCP")
logger.info("FastMCP server initialized successfully")

class SessionManager:
    """Manages scraper sessions and handles connection reuse"""
    
    def __init__(self):
        self._marks_scraper = None
        self._attendance_scraper = None
        self._timetable_scraper = None
        self._coursecode_scraper = None # NEW: Initialize coursecode scraper
        logger.info("SessionManager initialized")
    
    async def get_scraper(self) -> CAMarksScraper:
        """Get or create a marks scraper instance"""
        if self._marks_scraper is None:
            logger.info("Creating new marks scraper instance...")
            self._marks_scraper = CAMarksScraper()
            logger.info("New marks scraper instance created")
        return self._marks_scraper
    
    async def get_attendance_scraper(self) -> AttendanceScraper:
        """Get or create an attendance scraper instance"""
        if self._attendance_scraper is None:
            logger.info("Creating new attendance scraper instance...")
            self._attendance_scraper = AttendanceScraper()
            logger.info("New attendance scraper instance created")
        return self._attendance_scraper
    
    async def get_timetable_scraper(self) -> TimeTableScraper:
        """Get or create a timetable scraper instance"""
        if self._timetable_scraper is None:
            logger.info("Creating new timetable scraper instance...")
            self._timetable_scraper = TimeTableScraper()
            logger.info("New timetable scraper instance created")
        return self._timetable_scraper

    async def get_coursecode_scraper(self) -> CourseCodeScraper: # NEW: Method to get coursecode scraper
        """Get or create a coursecode scraper instance"""
        if self._coursecode_scraper is None:
            logger.info("Creating new coursecode scraper instance...")
            self._coursecode_scraper = CourseCodeScraper()
            logger.info("New coursecode scraper instance created")
        return self._coursecode_scraper
    
    async def close_session(self):
        """Close all scraper sessions"""
        if self._marks_scraper:
            logger.info("Closing marks scraper session...")
            self._marks_scraper.close()
            self._marks_scraper = None
            logger.info("Marks scraper session closed successfully")
        
        if self._attendance_scraper:
            logger.info("Closing attendance scraper session...")
            self._attendance_scraper.close()
            self._attendance_scraper = None
            logger.info("Attendance scraper session closed successfully")
        
        if self._timetable_scraper:
            logger.info("Closing timetable scraper session...")
            self._timetable_scraper.close()
            self._timetable_scraper = None
            logger.info("Timetable scraper session closed successfully")

        if self._coursecode_scraper: # NEW: Close coursecode scraper session
            logger.info("Closing coursecode scraper session...")
            self._coursecode_scraper.close()
            self._coursecode_scraper = None
            logger.info("Coursecode scraper session closed successfully")

# Create global session manager
logger.info("Creating global session manager...")
session_manager = SessionManager()
logger.info("Global session manager created")

# Register all tools
logger.info("Registering MCP tools...")
register_marks_tools(mcp, session_manager)
register_attendance_tools(mcp, session_manager)
register_timetable_tools(mcp, session_manager)
register_coursecode_tools(mcp, session_manager) # NEW: Register coursecode tools
logger.info("All tools registered successfully")

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("Starting TechMCP server on localhost:8080 with SSE transport")
        logger.info("Server will be accessible at: http://127.0.0.1:8080/sse")
        logger.info("=" * 50)
        # Run the server with SSE transport on port 8080
        mcp.run(transport="sse", host="127.0.0.1", port=8080)
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        # Cleanup on exit
        logger.info("Performing cleanup...")
        # session cleanup will be handled automatically
        logger.info("TechMCP server cleanup completed")