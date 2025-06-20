"""
TechMCP Marks Tools

This module contains all MCP tools related to CA marks, assignments, and tutorials.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.marks_scraper import CAMarksScraper, LabCourseMarks, TheoryCourseMarks

logger = logging.getLogger(__name__)

def find_subject(subjects: List[Union[LabCourseMarks, TheoryCourseMarks]], search_term: str) -> Optional[Union[LabCourseMarks, TheoryCourseMarks]]:
    """Helper function to find a subject by code or name"""
    search_term = search_term.lower()
    logger.debug(f"Searching for subject: '{search_term}' in {len(subjects)} subjects")
    for subject in subjects:
        if search_term in subject.subject_code.lower() or search_term in subject.subject_name.lower():
            logger.debug(f"Found matching subject: {subject.subject_code} - {subject.subject_name}")
            return subject
    logger.debug(f"No subject found matching: '{search_term}'")
    return None

async def handle_scraper_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle scraper errors consistently"""
    logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
    await session_manager.close_session()  # Reset session on error
    return {
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

def register_marks_tools(mcp_instance, session_manager_instance):
    """Register all marks-related MCP tools"""
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance
    
    logger.info("Registering marks tools...")

    @mcp.tool
    async def get_ca1_subject_mark(subject: str) -> Dict[str, Any]:
        """Get CA1 mark for a specific subject.
        
        Args:
            subject: Subject code or name to get CA1 mark for
            
        Returns:
            Dictionary containing CA1 mark details for the subject
        """
        log_tool_call("get_ca1_subject_mark", subject=subject)
        
        try:
            scraper = await session_manager.get_scraper()
            logger.info(f"get_ca1_subject_mark called for subject: {subject}")
            marks = scraper.get_ca_marks()
            
            lab_courses = marks.get('lab_courses', [])
            theory_courses = marks.get('theory_courses', [])
            
            # Search in lab courses first
            for course in lab_courses:
                if course.subject_code.lower() == subject.lower() or course.subject_name.lower() == subject.lower():
                    result = {
                        "success": True,
                        "course_type": "lab",
                        "subject_code": course.subject_code,
                        "subject_name": course.subject_name,
                        "ca1_marks": course.ca1_marks,
                        "max_marks": 25,
                        "marks_details": {
                            "ca1": course.ca1_marks,
                            "ca2": course.ca2_marks,
                            "total": course.total_marks,
                            "converted_total": course.conv_total
                        }
                    }
                    log_tool_response("get_ca1_subject_mark", result)
                    return result
            
            # Search in theory courses
            for course in theory_courses:
                if course.subject_code.lower() == subject.lower() or course.subject_name.lower() == subject.lower():
                    result = {
                        "success": True,
                        "course_type": "theory", 
                        "subject_code": course.subject_code,
                        "subject_name": course.subject_name,
                        "ca1_marks": course.t1_marks,  # T1 is equivalent to CA1
                        "max_marks": 30,
                        "marks_details": {
                            "t1": course.t1_marks,
                            "t2": course.t2_marks,
                            "assignment": course.ap_marks,
                            "tutorial": course.mpt_marks,
                            "total": course.total_marks,
                            "converted_total": course.conv_total
                        }
                    }
                    log_tool_response("get_ca1_subject_mark", result)
                    return result
                    
            # Subject not found
            result = {
                "success": False,
                "error": f"Subject '{subject}' not found",
                "available_subjects": [c.subject_code for c in lab_courses + theory_courses]
            }
            log_tool_response("get_ca1_subject_mark", result)
            return result
            
        except Exception as e:
            log_tool_response("get_ca1_subject_mark", None, error=e)
            return await handle_scraper_error(e, "get CA1 subject mark")

    @mcp.tool
    async def get_ca2_subject_mark(subject: str) -> Dict[str, Any]:
        """Get CA2 mark for a specific subject.
        
        Args:
            subject: Subject code or name to search for (e.g., 'CS101', 'Data Structures')
            
        Returns:
            Dict containing subject details and CA2 mark or error information
        """
        logger.info(f"get_ca2_subject_mark called with subject: '{subject}'")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            all_subjects = marks['lab_courses'] + marks['theory_courses']
            subject_marks = find_subject(all_subjects, subject)
            
            if not subject_marks:
                logger.warning(f"Subject '{subject}' not found")
                return {
                    "error": True,
                    "message": f"Subject '{subject}' not found",
                    "available_subjects": [s.subject_code for s in all_subjects]
                }
                
            if isinstance(subject_marks, LabCourseMarks):
                logger.info(f"Found lab course: {subject_marks.subject_code} with CA2 marks: {subject_marks.ca2_marks}")
                return {
                    "error": False,
                    "subject_code": subject_marks.subject_code,
                    "subject_name": subject_marks.subject_name,
                    "ca2_marks": subject_marks.ca2_marks,
                    "course_type": "lab"
                }
            else:
                logger.info(f"Found theory course: {subject_marks.subject_code} with CA2 marks: {subject_marks.t2_marks}")
                return {
                    "error": False,
                    "subject_code": subject_marks.subject_code,
                    "subject_name": subject_marks.subject_name,
                    "ca2_marks": subject_marks.t2_marks,
                    "course_type": "theory"
                }
        except Exception as e:
            logger.error(f"Exception in get_ca2_subject_mark: {e}", exc_info=True)
            return await handle_scraper_error(e, "get CA2 subject mark")

    @mcp.tool
    async def get_ca1_all_marks() -> Dict[str, Any]:
        """Get CA1 marks for all subjects.
        
        Returns:
            Dict containing list of all subjects with their CA1 marks or error information
        """
        logger.info("get_ca1_all_marks called")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            result = []
            
            for lab in marks['lab_courses']:
                if lab.ca1_marks is not None:
                    result.append({
                        "subject_code": lab.subject_code,
                        "subject_name": lab.subject_name,
                        "ca1_marks": lab.ca1_marks,
                        "course_type": "lab"
                    })
                    
            for theory in marks['theory_courses']:
                if theory.t1_marks is not None:
                    result.append({
                        "subject_code": theory.subject_code,
                        "subject_name": theory.subject_name,
                        "ca1_marks": theory.t1_marks,
                        "course_type": "theory"
                    })
            
            logger.info(f"Retrieved CA1 marks for {len(result)} subjects")
            return {
                "error": False,
                "subjects": result,
                "total_subjects": len(result),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Exception in get_ca1_all_marks: {e}", exc_info=True)
            return await handle_scraper_error(e, "get all CA1 marks")

    @mcp.tool
    async def get_ca2_all_marks() -> Dict[str, Any]:
        """Get CA2 marks for all subjects.
        
        Returns:
            Dict containing list of all subjects with their CA2 marks or error information
        """
        logger.info("get_ca2_all_marks called")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            result = []
            
            for lab in marks['lab_courses']:
                if lab.ca2_marks is not None:
                    result.append({
                        "subject_code": lab.subject_code,
                        "subject_name": lab.subject_name,
                        "ca2_marks": lab.ca2_marks,
                        "course_type": "lab"
                    })
                    
            for theory in marks['theory_courses']:
                if theory.t2_marks is not None:
                    result.append({
                        "subject_code": theory.subject_code,
                        "subject_name": theory.subject_name,
                        "ca2_marks": theory.t2_marks,
                        "course_type": "theory"
                    })
            
            logger.info(f"Retrieved CA2 marks for {len(result)} subjects")
            return {
                "error": False,
                "subjects": result,
                "total_subjects": len(result),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Exception in get_ca2_all_marks: {e}", exc_info=True)
            return await handle_scraper_error(e, "get all CA2 marks")

    @mcp.tool
    async def get_assignment_mark_by_subject(subject: str) -> Dict[str, Any]:
        """Get assignment mark for a specific subject.
        
        Args:
            subject: Subject code or name to search for (theory courses only)
            
        Returns:
            Dict containing subject details and assignment mark or error information
        """
        logger.info(f"get_assignment_mark_by_subject called with subject: '{subject}'")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            all_subjects = marks['theory_courses']  # Only theory courses have assignments
            subject_marks = find_subject(all_subjects, subject)
            
            if not subject_marks:
                logger.warning(f"Theory subject '{subject}' not found")
                return {
                    "error": True,
                    "message": f"Theory subject '{subject}' not found",
                    "available_subjects": [s.subject_code for s in all_subjects]
                }
                
            logger.info(f"Found theory course: {subject_marks.subject_code} with assignment marks: {subject_marks.ap_marks}")
            return {
                "error": False,
                "subject_code": subject_marks.subject_code,
                "subject_name": subject_marks.subject_name,
                "assignment_marks": subject_marks.ap_marks,
                "course_type": "theory"
            }
        except Exception as e:
            logger.error(f"Exception in get_assignment_mark_by_subject: {e}", exc_info=True)
            return await handle_scraper_error(e, "get assignment mark by subject")

    @mcp.tool
    async def get_all_assignment_marks() -> Dict[str, Any]:
        """Get assignment marks for all subjects.
        
        Returns:
            Dict containing list of all subjects with their assignment marks or error information
        """
        logger.info("get_all_assignment_marks called")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            result = []
            
            for theory in marks['theory_courses']:
                if theory.ap_marks is not None:
                    result.append({
                        "subject_code": theory.subject_code,
                        "subject_name": theory.subject_name,
                        "assignment_marks": theory.ap_marks,
                        "course_type": "theory"
                    })
            
            logger.info(f"Retrieved assignment marks for {len(result)} theory subjects")
            return {
                "error": False,
                "subjects": result,
                "total_subjects": len(result),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Exception in get_all_assignment_marks: {e}", exc_info=True)
            return await handle_scraper_error(e, "get all assignment marks")

    @mcp.tool
    async def get_tutorial_marks_by_subject(subject: str) -> Dict[str, Any]:
        """Get tutorial marks for a specific subject.
        
        Args:
            subject: Subject code or name to search for (theory courses only)
            
        Returns:
            Dict containing subject details and tutorial marks or error information
        """
        logger.info(f"get_tutorial_marks_by_subject called with subject: '{subject}'")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            all_subjects = marks['theory_courses']  # Only theory courses have tutorials
            subject_marks = find_subject(all_subjects, subject)
            
            if not subject_marks:
                logger.warning(f"Theory subject '{subject}' not found")
                return {
                    "error": True,
                    "message": f"Theory subject '{subject}' not found",
                    "available_subjects": [s.subject_code for s in all_subjects]
                }
                
            logger.info(f"Found theory course: {subject_marks.subject_code} with tutorial marks: {subject_marks.mpt_marks}")
            return {
                "error": False,
                "subject_code": subject_marks.subject_code,
                "subject_name": subject_marks.subject_name,
                "tutorial_marks": subject_marks.mpt_marks,
                "course_type": "theory"
            }
        except Exception as e:
            logger.error(f"Exception in get_tutorial_marks_by_subject: {e}", exc_info=True)
            return await handle_scraper_error(e, "get tutorial marks by subject")

    @mcp.tool
    async def get_all_tutorial_marks() -> Dict[str, Any]:
        """Get tutorial marks for all subjects.
        
        Returns:
            Dict containing list of all subjects with their tutorial marks or error information
        """
        logger.info("get_all_tutorial_marks called")
        try:
            scraper = await session_manager.get_scraper()
            marks = scraper.get_ca_marks()
            result = []
            
            for theory in marks['theory_courses']:
                if theory.mpt_marks is not None:
                    result.append({
                        "subject_code": theory.subject_code,
                        "subject_name": theory.subject_name,
                        "tutorial_marks": theory.mpt_marks,
                        "course_type": "theory"
                    })
            
            logger.info(f"Retrieved tutorial marks for {len(result)} theory subjects")
            return {
                "error": False,
                "subjects": result,
                "total_subjects": len(result),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Exception in get_all_tutorial_marks: {e}", exc_info=True)
            return await handle_scraper_error(e, "get all tutorial marks")

    @mcp.tool
    async def list_available_subjects() -> Dict[str, Any]:
        """List all available subjects with their codes and names.
        
        Returns:
            Dictionary containing lists of lab and theory subjects with their details
        """
        log_tool_call("list_available_subjects")
        
        try:
            logger.info("Creating new scraper session...")
            scraper = await session_manager.get_scraper()
            logger.info("New scraper session created successfully")
            
            marks = scraper.get_ca_marks()
            
            lab_subjects = [
                {
                    "subject_code": course.subject_code,
                    "subject_name": course.subject_name,
                    "course_type": "lab"
                }
                for course in marks.get('lab_courses', [])
            ]
            
            theory_subjects = [
                {
                    "subject_code": course.subject_code,
                    "subject_name": course.subject_name,
                    "course_type": "theory"
                }
                for course in marks.get('theory_courses', [])
            ]
            
            result = {
                "success": True,
                "total_subjects": len(lab_subjects) + len(theory_subjects),
                "lab_subjects": lab_subjects,
                "theory_subjects": theory_subjects,
                "summary": {
                    "lab_count": len(lab_subjects),
                    "theory_count": len(theory_subjects)
                }
            }
            
            logger.info(f"Listed {len(lab_subjects)} lab subjects and {len(theory_subjects)} theory subjects")
            log_tool_response("list_available_subjects", result)
            return result
            
        except Exception as e:
            log_tool_response("list_available_subjects", None, error=e)
            return await handle_scraper_error(e, "list available subjects")

    @mcp.tool
    async def health_check() -> Dict[str, Any]:
        """Perform a health check of the server and scraper.
        
        Returns:
            Dict containing health status information
        """
        logger.info("health_check called")
        try:
            # Basic connectivity test
            scraper = await session_manager.get_scraper()
            
            logger.info("Health check passed - server is healthy")
            return {
                "error": False,
                "status": "healthy",
                "server_name": "TechMCP",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "session_active": scraper is not None
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "error": True,
                "status": "unhealthy",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    logger.info("All marks tools registered successfully") 