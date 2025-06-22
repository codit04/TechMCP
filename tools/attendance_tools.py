"""
TechMCP Attendance Tools

This module contains all MCP tools related to attendance data, bunking calculations, and subject-wise attendance metrics.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import asyncio # Needed for async operations

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.attendance_scraper import AttendanceScraper, SubjectAttendance
from scrapers.coursecode_scraper import CourseCodeScraper, CourseInfo # NEW: Import CourseCodeScraper and CourseInfo

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

async def handle_attendance_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle attendance scraper errors consistently"""
    logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
    await session_manager.close_session()  # Reset session on error for safety
    return {
        "success": False,
        "error": True,
        "message": f"Failed to {operation}: {str(error)}",
        "timestamp": datetime.now().isoformat()
    }

def find_subject_attendance(attendance_list: List[SubjectAttendance], course_code: str) -> Optional[SubjectAttendance]:
    """Helper function to find a subject attendance by exact course code."""
    course_code_upper = course_code.upper().strip()
    logger.debug(f"Searching for attendance subject with code: '{course_code}' in {len(attendance_list)} subjects")
    for attendance in attendance_list:
        if course_code_upper == attendance.course_code.upper():
            logger.debug(f"Found matching subject: {attendance.course_code}")
            return attendance
    logger.debug(f"No subject found matching course code: '{course_code}'")
    return None

async def get_course_name_from_code(course_code: str) -> Optional[str]:
    """Helper function to get course name from course code using CourseCodeScraper."""
    try:
        course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
        all_courses: List[CourseInfo] = course_scraper.fetch_course_list() # This is synchronous call from scraper
        for course in all_courses:
            if course.course_code.upper() == course_code.upper():
                return course.course_name
        return None
    except Exception as e:
        logger.error(f"Error fetching course name for {course_code}: {e}", exc_info=True)
        return None

async def resolve_course_identifier_to_code(course_identifier: str) -> Optional[str]:
    """
    Resolves a course identifier (code or name) to a course code.
    If the identifier is a course name, it will find the corresponding course code.
    """
    course_identifier_upper = course_identifier.upper().strip()
    
    # First, assume it's a course code and try to find attendance directly
    # This might not be strictly necessary here if the main tools will do the attendance search
    # But it's good for robust resolution.

    # Now, try to resolve via CourseCodeScraper
    try:
        course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
        all_courses: List[CourseInfo] = course_scraper.fetch_course_list()

        # Try exact course code match first
        for course in all_courses:
            if course.course_code.upper() == course_identifier_upper:
                logger.info(f"Resolved '{course_identifier}' as course code '{course.course_code}'")
                return course.course_code

        # If not an exact code, try matching as a course name
        for course in all_courses:
            if course.course_name.upper() == course_identifier_upper:
                logger.info(f"Resolved '{course_identifier}' as course name for code '{course.course_code}'")
                return course.course_code
        
        logger.warning(f"Could not resolve course identifier '{course_identifier}' to any known course code or name.")
        return None

    except Exception as e:
        logger.error(f"Error resolving course identifier '{course_identifier}': {e}", exc_info=True)
        return None


# FastMCP Tool Registration
def register_attendance_tools(mcp_instance, session_manager_instance):
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance

    logger.info("Registering attendance tools...")

    @mcp.tool(name="get_subject_attendance_percentage", description="Retrieves attendance percentage and other details for a specific subject by its code or name.")
    async def get_subject_attendance_percentage(course_identifier: str) -> Dict[str, Any]:
        """
        Retrieves attendance percentage and other details for a specific subject by its code or name.
        Args:
            course_identifier: The course code or name to retrieve attendance for.
        Returns:
            Dictionary containing success status, message, and subject attendance details.
        """
        log_tool_call("get_subject_attendance_percentage", course_identifier=course_identifier)
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            
            resolved_course_code = await resolve_course_identifier_to_code(course_identifier)
            if not resolved_course_code:
                return {
                    "success": False,
                    "message": f"Could not find a course with identifier '{course_identifier}'. Please check the code or name.",
                    "course_identifier": course_identifier,
                    "timestamp": datetime.now().isoformat()
                }

            attendance_list = attendance_scraper.get_attendance_data()
            subject_attendance = find_subject_attendance(attendance_list, resolved_course_code)

            if subject_attendance:
                course_name = await get_course_name_from_code(resolved_course_code)
                result = {
                    "success": True,
                    "message": f"Attendance for {course_name if course_name else resolved_course_code} retrieved successfully.",
                    "subject": {
                        "course_code": subject_attendance.course_code,
                        "course_name": course_name, # NEW: Include course name
                        "total_hours": subject_attendance.total_hours,
                        "exempted_hours": subject_attendance.exempted_hours,
                        "absent_hours": subject_attendance.absent_hours,
                        "present_hours": subject_attendance.present_hours,
                        "attendance_percentage": subject_attendance.attendance_percentage,
                        "exemption_percentage": subject_attendance.exemption_percentage,
                        "exemption_med_percentage": subject_attendance.exemption_med_percentage,
                        "attendance_from": subject_attendance.attendance_from,
                        "attendance_to": subject_attendance.attendance_to,
                        "available_bunks": subject_attendance.available_bunks # Keep if needed, or remove if specific bunk tool is preferred
                    },
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_attendance_percentage", result)
                return result
            else:
                message = f"No attendance data found for course '{course_identifier}' (resolved to code: {resolved_course_code})."
                result = {
                    "success": False,
                    "message": message,
                    "course_identifier": course_identifier,
                    "resolved_code": resolved_course_code,
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_attendance_percentage", result)
                return result
        except Exception as e:
            log_tool_response("get_subject_attendance_percentage", None, error=e)
            return await handle_attendance_error(e, f"get attendance percentage for {course_identifier}")

    @mcp.tool(name="get_all_attendance_percentages", description="Fetches attendance percentages for all subjects.")
    async def get_all_attendance_percentages() -> Dict[str, Any]:
        """
        Fetches attendance percentages for all subjects.
        Returns:
            Dictionary containing success status, message, and a list of all subjects' attendance.
        """
        log_tool_call("get_all_attendance_percentages")
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            attendance_list = attendance_scraper.get_attendance_data()
            
            course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
            all_courses: List[CourseInfo] = course_scraper.fetch_course_list()
            course_code_to_name_map = {c.course_code.upper(): c.course_name for c in all_courses}

            subjects_data = []
            for sub in attendance_list:
                course_name = course_code_to_name_map.get(sub.course_code.upper(), "N/A")
                subjects_data.append({
                    "course_code": sub.course_code,
                    "course_name": course_name, # NEW: Include course name
                    "attendance_percentage": sub.attendance_percentage,
                    "present_hours": sub.present_hours,
                    "total_hours": sub.total_hours,
                    "available_bunks": sub.available_bunks # Assuming this is calculated by scraper
                })
            
            result = {
                "success": True,
                "message": f"Successfully retrieved attendance for {len(subjects_data)} subjects.",
                "subjects": subjects_data,
                "timestamp": datetime.now().isoformat()
            }
            log_tool_response("get_all_attendance_percentages", result)
            return result
        except Exception as e:
            log_tool_response("get_all_attendance_percentages", None, error=e)
            return await handle_attendance_error(e, "get all attendance percentages")

    @mcp.tool(name="get_subject_absent_hours", description="Gets the total absent hours for a specific subject by its code or name.")
    async def get_subject_absent_hours(course_identifier: str) -> Dict[str, Any]:
        """
        Gets the total absent hours for a specific subject by its code or name.
        Args:
            course_identifier: The course code or name for which to get absent hours.
        Returns:
            Dictionary containing success status, message, and absent hours.
        """
        log_tool_call("get_subject_absent_hours", course_identifier=course_identifier)
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            
            resolved_course_code = await resolve_course_identifier_to_code(course_identifier)
            if not resolved_course_code:
                return {
                    "success": False,
                    "message": f"Could not find a course with identifier '{course_identifier}'. Please check the code or name.",
                    "course_identifier": course_identifier,
                    "timestamp": datetime.now().isoformat()
                }

            attendance_list = attendance_scraper.get_attendance_data()
            subject_attendance = find_subject_attendance(attendance_list, resolved_course_code)

            if subject_attendance:
                course_name = await get_course_name_from_code(resolved_course_code)
                result = {
                    "success": True,
                    "message": f"Absent hours for {course_name if course_name else resolved_course_code} retrieved.",
                    "subject": {
                        "course_code": subject_attendance.course_code,
                        "course_name": course_name, # NEW: Include course name
                        "absent_hours": subject_attendance.absent_hours
                    },
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_absent_hours", result)
                return result
            else:
                message = f"No attendance data found for course '{course_identifier}' (resolved to code: {resolved_course_code})."
                result = {
                    "success": False,
                    "message": message,
                    "course_identifier": course_identifier,
                    "resolved_code": resolved_course_code,
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_absent_hours", result)
                return result
        except Exception as e:
            log_tool_response("get_subject_absent_hours", None, error=e)
            return await handle_attendance_error(e, f"get absent hours for {course_identifier}")

    @mcp.tool(name="get_all_absent_hours", description="Retrieves total absent hours for all subjects.")
    async def get_all_absent_hours() -> Dict[str, Any]:
        """
        Retrieves total absent hours for all subjects.
        Returns:
            Dictionary containing success status, message, and a list of subjects with absent hours.
        """
        log_tool_call("get_all_absent_hours")
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            attendance_list = attendance_scraper.get_attendance_data()

            course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
            all_courses: List[CourseInfo] = course_scraper.fetch_course_list()
            course_code_to_name_map = {c.course_code.upper(): c.course_name for c in all_courses}

            subjects_data = []
            for sub in attendance_list:
                course_name = course_code_to_name_map.get(sub.course_code.upper(), "N/A")
                subjects_data.append({
                    "course_code": sub.course_code,
                    "course_name": course_name, # NEW: Include course name
                    "absent_hours": sub.absent_hours
                })
            
            result = {
                "success": True,
                "message": f"Successfully retrieved absent hours for {len(subjects_data)} subjects.",
                "subjects": subjects_data,
                "timestamp": datetime.now().isoformat()
            }
            log_tool_response("get_all_absent_hours", result)
            return result
        except Exception as e:
            log_tool_response("get_all_absent_hours", None, error=e)
            return await handle_attendance_error(e, "get all absent hours")

    @mcp.tool(name="get_subject_present_hours", description="Gets total present hours for a specific subject by its code or name.")
    async def get_subject_present_hours(course_identifier: str) -> Dict[str, Any]:
        """
        Gets total present hours for a specific subject by its code or name.
        Args:
            course_identifier: The course code or name for which to get present hours.
        Returns:
            Dictionary containing success status, message, and present hours.
        """
        log_tool_call("get_subject_present_hours", course_identifier=course_identifier)
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            
            resolved_course_code = await resolve_course_identifier_to_code(course_identifier)
            if not resolved_course_code:
                return {
                    "success": False,
                    "message": f"Could not find a course with identifier '{course_identifier}'. Please check the code or name.",
                    "course_identifier": course_identifier,
                    "timestamp": datetime.now().isoformat()
                }

            attendance_list = attendance_scraper.get_attendance_data()
            subject_attendance = find_subject_attendance(attendance_list, resolved_course_code)

            if subject_attendance:
                course_name = await get_course_name_from_code(resolved_course_code)
                result = {
                    "success": True,
                    "message": f"Present hours for {course_name if course_name else resolved_course_code} retrieved.",
                    "subject": {
                        "course_code": subject_attendance.course_code,
                        "course_name": course_name, # NEW: Include course name
                        "present_hours": subject_attendance.present_hours
                    },
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_present_hours", result)
                return result
            else:
                message = f"No attendance data found for course '{course_identifier}' (resolved to code: {resolved_course_code})."
                result = {
                    "success": False,
                    "message": message,
                    "course_identifier": course_identifier,
                    "resolved_code": resolved_course_code,
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_present_hours", result)
                return result
        except Exception as e:
            log_tool_response("get_subject_present_hours", None, error=e)
            return await handle_attendance_error(e, f"get present hours for {course_identifier}")

    @mcp.tool(name="get_all_present_hours", description="Retrieves total present hours for all subjects.")
    async def get_all_present_hours() -> Dict[str, Any]:
        """
        Retrieves total present hours for all subjects.
        Returns:
            Dictionary containing success status, message, and a list of subjects with present hours.
        """
        log_tool_call("get_all_present_hours")
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            attendance_list = attendance_scraper.get_attendance_data()

            course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
            all_courses: List[CourseInfo] = course_scraper.fetch_course_list()
            course_code_to_name_map = {c.course_code.upper(): c.course_name for c in all_courses}

            subjects_data = []
            for sub in attendance_list:
                course_name = course_code_to_name_map.get(sub.course_code.upper(), "N/A")
                subjects_data.append({
                    "course_code": sub.course_code,
                    "course_name": course_name, # NEW: Include course name
                    "present_hours": sub.present_hours
                })
            
            result = {
                "success": True,
                "message": f"Successfully retrieved present hours for {len(subjects_data)} subjects.",
                "subjects": subjects_data,
                "timestamp": datetime.now().isoformat()
            }
            log_tool_response("get_all_present_hours", result)
            return result
        except Exception as e:
            log_tool_response("get_all_present_hours", None, error=e)
            return await handle_attendance_error(e, "get all present hours")

    @mcp.tool(name="get_subject_available_bunks", description="Calculates available bunks for a specific subject by its code or name.")
    async def get_subject_available_bunks(course_identifier: str, min_attendance: float = 75.0) -> Dict[str, Any]:
        """
        Calculates available bunks for a specific subject by its code or name.
        Args:
            course_identifier: The course code or name for which to calculate available bunks.
            min_attendance: The minimum attendance percentage to maintain (default: 75.0).
        Returns:
            Dictionary containing success status, message, and available bunks.
        """
        log_tool_call("get_subject_available_bunks", course_identifier=course_identifier, min_attendance=min_attendance)
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            
            resolved_course_code = await resolve_course_identifier_to_code(course_identifier)
            if not resolved_course_code:
                return {
                    "success": False,
                    "message": f"Could not find a course with identifier '{course_identifier}'. Please check the code or name.",
                    "course_identifier": course_identifier,
                    "timestamp": datetime.now().isoformat()
                }

            attendance_list = attendance_scraper.get_attendance_data()
            subject_attendance = find_subject_attendance(attendance_list, resolved_course_code)

            if subject_attendance:
                course_name = await get_course_name_from_code(resolved_course_code)
                available_bunks = attendance_scraper._calculate_available_bunks(
                    subject_attendance.total_hours,
                    subject_attendance.present_hours,
                    min_attendance
                )
                
                status = "Safe to bunk" if available_bunks > 0 else "Cannot bunk"
                if subject_attendance.attendance_percentage < min_attendance:
                    status = "Below minimum attendance"

                result = {
                    "success": True,
                    "message": f"Available bunks for {course_name if course_name else resolved_course_code} calculated.",
                    "subject": {
                        "course_code": subject_attendance.course_code,
                        "course_name": course_name, # NEW: Include course name
                        "available_bunks": available_bunks,
                        "current_attendance": subject_attendance.attendance_percentage,
                        "present_hours": subject_attendance.present_hours,
                        "total_hours": subject_attendance.total_hours,
                        "status": status
                    },
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_available_bunks", result)
                return result
            else:
                message = f"No attendance data found for course '{course_identifier}' (resolved to code: {resolved_course_code})."
                result = {
                    "success": False,
                    "message": message,
                    "course_identifier": course_identifier,
                    "resolved_code": resolved_course_code,
                    "timestamp": datetime.now().isoformat()
                }
                log_tool_response("get_subject_available_bunks", result)
                return result
        except Exception as e:
            log_tool_response("get_subject_available_bunks", None, error=e)
            return await handle_attendance_error(e, f"get available bunks for {course_identifier}")

    @mcp.tool(name="get_all_available_bunks", description="Calculates available bunks for all subjects.")
    async def get_all_available_bunks(min_attendance: float = 75.0) -> Dict[str, Any]:
        """
        Calculates available bunks for all subjects.
        Args:
            min_attendance: The minimum attendance percentage to maintain (default: 75.0).
        Returns:
            Dictionary containing success status, message, and a summary of available bunks for all subjects.
        """
        log_tool_call("get_all_available_bunks", min_attendance=min_attendance)
        try:
            attendance_scraper: AttendanceScraper = await session_manager.get_attendance_scraper()
            attendance_list = attendance_scraper.get_attendance_data()

            course_scraper: CourseCodeScraper = await session_manager.get_coursecode_scraper()
            all_courses: List[CourseInfo] = course_scraper.fetch_course_list()
            course_code_to_name_map = {c.course_code.upper(): c.course_name for c in all_courses}

            subjects_bunks = []
            total_available_bunks = 0
            subjects_below_minimum = 0

            for sub in attendance_list:
                available_bunks = attendance_scraper._calculate_available_bunks(
                    sub.total_hours, sub.present_hours, min_attendance
                )
                
                status = "Safe to bunk" if available_bunks > 0 else "Cannot bunk"
                if sub.attendance_percentage < min_attendance:
                    status = "Below minimum attendance"
                    subjects_below_minimum += 1

                course_name = course_code_to_name_map.get(sub.course_code.upper(), "N/A")

                subjects_bunks.append({
                    "course_code": sub.course_code,
                    "course_name": course_name, # NEW: Include course name
                    "available_bunks": available_bunks,
                    "current_attendance": sub.attendance_percentage,
                    "present_hours": sub.present_hours,
                    "total_hours": sub.total_hours,
                    "status": status
                })
                total_available_bunks += available_bunks
            
            result = {
                "success": True,
                "subjects": subjects_bunks,
                "summary": {
                    "total_subjects": len(subjects_bunks),
                    "total_available_bunks": total_available_bunks,
                    "subjects_below_minimum": subjects_below_minimum,
                    "subjects_safe_to_bunk": len([s for s in subjects_bunks if s["available_bunks"] > 0]),
                    "minimum_required_attendance": min_attendance,
                    "average_bunks_per_subject": round(total_available_bunks / len(subjects_bunks), 2) if subjects_bunks else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Calculated bunks for {len(subjects_bunks)} subjects")
            log_tool_response("get_all_available_bunks", result)
            return result
            
        except Exception as e:
            log_tool_response("get_all_available_bunks", None, error=e)
            return await handle_attendance_error(e, "get all available bunks")

    logger.info("Attendance tools registered successfully")
