"""
TechMCP Timetable Tools

This module contains all MCP tools related to timetable data, class schedules, and time management.
"""

import logging
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, time, timedelta

# These will be imported when the tools are registered
mcp = None
session_manager = None

# Import from our scrapers package
from scrapers.timetable_scraper import TimeTableScraper, TimeTableEntry

logger = logging.getLogger(__name__)

def find_timetable_entries(timetable_list: List[TimeTableEntry], 
                         day: Optional[str] = None, 
                         course_code: Optional[str] = None) -> List[TimeTableEntry]:
    """Helper function to find timetable entries by day and/or course code"""
    filtered_entries = timetable_list
    
    if day:
        day_lower = day.lower()
        logger.debug(f"Filtering by day: '{day}'")
        filtered_entries = [entry for entry in filtered_entries 
                          if entry.day.lower() == day_lower]
    
    if course_code:
        course_code_upper = course_code.upper()
        logger.debug(f"Filtering by course code: '{course_code}'")
        filtered_entries = [entry for entry in filtered_entries 
                          if entry.course_code.upper() == course_code_upper]
    
    logger.debug(f"Found {len(filtered_entries)} matching entries")
    return filtered_entries

def format_time_entry(entry: TimeTableEntry) -> Dict[str, Any]:
    """Format a timetable entry for display"""
    return {
        "day": entry.day,
        "period": entry.period,
        "time": f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}",
        "start_time": entry.start_time.strftime('%H:%M'),
        "end_time": entry.end_time.strftime('%H:%M'),
        "course_code": entry.course_code,
        "course_name": entry.course_name,
        "faculty": entry.faculty,
        "room": entry.room
    }

def get_day_from_date(date_obj: datetime) -> str:
    """Get day name from datetime object"""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[date_obj.weekday()]

def is_break_time(current_time: time, break_times: list) -> tuple:
    """Check if current time is within break and return break info"""
    for break_start, break_end in break_times:
        if break_start <= current_time <= break_end:
            break_type = "Morning Break" if break_start.hour == 10 else "Lunch Break" if break_start.hour == 12 else "Afternoon Break"
            return True, break_type, break_start, break_end
    return False, None, None, None

def get_next_period_after_break(current_time: time, period_times: dict, break_times: list) -> Optional[int]:
    """Find the next period after current break time"""
    # Find which break we're in
    current_break_end = None
    for break_start, break_end in break_times:
        if break_start <= current_time <= break_end:
            current_break_end = break_end
            break
    
    if not current_break_end:
        return None
    
    # Find the first period that starts after the break ends
    for period, (start_time, end_time) in period_times.items():
        if start_time >= current_break_end:
            return period
    
    return None

async def handle_timetable_error(error: Exception, operation: str) -> Dict[str, Any]:
    """Handle timetable scraper errors consistently"""
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

def register_timetable_tools(mcp_instance, session_manager_instance):
    """Register all timetable-related MCP tools"""
    global mcp, session_manager
    mcp = mcp_instance
    session_manager = session_manager_instance
    
    logger.info("Registering timetable tools...")

    @mcp.tool(
        annotations={
            "title": "Get Next Class",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_next_class() -> Dict[str, Any]:
        """Get the next scheduled class from current time.
        
        Returns:
            Dictionary containing details of the next class
        """
        log_tool_call("get_next_class")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_next_class called")
            timetable_data = scraper.get_timetable_data()
            
            now = datetime.now()
            current_day = get_day_from_date(now)
            current_time = now.time()
            
            # Check if currently in break time
            is_in_break, break_type, break_start, break_end = is_break_time(current_time, scraper.BREAK_TIMES)
            
            # Find today's classes first
            today_classes = find_timetable_entries(timetable_data, day=current_day)
            
            # Look for next class today
            next_class = None
            
            if is_in_break:
                # If in break, find the first class after break ends
                for entry in sorted(today_classes, key=lambda x: x.start_time):
                    if entry.start_time >= break_end:
                        next_class = entry
                        break
            else:
                # Normal logic: find next class after current time
                for entry in sorted(today_classes, key=lambda x: x.start_time):
                    if entry.start_time > current_time:
                        next_class = entry
                        break
            
            # If no more classes today, look for tomorrow's first class
            if not next_class:
                tomorrow = now + timedelta(days=1)
                tomorrow_day = get_day_from_date(tomorrow)
                tomorrow_classes = find_timetable_entries(timetable_data, day=tomorrow_day)
                
                if tomorrow_classes:
                    next_class = min(tomorrow_classes, key=lambda x: x.start_time)
            
            # If still no class found, look for next week's Monday
            if not next_class:
                days_ahead = 7 - now.weekday()  # Days until next Monday
                next_monday = now + timedelta(days=days_ahead)
                monday_classes = find_timetable_entries(timetable_data, day="Monday")
                
                if monday_classes:
                    next_class = min(monday_classes, key=lambda x: x.start_time)
            
            if not next_class:
                result = {
                    "success": False,
                    "message": "No upcoming classes found in timetable",
                    "current_time": now.strftime('%Y-%m-%d %H:%M'),
                    "current_day": current_day
                }
                log_tool_response("get_next_class", result)
                return result
            
            # Calculate time until next class
            if next_class.day == current_day:
                next_datetime = datetime.combine(now.date(), next_class.start_time)
                time_until = next_datetime - now
            else:
                # Calculate days until the next class day
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                current_day_idx = days_order.index(current_day)
                next_day_idx = days_order.index(next_class.day)
                
                if next_day_idx <= current_day_idx:
                    days_diff = 7 - current_day_idx + next_day_idx
                else:
                    days_diff = next_day_idx - current_day_idx
                
                next_date = now.date() + timedelta(days=days_diff)
                next_datetime = datetime.combine(next_date, next_class.start_time)
                time_until = next_datetime - now
            
            result = {
                "success": True,
                "next_class": format_time_entry(next_class),
                "time_until": {
                    "total_minutes": int(time_until.total_seconds() / 60),
                    "hours": int(time_until.total_seconds() // 3600),
                    "minutes": int((time_until.total_seconds() % 3600) // 60),
                    "formatted": f"{int(time_until.total_seconds() // 3600)}h {int((time_until.total_seconds() % 3600) // 60)}m"
                },
                "next_class_datetime": next_datetime.strftime('%Y-%m-%d %H:%M'),
                "current_time": now.strftime('%Y-%m-%d %H:%M'),
                "current_status": "In Break" if is_in_break else "In Class" if scraper.get_current_period(now) > 0 else "Free Time"
            }
            
            # Add break information if currently in break
            if is_in_break:
                result["current_break"] = {
                    "type": break_type,
                    "start_time": break_start.strftime('%H:%M'),
                    "end_time": break_end.strftime('%H:%M'),
                    "remaining_minutes": int((datetime.combine(now.date(), break_end) - now).total_seconds() / 60)
                }
            
            logger.info(f"Found next class: {next_class.course_code} on {next_class.day} at {next_class.start_time}")
            log_tool_response("get_next_class", result)
            return result
            
        except Exception as e:
            log_tool_response("get_next_class", None, error=e)
            return await handle_timetable_error(e, "get next class")

    @mcp.tool(
        annotations={
            "title": "Get Today's Schedule",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_todays_schedule() -> Dict[str, Any]:
        """Get complete schedule for today.
        
        Returns:
            Dictionary containing all classes scheduled for today
        """
        log_tool_call("get_todays_schedule")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_todays_schedule called")
            timetable_data = scraper.get_timetable_data()
            
            now = datetime.now()
            today = get_day_from_date(now)
            
            today_classes = find_timetable_entries(timetable_data, day=today)
            
            if not today_classes:
                result = {
                    "success": True,
                    "message": f"No classes scheduled for {today}",
                    "day": today,
                    "date": now.strftime('%Y-%m-%d'),
                    "classes": []
                }
                log_tool_response("get_todays_schedule", result)
                return result
            
            # Sort classes by time
            sorted_classes = sorted(today_classes, key=lambda x: x.start_time)
            formatted_classes = [format_time_entry(entry) for entry in sorted_classes]
            
            result = {
                "success": True,
                "day": today,
                "date": now.strftime('%Y-%m-%d'),
                "total_classes": len(formatted_classes),
                "classes": formatted_classes,
                "schedule_summary": {
                    "first_class": formatted_classes[0]["time"] if formatted_classes else None,
                    "last_class": formatted_classes[-1]["time"] if formatted_classes else None,
                    "total_periods": len(formatted_classes)
                }
            }
            
            logger.info(f"Retrieved {len(formatted_classes)} classes for {today}")
            log_tool_response("get_todays_schedule", result)
            return result
            
        except Exception as e:
            log_tool_response("get_todays_schedule", None, error=e)
            return await handle_timetable_error(e, "get today's schedule")

    @mcp.tool(
        annotations={
            "title": "Get Schedule From Now",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_schedule_from_now() -> Dict[str, Any]:
        """Get remaining classes for today from current time.
        
        Returns:
            Dictionary containing classes remaining for today
        """
        log_tool_call("get_schedule_from_now")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_schedule_from_now called")
            timetable_data = scraper.get_timetable_data()
            
            now = datetime.now()
            today = get_day_from_date(now)
            current_time = now.time()
            
            today_classes = find_timetable_entries(timetable_data, day=today)
            
            # Filter classes that start after current time
            remaining_classes = [entry for entry in today_classes if entry.start_time > current_time]
            
            if not remaining_classes:
                result = {
                    "success": True,
                    "message": f"No more classes remaining for today ({today})",
                    "day": today,
                    "current_time": now.strftime('%H:%M'),
                    "classes": []
                }
                log_tool_response("get_schedule_from_now", result)
                return result
            
            # Sort classes by time
            sorted_classes = sorted(remaining_classes, key=lambda x: x.start_time)
            formatted_classes = [format_time_entry(entry) for entry in sorted_classes]
            
            result = {
                "success": True,
                "day": today,
                "current_time": now.strftime('%H:%M'),
                "remaining_classes": len(formatted_classes),
                "classes": formatted_classes,
                "next_class": formatted_classes[0] if formatted_classes else None
            }
            
            logger.info(f"Found {len(formatted_classes)} remaining classes for {today}")
            log_tool_response("get_schedule_from_now", result)
            return result
            
        except Exception as e:
            log_tool_response("get_schedule_from_now", None, error=e)
            return await handle_timetable_error(e, "get schedule from now")

    @mcp.tool(
        annotations={
            "title": "Get Tomorrow's Schedule",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_tomorrows_schedule() -> Dict[str, Any]:
        """Get complete schedule for tomorrow.
        
        Returns:
            Dictionary containing all classes scheduled for tomorrow
        """
        log_tool_call("get_tomorrows_schedule")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_tomorrows_schedule called")
            timetable_data = scraper.get_timetable_data()
            
            now = datetime.now()
            tomorrow = now + timedelta(days=1)
            tomorrow_day = get_day_from_date(tomorrow)
            
            tomorrow_classes = find_timetable_entries(timetable_data, day=tomorrow_day)
            
            if not tomorrow_classes:
                result = {
                    "success": True,
                    "message": f"No classes scheduled for tomorrow ({tomorrow_day})",
                    "day": tomorrow_day,
                    "date": tomorrow.strftime('%Y-%m-%d'),
                    "classes": []
                }
                log_tool_response("get_tomorrows_schedule", result)
                return result
            
            # Sort classes by time
            sorted_classes = sorted(tomorrow_classes, key=lambda x: x.start_time)
            formatted_classes = [format_time_entry(entry) for entry in sorted_classes]
            
            result = {
                "success": True,
                "day": tomorrow_day,
                "date": tomorrow.strftime('%Y-%m-%d'),
                "total_classes": len(formatted_classes),
                "classes": formatted_classes,
                "schedule_summary": {
                    "first_class": formatted_classes[0]["time"] if formatted_classes else None,
                    "last_class": formatted_classes[-1]["time"] if formatted_classes else None,
                    "total_periods": len(formatted_classes)
                }
            }
            
            logger.info(f"Retrieved {len(formatted_classes)} classes for tomorrow ({tomorrow_day})")
            log_tool_response("get_tomorrows_schedule", result)
            return result
            
        except Exception as e:
            log_tool_response("get_tomorrows_schedule", None, error=e)
            return await handle_timetable_error(e, "get tomorrow's schedule")

    @mcp.tool(
        annotations={
            "title": "Get Schedule For Day",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_schedule_for_day(day: str) -> Dict[str, Any]:
        """Get schedule for a specific day of the week.
        
        Args:
            day: Day of the week (e.g., 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')
            
        Returns:
            Dictionary containing all classes scheduled for the specified day
        """
        log_tool_call("get_schedule_for_day", day=day)
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info(f"get_schedule_for_day called for: {day}")
            timetable_data = scraper.get_timetable_data()
            
            # Validate day input
            valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_title = day.title()  # Capitalize first letter
            
            if day_title not in valid_days:
                result = {
                    "success": False,
                    "error": f"Invalid day '{day}'. Valid days are: {', '.join(valid_days)}",
                    "valid_days": valid_days
                }
                log_tool_response("get_schedule_for_day", result)
                return result
            
            day_classes = find_timetable_entries(timetable_data, day=day_title)
            
            if not day_classes:
                result = {
                    "success": True,
                    "message": f"No classes scheduled for {day_title}",
                    "day": day_title,
                    "classes": []
                }
                log_tool_response("get_schedule_for_day", result)
                return result
            
            # Sort classes by time
            sorted_classes = sorted(day_classes, key=lambda x: x.start_time)
            formatted_classes = [format_time_entry(entry) for entry in sorted_classes]
            
            result = {
                "success": True,
                "day": day_title,
                "total_classes": len(formatted_classes),
                "classes": formatted_classes,
                "schedule_summary": {
                    "first_class": formatted_classes[0]["time"] if formatted_classes else None,
                    "last_class": formatted_classes[-1]["time"] if formatted_classes else None,
                    "total_periods": len(formatted_classes),
                    "subjects": list(set(entry["course_code"] for entry in formatted_classes if entry["course_code"]))
                }
            }
            
            logger.info(f"Retrieved {len(formatted_classes)} classes for {day_title}")
            log_tool_response("get_schedule_for_day", result)
            return result
            
        except Exception as e:
            log_tool_response("get_schedule_for_day", None, error=e)
            return await handle_timetable_error(e, "get schedule for day")

    @mcp.tool(
        annotations={
            "title": "Get Weekly Schedule",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_weekly_schedule() -> Dict[str, Any]:
        """Get complete weekly timetable.
        
        Returns:
            Dictionary containing the full weekly schedule organized by days
        """
        log_tool_call("get_weekly_schedule")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_weekly_schedule called")
            timetable_data = scraper.get_timetable_data()
            
            days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            weekly_schedule = {}
            total_classes = 0
            
            for day in days_order:
                day_classes = find_timetable_entries(timetable_data, day=day)
                sorted_classes = sorted(day_classes, key=lambda x: x.start_time)
                formatted_classes = [format_time_entry(entry) for entry in sorted_classes]
                
                weekly_schedule[day] = {
                    "classes": formatted_classes,
                    "total_classes": len(formatted_classes),
                    "first_class": formatted_classes[0]["time"] if formatted_classes else None,
                    "last_class": formatted_classes[-1]["time"] if formatted_classes else None
                }
                total_classes += len(formatted_classes)
            
            # Calculate weekly summary
            all_subjects = set()
            for day_data in weekly_schedule.values():
                for class_info in day_data["classes"]:
                    if class_info["course_code"]:
                        all_subjects.add(class_info["course_code"])
            
            result = {
                "success": True,
                "weekly_schedule": weekly_schedule,
                "summary": {
                    "total_classes_per_week": total_classes,
                    "total_subjects": len(all_subjects),
                    "subjects_list": sorted(list(all_subjects)),
                    "busiest_day": max(weekly_schedule.items(), key=lambda x: x[1]["total_classes"])[0] if total_classes > 0 else None,
                    "lightest_day": min(weekly_schedule.items(), key=lambda x: x[1]["total_classes"])[0] if total_classes > 0 else None
                },
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(f"Generated weekly schedule with {total_classes} total classes")
            log_tool_response("get_weekly_schedule", result)
            return result
            
        except Exception as e:
            log_tool_response("get_weekly_schedule", None, error=e)
            return await handle_timetable_error(e, "get weekly schedule")

    @mcp.tool(
        annotations={
            "title": "Get Break Schedule",
            "readOnlyHint": True,
            "openWorldHint": False
        }
    )
    async def get_break_schedule() -> Dict[str, Any]:
        """Get information about break times and current break status.
        
        Returns:
            Dictionary containing break schedule and current status
        """
        log_tool_call("get_break_schedule")
        
        try:
            scraper = await session_manager.get_timetable_scraper()
            logger.info("get_break_schedule called")
            
            now = datetime.now()
            current_time = now.time()
            
            # Check if currently in break
            is_in_break, break_type, break_start, break_end = is_break_time(current_time, scraper.BREAK_TIMES)
            
            # Format break times
            break_schedule = []
            for break_start, break_end in scraper.BREAK_TIMES:
                break_name = "Morning Break" if break_start.hour == 10 else "Lunch Break" if break_start.hour == 12 else "Afternoon Break"
                break_schedule.append({
                    "name": break_name,
                    "start_time": break_start.strftime('%H:%M'),
                    "end_time": break_end.strftime('%H:%M'),
                    "duration_minutes": int((datetime.combine(datetime.today(), break_end) - 
                                           datetime.combine(datetime.today(), break_start)).total_seconds() / 60)
                })
            
            result = {
                "success": True,
                "break_schedule": break_schedule,
                "current_time": now.strftime('%H:%M'),
                "current_status": {
                    "is_break_time": is_in_break,
                    "status": "In Break" if is_in_break else "Regular Time"
                }
            }
            
            # Add current break details if in break
            if is_in_break:
                result["current_break"] = {
                    "type": break_type,
                    "start_time": break_start.strftime('%H:%M'),
                    "end_time": break_end.strftime('%H:%M'),
                    "remaining_minutes": int((datetime.combine(now.date(), break_end) - now).total_seconds() / 60)
                }
            else:
                # Find next break
                next_break = None
                for break_start, break_end in scraper.BREAK_TIMES:
                    if break_start > current_time:
                        break_name = "Morning Break" if break_start.hour == 10 else "Lunch Break" if break_start.hour == 12 else "Afternoon Break"
                        time_until_break = datetime.combine(now.date(), break_start) - now
                        next_break = {
                            "type": break_name,
                            "start_time": break_start.strftime('%H:%M'),
                            "end_time": break_end.strftime('%H:%M'),
                            "minutes_until": int(time_until_break.total_seconds() / 60)
                        }
                        break
                
                if next_break:
                    result["next_break"] = next_break
            
            logger.info(f"Retrieved break schedule with current status: {result['current_status']['status']}")
            log_tool_response("get_break_schedule", result)
            return result
            
        except Exception as e:
            log_tool_response("get_break_schedule", None, error=e)
            return await handle_timetable_error(e, "get break schedule")

    logger.info("Timetable tools registered successfully") 