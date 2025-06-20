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
from scrapers import CAMarksScraper
from tools.marks_tools import register_marks_tools

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
        self._scraper = None
        logger.info("SessionManager initialized")
    
    async def get_scraper(self) -> CAMarksScraper:
        """Get or create a scraper instance"""
        if self._scraper is None:
            logger.info("Creating new scraper instance...")
            self._scraper = CAMarksScraper()
            logger.info("New scraper instance created")
        return self._scraper
    
    async def close_session(self):
        """Close the current scraper session"""
        if self._scraper:
            logger.info("Closing scraper session...")
            self._scraper.close()
            self._scraper = None
            logger.info("Scraper session closed successfully")

# Create global session manager
logger.info("Creating global session manager...")
session_manager = SessionManager()
logger.info("Global session manager created")

# Register all marks tools
logger.info("Registering MCP tools...")
register_marks_tools(mcp, session_manager)
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