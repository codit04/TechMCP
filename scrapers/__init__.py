"""
Scrapers package for TechMCP

This package contains all web scrapers for PSG Tech e-campus portal.
"""
from .coursecode_scraper import CourseCodeScraper, CourseInfo
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
    'TimeTableEntry',
    'CourseCodeScraper',
    'CourseInfo'
] 
