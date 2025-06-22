"""
TechMCP Course Code Tools

This module contains all MCP tools related to course code data, course information, and course management.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.coursecode_scraper import CourseCodeScraper, CourseInfo

logger = logging.getLogger(__name__)

# Helper functions for logging tool calls and responses
def log_tool_call(tool_name: str, **kwargs):
    logger.info(f"⚡ TOOL_CALL: {tool_name} - Params: {kwargs}")

def log_tool_response(tool_name: str, result: Any, error: Optional[Exception] = None):
    if error:
        logger.error(f"❌ ERROR - Function: {tool_name}")
        logger.error(f"📤 ERROR_RESPONSE - Error: {str(error)}")
        logger.error(f"📤 ERROR_RESPONSE - Type: {type(error).__name__}")
        logger.error(f"📤 ERROR_RESPONSE - Timestamp: {datetime.now().isoformat()}")
    else:
        logger.info(f"✅ TOOL_RESPONSE: {tool_name} - Result: {result}")

async def handle_coursecode_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle course code scraper errors consistently"""
    logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
    await session_manager.close_session()  # Reset session on error
    return {
        "success": False,
        "error": True,
        "message": f"Failed to {operation}: {str(error)}",
        "timestamp": datetime.now().isoformat()
    }

def format_course_entry(course: CourseInfo) -> Dict[str, str]:
    """Formats a single CourseInfo object into a dictionary."""
    return {
        "course_code": course.course_code,
        "course_name": course.course_name
    }

def get_course_statistics(course_list: List[CourseInfo]) -> Dict[str, Any]:
    """Generates statistics from a list of CourseInfo objects."""
    total_courses = len(course_list)
    if total_courses == 0:
        return {
            "total_courses": 0,
            "departments": {},
            "unique_departments": 0,
            "average_course_name_length": 0,
            "average_course_code_length": 0
        }

    department_counts = {}
    total_name_length = 0
    total_code_length = 0

    for course in course_list:
        department_code = course.course_code[:2].upper() # Assuming department is first two chars
        department_counts[department_code] = department_counts.get(department_code, 0) + 1
        total_name_length += len(course.course_name)
        total_code_length += len(course.course_code)

    return {
        "total_courses": total_courses,
        "departments": dict(sorted(department_counts.items())),
        "unique_departments": len(department_counts),
        "average_course_name_length": round(total_name_length / total_courses, 2),
        "average_course_code_length": round(total_code_length / total_courses, 2)
    }

def find_courses(course_list: List[CourseInfo],
                search_term: Optional[str] = None,
                course_code: Optional[str] = None) -> List[CourseInfo]:
    """Helper function to find courses by search term or course code from a list of CourseInfo."""
    filtered_courses = []

    if course_code:
        course_code_upper = course_code.upper()
        logger.debug(f"Filtering by exact course code: '{course_code}'")
        for course in course_list:
            if course.course_code.upper() == course_code_upper:
                filtered_courses.append(course)
    elif search_term:
        search_term_lower = search_term.lower()
        logger.debug(f"Searching for term: '{search_term}' in course codes and names")
        for course in course_list:
            if (search_term_lower in course.course_code.lower() or
                search_term_lower in course.course_name.lower()):
                filtered_courses.append(course)
    else:
        # If no search term or course code, return all courses
        filtered_courses = list(course_list)

    logger.debug(f"Found {len(filtered_courses)} matching courses")
    return filtered_courses


# FastMCP Tool Registration
def register_coursecode_tools(mcp_instance, session_manager_instance):
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance

    logger.info("Registering course code tools...")

    @mcp.tool(name="get_all_courses", description="Retrieves a list of all courses with their codes and names.")
    async def get_all_courses() -> Dict[str, Any]:
        """
        Retrieves a list of all courses with their codes and names.
        Returns:
            Dictionary containing success status, message, and a list of courses.
        """
        log_tool_call("get_all_courses")
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info("get_all_courses called")
            
            course_list = scraper.fetch_course_list() # This returns List[CourseInfo]
            
            formatted_courses = [format_course_entry(course) for course in course_list]
            
            result = {
                "success": True,
                "message": f"Successfully retrieved {len(formatted_courses)} courses.",
                "courses": formatted_courses,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"Retrieved {len(formatted_courses)} courses")
            log_tool_response("get_all_courses", result)
            return result
        except Exception as e:
            log_tool_response("get_all_courses", None, error=e)
            return await handle_coursecode_error(e, "get all courses")


    @mcp.tool(name="search_courses", description="Searches for courses by a given term in course codes or names.")
    async def search_courses(search_term: str) -> Dict[str, Any]:
        """
        Searches for courses by a given term in course codes or names.
        Args:
            search_term: The term to search for.
        Returns:
            Dictionary containing success status, message, and a list of matching courses.
        """
        log_tool_call("search_courses", search_term=search_term)
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info(f"search_courses called with search_term: {search_term}")

            all_courses = scraper.fetch_course_list() # This returns List[CourseInfo]
            matching_courses_info = find_courses(all_courses, search_term=search_term)
            
            formatted_courses = [format_course_entry(course) for course in matching_courses_info]

            if not formatted_courses:
                message = f"No courses found matching '{search_term}'."
            else:
                message = f"Found {len(formatted_courses)} courses matching '{search_term}'."

            result = {
                "success": True,
                "message": message,
                "search_term": search_term,
                "courses": formatted_courses,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(message)
            log_tool_response("search_courses", result)
            return result
        except Exception as e:
            log_tool_response("search_courses", None, error=e)
            return await handle_coursecode_error(e, "search courses")


    @mcp.tool(name="get_course_details", description="Provides detailed information for a specific course code.")
    async def get_course_details(course_code: str) -> Dict[str, Any]:
        """
        Provides detailed information for a specific course code.
        Args:
            course_code: The exact course code to retrieve details for.
        Returns:
            Dictionary containing success status, message, and course details.
        """
        log_tool_call("get_course_details", course_code=course_code)
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info(f"get_course_details called for course_code: {course_code}")

            all_courses = scraper.fetch_course_list() # This returns List[CourseInfo]
            # Use find_courses to get the CourseInfo object
            matching_course_info = find_courses(all_courses, course_code=course_code)
            
            if not matching_course_info:
                # If no exact match, try suggesting similar ones (optional, for more helpful responses)
                suggested_courses_info = find_courses(all_courses, search_term=course_code)
                formatted_suggestions = [format_course_entry(c) for c in suggested_courses_info]
                
                result = {
                    "success": False,
                    "message": f"Course '{course_code}' not found.",
                    "course_code": course_code,
                    "suggestions": formatted_suggestions,
                    "timestamp": datetime.now().isoformat()
                }
                logger.warning(f"Course '{course_code}' not found. {len(formatted_suggestions)} suggestions provided.")
                log_tool_response("get_course_details", result)
                return result
            
            # Assuming find_courses returns a list, and we want the first exact match
            course_details = format_course_entry(matching_course_info[0])

            # Optionally add department info
            department_code = course_details["course_code"][:2].upper()
            course_details["department_code"] = department_code
            # You might want a mapping for department_code to full department name

            result = {
                "success": True,
                "message": f"Details for course '{course_code}' retrieved successfully.",
                "course": course_details,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"Details retrieved for course: {course_code}")
            log_tool_response("get_course_details", result)
            return result
        except Exception as e:
            log_tool_response("get_course_details", None, error=e)
            return await handle_coursecode_error(e, f"get details for course '{course_code}'")


    @mcp.tool(name="get_courses_by_department", description="Filters and returns courses belonging to a specified department code.")
    async def get_courses_by_department(department_code: str) -> Dict[str, Any]:
        """
        Filters and returns courses belonging to a specified department code.
        Args:
            department_code: The two-character department code (e.g., "PD", "BT").
        Returns:
            Dictionary containing success status, message, and a list of courses for the department.
        """
        log_tool_call("get_courses_by_department", department_code=department_code)
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info(f"get_courses_by_department called for department: {department_code}")

            all_courses = scraper.fetch_course_list() # This returns List[CourseInfo]
            
            department_code_upper = department_code.upper()
            filtered_courses_info = [
                course for course in all_courses
                if course.course_code.upper().startswith(department_code_upper)
            ]
            
            formatted_courses = [format_course_entry(course) for course in filtered_courses_info]

            if not formatted_courses:
                message = f"No courses found for department '{department_code}'."
            else:
                message = f"Found {len(formatted_courses)} courses for department '{department_code}'."

            result = {
                "success": True,
                "message": message,
                "department_code": department_code,
                "courses": formatted_courses,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(message)
            log_tool_response("get_courses_by_department", result)
            return result
        except Exception as e:
            log_tool_response("get_courses_by_department", None, error=e)
            return await handle_coursecode_error(e, f"get courses by department '{department_code}'")


    @mcp.tool(name="get_course_statistics", description="Generates comprehensive statistics about the course catalog.")
    async def get_course_statistics() -> Dict[str, Any]:
        """
        Generates comprehensive statistics about the course catalog, including total courses, department distribution,
        and average name/code lengths.
        Returns:
            Dictionary containing success status, message, and statistics.
        """
        log_tool_call("get_course_statistics")
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info("get_course_statistics called")

            course_list = scraper.fetch_course_list() # This returns List[CourseInfo]
            stats = get_course_statistics(course_list)
            
            result = {
                "success": True,
                "message": "Course statistics generated successfully.",
                "statistics": stats,
                "timestamp": datetime.now().isoformat()
            }
            logger.info("Course statistics generated.")
            log_tool_response("get_course_statistics", result)
            return result
        except Exception as e:
            log_tool_response("get_course_statistics", None, error=e)
            return await handle_coursecode_error(e, "get course statistics")


    @mcp.tool(name="refresh_course_cache", description="Explicitly clears and re-fetches the course cache, ensuring the latest data.")
    async def refresh_course_cache() -> Dict[str, Any]:
        """
        Explicitly clears and re-fetches the course cache, ensuring the latest data.
        Returns:
            Dictionary containing refresh status and updated course count
        """
        log_tool_call("refresh_course_cache")
        
        try:
            scraper = await session_manager.get_coursecode_scraper()
            logger.info("refresh_course_cache called")
            
            # Clear existing cache
            scraper.cache = None
            scraper.last_fetch = None
            
            # Fetch fresh data
            course_list = scraper.fetch_course_list() # This returns List[CourseInfo]
            
            stats = get_course_statistics(course_list) # This now expects List[CourseInfo]
            
            result = {
                "success": True,
                "message": "Course cache refreshed successfully",
                "courses_loaded": len(course_list),
                "statistics": stats,
                "refreshed_at": datetime.now().isoformat(),
                "cache_info": {
                    "is_cached": scraper.is_cache_valid(),
                    "last_fetch": scraper.last_fetch.isoformat() if scraper.last_fetch else None
                }
            }
            
            logger.info(f"Cache refreshed with {len(course_list)} courses")
            log_tool_response("refresh_course_cache", result)
            return result
            
        except Exception as e:
            log_tool_response("refresh_course_cache", None, error=e)
            return await handle_coursecode_error(e, "refresh course cache")

    logger.info("Course code tools registered successfully")
