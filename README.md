# CA Marks MCP Server

A Model Context Protocol (MCP) server for extracting Continuous Assessment (CA) marks from PSG Tech's web portal. This server provides LLM-friendly endpoints to fetch and analyze CA marks data.

## Features

- Automated authentication with PSG Tech portal
- Real-time CA marks extraction
- Support for both CA1 and CA2 marks
- Subject-wise marks retrieval
- Secure credential management
- MCP-compliant API endpoints

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Access to PSG Tech student portal

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd ca-marks-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure credentials:
```bash
cp config.json.example config.json
```
Edit `config.json` and add your portal credentials:
```json
{
    "credentials": {
        "roll_number": "YOUR_ROLL_NUMBER",
        "password": "YOUR_PASSWORD"
    }
}
```

## Usage

1. Start the MCP server:
```bash
python server.py
```

2. The server will start at `http://localhost:8000` by default

3. MCP endpoints will be available at:
- `/mcp/get_ca_marks` - Get all CA marks
- `/mcp/get_subject_marks` - Get marks for a specific subject
- `/mcp/get_ca1_marks` - Get only CA1 marks
- `/mcp/get_ca2_marks` - Get only CA2 marks

## API Response Format

```json
{
    "status": "success",
    "data": {
        "subjects": [
            {
                "subject_name": "Data Structures",
                "subject_code": "CS201",
                "ca1_marks": 18.5,
                "ca2_marks": 19.0,
                "max_marks": 20
            }
        ],
        "semester": "Current",
        "last_updated": "2025-06-18T10:30:00Z"
    }
}
```

## Security Considerations

1. Never commit your `config.json` with real credentials
2. Use environment variables in production
3. Implement rate limiting for production use
4. Keep your dependencies updated

## Error Handling

The server handles various error scenarios:
- Invalid credentials
- Network connectivity issues
- Session expiration
- Portal structure changes
- Missing or invalid data

## Development

To contribute to the project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

## License

[License Type] - See LICENSE file for details

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Roadmap

Future enhancements planned:
1. CA test schedule extraction
2. Attendance data integration
3. Class timetable support
4. Unified college portal API

## Acknowledgments

- PSG Tech for providing the student portal
- FastMCP team for the MCP framework
- Contributors and maintainers