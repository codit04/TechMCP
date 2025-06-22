"""
TechMCP Course Code Tools

This module contains all MCP tools related to course code data, course information, and course management.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timedelta, time # Import 'time' for handling datetime.time objects
import asyncio

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.coursecode_scraper import CourseCodeScraper, CourseInfo
# Note: The TimetableEntry here must match the definition in your timetable_scraper.py
# which is now pointing to PSG Tech portal.
from scrapers.timetable_scraper import TimeTableScraper, TimeTableEntry 

logger = logging.getLogger(__name__)

# Helper functions for logging tool calls and responses
def log_tool_call(tool_name: str, **kwargs):
    logger.info(f"⚡ TOOL_CALL: {tool_name} - Params: {kwargs}")

def log_tool_response(tool_name: str, result: Any, error: Optional[Exception] = None):
    if error:
        logger.error(f"❌ ERROR - Function: {tool_name}")
        logger.error(f"📤 ERROR_RESPONSE - Error: {str(error)}")
        logger.error(f"📤 ERROR_RESPONSE - Type: {type(error).__name__}")
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
    }

def format_course_entry(course: CourseInfo) -> Dict[str, str]:
    """Formats a single CourseInfo object into a dictionary."""
    return {
        "course_code": course.course_code,
        "course_name": course.course_name
    }

def find_courses(course_list: List[CourseInfo],
                search_term: Optional[str] = None,
                course_code_exact: Optional[str] = None) -> List[CourseInfo]:
    """Helper function to find courses by search term or exact course code from a list of CourseInfo."""
    filtered_courses = []

    if course_code_exact:
        course_code_upper = course_code_exact.upper()
        logger.debug(f"Filtering by exact course code: '{course_code_exact}'")
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
            
            course_list = scraper.fetch_course_list()
            
            formatted_courses = [format_course_entry(course) for course in course_list]
            
            result = {
                "success": True,
                "message": f"Successfully retrieved {len(formatted_courses)} courses.",
                "courses": formatted_courses,
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

            all_courses = scraper.fetch_course_list()
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
            }
            logger.info(message)
            log_tool_response("search_courses", result)
            return result
        except Exception as e:
            log_tool_response("search_courses", None, error=e)
            return await handle_coursecode_error(e, "search courses")


    @mcp.tool(name="get_course_details", description="Provides detailed information for a specific course, including its timetable, by either course code or course name.")
    async def get_course_details(identifier: str) -> Dict[str, Any]:
        """
        Provides detailed information for a specific course, including its timetable,
        by either exact course code or a search term for its name.
        Args:
            identifier: The exact course code (e.g., "BT101") or a search term/name (e.g., "Data Structures").
        Returns:
            Dictionary containing success status, message, and course details.
        """
        log_tool_call("get_course_details", identifier=identifier)
        try:
            course_scraper = await session_manager.get_coursecode_scraper()
            timetable_scraper = await session_manager.get_timetable_scraper()
            
            logger.info(f"get_course_details called with identifier: {identifier}")

            all_courses = course_scraper.fetch_course_list()
            
            # 1. Try to find by exact course code first
            matching_course_info_by_code = find_courses(all_courses, course_code_exact=identifier)
            
            selected_course_info: Optional[CourseInfo] = None
            if matching_course_info_by_code:
                selected_course_info = matching_course_info_by_code[0] # Take the first exact match
                logger.info(f"Found course by exact code: {identifier}")
            else:
                # 2. If not found by exact code, try finding by search term (could be name or partial code)
                matching_course_info_by_name = find_courses(all_courses, search_term=identifier)
                if matching_course_info_by_name:
                    if len(matching_course_info_by_name) == 1:
                        selected_course_info = matching_course_info_by_name[0]
                        logger.info(f"Found unique course by name/term: {identifier}")
                    else:
                        # Multiple matches, return suggestions and ask user to clarify
                        formatted_suggestions = [format_course_entry(c) for c in matching_course_info_by_name]
                        result = {
                            "success": False,
                            "message": f"Multiple courses found for '{identifier}'. Please be more specific or provide the exact course code.",
                            "identifier": identifier,
                            "suggestions": formatted_suggestions,
                        }
                        logger.warning(f"Multiple courses found for '{identifier}'. {len(formatted_suggestions)} suggestions provided.")
                        log_tool_response("get_course_details", result)
                        return result
                else:
                    # No match found at all
                    result = {
                        "success": False,
                        "message": f"Course '{identifier}' not found by code or name.",
                        "identifier": identifier,
                        "suggestions": [],
                    }
                    logger.warning(f"Course '{identifier}' not found.")
                    log_tool_response("get_course_details", result)
                    return result
            
            # Proceed if a unique course was identified
            course_details = format_course_entry(selected_course_info)

            # Fetch and add timetable details
            timetable_data = timetable_scraper.get_timetable_data()
            
            course_timetable_entries = [
                entry for entry in timetable_data
                if entry.course_code.upper() == selected_course_info.course_code.upper()
            ]

            timetable_summary = {}
            if course_timetable_entries:
                total_hours = 0.0
                days_of_week = set()
                slots = []

                for entry in course_timetable_entries:
                    # Calculate duration_hours on the fly from start_time and end_time (datetime.time objects)
                    # Use a dummy date for timedelta calculation if they are just time objects
                    dummy_date = datetime.today().date()
                    start_dt = datetime.combine(dummy_date, entry.start_time)
                    end_dt = datetime.combine(dummy_date, entry.end_time)
                    
                    # Handle overnight classes if applicable (though unlikely for typical timetable periods)
                    if end_dt < start_dt:
                        end_dt += timedelta(days=1) # Add a day if end is chronologically before start
                    
                    duration_td = end_dt - start_dt
                    duration_hours = duration_td.total_seconds() / 3600.0

                    total_hours += duration_hours
                    days_of_week.add(entry.day) # Use 'day' from the new TimeTableEntry
                    slots.append({
                        "day": entry.day, # Use 'day'
                        "period": entry.period, # Add period
                        "start_time": entry.start_time.strftime("%H:%M"), # Format time objects to string
                        "end_time": entry.end_time.strftime("%H:%M"),     # Format time objects to string
                        "duration_hours": round(duration_hours, 2),       # Add calculated duration
                        "room": entry.room,
                        "faculty": entry.faculty # Use 'faculty'
                    })
                
                timetable_summary = {
                    "total_hours_per_week": round(total_hours, 2),
                    "number_of_days_per_week": len(days_of_week),
                    "days_of_week": sorted(list(days_of_week)),
                    "schedule_slots": slots
                }
                logger.info(f"Found timetable entries for course {selected_course_info.course_code}")
            else:
                logger.info(f"No timetable entries found for course {selected_course_info.course_code}")
                timetable_summary = {
                    "message": "No timetable data available for this course.",
                    "total_hours_per_week": 0,
                    "number_of_days_per_week": 0,
                    "days_of_week": [],
                    "schedule_slots": []
                }
            
            course_details["timetable_info"] = timetable_summary # Add timetable info to course details

            result = {
                "success": True,
                "message": f"Details for course '{selected_course_info.course_code}' ({selected_course_info.course_name}) retrieved successfully.",
                "course": course_details,
            }
            logger.info(f"Details retrieved for course: {selected_course_info.course_code}")
            log_tool_response("get_course_details", result)
            return result
        except Exception as e:
            log_tool_response("get_course_details", None, error=e)
            return await handle_coursecode_error(e, f"get details for course '{identifier}'")


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

            all_courses = scraper.fetch_course_list()
            
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
            }
            logger.info(message)
            log_tool_response("get_courses_by_department", result)
            return result
        except Exception as e:
            log_tool_response("get_courses_by_department", None, error=e)
            return await handle_coursecode_error(e, f"get courses by department '{department_code}'")

    logger.info("Course code tools registered successfully")
