"""
TechMCP Scrapers Package

This package contains all the scrapers for different e-campus functionalities.
"""

from .marks_scraper import CAMarksScraper, LabCourseMarks, TheoryCourseMarks

__all__ = ['CAMarksScraper', 'LabCourseMarks', 'TheoryCourseMarks'] 