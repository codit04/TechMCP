"""
TechMCP Attendance Tools

This module contains all MCP tools related to attendance data, bunking calculations, and subject-wise attendance metrics.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.attendance_scraper import AttendanceScraper, SubjectAttendance

logger = logging.getLogger(__name__)

def find_subject_attendance(attendance_list: List[SubjectAttendance], search_term: str) -> Optional[SubjectAttendance]:
    """Helper function to find a subject attendance by course code"""
    search_term = search_term.upper().strip()
    logger.debug(f"Searching for attendance subject: '{search_term}' in {len(attendance_list)} subjects")
    for attendance in attendance_list:
        if search_term == attendance.course_code.upper():
            logger.debug(f"Found matching subject: {attendance.course_code}")
            return attendance
    logger.debug(f"No subject found matching: '{search_term}'")
    return None

async def handle_attendance_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle attendance scraper errors consistently"""
    logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
    await session_manager.close_session()  # Reset session on error
    return {
        "success": False,
        "error": True,
        "message": f"Failed to {operation}: {str(error)}",
        "operation": operation
    }

# Request/Response logging helper functions
def log_tool_call(func_name: str, **kwargs):
    """Log the start of a tool call"""
    timestamp = datetime.now().isoformat()
    logger.info(f"🔥 MCP TOOL CALL: {func_name}")
    logger.info(f"📥 REQUEST - Function: {func_name}")
    logger.info(f"📥 REQUEST - Kwargs: {kwargs}")
    logger.info(f"📥 REQUEST - Timestamp: {timestamp}")

def log_tool_response(func_name: str, result, error=None):
    """Log the response of a tool call"""
    timestamp = datetime.now().isoformat()
    
    if error:
        logger.error(f"❌ ERROR - Function: {func_name}")
        logger.error(f"📤 ERROR_RESPONSE - Error: {str(error)}")
        logger.error(f"📤 ERROR_RESPONSE - Type: {type(error).__name__}")
        logger.error(f"📤 ERROR_RESPONSE - Timestamp: {timestamp}")
    else:
        logger.info(f"✅ SUCCESS - Function: {func_name}")
        logger.info(f"📤 RESPONSE - Type: {type(result).__name__}")
        if isinstance(result, (dict, list)):
            logger.info(f"📤 RESPONSE - Length: {len(result)} items")
            logger.info(f"📤 RESPONSE - Preview: {str(result)[:200]}...")
        else:
            logger.info(f"📤 RESPONSE - Value: {str(result)[:200]}...")
        logger.info(f"📤 RESPONSE - Timestamp: {timestamp}")

def register_attendance_tools(mcp_instance, session_manager_instance):
    """Register all attendance-related MCP tools"""
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance
    
    logger.info("Registering attendance tools...")

    @mcp.tool
    async def get_subject_attendance_percentage(course_code: str) -> Dict[str, Any]:
        """Get attendance percentage for a specific subject by course code.
        
        Args:
            course_code: Course code to get attendance percentage for (e.g., '20XT81', '20XT82')
            
        Returns:
            Dictionary containing subject attendance percentage details
        """
        log_tool_call("get_subject_attendance_percentage", course_code=course_code)
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info(f"get_subject_attendance_percentage called for course: {course_code}")
            attendance_data = scraper.get_attendance_data()
            
            subject_attendance = find_subject_attendance(attendance_data, course_code)
            
            if not subject_attendance:
                result = {
                    "success": False,
                    "error": f"Course '{course_code}' not found",
                    "available_courses": [att.course_code for att in attendance_data]
                }
                log_tool_response("get_subject_attendance_percentage", result)
                return result
            
            result = {
                "success": True,
                "course_code": subject_attendance.course_code,
                "attendance_percentage": subject_attendance.attendance_percentage,
                "present_hours": subject_attendance.present_hours,
                "total_hours": subject_attendance.total_hours,
                "absent_hours": subject_attendance.absent_hours,
                "exempted_hours": subject_attendance.exempted_hours,
                "attendance_period": {
                    "from": subject_attendance.attendance_from,
                    "to": subject_attendance.attendance_to
                }
            }
            log_tool_response("get_subject_attendance_percentage", result)
            return result
            
        except Exception as e:
            log_tool_response("get_subject_attendance_percentage", None, error=e)
            return await handle_attendance_error(e, "get subject attendance percentage")

    @mcp.tool
    async def get_all_attendance_percentages() -> Dict[str, Any]:
        """Get attendance percentage for all subjects.
        
        Returns:
            Dictionary containing attendance percentages for all subjects
        """
        log_tool_call("get_all_attendance_percentages")
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info("get_all_attendance_percentages called")
            attendance_data = scraper.get_attendance_data()
            
            subjects_attendance = []
            total_present = 0
            total_hours = 0
            
            for attendance in attendance_data:
                subjects_attendance.append({
                    "course_code": attendance.course_code,
                    "attendance_percentage": attendance.attendance_percentage,
                    "present_hours": attendance.present_hours,
                    "total_hours": attendance.total_hours,
                    "absent_hours": attendance.absent_hours
                })
                total_present += attendance.present_hours
                total_hours += attendance.total_hours
            
            overall_percentage = (total_present / total_hours * 100) if total_hours > 0 else 0
            
            result = {
                "success": True,
                "subjects": subjects_attendance,
                "summary": {
                    "total_subjects": len(subjects_attendance),
                    "overall_attendance_percentage": round(overall_percentage, 2),
                    "total_present_hours": total_present,
                    "total_hours": total_hours,
                    "total_absent_hours": total_hours - total_present
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved attendance for {len(subjects_attendance)} subjects")
            log_tool_response("get_all_attendance_percentages", result)
            return result
            
        except Exception as e:
            log_tool_response("get_all_attendance_percentages", None, error=e)
            return await handle_attendance_error(e, "get all attendance percentages")

    @mcp.tool
    async def get_subject_absent_hours(course_code: str) -> Dict[str, Any]:
        """Get total absent hours for a specific subject by course code.
        
        Args:
            course_code: Course code to get absent hours for (e.g., '20XT81', '20XT82')
            
        Returns:
            Dictionary containing subject absent hours details
        """
        log_tool_call("get_subject_absent_hours", course_code=course_code)
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info(f"get_subject_absent_hours called for course: {course_code}")
            attendance_data = scraper.get_attendance_data()
            
            subject_attendance = find_subject_attendance(attendance_data, course_code)
            
            if not subject_attendance:
                result = {
                    "success": False,
                    "error": f"Course '{course_code}' not found",
                    "available_courses": [att.course_code for att in attendance_data]
                }
                log_tool_response("get_subject_absent_hours", result)
                return result
            
            result = {
                "success": True,
                "course_code": subject_attendance.course_code,
                "absent_hours": subject_attendance.absent_hours,
                "total_hours": subject_attendance.total_hours,
                "present_hours": subject_attendance.present_hours,
                "attendance_percentage": subject_attendance.attendance_percentage,
                "attendance_period": {
                    "from": subject_attendance.attendance_from,
                    "to": subject_attendance.attendance_to
                }
            }
            log_tool_response("get_subject_absent_hours", result)
            return result
            
        except Exception as e:
            log_tool_response("get_subject_absent_hours", None, error=e)
            return await handle_attendance_error(e, "get subject absent hours")

    @mcp.tool
    async def get_all_absent_hours() -> Dict[str, Any]:
        """Get total absent hours for all subjects.
        
        Returns:
            Dictionary containing absent hours for all subjects with summary
        """
        log_tool_call("get_all_absent_hours")
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info("get_all_absent_hours called")
            attendance_data = scraper.get_attendance_data()
            
            subjects_absent = []
            total_absent = 0
            
            for attendance in attendance_data:
                subjects_absent.append({
                    "course_code": attendance.course_code,
                    "absent_hours": attendance.absent_hours,
                    "total_hours": attendance.total_hours,
                    "attendance_percentage": attendance.attendance_percentage
                })
                total_absent += attendance.absent_hours
            
            result = {
                "success": True,
                "subjects": subjects_absent,
                "summary": {
                    "total_subjects": len(subjects_absent),
                    "total_absent_hours": total_absent,
                    "average_absent_per_subject": round(total_absent / len(subjects_absent), 2) if subjects_absent else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved absent hours for {len(subjects_absent)} subjects")
            log_tool_response("get_all_absent_hours", result)
            return result
            
        except Exception as e:
            log_tool_response("get_all_absent_hours", None, error=e)
            return await handle_attendance_error(e, "get all absent hours")

    @mcp.tool
    async def get_subject_present_hours(course_code: str) -> Dict[str, Any]:
        """Get total present hours for a specific subject by course code.
        
        Args:
            course_code: Course code to get present hours for (e.g., '20XT81', '20XT82')
            
        Returns:
            Dictionary containing subject present hours details
        """
        log_tool_call("get_subject_present_hours", course_code=course_code)
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info(f"get_subject_present_hours called for course: {course_code}")
            attendance_data = scraper.get_attendance_data()
            
            subject_attendance = find_subject_attendance(attendance_data, course_code)
            
            if not subject_attendance:
                result = {
                    "success": False,
                    "error": f"Course '{course_code}' not found",
                    "available_courses": [att.course_code for att in attendance_data]
                }
                log_tool_response("get_subject_present_hours", result)
                return result
            
            result = {
                "success": True,
                "course_code": subject_attendance.course_code,
                "present_hours": subject_attendance.present_hours,
                "total_hours": subject_attendance.total_hours,
                "absent_hours": subject_attendance.absent_hours,
                "attendance_percentage": subject_attendance.attendance_percentage,
                "attendance_period": {
                    "from": subject_attendance.attendance_from,
                    "to": subject_attendance.attendance_to
                }
            }
            log_tool_response("get_subject_present_hours", result)
            return result
            
        except Exception as e:
            log_tool_response("get_subject_present_hours", None, error=e)
            return await handle_attendance_error(e, "get subject present hours")

    @mcp.tool
    async def get_all_present_hours() -> Dict[str, Any]:
        """Get total present hours for all subjects.
        
        Returns:
            Dictionary containing present hours for all subjects with summary
        """
        log_tool_call("get_all_present_hours")
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info("get_all_present_hours called")
            attendance_data = scraper.get_attendance_data()
            
            subjects_present = []
            total_present = 0
            
            for attendance in attendance_data:
                subjects_present.append({
                    "course_code": attendance.course_code,
                    "present_hours": attendance.present_hours,
                    "total_hours": attendance.total_hours,
                    "attendance_percentage": attendance.attendance_percentage
                })
                total_present += attendance.present_hours
            
            result = {
                "success": True,
                "subjects": subjects_present,
                "summary": {
                    "total_subjects": len(subjects_present),
                    "total_present_hours": total_present,
                    "average_present_per_subject": round(total_present / len(subjects_present), 2) if subjects_present else 0
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved present hours for {len(subjects_present)} subjects")
            log_tool_response("get_all_present_hours", result)
            return result
            
        except Exception as e:
            log_tool_response("get_all_present_hours", None, error=e)
            return await handle_attendance_error(e, "get all present hours")

    @mcp.tool
    async def get_subject_available_bunks(course_code: str, min_attendance: float = 75.0) -> Dict[str, Any]:
        """Calculate available bunks for a specific subject using Bunker API formula.
        
        Args:
            course_code: Course code to calculate bunks for (e.g., '20XT81', '20XT82')
            min_attendance: Minimum required attendance percentage (default: 75.0)
            
        Returns:
            Dictionary containing available bunks and related calculations
        """
        log_tool_call("get_subject_available_bunks", course_code=course_code, min_attendance=min_attendance)
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info(f"get_subject_available_bunks called for course: {course_code}")
            attendance_data = scraper.get_attendance_data()
            
            subject_attendance = find_subject_attendance(attendance_data, course_code)
            
            if not subject_attendance:
                result = {
                    "success": False,
                    "error": f"Course '{course_code}' not found",
                    "available_courses": [att.course_code for att in attendance_data]
                }
                log_tool_response("get_subject_available_bunks", result)
                return result
            
            # Calculate available bunks with custom minimum attendance
            min_attendance_ratio = min_attendance / 100
            min_required_present = min_attendance_ratio * subject_attendance.total_hours
            
            if subject_attendance.present_hours < min_required_present:
                available_bunks = 0
                status = "Below minimum attendance"
            else:
                available_bunks = int((subject_attendance.present_hours - min_required_present) / min_attendance_ratio)
                available_bunks = max(0, available_bunks)
                status = "Safe to bunk" if available_bunks > 0 else "At minimum attendance"
            
            result = {
                "success": True,
                "course_code": subject_attendance.course_code,
                "available_bunks": available_bunks,
                "current_attendance": subject_attendance.attendance_percentage,
                "minimum_required_attendance": min_attendance,
                "present_hours": subject_attendance.present_hours,
                "total_hours": subject_attendance.total_hours,
                "absent_hours": subject_attendance.absent_hours,
                "min_required_present_hours": round(min_required_present, 2),
                "status": status,
                "calculation_details": {
                    "formula": "available_bunks = (present_hours - min_required_present) / min_attendance_ratio",
                    "min_attendance_ratio": min_attendance_ratio,
                    "current_surplus": subject_attendance.present_hours - min_required_present
                }
            }
            log_tool_response("get_subject_available_bunks", result)
            return result
            
        except Exception as e:
            log_tool_response("get_subject_available_bunks", None, error=e)
            return await handle_attendance_error(e, "get subject available bunks")

    @mcp.tool
    async def get_all_available_bunks(min_attendance: float = 75.0) -> Dict[str, Any]:
        """Calculate available bunks for all subjects using Bunker API formula.
        
        Args:
            min_attendance: Minimum required attendance percentage (default: 75.0)
            
        Returns:
            Dictionary containing available bunks for all subjects with summary
        """
        log_tool_call("get_all_available_bunks", min_attendance=min_attendance)
        
        try:
            scraper = await session_manager.get_attendance_scraper()
            logger.info("get_all_available_bunks called")
            attendance_data = scraper.get_attendance_data()
            
            subjects_bunks = []
            total_available_bunks = 0
            subjects_below_minimum = 0
            
            min_attendance_ratio = min_attendance / 100
            
            for attendance in attendance_data:
                min_required_present = min_attendance_ratio * attendance.total_hours
                
                if attendance.present_hours < min_required_present:
                    available_bunks = 0
                    status = "Below minimum attendance"
                    subjects_below_minimum += 1
                else:
                    available_bunks = int((attendance.present_hours - min_required_present) / min_attendance_ratio)
                    available_bunks = max(0, available_bunks)
                    status = "Safe to bunk" if available_bunks > 0 else "At minimum attendance"
                
                subjects_bunks.append({
                    "course_code": attendance.course_code,
                    "available_bunks": available_bunks,
                    "current_attendance": attendance.attendance_percentage,
                    "present_hours": attendance.present_hours,
                    "total_hours": attendance.total_hours,
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