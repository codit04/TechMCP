# 🎓 TechMCP - PSG College of Technology MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0+-orange)](https://github.com/jlowin/fastmcp)
[![PSG Tech](https://img.shields.io/badge/PSG-College%20of%20Technology-red)](https://psgtech.edu)

**TechMCP** is a comprehensive Model Context Protocol (MCP) server that seamlessly integrates with PSG College of Technology's e-campus portal. It provides AI assistants like Claude, Cursor, and Raycast with direct access to student academic data including CA marks, attendance records, and timetable information.

> 🚀 **Server hosting coming soon!** No more local setup required.

## ✨ Features

### 📊 **CA Marks & Assessment Tools**
- **CA1 & CA2 Marks**: Fetch continuous assessment marks for individual subjects or all subjects
- **Assignment Marks**: Get assignment scores for theory courses
- **Tutorial Marks**: Access tutorial marks and MPT scores
- **Subject Search**: Search by subject code or subject name
- **Health Monitoring**: Built-in health checks for scraper status

### 📅 **Attendance Management**
- **Attendance Percentage**: Real-time attendance tracking for all subjects
- **Present/Absent Hours**: Detailed hour-wise attendance breakdown
- **Bunk Calculator**: Smart calculation of available bunks while maintaining minimum attendance
- **Subject-wise Analysis**: Individual subject attendance details
- **Attendance Alerts**: Monitor attendance status across all courses

### 🕒 **Smart Timetable System**
- **Live Schedule**: Get current day's complete timetable
- **Next Class**: Find your immediate next class with location details
- **Remaining Classes**: See what's left for today
- **Weekly Schedule**: Complete week view with all subjects
- **Break Schedule**: Track break times and current break status
- **Tomorrow's Schedule**: Plan ahead with next day's timetable
- **Day-specific Schedule**: Get timetable for any day of the week

### 🎯 **Course Management**
- **Course Directory**: Complete list of all available courses
- **Course Search**: Find courses by code or name
- **Detailed Course Info**: Get comprehensive course details including timetable
- **Subject Mapping**: Automatic mapping between course codes and names

### 🔮 **Coming Soon**
- **CGPA Calculator**: Calculate current CGPA and predict future performance
- **CA Schedule**: Upcoming continuous assessment dates
- **Semester Schedule**: Important academic dates and deadlines

## 📋 Prerequisites

- **Python 3.10+**
- **Valid PSG Tech e-campus credentials**
- **Internet connection** for portal access

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/codit04/TechMCP.git
cd TechMCP
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials
**⚠️ IMPORTANT**: You **must** update the `config.json` file with your PSG Tech e-campus credentials:

```json
{
    "credentials": {
        "roll_number": "YOUR_ACTUAL_ROLL_NUMBER",
        "password": "YOUR_ACTUAL_PASSWORD"
    },
    "server": {
        "host": "localhost",
        "port": 8080,
        "sse_mode": true
    }
}
```

### 4. Start the Server
```bash
python server.py
```

The server will start on `http://127.0.0.1:8080/sse` and be ready for MCP connections.

## 🔗 Connecting to AI Assistants

### 🖱️ **Cursor IDE**

1. Create the MCP configuration directory:
```bash
mkdir -p ~/.cursor
```

2. Create `~/.cursor/mcp.json` with the following content:
```json
{
  "mcpServers": {
    "techmcp": {
      "url": "http://127.0.0.1:8080/sse",
      "name": "TechMCP - PSG Tech Integration",
      "transport":"sse"
    }
  }
}
```

3. Restart Cursor IDE
4. The server will appear in your MCP settings
5. Start asking questions like: *"What are my CA1 marks?"* or *"What's my next class?"*

### 🤖 **Claude Desktop**

1. Install the server locally:
```bash
# From the TechMCP directory
mcp install server.py
```

2. Restart Claude Desktop
3. The TechMCP server will be available in Claude's tools panel
4. Ask Claude about your academic data directly!

### ⚡ **Raycast**

1. Ensure the server is running on `http://127.0.0.1:8080/sse`
2. Install a compatible MCP extension for Raycast
3. Configure the server URL in Raycast settings
4. Access your academic data through Raycast commands

## 🛠️ Available Tools

### **Marks & Assessment**
- `get_ca1_subject_mark` - Get CA1 mark for a specific subject
- `get_ca2_subject_mark` - Get CA2 mark for a specific subject
- `get_ca1_all_marks` - Get CA1 marks for all subjects
- `get_ca2_all_marks` - Get CA2 marks for all subjects
- `get_assignment_mark_by_subject` - Get assignment marks for a subject
- `get_all_assignment_marks` - Get all assignment marks
- `get_tutorial_marks_by_subject` - Get tutorial marks for a subject
- `get_all_tutorial_marks` - Get all tutorial marks
- `list_available_subjects` - List all available subjects
- `health_check` - Check scraper health status

### **Attendance Management**
- `get_subject_attendance_percentage` - Get attendance % for a subject
- `get_all_attendance_percentages` - Get attendance % for all subjects
- `get_subject_absent_hours` - Get absent hours for a subject
- `get_all_absent_hours` - Get absent hours for all subjects
- `get_subject_present_hours` - Get present hours for a subject
- `get_all_present_hours` - Get present hours for all subjects
- `get_subject_available_bunks` - Calculate available bunks for a subject
- `get_all_available_bunks` - Calculate available bunks for all subjects

### **Timetable & Schedule**
- `get_next_class` - Get your next scheduled class
- `get_todays_schedule` - Get today's complete schedule
- `get_schedule_from_now` - Get remaining classes for today
- `get_tomorrows_schedule` - Get tomorrow's schedule
- `get_schedule_for_day` - Get schedule for a specific day
- `get_weekly_schedule` - Get complete weekly timetable
- `get_break_schedule` - Get break times and current status

### **Course Information**
- `get_all_courses` - Get list of all courses
- `search_courses` - Search courses by name or code
- `get_course_details` - Get detailed course information

## 💡 Usage Examples

### With Cursor/Claude
```
"What are my CA1 marks for Data Structures?"
"Show me my attendance percentage for all subjects"
"What's my next class?"
"How many hours can I bunk in Computer Networks while maintaining 75% attendance?"
"What's my complete schedule for tomorrow?"
```

### Direct API Usage
```bash
# Get CA1 marks for a subject
curl -X POST http://127.0.0.1:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "get_ca1_subject_mark", "params": {"subject": "20XTO1"}}'
```

## 🤝 Contributing

We welcome contributions to improve TechMCP! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### 🐛 Issues & Suggestions

- **GitHub Issues**: [Create an issue](https://github.com/your-username/TechMCP/issues) for bugs or feature requests
- **Discord Community**: Join our discussion at [@discord.gg/fRFGPQKERJ](https://discord.gg/fRFGPQKERJ)

## 🙏 Acknowledgments

- **[@mathanamathav](https://github.com/mathanamathav)** - Inspiration from the [bunker-api](https://github.com/mathanamathav/bunker-api) project
- **[PSG College of Technology](https://psgtech.edu)** - For the excellent e-campus portal
- **[E-Campus Portal](https://ecampus.psgtech.ac.in/studzone)** - The source of all academic data

## ⚖️ Legal & Privacy

- This project is for **educational purposes only**
- Uses **your own credentials** to access **your own data**
- **No data is stored** or transmitted to external servers
- Respects PSG Tech's e-campus **terms of service**
- **Open source** and transparent

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔧 Technical Details

- **Framework**: FastMCP 2.0+
- **Web Scraping**: Beautiful Soup 4, httpx
- **Data Models**: Pydantic
- **Transport**: Server-Sent Events (SSE)
- **Authentication**: Session-based with CSRF protection

---

<div align="center">

**Made with ❤️ for PSG Tech Students**

*Simplifying academic data access through AI*

[⭐ Star this repo](https://github.com/codit04/TechMCP) | [🐛 Report Bug](https://github.com/codit04/TechMCP/issues) | [💬 Join Discord](https://discord.gg/fRFGPQKERJ)

</div>
