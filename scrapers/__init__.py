"""
Scrapers package for TechMCP

This package contains all web scrapers for PSG Tech e-campus portal.
"""

from .marks_scraper import CAMarksScraper, LabCourseMarks, TheoryCourseMarks
from .attendance_scraper import AttendanceScraper, SubjectAttendance
from .timetable_scraper import TimeTableScraper, TimeTableEntry

__all__ = [
    'CAMarksScraper',
    'LabCourseMarks', 
    'TheoryCourseMarks',
    'AttendanceScraper',
    'SubjectAttendance',
    'TimeTableScraper',
    'TimeTableEntry'
] 