# your_project_folder/tools/coursecode_tools.py

"""
MCP Tools for Course Code and Name Lookup.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import re # For case-insensitive search

# These will be imported and set by the main application
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.coursecode_scraper import CourseCodeScraper, CourseInfo

logger = logging.getLogger(__name__)

# --- Helper Functions for Tool Execution ---

def log_tool_call(func_name: str, **kwargs):
    """Log the start of a tool call."""
    timestamp = datetime.now().isoformat()
    logger.info(f"🔥 MCP TOOL CALL: {func_name}")
    logger.debug(f"📥 REQUEST - Function: {func_name}")
    logger.debug(f"📥 REQUEST - Kwargs: {kwargs}")
    logger.debug(f"📥 REQUEST - Timestamp: {timestamp}")

def log_tool_response(func_name: str, result, error=None):
    """Log the response of a tool call."""
    timestamp = datetime.now().isoformat()
    
    if error:
        logger.error(f"❌ ERROR - Function: {func_name}")
        logger.error(f"📤 ERROR_RESPONSE - Error: {str(error)}")
        logger.error(f"📤 ERROR_RESPONSE - Type: {type(error).__name__}")
        logger.error(f"📤 ERROR_RESPONSE - Timestamp: {timestamp}")
    else:
        logger.info(f"✅ SUCCESS - Function: {func_name}")
        logger.debug(f"📤 RESPONSE - Type: {type(result).__name__}")
        if isinstance(result, (dict, list)):
            logger.debug(f"📤 RESPONSE - Length: {len(result)} items")
            logger.debug(f"📤 RESPONSE - Preview: {str(result)[:200]}...")
        else:
            logger.debug(f"📤 RESPONSE - Value: {str(result)[:200]}...")
        logger.debug(f"📤 RESPONSE - Timestamp: {timestamp}")

async def handle_scraper_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle scraper errors consistently and trigger session reset."""
    logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
    if session_manager: # Ensure session_manager is available before closing
        # We need to await close_session as it's an async method
        await session_manager.close_session() 
    return {
        "success": False,
        "error_message": f"Failed to {operation}: {str(error)}",
        "operation": operation
    }

async def _get_all_courses_from_scraper() -> List[CourseInfo]:
    """
    Helper function to retrieve cached or fresh course list from the scraper.
    Handles potential scraper errors by re-raising them for the caller to catch.
    """
    if session_manager is None:
        raise RuntimeError("Session manager is not initialized. Tools cannot operate.")
    try:
        # --- MODIFICATION: Call the specific coursecode getter ---
        scraper = await session_manager.get_coursecode_scraper() 
        course_list = scraper.fetch_course_list() # This handles scraper's own caching
        return course_list
    except Exception as e:
        logger.error(f"Error retrieving courses from scraper: {e}", exc_info=True)
        raise # Re-raise to be caught by handle_scraper_error in tool functions

def register_coursecode_tools(mcp_instance, session_manager_instance):
    """
    Registers all course-related MCP tools with the provided MCP instance
    and sets up the session manager.
    """
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance
    
    logger.info("Registering course tools...")

    @mcp.tool
    async def get_course_name_by_code(course_code: str) -> Dict[str, Any]:
        """
        Retrieves the full course name given a course code.
        The search is case-insensitive.
        
        Args:
            course_code (str): The exact course code (e.g., "19XXA01", "CS101").
        
        Returns:
            Dict: A dictionary with 'success', 'course_code', 'course_name' if found,
                  or 'success: False' and 'error_message' if not found.
        """
        log_tool_call("get_course_name_by_code", course_code=course_code)
        try:
            all_courses = await _get_all_courses_from_scraper()
            
            # Create a quick lookup map for efficient search
            course_map = {c.course_code.upper(): c.course_name for c in all_courses}
            
            search_code = course_code.upper()
            if search_code in course_map:
                result = {
                    "success": True,
                    "course_code": course_code,
                    "course_name": course_map[search_code]
                }
                log_tool_response("get_course_name_by_code", result)
                return result
            else:
                result = {
                    "success": False,
                    "error_message": f"Course with code '{course_code}' not found.",
                    "available_codes_count": len(all_courses)
                }
                log_tool_response("get_course_name_by_code", result)
                return result
        except Exception as e:
            log_tool_response("get_course_name_by_code", None, error=e)
            return await handle_scraper_error(e, "get course name by code")

    @mcp.tool
    async def get_course_code_by_name(course_name_query: str) -> Dict[str, Any]:
        """
        Retrieves course code(s) for a given course name query.
        Performs a case-insensitive, partial match search.
        
        Args:
            course_name_query (str): A query string for the course name (e.g., "data structures", "machine learning").
        
        Returns:
            Dict: A dictionary with 'success', 'matching_courses' (list of dictionaries containing course_code and course_name),
                  or 'success: False' and 'error_message'.
        """
        log_tool_call("get_course_code_by_name", course_name_query=course_name_query)
        try:
            all_courses = await _get_all_courses_from_scraper()
            
            matching_courses = []
            search_term = course_name_query.lower()
            
            for course in all_courses:
                # Use regex for word boundary matching first, then fallback to simple 'in'
                # This ensures "lab" doesn't match "syllabus" etc.
                if re.search(r'\b' + re.escape(search_term) + r'\b', course.course_name.lower()):
                    matching_courses.append(course.dict()) # Convert Pydantic model to dict
                elif search_term in course.course_name.lower() and course.dict() not in matching_courses:
                    matching_courses.append(course.dict())
            
            if matching_courses:
                result = {
                    "success": True,
                    "matching_courses": matching_courses,
                    "total_matches": len(matching_courses)
                }
                log_tool_response("get_course_code_by_name", result)
                return result
            else:
                result = {
                    "success": False,
                    "error_message": f"No courses found matching '{course_name_query}'.",
                    "available_courses_count": len(all_courses)
                }
                log_tool_response("get_course_code_by_name", result)
                return result
        except Exception as e:
            log_tool_response("get_course_code_by_name", None, error=e)
            return await handle_scraper_error(e, "get course code by name")

    @mcp.tool
    async def list_lab_courses() -> Dict[str, Any]:
        """
        Lists all courses that contain "Lab" (case-insensitive) in their course name.
        
        Returns:
            Dict: A dictionary with 'success', 'lab_courses' (list of dictionaries containing course_code and course_name),
                  or 'success: False' and 'error_message'.
        """
        log_tool_call("list_lab_courses")
        try:
            all_courses = await _get_all_courses_from_scraper()
            
            lab_courses = []
            for course in all_courses:
                if "LAB" in course.course_name.upper(): # Explicitly check for "LAB"
                    lab_courses.append(course.dict()) # Convert Pydantic model to dict
            
            if lab_courses:
                result = {
                    "success": True,
                    "lab_courses": lab_courses,
                    "total_lab_courses": len(lab_courses)
                }
                log_tool_response("list_lab_courses", result)
                return result
            else:
                result = {
                    "success": False,
                    "error_message": "No courses with 'Lab' in their name were found.",
                    "available_courses_count": len(all_courses)
                }
                log_tool_response("list_lab_courses", result)
                return result
        except Exception as e:
            log_tool_response("list_lab_courses", None, error=e)
            return await handle_scraper_error(e, "list lab courses")

    @mcp.tool
    async def list_all_courses() -> Dict[str, Any]:
        """
        Lists all available courses with their codes and names.
        
        Returns:
            Dict: A dictionary with 'success', 'courses' (list of dictionaries containing course_code and course_name),
                  and 'total_courses', or 'success: False' and 'error_message'.
        """
        log_tool_call("list_all_courses")
        try:
            all_courses = await _get_all_courses_from_scraper()
            
            courses_data = [course.dict() for course in all_courses]
            
            if courses_data:
                result = {
                    "success": True,
                    "courses": courses_data,
                    "total_courses": len(courses_data)
                }
                log_tool_response("list_all_courses", result)
                return result
            else:
                result = {
                    "success": False,
                    "error_message": "No courses found at all. Scraper might have failed to retrieve data.",
                    "available_courses_count": 0
                }
                log_tool_response("list_all_courses", result)
                return result
        except Exception as e:
            log_tool_response("list_all_courses", None, error=e)
            return await handle_scraper_error(e, "list all courses")

    @mcp.tool
    async def get_course_code_name_dict() -> Dict[str, Any]:
        """
        Returns a dictionary mapping all course codes to their respective course names.
        
        Returns:
            Dict: A dictionary with 'success', 'course_dict' (mapping course_code to course_name),
                  and 'total_courses', or 'success: False' and 'error_message'.
        """
        log_tool_call("get_course_code_name_dict")
        try:
            all_courses = await _get_all_courses_from_scraper()
            
            course_name_dict = {course.course_code: course.course_name for course in all_courses}
            
            if course_name_dict:
                result = {
                    "success": True,
                    "course_dict": course_name_dict,
                    "total_courses": len(course_name_dict)
                }
                log_tool_response("get_course_code_name_dict", result)
                return result
            else:
                result = {
                    "success": False,
                    "error_message": "No courses found to create dictionary. Scraper might have failed to retrieve data.",
                    "available_courses_count": 0
                }
                log_tool_response("get_course_code_name_dict", result)
                return result
        except Exception as e:
            log_tool_response("get_course_code_name_dict", None, error=e)
            return await handle_scraper_error(e, "get course code name dictionary")


    logger.info("All course tools registered successfully.")