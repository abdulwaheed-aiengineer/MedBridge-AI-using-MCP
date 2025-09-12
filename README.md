# MedBridge AI - Unity Care Clinic

A modern, bilingual AI-powered medical triage and appointment booking system. Built with FastAPI backend, MCP (Model Context Protocol) integration, and a clean HTML/CSS/JS frontend.

## Features

### Medical Triage & Booking
- **Intelligent Symptom Analysis**: AI-powered condition classification (fever, headache, flu, eye issues, skin problems)
- **Doctor Matching**: Automatic doctor recommendations based on symptoms and specialization
- **Real-time Availability**: Google Calendar integration for live appointment slots
- **Bilingual Support**: English and Roman Urdu with automatic translation
- **Appointment Booking**: Complete booking flow with email confirmations and calendar invites

### Chat Experience
- **Streaming Responses**: Real-time token streaming for natural conversation flow
- **Session Persistence**: Resume conversations with localStorage
- **Smart Formatting**: Clean display of doctor availability with bullet points
- **Error Handling**: Graceful retry with exponential backoff
- **Mobile Responsive**: Optimized for all device sizes

### Technical Features
- **MCP Integration**: Model Context Protocol for seamless AI tool calling
- **Google Calendar API**: Real-time availability checking and appointment creation
- **SMTP Integration**: Automated email notifications and confirmations
- **Environment Security**: Proper .gitignore and environment variable management
- **FastAPI Backend**: Modern async web framework with streaming support

## Quick Start

### Prerequisites
- Python 3.13+
- OpenAI API key
- Google Calendar API credentials
- SMTP credentials (Gmail, Outlook, etc.)

### Installation

1. **Clone and setup**:
```bash
git clone https://github.com/abdulwaheed-aiengineer/MedBridge-AI-using-MCP.git
cd MedBridge-AI-using-MCP
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
# Create .env file with your credentials
cp .env.example .env
# Edit .env with your API keys and settings
```

3. **Required Environment Variables**:
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Google Calendar Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service-account.json
CLINIC_TIMEZONE=Asia/Karachi

# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=your_email@gmail.com

# Optional Configuration
MIN_LEAD_MINUTES=30
PORT=8000
```

4. **Run the application**:
```bash
python api.py
```

5. **Access the interface**:
   - Open http://localhost:8000 in your browser
   - The chat interface will load automatically

## Usage Examples

### Basic Triage
```
User: "I have a headache"
Assistant: "I can help you find a doctor for your headache. Let me search for available specialists..."
```

### Doctor-Specific Booking
```
User: "Dr Diego is available in this week?"
Assistant: "Let me check Dr. Diego's availability for this week..."
```

### Language Support
```
User: "Mujhe bukhar hai" (Roman Urdu for "I have fever")
Assistant: "I understand you have a fever. Let me find appropriate doctors for you..."
```

### Availability Display
The system now displays availability in a clean, structured format:
```
Tuesday, September 09
• 11:00
• 11:30
• 12:00
• 12:30
• 16:00
• 16:30
• 17:00
• 17:30

Thursday, September 11
• 11:00
• 11:30
• 12:00
• 12:30
```

## Architecture

### Frontend (static/chat.html)
- **Pure HTML/CSS/JS**: No build process, no frameworks
- **Modern Design System**: CSS custom properties with consistent spacing and colors
- **Real-time Streaming**: Server-sent events for live chat experience
- **Responsive Design**: Mobile-first approach with clean UI

### Backend (api.py)
- **FastAPI**: Modern async web framework
- **MCP Integration**: Model Context Protocol for AI tool calling
- **Streaming Support**: Real-time response streaming
- **Language Detection**: Automatic English/Roman Urdu detection and translation
- **Post-processing**: Automatic formatting fixes for clean output

### MCP Server (server.py)
- **Google Calendar**: Appointment scheduling and availability checking
- **SMTP**: Email notifications and confirmations
- **Doctor Database**: JSON-based doctor directory with condition mapping
- **Availability Engine**: Smart slot calculation with calendar integration

### Data Structure (data/doctors.json)
```json
{
  "doctors": [
    {
      "doctor_id": "dr_eric",
      "name": "Dr. Eric",
      "specialization": "Ophthalmology",
      "experience_years": 7,
      "fees": { "online_pkr": 2500, "inperson_pkr": 3500 },
      "weekly_schedule": {
        "Mon": ["10:00-12:00", "15:00-17:00"],
        "Wed": ["10:00-12:00"],
        "Fri": ["15:00-17:00"]
      },
      "calendar_id": "ericpatsilevas83@gmail.com",
      "location": "Unity Care Clinic, Lahore",
      "email": "ericpatsilevas83@gmail.com"
    }
  ],
  "condition_map": {
    "fever": ["dr_ali"],
    "headache": ["dr_ali"],
    "flu": ["dr_ali"],
    "eye_issue": ["dr_eric"],
    "skin_rash": ["dr_diego"]
  }
}
```

## Design System

### Colors
```css
/* MedBridge AI Theme */
--primary-gradient: linear-gradient(135deg, #f3f9ff 0%, #eaf6ff 100%);
--secondary-gradient: linear-gradient(180deg, #f0f7ff 0%, #e7f3ff 100%);
--heart-green: #38bdf8;
--ai-green: #38bdf8;
--text-dark: #0f172a;
--bg-page: #f7fbff;
--bg-light: #ffffff;
--accent: #0ea5e9;
--text-muted: #6b7280;
```

### Spacing Scale
```css
--spacing-xs: 4px
--spacing-sm: 8px
--spacing-md: 16px
--spacing-lg: 24px
--spacing-xl: 32px
```

## Testing

### Manual Testing
```bash
# Start the server
python api.py

# Open browser to http://localhost:8000
```

## Security & Privacy

- **Environment Variables**: All sensitive data stored in .env (not tracked by git)
- **No Browser Secrets**: All API keys remain server-side
- **Session Isolation**: Each chat session is independent
- **Minimal Data Storage**: Only essential session data in localStorage
- **HTTPS Ready**: Production-ready with SSL support

## Deployment

### Environment Setup
1. Set all required environment variables in your hosting platform
2. Ensure Google Service Account JSON is accessible
3. Configure SMTP credentials for email notifications

### Platform Examples
- **Render**: Python runtime with environment variables
- **Railway**: Direct GitHub deployment
- **DigitalOcean**: App Platform with Python runtime
- **Heroku**: Add Procfile with web: python api.py

## Project Structure

```
triage-mcp/
├── api.py                 # FastAPI backend with streaming
├── server.py              # MCP server with Google Calendar integration
├── client.py              # Standalone MCP client for testing
├── static/
│   └── chat.html          # Frontend chat interface
├── data/
│   └── doctors.json       # Doctor database and condition mapping
├── .env                   # Environment variables (not tracked)
├── .gitignore             # Git ignore rules
├── pyproject.toml         # Python dependencies
└── README.md              # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch: git checkout -b feature-name
3. Make your changes
4. Test thoroughly
5. Commit your changes: git commit -m 'Add feature'
6. Push to the branch: git push origin feature-name
7. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Emergency**: Call 1122 (Pakistan emergency services)
- **Technical Issues**: Check logs and environment configuration
- **Appointment Changes**: Use chat interface or contact clinic directly
- **Privacy Concerns**: Review environment variable configuration

---

Built with love for Unity Care Clinic - Making healthcare accessible through AI